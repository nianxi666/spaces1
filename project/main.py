import re
import threading
import time
import uuid
import shlex
import os
import shutil
from datetime import datetime
from flask import (
    Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app, send_from_directory, Response
)
from urllib.parse import urlparse, urljoin
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from .database import load_db, save_db
import json
from .tasks import tasks, execute_inference_task
from .s3_utils import generate_presigned_url, get_s3_config, get_public_s3_url
from .utils import predict_output_filename

main_bp = Blueprint('main', __name__)

@main_bp.route('/robots.txt')
def robots_txt():
    return send_from_directory(current_app.static_folder, 'robots.txt')

@main_bp.route('/sw.js')
def sw_js():
    return send_from_directory(current_app.static_folder, 'sw.js')

@main_bp.route('/ads.txt')
def ads_txt():
    return send_from_directory(current_app.static_folder, 'ads.txt')

@main_bp.route('/set-language/<lang_code>')
def set_language(lang_code):
    if lang_code in ['zh', 'en']:
        session['locale'] = lang_code
    else:
        session['locale'] = 'en' # Default fallback

    # Safe redirect
    target = request.referrer
    if not target or urlparse(target).netloc != urlparse(request.host_url).netloc:
        target = url_for('main.index')

    return redirect(target)

@main_bp.route('/sitemap.xml')
def sitemap():
    db = load_db()
    server_domain = db.get('settings', {}).get('server_domain', request.url_root.rstrip('/'))
    today = datetime.now().strftime('%Y-%m-%d')

    def external_url_for(endpoint, **values):
        if '127.0.0.1' in server_domain or 'localhost' in server_domain:
            return url_for(endpoint, **values, _external=True)
        return f"{server_domain}{url_for(endpoint, **values)}"

    # Static pages with priority and change frequency
    static_urls = [
        {'loc': external_url_for('main.index'), 'lastmod': today, 'changefreq': 'daily', 'priority': '1.0'},
        {'loc': external_url_for('auth.login'), 'lastmod': today, 'changefreq': 'monthly', 'priority': '0.5'},
        {'loc': external_url_for('auth.register'), 'lastmod': today, 'changefreq': 'monthly', 'priority': '0.5'},
        {'loc': external_url_for('main.article_list'), 'lastmod': today, 'changefreq': 'weekly', 'priority': '0.8'},
    ]

    # Dynamic pages from "spaces"
    spaces = db.get('spaces', {}).values()
    space_urls = []
    for space in spaces:
        last_mod_date = today
        if 'last_modified' in space:
            try:
                dt = datetime.fromisoformat(space['last_modified'])
                last_mod_date = dt.strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                pass
        url_data = {
            'loc': external_url_for('main.ai_project_view', ai_project_id=space['id']),
            'lastmod': last_mod_date,
            'changefreq': 'weekly',
            'priority': '0.9'
        }
        space_urls.append(url_data)

    # Dynamic pages from "articles"
    articles = db.get('articles', {}).values()
    article_urls = []
    for article in articles:
        last_mod_date = today
        if 'updated_at' in article:
            try:
                dt = datetime.fromisoformat(article['updated_at'])
                last_mod_date = dt.strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                pass
        url_data = {
            'loc': external_url_for('main.article_view', slug=article['slug']),
            'lastmod': last_mod_date,
            'changefreq': 'monthly',
            'priority': '0.7'
        }
        article_urls.append(url_data)

    all_urls = static_urls + space_urls + article_urls
    sitemap_xml = render_template('sitemap_template.xml', urls=all_urls)
    return Response(sitemap_xml, mimetype='application/xml')

