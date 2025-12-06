import os
import uuid
import json
import psutil
import time
import requests
from datetime import datetime, timedelta
from flask import (
    Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
)
from werkzeug.utils import secure_filename
from flask import current_app
from .database import load_db, save_db
from .s3_utils import get_public_s3_url
from .utils import allowed_file, slugify
from .netmind_config import (
    DEFAULT_NETMIND_RATE_LIMIT_MAX_REQUESTS,
    DEFAULT_NETMIND_RATE_LIMIT_WINDOW_SECONDS,
    sanitize_rate_limit_max_requests,
    sanitize_rate_limit_window
)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def ensure_pro_settings(db):
    if 'pro_settings' not in db:
        db['pro_settings'] = {
            'enabled': False,
            'task_description': ''
        }
    else:
        db['pro_settings'].setdefault('enabled', False)
        db['pro_settings'].setdefault('task_description', '')
    return db['pro_settings']

def ensure_kofi_settings(db):
    if 'settings' not in db:
        db['settings'] = {}
    if 'kofi_settings' not in db['settings']:
        db['settings']['kofi_settings'] = {
            'verification_token': '',
            'shop_url': 'https://ko-fi.com/s/405169aafb'
        }
    return db['settings']['kofi_settings']

def ensure_netmind_settings(db):
    if 'netmind_settings' not in db:
        db['netmind_settings'] = {
            'keys': [],
            'ad_suffix': '',
            'ad_enabled': False,
            'enable_alias_mapping': False,
            'base_url': 'https://api.netmind.ai/inference-api/openai/v1',
            'model_aliases': {},
            'rate_limit_window_seconds': DEFAULT_NETMIND_RATE_LIMIT_WINDOW_SECONDS,
            'rate_limit_max_requests': DEFAULT_NETMIND_RATE_LIMIT_MAX_REQUESTS
        }
    else:
        db['netmind_settings'].setdefault('model_aliases', {})
        db['netmind_settings'].setdefault('ad_enabled', False)
        db['netmind_settings'].setdefault('enable_alias_mapping', False)
        db['netmind_settings'].setdefault('rate_limit_window_seconds', DEFAULT_NETMIND_RATE_LIMIT_WINDOW_SECONDS)
        db['netmind_settings'].setdefault('rate_limit_max_requests', DEFAULT_NETMIND_RATE_LIMIT_MAX_REQUESTS)

    settings = db['netmind_settings']
    settings['rate_limit_window_seconds'] = sanitize_rate_limit_window(
        settings.get('rate_limit_window_seconds'),
        fallback=DEFAULT_NETMIND_RATE_LIMIT_WINDOW_SECONDS
    )
    settings['rate_limit_max_requests'] = sanitize_rate_limit_max_requests(
        settings.get('rate_limit_max_requests'),
        fallback=DEFAULT_NETMIND_RATE_LIMIT_MAX_REQUESTS
    )
    return db['netmind_settings']

def sync_netmind_aliases(db):
    settings = ensure_netmind_settings(db)
    alias_map = {}
    for space in db.get('spaces', {}).values():
        if space.get('card_type') != 'netmind':
            continue
        alias = (space.get('netmind_model') or '').strip()
        upstream = (space.get('netmind_upstream_model') or alias or '').strip()
        if alias and upstream:
            alias_map[alias] = upstream
    settings['model_aliases'] = alias_map if settings.get('enable_alias_mapping') else {}

@admin_bp.before_request
def check_admin():
    username = session.get('username')
    if not session.get('logged_in') or not username:
        flash('请先登录管理员账号。', 'error')
        return redirect(url_for('auth.login'))

    db = load_db()
    user_in_db = db.get('users', {}).get(username)
    db_admin_status = user_in_db.get('is_admin') if user_in_db else False

    # 如果数据库中的管理员状态与 Session 不一致，则以数据库为准
    if db_admin_status and not session.get('is_admin'):
        session['is_admin'] = True
    elif not db_admin_status:
        session['is_admin'] = False
        flash('无权访问。', 'error')
        return redirect(url_for('main.index'))

@admin_bp.route('/')
def admin_panel():
    db = load_db()
    spaces_list = sorted(db['spaces'].values(), key=lambda x: x['name'])
    announcement = db.get('announcement', {})
    return render_template('admin_panel.html', spaces=spaces_list, announcement=announcement)

@admin_bp.route('/system_stats')
def system_stats():
    # Ensure only admins can access this endpoint, although it's already protected by before_request
    if not session.get('is_admin'):
        return jsonify({'error': '无权访问'}), 403

    try:
        cpu_percent = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return jsonify({
            'cpu_percent': cpu_percent,
            'mem_percent': mem.percent,
            'disk_percent': disk.percent,
            'disk_free_gb': round(disk.free / (1024**3), 2),
            'disk_total_gb': round(disk.total / (1024**3), 2)
        })
    except Exception as e:
        # In case psutil fails for some reason
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/pro_settings', methods=['GET', 'POST'])
def manage_pro_settings():
    db = load_db()
    pro_settings = ensure_pro_settings(db)
    kofi_settings = ensure_kofi_settings(db)

    if request.method == 'POST':
        pro_settings['enabled'] = request.form.get('enabled') == 'on'
        pro_settings['task_description'] = request.form.get('task_description', '')

        kofi_settings['verification_token'] = request.form.get('verification_token', '').strip()
        kofi_settings['shop_url'] = request.form.get('shop_url', '').strip()

        save_db(db)
        flash('Pro 会员设置已保存。', 'success')
        return redirect(url_for('admin.manage_pro_settings'))

    return render_template('admin_pro_settings.html', settings=pro_settings, kofi_settings=kofi_settings)