@main_bp.route('/')
def index():
    db = load_db()
    ai_projects_list = sorted(db["spaces"].values(), key=lambda x: x["name"])
    username = session.get('username')

    # Add 'is_liked' status to each project for the current user
    for project in ai_projects_list:
        if username and 'liked_by' in project and username in project['liked_by']:
            project['is_liked'] = True
        else:
            project['is_liked'] = False

    categories = db.get('categories', [])
    announcement = db.get('announcement', {})

    # --- Hreflang links generation ---
    server_domain = db.get('settings', {}).get('server_domain', request.url_root.rstrip('/'))
    def external_url_for(endpoint, **values):
        if '127.0.0.1' in server_domain or 'localhost' in server_domain:
             return url_for(endpoint, **values, _external=True)
        return f"{server_domain}{url_for(endpoint, **values)}"

    # Note: The 'en' URL is hypothetical. It assumes you will have a mechanism
    # to serve English content based on a 'lang' query parameter or similar.
    hreflang_links = [
        {'lang': 'zh', 'url': external_url_for('main.index')},
        {'lang': 'en', 'url': external_url_for('main.index', lang='en')},
        {'lang': 'x-default', 'url': external_url_for('main.index')}
    ]

    # Find the latest message from an admin
    latest_admin_message = None
    chat_messages = db.get('chat_messages', [])
    admin_usernames = [u for u, d in db.get('users', {}).items() if d.get('is_admin')]

    for message in reversed(chat_messages):
        if message.get('username') in admin_usernames:
            latest_admin_message = message
            break

    banner = db.get('banner', {})

    return render_template(
        "index.html",
        ai_projects=ai_projects_list,
        announcement=announcement,
        categories=categories,
        hreflang_links=hreflang_links,
        latest_admin_message=latest_admin_message,
        banner=banner
    )


@main_bp.route('/profile')
def profile():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    db = load_db()
    user_data = db['users'].get(session['username'], {})
    api_key = user_data.get('api_key', '未找到 API 密钥')
    if not session.get('is_admin') and api_key and len(api_key) > 8:
        api_key = f"{api_key[:4]}...{api_key[-4:]}"
    settings = db.get('settings', {})
    pro_settings = db.get('pro_settings', {})
    return render_template('profile.html', user=user_data, api_key=api_key, settings=settings, pro_settings=pro_settings)

@main_bp.route('/pro/apply', methods=['GET', 'POST'])
def pro_apply():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    db = load_db()
    pro_settings = db.get('pro_settings', {})

    if not pro_settings.get('enabled'):
        flash('Pro 会员功能当前不可用。', 'error')
        return redirect(url_for('main.profile'))

    username = session['username']
    user = db['users'].get(username, {})

    if request.method == 'POST':
        link = request.form.get('submission_link', '').strip()
        if not link:
            flash('请提交任务链接。', 'error')
        else:
            user['pro_submission_link'] = link
            user['pro_submission_status'] = 'pending'
            user['pro_submission_date'] = datetime.utcnow().isoformat()
            save_db(db)
            flash('申请已提交，请等待审核。', 'success')
            return redirect(url_for('main.profile'))

    return render_template('pro_apply.html', pro_settings=pro_settings, user=user)


@main_bp.route('/change_password', methods=['POST'])
def change_password():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    username = session['username']
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not all([current_password, new_password, confirm_password]):
        flash('所有字段都是必填的。', 'error')
        return redirect(url_for('main.profile'))

    if new_password != confirm_password:
        flash('新密码和确认密码不匹配。', 'error')
        return redirect(url_for('main.profile'))

    db = load_db()
    user = db['users'].get(username, {})

    if not user:
        flash('未找到用户。', 'error')
        return redirect(url_for('auth.logout'))

    if not check_password_hash(user.get('password_hash', ''), current_password):
        flash('当前密码不正确。', 'error')
        return redirect(url_for('main.profile'))

    user['password_hash'] = generate_password_hash(new_password)
    save_db(db)

    flash('密码已成功更新。', 'success')
    return redirect(url_for('main.profile'))

@main_bp.route('/delete_account', methods=['POST'])
def delete_account():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    username = session['username']
    if username == 'admin':
        flash('管理员账户不能被删除。', 'error')
        return redirect(url_for('main.profile'))

    db = load_db()

    # 1. Delete user's results directory
    user_dir = os.path.join(current_app.instance_path, current_app.config['RESULTS_FOLDER'], username)
    if os.path.exists(user_dir):
        shutil.rmtree(user_dir)

    # 2. Remove user's likes from all spaces
    for space in db.get('spaces', {}).values():
        if 'liked_by' in space and username in space['liked_by']:
            space['liked_by'].remove(username)

    # 4. Remove user's state
    if username in db.get('user_states', {}):
        del db['user_states'][username]

    # 5. Remove user's generated invitation codes
    generated_code_prefix = f"ldo-{username}-"
    codes_to_delete = [code for code in db.get('invitation_codes', {}) if code.startswith(generated_code_prefix)]
    for code in codes_to_delete:
        del db['invitation_codes'][code]

    # 6. Delete the user object itself
    if username in db['users']:
        del db['users'][username]

    save_db(db)

    # 7. Log the user out
    session.clear()
    flash('您的账户和所有相关数据已被成功删除。', 'success')
    return redirect(url_for('auth.login'))

@main_bp.route('/favorites')
def favorites():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    db = load_db()
    username = session['username']

    all_spaces = db.get('spaces', {}).values()
    liked_spaces = [space for space in all_spaces if username in space.get('liked_by', [])]

    # Add is_liked status for the template
    for space in liked_spaces:
        space['is_liked'] = True

    return render_template('favorites.html', ai_projects=liked_spaces)

@main_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    db = load_db()

    if request.method == 'POST':
        if session.get('is_admin'):
            db['settings']['server_domain'] = request.form['server_domain'].rstrip('/')
            save_db(db)
            flash('设置已保存!', 'success')
        else:
            flash('只有管理员可以修改设置。', 'error')
        return redirect(url_for('main.settings'))

    settings = db.get('settings', {})
    return render_template('settings.html', settings=settings)


@main_bp.route("/ai_project/<ai_project_id>")
def ai_project_view(ai_project_id):
    db = load_db()
    ai_project = db["spaces"].get(ai_project_id)
    if not ai_project:
        return "AI Project not found", 404

    # Allow public access but prepare user-specific data if logged in
    username = session.get("username")
    user_data = {}
    api_key = "YOUR_API_KEY_PLACEHOLDER"
    user_has_invitation_code = False
    is_waiting_for_file = False
    selected_file_key = None
    remote_inference_configs = []
    last_remote_inference_result = None

    DEFAULT_DOMAIN_PLACEHOLDER = 'https://pumpkinai.it.com'
    raw_server_domain = (db.get('settings', {}).get('server_domain') or '').rstrip('/')
    current_request_domain = (request.url_root or '').rstrip('/')
    effective_server_domain = raw_server_domain if raw_server_domain and raw_server_domain != DEFAULT_DOMAIN_PLACEHOLDER else (current_request_domain or raw_server_domain)

    space_card_type = ai_project.get('card_type', 'standard')
    remote_inference_timeout_seconds = ai_project.get('remote_inference_timeout_seconds', 300) or 300

    # Block deprecated card types
    if space_card_type in ['cerebrium', 'standard']:
        return render_template('error.html', 
                             error_title='Space Type Deprecated',
                             error_message=f'This space uses a deprecated card type "{space_card_type}". Please contact the administrator to update it to "remote_inference" or "netmind".'), 403

    announcement = db.get('announcement', {})

    if username:
        user_data = db["users"].get(username, {})
        api_key = user_data.get("api_key") or "YOUR_API_KEY_PLACEHOLDER"
        user_has_invitation_code = user_data.get("has_invitation_code", False)
        user_state = db.get("user_states", {}).get(username, {})
        is_waiting_for_file = user_state.get("is_waiting_for_file", False)
        selected_file_key = user_state.get("selected_files", {}).get(ai_project_id)
        remote_inference_configs = user_data.get('remote_inference_configs', [])
        raw_result = user_state.get('remote_inference_results', {}).get(ai_project_id)
        if isinstance(raw_result, dict):
            last_remote_inference_result = dict(raw_result)
            if 'status' not in last_remote_inference_result:
                last_remote_inference_result['status'] = 'completed'
            if not last_remote_inference_result.get('public_url') and last_remote_inference_result.get('output_key'):
                regenerated_url = get_public_s3_url(last_remote_inference_result['output_key'])
                if regenerated_url:
                    last_remote_inference_result['public_url'] = regenerated_url
            if 'saved_at' not in last_remote_inference_result:
                last_remote_inference_result['saved_at'] = datetime.utcnow().isoformat() + 'Z'
            if 'saved_at_ms' not in last_remote_inference_result:
                saved_value = last_remote_inference_result.get('saved_at')
                if saved_value:
                    try:
                        normalized = saved_value.replace('Z', '+00:00')
                        saved_dt = datetime.fromisoformat(normalized)
                        last_remote_inference_result['saved_at_ms'] = int(saved_dt.timestamp() * 1000)
                    except ValueError:
                        pass

    if space_card_type == 'netmind':
        return render_template(
            'space_netmind_chat.html',
            ai_project=ai_project,
            api_key=api_key,
            server_domain=effective_server_domain,
            announcement=announcement
        )

    s3_public_base_url = None
    s3_config = get_s3_config()
    if s3_config:
        endpoint = s3_config.get('S3_ENDPOINT_URL')
        bucket = s3_config.get('S3_BUCKET_NAME')
        if endpoint and bucket:
            s3_public_base_url = f"{endpoint.rstrip('/')}/{bucket}"

    param_form_html = ""
    if ai_project.get("params") and isinstance(ai_project["params"], list):
        for param in ai_project["params"]:
            name = param.get("name", "")
            label = param.get("label", name)
            param_type = param.get("type", "text")
            default = param.get("default", "")
            help_text = param.get("help_text", "")

            input_html = ''
            if param_type == 'boolean':
                checked = 'checked' if default else ''
                input_html = f'<input type="checkbox" name="{name}" id="param_{name}" {checked} style="width: auto;">'
            else:
                input_html = f'<input type="{param_type}" name="{name}" id="param_{name}" value="{default}" class="form-control" style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box;">'

            help_html = f'<small style="color: #666; display: block; margin-top: 4px;">{help_text}</small>' if help_text else ''

            param_form_html += f'''
                <div class="form-group">
                    <label for="param_{name}">{label}</label>
                    {input_html}
                    {help_html}
                </div>
            '''

    # --- Hreflang and API URL generation ---
    server_domain = effective_server_domain or raw_server_domain or current_request_domain
    def external_url_for(endpoint, **values):
        if '127.0.0.1' in server_domain or 'localhost' in server_domain:
             return url_for(endpoint, **values, _external=True)
        return f"{server_domain}{url_for(endpoint, **values)}"

    hreflang_links = [
        {'lang': 'zh', 'url': external_url_for('main.ai_project_view', ai_project_id=ai_project_id)},
        {'lang': 'en', 'url': external_url_for('main.ai_project_view', ai_project_id=ai_project_id, lang='en')},
        {'lang': 'x-default', 'url': external_url_for('main.ai_project_view', ai_project_id=ai_project_id)}
    ]

    # --- API Examples Generation ---
    api_examples = []
    api_base_url = f"{server_domain}/api/v1" if server_domain else "/api/v1"
    run_api_url = f"{api_base_url}/spaces/run"
    status_api_url_base = f"{api_base_url}/task"

    for template_id, template_data in ai_project.get('templates', {}).items():
        template_name = template_data.get('name', f'Template {template_id}')
        space_name = ai_project.get('name')

        # Base payload
        payload = {
            "space_name": space_name,
            "gpu_template": template_name,
        }
        # Add prompt or file_url based on template config
        if template_data.get('disable_prompt'):
            payload["file_url"] = "https://example.com/path/to/your/file.glb"
        else:
            payload["prompt"] = "Your creative prompt here"

        # --- cURL Example ---
        json_payload_curl = json.dumps(payload, indent=2)
        curl_command = (
            f'curl -X POST "{run_api_url}" \\\n'
            f'-H "Authorization: Bearer {api_key}" \\\n'
            f'-H "Content-Type: application/json" \\\n'
            f"-d '{json_payload_curl}'"
        )

        # --- Python Async Example ---
        payload_str_py = json.dumps(payload, indent=4)
        python_async_command = f'''
import requests
import time
import json

API_KEY = "{api_key}"
BASE_URL = "{api_base_url}"
PAYLOAD = {payload_str_py.replace('true', 'True').replace('false', 'False')}

headers = {{
    "Authorization": f"Bearer {{API_KEY}}",
    "Content-Type": "application/json"
}}

# 1. Start task
print(">>> Starting task...")
start_response = requests.post(f"{{BASE_URL}}/spaces/run", json=PAYLOAD, headers=headers)
start_response.raise_for_status()
task_id = start_response.json()["task_id"]
print(f"Task started successfully, Task ID: {{task_id}}")

# 2. Poll for status
print("\\n>>> Polling for status...")
while True:
    status_response = requests.get(f"{{BASE_URL}}/task/{{task_id}}/status", headers=headers)
    status_response.raise_for_status()
    data = status_response.json()
    status = data.get("status")
    print(f"Current task status: {{status}}")

    if status in ["completed", "failed"]:
        print("\\n--- Task Finished ---")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        break

    time.sleep(5)
'''

        # --- Python Stream Example ---
        stream_payload = payload.copy()
        stream_payload["stream"] = True
        stream_payload_str_py = json.dumps(stream_payload, indent=4)
        python_stream_command = f'''
import requests
import json

API_KEY = "{api_key}"
BASE_URL = "{api_base_url}"
PAYLOAD = {stream_payload_str_py.replace('true', 'True').replace('false', 'False')}

headers = {{
    "Authorization": f"Bearer {{API_KEY}}",
    "Content-Type": "application/json"
}}

print(">>> Starting stream...")
with requests.post(f"{{BASE_URL}}/spaces/run", json=PAYLOAD, headers=headers, stream=True) as response:
    response.raise_for_status()
    for line in response.iter_lines():
        if line:
            print(line.decode('utf-8'))
'''

        api_examples.append({
            'name': template_name,
            'id': template_id,
            'curl': curl_command.strip(),
            'python_async': python_async_command.strip(),
            'python_stream': python_stream_command.strip()
        })

    return render_template(
        "ai_project_view.html",
        ai_project=ai_project,
        param_form_html=param_form_html,
        api_key=api_key or "",
        is_waiting_for_file=is_waiting_for_file or False,
        announcement=announcement or {},
        user_has_invitation_code=user_has_invitation_code or False,
        selected_file_key=selected_file_key,
        hreflang_links=hreflang_links or [],
        api_examples=api_examples or [],
        space_card_type=space_card_type or 'standard',
        s3_public_base_url=s3_public_base_url,
        current_username=username or "",
        remote_inference_configs=remote_inference_configs or [],
        last_remote_inference_result=last_remote_inference_result,
        remote_inference_timeout_seconds=remote_inference_timeout_seconds or 300,
        # Input configuration for remote_inference
        custom_api_url=ai_project.get('custom_api_url', ''),
        enable_prompt=ai_project.get('enable_prompt', True),
        enable_image_input=ai_project.get('enable_image_input', False),
        enable_audio_input=ai_project.get('enable_audio_input', False),
        enable_file_input=ai_project.get('enable_file_input', False)
    )