@admin_bp.route('/kofi/test', methods=['POST'])
def test_kofi_webhook():
    """Simulate a Ko-fi webhook to test configuration."""
    if not session.get('is_admin'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    db = load_db()
    kofi_settings = ensure_kofi_settings(db)
    token = kofi_settings.get('verification_token')

    if not token:
        return jsonify({'success': False, 'error': '请先配置 Verification Token'}), 400

    # Construct a dummy payload
    payload = {
        'verification_token': token,
        'message_id': str(uuid.uuid4()),
        'timestamp': datetime.utcnow().isoformat(),
        'type': 'Shop Order',
        'is_public': True,
        'from_name': 'Test User',
        'message': 'Test Order',
        'amount': '5.00',
        'currency': 'USD',
        'email': 'admin_test@example.com',
        'shop_items': [
            {'direct_link_code': '405169aafb', 'quantity': 1}
        ]
    }

    # Attempt to hit the local webhook endpoint to verifying functionality
    # We use 127.0.0.1 explicitly to avoid DNS issues in some environments
    port = '5001' # Default Flask port as per memory
    if request.host and ':' in request.host:
         port = request.host.split(':')[-1]

    target_url = f"http://127.0.0.1:{port}{url_for('api.kofi_webhook')}"

    try:
        # Send data as form-data 'data' JSON string, mimicking Ko-fi
        response = requests.post(target_url, data={'data': json.dumps(payload)}, timeout=5)

        if response.status_code == 200:
             return jsonify({
                'success': True,
                'message': f'测试成功！Webhook 端点响应正常 (200 OK)。\nPayload sent to: {target_url}'
            })
        elif response.status_code == 403:
             return jsonify({
                'success': False,
                'error': f'验证失败 (403)。请检查 Verification Token 是否一致。'
            })
        else:
             return jsonify({
                'success': False,
                'error': f'Webhook 端点返回异常状态: {response.status_code}'
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'无法连接到本地 Webhook 端点 ({target_url}): {str(e)}'
        }), 500

@admin_bp.route('/users')
def manage_users():
    db = load_db()
    users = db.get('users', {})
    daily_active_users = db.get('daily_active_users', {})
    pro_settings = ensure_pro_settings(db)

    # Date filter
    filter_date = request.args.get('date')

    if filter_date:
        # If a date is selected, only show users active on that day
        # daily_active_users is structure: {"2023-10-27": ["username1", "username2"], ...}
        active_users_for_date = daily_active_users.get(filter_date, [])
        filtered_users = {u: users[u] for u in active_users_for_date if u in users}
    else:
        filtered_users = users

    users_list = []
    now = datetime.utcnow()
    online_threshold = timedelta(minutes=5)

    for username, user_data in filtered_users.items():
        user_info = {'username': username, **user_data}

        # Check for online status
        user_info['is_online'] = False
        user_info['last_seen_relative'] = "从未"

        last_seen_iso = user_data.get('last_seen')
        if last_seen_iso:
            try:
                last_seen_dt = datetime.fromisoformat(last_seen_iso)
                diff = now - last_seen_dt

                if diff < online_threshold:
                    user_info['is_online'] = True

                # Format relative time
                total_seconds = int(diff.total_seconds())
                if total_seconds < 60:
                     user_info['last_seen_relative'] = "刚刚"
                elif total_seconds < 3600:
                     user_info['last_seen_relative'] = f"{total_seconds // 60} 分钟前"
                elif total_seconds < 86400:
                     user_info['last_seen_relative'] = f"{total_seconds // 3600} 小时前"
                else:
                     user_info['last_seen_relative'] = f"{total_seconds // 86400} 天前"

            except (ValueError, TypeError):
                pass # Ignore invalid format

        users_list.append(user_info)

    return render_template(
        'admin_users.html',
        users=users_list,
        pro_enabled=pro_settings.get('enabled'),
        selected_date=filter_date
    )

@admin_bp.route('/users/approve_pro/<username>', methods=['POST'])
def approve_pro_user(username):
    db = load_db()
    user = db.get('users', {}).get(username)
    if user:
        user['is_pro'] = True
        user['pro_submission_status'] = 'approved'
        save_db(db)
        flash(f'用户 {username} 已升级为 Pro 会员。', 'success')
    else:
        flash('未找到用户。', 'error')
    return redirect(url_for('admin.manage_users'))

@admin_bp.route('/users/reject_pro/<username>', methods=['POST'])
def reject_pro_user(username):
    db = load_db()
    user = db.get('users', {}).get(username)
    if user:
        user['is_pro'] = False
        user['pro_submission_status'] = 'rejected'
        save_db(db)
        flash(f'已拒绝用户 {username} 的 Pro 会员申请。', 'success')
    else:
        flash('未找到用户。', 'error')
    return redirect(url_for('admin.manage_users'))

@admin_bp.route('/users/<username>/custom-gpu')
def manage_user_custom_gpu(username):
    db = load_db()
    user = db.get('users', {}).get(username)
    if not user:
        flash('未找到用户。', 'error')
        return redirect(url_for('admin.manage_users'))

    if 'cerebrium_configs' not in user:
        user['cerebrium_configs'] = []
        save_db(db)

    return render_template('admin_user_cerebrium.html', target_user=username, user=user)


@admin_bp.route('/users/<username>/custom-gpu/add', methods=['POST'])
def add_user_custom_gpu_config(username):
    db = load_db()
    user = db.get('users', {}).get(username)
    if not user:
        flash('未找到用户。', 'error')
        return redirect(url_for('admin.manage_users'))

    name = request.form.get('name', '').strip()
    api_url = request.form.get('api_url', '').strip()
    api_token = request.form.get('api_token', '').strip()

    if not all([name, api_url, api_token]):
        flash('名称、API地址和密钥均不能为空。', 'error')
        return redirect(url_for('admin.manage_user_custom_gpu', username=username))

    config = {
        'id': str(uuid.uuid4()),
        'name': name,
        'api_url': api_url,
        'api_token': api_token,
        'created_at': datetime.utcnow().isoformat()
    }

    user.setdefault('cerebrium_configs', []).append(config)

    # Auto-send message to group chat
    if db.get('settings', {}).get('chat_enabled', True):
        # Construct bilingual message
        # Use a safe fallback for the admin username, though session should have it
        admin_username = session.get('username', 'Admin')
        msg_content = (
            f"已为用户 @{username} 添加 {name}，其他用户请耐心等待。\n"
            f"Added {name} for user @{username}, other users please wait patiently."
        )

        new_message = {
            'id': str(uuid.uuid4()),
            'username': admin_username,
            'content': msg_content,
            'timestamp': time.time()
        }

        if 'chat_messages' not in db:
            db['chat_messages'] = []

        db['chat_messages'].append(new_message)

        # Archiving logic (keep last 100 messages)
        if len(db['chat_messages']) > 99:
            if 'chat_history' not in db:
                db['chat_history'] = []
            db['chat_history'].append(db['chat_messages'].pop(0))

    save_db(db)
    flash('已添加新的 GPU 配置。', 'success')
    return redirect(url_for('admin.manage_user_custom_gpu', username=username))

@admin_bp.route('/users/<username>/custom-gpu/<config_id>/edit', methods=['POST'])
def edit_user_custom_gpu_config(username, config_id):
    db = load_db()
    user = db.get('users', {}).get(username)
    if not user:
        flash('未找到用户。', 'error')
        return redirect(url_for('admin.manage_users'))

    configs = user.setdefault('cerebrium_configs', [])
    config = next((c for c in configs if c.get('id') == config_id), None)
    if not config:
        flash('未找到配置。', 'error')
        return redirect(url_for('admin.manage_user_custom_gpu', username=username))

    config['name'] = request.form.get('name', config.get('name', '')).strip()
    config['api_url'] = request.form.get('api_url', config.get('api_url', '')).strip()
    config['api_token'] = request.form.get('api_token', config.get('api_token', '')).strip()
    config['updated_at'] = datetime.utcnow().isoformat()

    save_db(db)
    flash('配置已更新。', 'success')
    return redirect(url_for('admin.manage_user_custom_gpu', username=username))

@admin_bp.route('/users/<username>/custom-gpu/<config_id>/delete', methods=['POST'])
def delete_user_custom_gpu_config(username, config_id):
    db = load_db()
    user = db.get('users', {}).get(username)
    if not user:
        flash('未找到用户。', 'error')
        return redirect(url_for('admin.manage_users'))

    configs = user.setdefault('cerebrium_configs', [])
    new_configs = [c for c in configs if c.get('id') != config_id]
    if len(new_configs) == len(configs):
        flash('未找到配置。', 'error')
        return redirect(url_for('admin.manage_user_custom_gpu', username=username))

    user['cerebrium_configs'] = new_configs
    save_db(db)
    flash('配置已删除。', 'success')
    return redirect(url_for('admin.manage_user_custom_gpu', username=username))

@admin_bp.route('/users/delete/<username>', methods=['POST'])
def delete_user(username):
    db = load_db()
    if username in db['users']:
        del db['users'][username]
        save_db(db)
        flash(f'用户 {username} 已被删除。', 'success')
    else:
        flash('未找到用户。', 'error')
    return redirect(url_for('admin.manage_users'))

@admin_bp.route('/announcement', methods=['GET', 'POST'])
def manage_announcement():
    db = load_db()

    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'main':
            announcement_data = {
                'enabled': request.form.get('enabled') == 'on',
                'title': request.form.get('title', ''),
                'content': request.form.get('content', ''),
                'type': request.form.get('type', 'info'),  # info, warning, success, error
                'show_on_homepage': request.form.get('show_on_homepage') == 'on',
                'show_on_projects': request.form.get('show_on_projects') == 'on'
            }
            db['announcement'] = announcement_data
            flash('全局公告设置已保存！', 'success')

        elif form_type == 'chat':
            chat_data = {
                'enabled': request.form.get('chat_enabled') == 'on',
                'content': request.form.get('chat_content', ''),
                'type': request.form.get('chat_type', 'info')
            }
            db['chat_announcement'] = chat_data
            flash('聊天界面公告设置已保存！', 'success')

        elif form_type == 'terminal':
            terminal_data = {
                'enabled': request.form.get('terminal_enabled') == 'on',
                'content': request.form.get('terminal_content', ''),
                'type': request.form.get('terminal_type', 'info')
            }
            db['terminal_announcement'] = terminal_data
            flash('云终端公告设置已保存！', 'success')

        save_db(db)
        return redirect(url_for('admin.manage_announcement'))

    announcement = db.get('announcement', {
        'enabled': False,
        'title': '',
        'content': '',
        'type': 'info',
        'show_on_homepage': True,
        'show_on_projects': True
    })
    chat_announcement = db.get('chat_announcement', {
        'enabled': False,
        'content': '',
        'type': 'info'
    })
    terminal_announcement = db.get('terminal_announcement', {
        'enabled': False,
        'content': '',
        'type': 'info'
    })
    return render_template('admin_announcement.html',
                           announcement=announcement,
                           chat_announcement=chat_announcement,
                           terminal_announcement=terminal_announcement)

@admin_bp.route('/gpu-pool', methods=['GET'])
def manage_gpu_pool():
    db = load_db()
    # Initialize if missing (handled in load_db actually, but explicitly here for safety)
    if 'gpu_pool' not in db:
        db['gpu_pool'] = []
    return render_template('admin_gpu_pool.html', gpu_pool=db['gpu_pool'])

@admin_bp.route('/gpu-pool/add', methods=['POST'])
def add_gpu_to_pool():
    db = load_db()
    if 'gpu_pool' not in db:
        db['gpu_pool'] = []

    name = request.form.get('name', '').strip()
    api_url = request.form.get('api_url', '').strip()
    api_token = request.form.get('api_token', '').strip()

    if not all([name, api_url, api_token]):
        flash('所有字段都是必填的。', 'error')
        return redirect(url_for('admin.manage_gpu_pool'))

    new_gpu = {
        'id': str(uuid.uuid4()),
        'name': name,
        'api_url': api_url,
        'api_token': api_token,
        'added_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    }

    db['gpu_pool'].append(new_gpu)
    save_db(db)
    flash(f'GPU {name} 已添加到池中。', 'success')
    return redirect(url_for('admin.manage_gpu_pool'))

@admin_bp.route('/gpu-pool/delete/<pool_id>', methods=['POST'])
def delete_gpu_from_pool(pool_id):
    db = load_db()
    if 'gpu_pool' not in db:
        return redirect(url_for('admin.manage_gpu_pool'))

    initial_len = len(db['gpu_pool'])
    db['gpu_pool'] = [gpu for gpu in db['gpu_pool'] if gpu['id'] != pool_id]

    if len(db['gpu_pool']) < initial_len:
        save_db(db)
        flash('GPU 已从池中移除。', 'success')
    else:
        flash('未找到该 GPU。', 'error')

    return redirect(url_for('admin.manage_gpu_pool'))

@admin_bp.route('/banner', methods=['GET', 'POST'])
def manage_banner():
    db = load_db()
    if request.method == 'POST':
        banner_data = {
            'enabled': request.form.get('enabled') == 'on',
            'image_url': request.form.get('image_url', ''),
            'link_url': request.form.get('link_url', '')
        }
        db['banner'] = banner_data
        save_db(db)
        flash('横幅设置已保存！', 'success')
        return redirect(url_for('admin.manage_banner'))

    banner = db.get('banner', {'enabled': False, 'image_url': '', 'link_url': ''})
    return render_template('admin_banner.html', banner=banner)

@admin_bp.route('/space/add', methods=['GET', 'POST'])
@admin_bp.route('/space/edit/<space_id>', methods=['GET', 'POST'])
def add_edit_space(space_id=None):
    db = load_db()
    space = db['spaces'].get(space_id) if space_id else None
    netmind_settings = ensure_netmind_settings(db)

    if request.method == 'POST':
        new_id = space_id or str(uuid.uuid4())

        # The cover is now a URL from S3, submitted in a hidden field.
        # The old logic for file upload is no longer needed.
        cover_filename = request.form.get('cover', 'default.png')
        cover_type = request.form.get('cover_type', 'image')
        card_type = request.form.get('card_type', 'standard')
        timeout_raw = (request.form.get('cerebrium_timeout_minutes') or '').strip()
        try:
            timeout_minutes = int(timeout_raw)
        except (ValueError, TypeError):
            timeout_minutes = None
        if not timeout_minutes or timeout_minutes <= 0:
            timeout_minutes = 5
        timeout_seconds = timeout_minutes * 60

        netmind_alias = request.form.get('netmind_model', '').strip()
        netmind_upstream = request.form.get('netmind_upstream_model', '').strip()
        if card_type == 'netmind' and not netmind_upstream:
            netmind_upstream = netmind_alias
        if not netmind_settings.get('enable_alias_mapping'):
            netmind_upstream = netmind_alias

        if space: # Editing an existing space
            space['name'] = request.form['name']
            space['description'] = request.form.get('description', '')
            space['cover'] = cover_filename
            space['cover_type'] = cover_type
            space['card_type'] = card_type
            space['cerebrium_timeout_seconds'] = timeout_seconds
            if card_type == 'netmind':
                space['netmind_model'] = netmind_alias
                space['netmind_upstream_model'] = netmind_upstream or ''
            else:
                space.pop('netmind_model', None)
                space.pop('netmind_upstream_model', None)
        else: # Creating a new space
            db['spaces'][new_id] = {
                'id': new_id,
                'name': request.form['name'],
                'description': request.form.get('description', ''),
                'cover': cover_filename,
                'cover_type': cover_type,
                'card_type': card_type,
                'cerebrium_timeout_seconds': timeout_seconds,
                'templates': {}, # Initialize with an empty templates dict
                'netmind_model': netmind_alias if card_type == 'netmind' else '',
                'netmind_upstream_model': netmind_upstream if card_type == 'netmind' else ''
            }
        sync_netmind_aliases(db)
        save_db(db)
        flash(f"Space '{request.form['name']}' 已保存。", 'success')
        return redirect(url_for('admin.add_edit_space', space_id=new_id))

    settings = db.get('settings', {})
    return render_template('add_edit_space.html', space=space, settings=settings, netmind_settings=netmind_settings)

@admin_bp.route('/space/<space_id>/set_cover', methods=['POST'])
def set_space_cover(space_id):
    db = load_db()
    space = db['spaces'].get(space_id)
    if not space:
        return jsonify({'success': False, 'error': 'Space not found'}), 404

    data = request.get_json()
    s3_key = data.get('s3_key')
    if not s3_key:
        return jsonify({'success': False, 'error': 'Missing s3_key'}), 400

    # Optional: Security check to ensure the admin is selecting a file from a valid user folder
    # This might be overly restrictive if admins can use any image, so it's commented out.
    # if not s3_key.startswith(f"{session['username']}/"):
    #     return jsonify({'success': False, 'error': 'Authorization denied for this file'}), 403

    cover_url = get_public_s3_url(s3_key)
    if not cover_url:
        return jsonify({'success': False, 'error': 'Could not generate public URL for the selected file.'}), 500

    space['cover'] = cover_url
    space['cover_type'] = 'image' # Selecting from results is always an image
    save_db(db)

    return jsonify({'success': True, 'new_cover_url': cover_url})


@admin_bp.route('/space/<space_id>/template/add', methods=['POST'])
def add_template(space_id):
    db = load_db()
    space = db['spaces'].get(space_id)
    if not space:
        return jsonify({'success': False, 'error': 'Space not found'}), 404

    data = request.json
    # Accommodate both 'name' from JS and direct form field name 'template_name' for robustness
    template_name = data.get('name') or data.get('template_name')
    if not template_name:
        return jsonify({'success': False, 'error': 'Template name is required'}), 400

    if 'templates' not in space:
        space['templates'] = {}

    new_template_id = str(uuid.uuid4())
    new_template = {
        'id': new_template_id,
        'name': template_name,
        'command_runner': data.get('command_runner', 'inferless'),
        'entrypoint_script': data.get('entrypoint_script', 'app.py'),
        'pre_command': data.get('pre_command', ''),
        'sub_command': data.get('sub_command', ''),
        'base_command': data.get('base_command', ''),
        'preset_params': data.get('preset_params', ''),
        'predicted_output_filename': data.get('predicted_output_filename', ''),
        'params': data.get('params', []),
        'timeout': int(data.get('timeout', 300)),
        'force_upload': bool(data.get('force_upload', False)),
        'enable_lora_upload': bool(data.get('enable_lora_upload', False)),
        'requires_invitation_code': bool(data.get('requires_invitation_code', False)),
        'disable_prompt': bool(data.get('disable_prompt', False))
    }

    space['templates'][new_template_id] = new_template
    save_db(db)

    return jsonify({'success': True, 'template': new_template})


@admin_bp.route('/space/<space_id>/template/edit/<template_id>', methods=['POST'])
def edit_template(space_id, template_id):
    db = load_db()
    space = db['spaces'].get(space_id)
    if not space or 'templates' not in space or template_id not in space['templates']:
        return jsonify({'success': False, 'error': 'Template not found'}), 404

    data = request.json
    template = space['templates'][template_id]

    # Handle name alias from frontend `template_name`
    if 'template_name' in data:
        data['name'] = data.pop('template_name')

    # A schema-like approach to define template structure and types
    allowed_keys = {
        'name': str, 'command_runner': str, 'entrypoint_script': str,
        'pre_command': str, 'sub_command': str, 'base_command': str,
        'preset_params': str, 'predicted_output_filename': str,
        'params': list, 'timeout': int, 'force_upload': bool,
        'enable_lora_upload': bool, 'requires_invitation_code': bool,
        'disable_prompt': bool
    }

    if not data.get('name'):
        return jsonify({'success': False, 'error': 'Template name is required'}), 400

    # Update template fields based on incoming data, with type casting
    for key, key_type in allowed_keys.items():
        if key in data:
            value = data[key]
            try:
                # Cast value to the expected type (e.g., "true" -> True, "300" -> 300)
                if key_type == bool:
                    template[key] = bool(value)
                elif key_type == int:
                    template[key] = int(value)
                elif key_type == list:
                    template[key] = list(value) if isinstance(value, list) else []
                else:
                    template[key] = str(value)
            except (ValueError, TypeError):
                # If casting fails, you might want to return an error or use a default
                # For simplicity, we can skip the update for this key or log an error
                # Here, we'll just stick to the old value if cast fails (except for name)
                pass

    save_db(db)
    return jsonify({'success': True, 'template': template})


@admin_bp.route('/space/<space_id>/template/delete/<template_id>', methods=['POST'])
def delete_template(space_id, template_id):
    db = load_db()
    space = db['spaces'].get(space_id)
    if not space or 'templates' not in space or template_id not in space['templates']:
        return jsonify({'success': False, 'error': 'Template not found'}), 404

    del space['templates'][template_id]
    save_db(db)
    return jsonify({'success': True})


@admin_bp.route('/space/delete/<space_id>')
def delete_space(space_id):
    db = load_db()
    if space_id in db['spaces']:
        cover = db['spaces'][space_id].get('cover')
        if cover and cover != 'default.png':
            cover_path = os.path.join(current_app.root_path, current_app.config['COVER_FOLDER'], cover)
            if os.path.exists(cover_path):
                os.remove(cover_path)

        del db['spaces'][space_id]
        sync_netmind_aliases(db)
        save_db(db)
        flash('Space 已删除。', 'success')

    return redirect(url_for('admin.admin_panel'))

@admin_bp.route('/keys', methods=['GET', 'POST'])
def manage_keys():
    keys_file = 'key.txt'
    if request.method == 'POST':
        new_keys = request.form.get('keys')
        try:
            with open(keys_file, 'w', encoding='utf-8') as f:
                f.write(new_keys)
            flash('密钥文件已成功更新。', 'success')
        except IOError as e:
            flash(f'写入文件时出错: {e}', 'error')
        return redirect(url_for('admin.manage_keys'))

    keys_content = ''
    try:
        with open(keys_file, 'r', encoding='utf-8') as f:
            keys_content = f.read()
    except FileNotFoundError:
        flash('key.txt 文件未找到。将创建一个新文件。', 'warning')
    except IOError as e:
        flash(f'读取文件时出错: {e}', 'error')

    return render_template('admin_keys.html', keys_content=keys_content)

@admin_bp.route('/netmind', methods=['GET', 'POST'])
def netmind_settings():
    db = load_db()
    settings = ensure_netmind_settings(db)
    # Keep alias list in sync so the admin page reflects latest per-space config
    sync_netmind_aliases(db)

    if request.method == 'POST':
        settings['base_url'] = request.form.get('base_url', '').strip()
        settings['ad_suffix'] = request.form.get('ad_suffix', '')
        settings['ad_enabled'] = request.form.get('ad_enabled') == 'on'
        settings['enable_alias_mapping'] = request.form.get('enable_alias_mapping') == 'on'
        settings['rate_limit_window_seconds'] = sanitize_rate_limit_window(
            request.form.get('rate_limit_window_seconds'),
            fallback=settings.get('rate_limit_window_seconds')
        )
        settings['rate_limit_max_requests'] = sanitize_rate_limit_max_requests(
            request.form.get('rate_limit_max_requests'),
            fallback=settings.get('rate_limit_max_requests')
        )
        if not settings['enable_alias_mapping']:
            settings['model_aliases'] = {}
        save_db(db)
        flash('模型代理配置已更新。', 'success')
        return redirect(url_for('admin.netmind_settings'))

    return render_template('admin_netmind.html', settings=settings)

@admin_bp.route('/netmind/key/add', methods=['POST'])
def netmind_add_key():
    db = load_db()
    settings = ensure_netmind_settings(db)

    new_key = request.form.get('new_key', '').strip()
    if new_key:
        if new_key not in settings['keys']:
            settings['keys'].append(new_key)
            save_db(db)
            flash('密钥已添加。', 'success')
        else:
            flash('密钥已存在。', 'warning')
    else:
        flash('密钥不能为空。', 'error')

    return redirect(url_for('admin.netmind_settings'))

@admin_bp.route('/netmind/key/delete', methods=['POST'])
def netmind_delete_key():
    db = load_db()
    settings = ensure_netmind_settings(db)
    key_to_delete = request.form.get('key_to_delete')

    if key_to_delete and key_to_delete in settings.get('keys', []):
        settings['keys'].remove(key_to_delete)
        save_db(db)
        flash('密钥已删除。', 'success')
    else:
        flash('未找到密钥。', 'error')

    return redirect(url_for('admin.netmind_settings'))

@admin_bp.route('/s3_settings', methods=['GET', 'POST'])
def manage_s3_settings():
    """
    Manages S3 configuration settings.
    """
    S3_CONFIG_FILE = current_app.config['S3_CONFIG_FILE']

    if request.method == 'POST':
        s3_config = {
            'S3_ENDPOINT_URL': request.form.get('s3_endpoint_url'),
            'S3_ACCESS_KEY_ID': request.form.get('s3_access_key_id'),
            'S3_SECRET_ACCESS_KEY': request.form.get('s3_secret_access_key'),
            'S3_BUCKET_NAME': request.form.get('s3_bucket_name'),
        }
        try:
            with open(S3_CONFIG_FILE, 'w') as f:
                json.dump(s3_config, f, indent=4)
            flash('S3 设置已成功保存。应用需要重启以使更改生效。', 'success')
        except IOError as e:
            flash(f'写入 S3 配置文件时出错: {e}', 'error')
        return redirect(url_for('admin.manage_s3_settings'))

    s3_config = {}
    try:
        if os.path.exists(S3_CONFIG_FILE):
            with open(S3_CONFIG_FILE, 'r') as f:
                s3_config = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        flash(f'读取 S3 配置文件时出错: {e}', 'warning')

    return render_template('admin_s3_settings.html', s3_config=s3_config)


@admin_bp.route('/modal_drive_settings', methods=['GET', 'POST'])
def manage_modal_drive_settings():
    """
    Manage Modal Drive proxy credentials.
    """
    db = load_db()
    settings = db.setdefault('settings', {})

    if request.method == 'POST':
        settings['modal_drive_base_url'] = request.form.get('modal_drive_base_url', '').strip()
        settings['modal_drive_auth_token'] = request.form.get('modal_drive_auth_token', '').strip()
        save_db(db)
        flash('无限容量网盘设置已保存。', 'success')
        return redirect(url_for('admin.manage_modal_drive_settings'))

    modal_settings = {
        'modal_drive_base_url': settings.get('modal_drive_base_url', ''),
        'modal_drive_auth_token': settings.get('modal_drive_auth_token', '')
    }
    return render_template('admin_modal_drive.html', settings=modal_settings)


@admin_bp.route('/invitation_codes', methods=['GET', 'POST'])
def manage_invitation_codes():
    db = load_db()
    # Ensure invitation_codes is a dictionary
    if 'invitation_codes' not in db or not isinstance(db['invitation_codes'], dict):
        db['invitation_codes'] = {}

    if request.method == 'POST':
        if 'add_code' in request.form:
            new_code = request.form.get('new_code') or str(uuid.uuid4())
            uses = request.form.get('uses', '1')

            if new_code in db['invitation_codes']:
                flash('此邀请码已存在。', 'error')
            else:
                try:
                    uses_int = int(uses)
                    if uses_int <= 0:
                        flash('可用次数必须为正数。', 'error')
                    else:
                        db['invitation_codes'][new_code] = {'uses': uses_int}
                        save_db(db)
                        flash(f"邀请码 '{new_code}' 已添加，可使用 {uses_int} 次。", 'success')
                except ValueError:
                    flash('无效的可用次数。', 'error')

        elif 'delete_code' in request.form:
            code_to_delete = request.form.get('code_to_delete')
            if code_to_delete in db['invitation_codes']:
                del db['invitation_codes'][code_to_delete]
                save_db(db)
                flash('邀请码已删除。', 'success')

    # Sort codes for display
    sorted_codes = dict(sorted(db['invitation_codes'].items()))
    return render_template('admin_invitation_codes.html', codes=sorted_codes)

@admin_bp.route('/categories', methods=['GET', 'POST'])
def manage_categories():
    db = load_db()
    if 'categories' not in db:
        db['categories'] = []

    category_to_edit = None
    if 'edit_id' in request.args:
        edit_id = request.args.get('edit_id')
        category_to_edit = next((cat for cat in db['categories'] if cat['id'] == edit_id), None)

    if request.method == 'POST':
        category_id = request.form.get('category_id')
        name = request.form.get('name')
        icon = request.form.get('icon')

        if not name or not icon:
            flash('名称和图标不能为空。', 'error')
            return redirect(url_for('admin.manage_categories'))

        if category_id: # Editing existing category
            for cat in db['categories']:
                if cat['id'] == category_id:
                    cat['name'] = name
                    cat['icon'] = icon
                    break
            flash('分类已更新。', 'success')
        else: # Adding new category
            new_category = {
                'id': str(uuid.uuid4()),
                'name': name,
                'icon': icon
            }
            db['categories'].append(new_category)
            flash('分类已添加。', 'success')

        save_db(db)
        return redirect(url_for('admin.manage_categories'))

    return render_template('admin_categories.html', categories=db['categories'], category_to_edit=category_to_edit)

@admin_bp.route('/sensitive_words')
def manage_sensitive_words():
    db = load_db()
    words = db.get('sensitive_words', [])
    return render_template('admin_sensitive_words.html', words=words)

@admin_bp.route('/sensitive_words/add', methods=['POST'])
def add_sensitive_word():
    db = load_db()
    word = request.form.get('word', '').strip()
    if word:
        if 'sensitive_words' not in db:
            db['sensitive_words'] = []
        if word not in db['sensitive_words']:
            db['sensitive_words'].append(word)
            save_db(db)
            flash(f"敏感词 '{word}' 已添加。", 'success')
        else:
            flash(f"敏感词 '{word}' 已存在。", 'info')
    else:
        flash('敏感词不能为空。', 'error')
    return redirect(url_for('admin.manage_sensitive_words'))

@admin_bp.route('/sensitive_words/delete/<word>')
def delete_sensitive_word(word):
    db = load_db()
    if 'sensitive_words' in db and word in db['sensitive_words']:
        db['sensitive_words'].remove(word)
        save_db(db)
        flash(f"敏感词 '{word}' 已删除。", 'success')
    return redirect(url_for('admin.manage_sensitive_words'))


@admin_bp.route('/category/delete/<category_id>')
def delete_category(category_id):
    db = load_db()
    db['categories'] = [cat for cat in db['categories'] if cat['id'] != category_id]
    save_db(db)
    flash('分类已删除。', 'success')
    return redirect(url_for('admin.manage_categories'))

# --- Article Management Routes ---

@admin_bp.route('/articles')
def manage_articles():
    db = load_db()
    articles = sorted(db.get('articles', {}).values(), key=lambda x: x.get('created_at', ''), reverse=True)
    return render_template('admin_articles.html', articles=articles)

@admin_bp.route('/article/add', methods=['GET', 'POST'])
@admin_bp.route('/article/edit/<article_id>', methods=['GET', 'POST'])
def add_edit_article(article_id=None):
    db = load_db()
    article = db.get('articles', {}).get(article_id) if article_id else None

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        custom_slug = request.form.get('slug')
        tags_raw = request.form.get('tags', '')
        tags = [tag.strip() for tag in tags_raw.split(',') if tag.strip()]

        if not title or not content:
            flash('标题和内容不能为空。', 'error')
            return render_template('add_edit_article.html', article=article)

        if article:  # Editing
            article['title'] = title
            article['content'] = content
            article['tags'] = tags
            article['slug'] = slugify(custom_slug or title)
            article['updated_at'] = datetime.utcnow().isoformat()
            flash('文章已更新。', 'success')
        else:  # Adding new
            new_id = str(uuid.uuid4())
            slug = slugify(custom_slug or title)
            if not slug:
                slug = new_id[:8]

            all_slugs = {a.get('slug') for a in db.get('articles', {}).values()}
            if slug in all_slugs:
                slug = f"{slug}-{new_id[:4]}"

            if 'articles' not in db:
                db['articles'] = {}

            db['articles'][new_id] = {
                'id': new_id,
                'title': title,
                'content': content,
                'tags': tags,
                'slug': slug,
                'author': session.get('username', 'admin'),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat(),
            }
            flash('文章已创建。', 'success')

        save_db(db)
        return redirect(url_for('admin.manage_articles'))

    return render_template('add_edit_article.html', article=article)

@admin_bp.route('/article/delete/<article_id>', methods=['POST'])
def delete_article(article_id):
    db = load_db()
    if article_id in db.get('articles', {}):
        del db['articles'][article_id]
        save_db(db)
        flash('文章已删除。', 'success')
    else:
        flash('未找到文章。', 'error')
    return redirect(url_for('admin.manage_articles'))

@admin_bp.route('/error_logs')
def error_logs():
    log_file_path = os.path.join(current_app.root_path, '../error.log')
    logs = []
    if os.path.exists(log_file_path):
        with open(log_file_path, 'r', encoding='utf-8') as f:
            logs = f.readlines()
    return render_template('admin_error_logs.html', logs=logs)

@admin_bp.route('/clear_logs')
def clear_logs():
    log_file_path = os.path.join(current_app.root_path, '../error.log')
    if os.path.exists(log_file_path):
        try:
            with open(log_file_path, 'w') as f:
                f.truncate()
            flash('错误日志已成功清除。', 'success')
        except IOError as e:
            flash(f'清除日志文件时出错: {e}', 'error')
    else:
        flash('未找到日志文件。', 'info')
    return redirect(url_for('admin.error_logs'))

@admin_bp.route('/save_ad_settings', methods=['POST'])
def save_ad_settings():
    """保存广告详细设置"""
    db = load_db()
    data = request.json
    
    if 'settings' not in db:
        db['settings'] = {}
    
    # Update settings from request
    if 'ads_enabled' in data:
        db['settings']['ads_enabled'] = bool(data['ads_enabled'])
    if 'adsterra_enabled' in data:
        db['settings']['adsterra_enabled'] = bool(data['adsterra_enabled'])
    if 'monetag_enabled' in data:
        db['settings']['monetag_enabled'] = bool(data['monetag_enabled'])
    if 'richads_enabled' in data:
        db['settings']['richads_enabled'] = bool(data['richads_enabled'])

    save_db(db)
    
    return jsonify({
        'success': True,
        'settings': {
            'ads_enabled': db['settings'].get('ads_enabled', False),
            'adsterra_enabled': db['settings'].get('adsterra_enabled', True),
            'monetag_enabled': db['settings'].get('monetag_enabled', True),
            'richads_enabled': db['settings'].get('richads_enabled', True)
        },
        'message': '广告设置已更新'
    })