@main_bp.route("/run_inference/<ai_project_id>", methods=["POST"])
def run_inference(ai_project_id):
    if not session.get('logged_in'):
        return jsonify({'error': '未登录'}), 401

    db = load_db()

    # Sensitive word check
    sensitive_words = db.get('sensitive_words', [])
    prompt = request.form.get('prompt', '')
    if sensitive_words:
        for word in sensitive_words:
            if word in prompt:
                return jsonify({'error': f'您的prompt中包含敏感词“{word}”，请修改后再提交。'}), 400

    username = session['username']

    if db.get('user_states', {}).get(username, {}).get('is_waiting_for_file'):
        return jsonify({'error': '您已经有一个任务正在运行，请等待其完成后再试。'}), 429

    ai_project = db["spaces"].get(ai_project_id)
    if not ai_project:
        return jsonify({'error': 'AI Project 未找到'}), 404

    template_id = request.form.get('template_id')
    if not template_id:
        return jsonify({'error': '请选择一个模板'}), 400

    template = ai_project.get('templates', {}).get(template_id)
    if not template:
        return jsonify({'error': '选择的模板无效'}), 404

    # Backend enforcement for restricted templates
    user_data = db['users'].get(username, {})
    if template.get('requires_invitation_code') and not user_data.get('has_invitation_code'):
        return jsonify({'error': '此模板需要邀请码，请在个人资料页面绑定。'}), 403

    s3_keys_str = request.form.get('s3_object_keys')
    if template.get('force_upload') and not s3_keys_str and not request.files.getlist('input_file'):
        return jsonify({'error': '此模板需要上传文件'}), 400

    user_data = db['users'].get(username)
    user_api_key = user_data.get('api_key')
    if not user_api_key:
        return jsonify({'error': '用户API密钥缺失'}), 500

    server_url = db.get('settings', {}).get('server_domain')
    if not server_url:
        return jsonify({'error': '服务器域名未配置'}), 500

    prompt = request.form.get('prompt', '')
    base_cmd = template.get("base_command", "")
    full_cmd = base_cmd
    if not template.get('disable_prompt'):
        full_cmd += f' --prompt {shlex.quote(prompt)}'

    preset_params = template.get("preset_params", "").strip()
    if preset_params:
        full_cmd += f' {preset_params}'

    # Handle file selected from S3 browser
    if s3_keys_str:
        s3_keys = json.loads(s3_keys_str)
        if s3_keys:
            s3_key = s3_keys[0]  # Use the first selected file
            file_url = get_public_s3_url(s3_key)

            if file_url:
                s3_key_lower = s3_key.lower()
                if s3_key_lower.endswith('.safetensors'):
                    arg_name = '--lora'
                elif s3_key_lower.endswith('.glb'):
                    arg_name = '--input_model'
                else:
                    arg_name = '--input_image'
                full_cmd += f' {arg_name} {shlex.quote(file_url)}'
            else:
                return jsonify({'error': '无法为所选文件生成下载链接，请检查S3配置。'}), 500

    temp_upload_paths = []
    files = request.files.getlist('input_file')

    if template.get('enable_lora_upload') and len(files) > 0:
        if len(files) > 2:
            return jsonify({'error': 'Lora模式最多只能上传2个文件。'}), 400

        safetensors_file = None
        other_file = None
        for file in files:
            if file.filename.endswith('.safetensors'):
                safetensors_file = file
            else:
                other_file = file

        if safetensors_file and other_file:
            # Handle safetensors file
            sf_filename = secure_filename(safetensors_file.filename)
            sf_unique_filename = f"{uuid.uuid4()}_{sf_filename}"
            upload_dir = os.path.join(current_app.instance_path, current_app.config['UPLOAD_FOLDER'])
            os.makedirs(upload_dir, exist_ok=True)
            sf_temp_path = os.path.join(upload_dir, sf_unique_filename)
            safetensors_file.save(sf_temp_path)
            temp_upload_paths.append(sf_temp_path)
            lora_url = f"{server_url}/uploads/{sf_unique_filename}"
            full_cmd += f' --lora {shlex.quote(lora_url)}'

            # Handle other file
            ot_filename = secure_filename(other_file.filename)
            ot_unique_filename = f"{uuid.uuid4()}_{ot_filename}"
            ot_temp_path = os.path.join(upload_dir, ot_unique_filename)
            other_file.save(ot_temp_path)
            temp_upload_paths.append(ot_temp_path)
            file_url = f"{server_url}/uploads/{ot_unique_filename}"

            ext = ot_filename.rsplit('.', 1)[1].lower()
            if ext == 'glb':
                arg_name = '--input_model'
            else:
                arg_map = {
                    'png': '--input_image', 'jpg': '--input_image', 'jpeg': '--input_image', 'gif': '--input_image',
                    'wav': '--input_audio', 'mp3': '--input_audio', 'ogg': '--input_audio',
                    'mp4': '--input_video', 'webm': '--input_video', 'mov': '--input_video'
                }
                arg_name = arg_map.get(ext, '--input_image')
            full_cmd += f' {arg_name} {shlex.quote(file_url)}'

        elif len(files) == 1: # Only one file was uploaded
            file = files[0]
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4()}_{filename}"
                upload_dir = os.path.join(current_app.instance_path, current_app.config['UPLOAD_FOLDER'])
                os.makedirs(upload_dir, exist_ok=True)
                temp_path = os.path.join(upload_dir, unique_filename)
                file.save(temp_path)
                temp_upload_paths.append(temp_path)
                file_url = f"{server_url}/uploads/{unique_filename}"

                ext = filename.rsplit('.', 1)[1].lower()
                if ext == 'safetensors':
                    full_cmd += f' --lora {shlex.quote(file_url)}'
                elif ext == 'glb':
                    full_cmd += f' --input_model {shlex.quote(file_url)}'
                else:
                    arg_map = {
                        'png': '--input_image', 'jpg': '--input_image', 'jpeg': '--input_image', 'gif': '--input_image',
                        'wav': '--input_audio', 'mp3': '--input_audio', 'ogg': '--input_audio',
                        'mp4': '--input_video', 'webm': '--input_video', 'mov': '--input_video'
                    }
                    arg_name = arg_map.get(ext, '--input_image')
                    full_cmd += f' {arg_name} {shlex.quote(file_url)}'

    elif len(files) > 0: # Not a lora-enabled template, handle first file only
        file = files[0]
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            upload_dir = os.path.join(current_app.instance_path, current_app.config['UPLOAD_FOLDER'])
            os.makedirs(upload_dir, exist_ok=True)
            temp_path = os.path.join(upload_dir, unique_filename)
            file.save(temp_path)
            temp_upload_paths.append(temp_path)
            file_url = f"{server_url}/uploads/{unique_filename}"

            ext = filename.rsplit('.', 1)[1].lower()
            if ext == 'glb':
                arg_name = '--input_model'
            else:
                arg_map = {
                    'png': '--input_image', 'jpg': '--input_image', 'jpeg': '--input_image', 'gif': '--input_image',
                    'wav': '--input_audio', 'mp3': '--input_audio', 'ogg': '--input_audio',
                    'mp4': '--input_video', 'webm': '--input_video', 'mov': '--input_video'
                }
                arg_name = arg_map.get(ext, '--input_image')
            full_cmd += f' {arg_name} {shlex.quote(file_url)}'

    seed = None
    if template.get("params") and isinstance(template["params"], list):
        param_parts = []
        for param in template["params"]:
            name = param.get("name")
            if not name: continue

            user_value = request.form.get(name)
            if name.lower() == 'seed' and user_value:
                try:
                    seed = int(user_value)
                except (ValueError, TypeError):
                    seed = str(user_value)

            param_type = param.get("type", "text")
            if param_type == 'boolean':
                if user_value:
                    param_parts.append(f"--{name}")
            else:
                final_value = user_value if user_value is not None else param.get("default", "")
                if final_value:
                    param_parts.append(f"--{name}")
                    param_parts.append(shlex.quote(str(final_value)))
        if param_parts:
            full_cmd += " " + " ".join(param_parts)

    # --- S3 Upload Logic ---
    # Use the admin-defined filename if it exists, otherwise predict it.
    predicted_filename = template.get('predicted_output_filename') or predict_output_filename(prompt, seed)

    if template.get('disable_prompt') and not template.get('predicted_output_filename'):
        predicted_filename = 'output/output.glb'

    # Get the file extension from the predicted filename
    file_ext = os.path.splitext(predicted_filename)[1]
    if not file_ext:
        # Default to .png if the extension is missing
        file_ext = '.png'

    # Create the new filename format: usernameYYYYMMDDHHMM.ext
    timestamp = datetime.now().strftime('%Y%m%d%H%M')
    new_filename = f"{username}{timestamp}{file_ext}"

    # Prepend username to create a unique "folder" for the user in S3
    s3_object_name = f"{username}/{new_filename}"

    # Generate a presigned URL for the S3 object name
    s3_urls = generate_presigned_url(s3_object_name)
    if not s3_urls:
        return jsonify({'error': '无法生成上传URL，请检查S3设置是否正确。'}), 500

    presigned_url = s3_urls['presigned_url']
    final_url = s3_urls['final_url']
    # --- End S3 Upload Logic ---

    task_id = str(uuid.uuid4())
    thread = threading.Thread(target=execute_inference_task, args=(
        task_id, username, full_cmd, temp_upload_paths, user_api_key, server_url,
        template, prompt, seed, presigned_url, s3_object_name, predicted_filename
    ))
    thread.start()

    # Increment user's run and inference counts
    user_data = db['users'].get(username, {})
    user_data['run_count'] = user_data.get('run_count', 0) + 1
    user_data['inference_count'] = user_data.get('inference_count', 0) + 1

    if 'user_states' not in db:
        db['user_states'] = {}
    db['user_states'][username] = {
        'is_waiting_for_file': True,
        'task_id': task_id,
        'ai_project_id': ai_project_id,
        'template_id': template_id,
        'start_time': time.time()
    }
    save_db(db)

    return jsonify({'task_id': task_id})


@main_bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    upload_dir = os.path.join(current_app.instance_path, current_app.config['UPLOAD_FOLDER'])
    return send_from_directory(upload_dir, filename)


@main_bp.route('/chat')
def chat():
    return render_template('chat.html')

@main_bp.route('/chat/history')
def chat_history():
    return render_template('chat_history.html')

@main_bp.route('/check_status/<task_id>')
def check_status(task_id):
    if not session.get('logged_in'):
        return jsonify({'error': '未登录'}), 401

    task = tasks.get(task_id)
    if not task:
        return jsonify({'status': 'not_found'}), 404

    # Make a copy to modify
    task_copy = task.copy()

    # Mask logs for non-admin users
    if not session.get('is_admin'):
        task_copy['logs'] = '****'

    return jsonify(task_copy)


@main_bp.route('/set_avatar', methods=['POST'])
def set_avatar():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    data = request.get_json()
    s3_key = data.get('s3_key')

    if not s3_key:
        return jsonify({'success': False, 'error': 'Missing s3_key'}), 400

    username = session['username']
    # Security check: ensure the user is selecting a file from their own directory
    if not s3_key.startswith(f"{username}/"):
        return jsonify({'success': False, 'error': 'Authorization denied'}), 403

    db = load_db()
    s3_config = get_s3_config()
    if not all([s3_config.get('S3_ENDPOINT_URL'), s3_config.get('S3_BUCKET_NAME')]):
         return jsonify({'success': False, 'error': 'S3 is not configured on the server.'}), 500

    # Construct the public URL
    avatar_url = f"{s3_config['S3_ENDPOINT_URL']}/{s3_config['S3_BUCKET_NAME']}/{s3_key}"

    db['users'][username]['avatar'] = avatar_url
    save_db(db)

    # Update the session so the change is reflected immediately in the header
    session['user_avatar'] = avatar_url

    return jsonify({'success': True, 'new_avatar_url': avatar_url})

@main_bp.route('/api/check_inference_status')
def check_inference_status():
    if not session.get('logged_in'):
        return jsonify({'error': '未登录'}), 401

    db = load_db()
    username = session['username']
    user_state = db.get('user_states', {}).get(username)

    if not user_state or not user_state.get('is_waiting_for_file'):
        return jsonify({'is_waiting': False})

    ai_project_id = user_state.get("ai_project_id")
    template_id = user_state.get("template_id")
    ai_project = db.get("spaces", {}).get(ai_project_id)

    if not ai_project or not template_id:
        user_state["is_waiting_for_file"] = False
        save_db(db)
        return jsonify({"is_waiting": False, "error": "Project or template not found for running task."})

    template = ai_project.get('templates', {}).get(template_id)
    if not template:
        user_state["is_waiting_for_file"] = False
        save_db(db)
        return jsonify({"is_waiting": False, "error": "Template configuration is missing."})

    timeout = template.get("timeout", 300)
    start_time = user_state.get('start_time', 0)

    if time.time() - start_time > timeout:
        user_state['is_waiting_for_file'] = False
        save_db(db)
        # Per user request, do not send a specific timeout message.
        # The button will just become re-enabled on the frontend.
        return jsonify({'is_waiting': False})

    return jsonify({'is_waiting': True})

# --- Public Article Routes ---

@main_bp.route('/articles')
def article_list():
    db = load_db()
    # Sort articles by creation date, newest first
    articles = sorted(db.get('articles', {}).values(), key=lambda x: x.get('created_at', ''), reverse=True)
    return render_template('articles.html', articles=articles)

@main_bp.route('/privacy')
def privacy_policy():
    """Renders the privacy policy page."""
    return render_template('privacy.html')


@main_bp.route('/article/<slug>')
def article_view(slug):
    db = load_db()
    # Find article by slug
    article = next((a for a in db.get('articles', {}).values() if a['slug'] == slug), None)

    if not article:
        return "Article not found", 404

    # --- Hreflang links generation ---
    server_domain = db.get('settings', {}).get('server_domain', request.url_root.rstrip('/'))
    def external_url_for(endpoint, **values):
        if '127.0.0.1' in server_domain or 'localhost' in server_domain:
             return url_for(endpoint, **values, _external=True)
        return f"{server_domain}{url_for(endpoint, **values)}"

    hreflang_links = [
        {'lang': 'zh', 'url': external_url_for('main.article_view', slug=slug)},
        {'lang': 'en', 'url': external_url_for('main.article_view', slug=slug, lang='en')},
        {'lang': 'x-default', 'url': external_url_for('main.article_view', slug=slug)}
    ]

    return render_template('article_view.html', article=article, hreflang_links=hreflang_links)
