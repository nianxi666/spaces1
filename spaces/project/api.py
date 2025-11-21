import os
import uuid
import shlex
import threading
import tempfile
from datetime import datetime
from flask import (
    Blueprint, request, jsonify, url_for, current_app, Response, stream_with_context
)
from werkzeug.utils import secure_filename
import time
import requests
import subprocess
import shutil
import base64
import json
from .database import load_db, save_db, backup_db
from .utils import allowed_file, get_user_by_token, predict_output_filename, slugify
from . import tasks
from .s3_utils import (
    generate_presigned_url,
    get_public_s3_url,
    rename_s3_object,
    list_files_for_user,
    get_s3_config
)
from flask import session

api_bp = Blueprint('api', __name__, url_prefix='/api')

HARDWARE_PROFILES = {
    'cpu': {
        'display_name': 'CPU (2 vCPU, 2GB)',
        'compute': None,
        'cpu': 2.0,
        'memory': 2.0,
        'docker_image': 'debian:bookworm-slim',
        'default_app_name': 'cloud-terminal'
    },
    'l40s': {
        'display_name': 'NVIDIA L40S (24GB)',
        'compute': 'ADA_L40',
        'cpu': 4.0,
        'memory': 32.0,
        'docker_image': 'nvidia/cuda:12.1.0-runtime-ubuntu22.04',
        'default_app_name': 'cloud-terminal'
    },
    'h100': {
        'display_name': 'NVIDIA H100 (80GB)',
        'compute': 'HOPPER_H100',
        'cpu': 8.0,
        'memory': 60.0,
        'docker_image': 'nvidia/cuda:12.1.0-runtime-ubuntu22.04',
        'default_app_name': 'cloud-terminal'
    }
}

DEFAULT_HARDWARE_KEY = 'cpu'

@api_bp.route('/upload', methods=['POST'])
def api_upload():
    """API upload endpoint with Bearer Token authentication."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing or invalid Authorization header'}), 401

    api_key = auth_header[7:]
    if not api_key:
        return jsonify({'error': 'Missing API key'}), 401

    db = load_db()
    found_user = None
    for username, user_data in db['users'].items():
        if user_data.get('api_key') == api_key:
            found_user = username
            break

    if not found_user:
        return jsonify({'error': 'Invalid API key'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        user_pan_dir = os.path.join(current_app.instance_path, current_app.config['RESULTS_FOLDER'], found_user)
        os.makedirs(user_pan_dir, exist_ok=True)

        original_name = filename
        counter = 1
        while os.path.exists(os.path.join(user_pan_dir, filename)):
            name, ext = os.path.splitext(original_name)
            filename = f"{name}_{counter}{ext}"
            counter += 1

        filepath = os.path.join(user_pan_dir, filename)
        file.save(filepath)

        # Database logic for API uploads
        db = load_db()
        file_id = str(uuid.uuid4())
        db['uploaded_files'][file_id] = {
            'username': found_user,
            'filename': filename,
            'filepath': filepath,
            'upload_type': 'api',
            'timestamp': time.time()
        }

        # 当文件上传成功时，更新用户状态
        if 'user_states' in db and found_user in db['user_states']:
            db['user_states'][found_user]['is_waiting_for_file'] = False

        # Enforce retention policy: max 2 files for API uploads
        user_api_files = [
            (fid, f) for fid, f in db['uploaded_files'].items()
            if f['username'] == found_user and f['upload_type'] == 'api'
        ]

        if len(user_api_files) > 2:
            user_api_files.sort(key=lambda x: x[1]['timestamp'])

            # Delete the oldest file(s)
            files_to_delete = user_api_files[:-2]
            for fid, file_to_delete in files_to_delete:
                if os.path.exists(file_to_delete['filepath']):
                    os.remove(file_to_delete['filepath'])
                del db['uploaded_files'][fid]

        save_db(db)

        # When called from the API, we need to generate the full URL
        file_url = url_for('results.download_file', username=found_user, filename=filename, _external=True)

        return jsonify({
            'message': f'File "{filename}" uploaded successfully to user "{found_user}"\'s results.',
            'filename': filename,
            'file_url': file_url
        }), 200
    else:
        return jsonify({'error': 'File type not allowed'}), 400

@api_bp.route('/generate-upload-url')
def generate_upload_url():
    """
    Generates a pre-signed URL for direct S3 uploads.
    Requires login.
    """
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    file_name = request.args.get('fileName')
    content_type = request.args.get('contentType')

    if not file_name or not content_type:
        return jsonify({'success': False, 'error': 'Missing fileName or contentType query parameter'}), 400

    username = session.get('username')
    if not username:
        return jsonify({'success': False, 'error': 'User not found in session'}), 401

    # Sanitize filename to prevent path traversal issues
    safe_file_name = secure_filename(file_name)
    # Create a unique filename to avoid overwrites, storing it in the user's "folder"
    unique_filename = f"{username}/{uuid.uuid4().hex[:8]}_{safe_file_name}"

    urls = generate_presigned_url(unique_filename, content_type=content_type)

    if urls and 'presigned_url' in urls:
        # Return the presigned URL for uploading and the final, public URL for embedding
        return jsonify({'success': True, 'presigned_url': urls['presigned_url'], 'final_url': urls['final_url']})
    else:
        return jsonify({'success': False, 'error': 'Could not generate upload URL. Is S3 configured correctly?'}), 500


@api_bp.route('/get-s3-view-url')
def get_s3_view_url():
    """
    Generates a public URL for an S3 object.
    """
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    object_key = request.args.get('key')
    if not object_key:
        return jsonify({'success': False, 'error': 'Missing object key parameter'}), 400

    # Security check: Ensure the user is trying to access their own files.
    if not object_key.startswith(f"{session['username']}/"):
        return jsonify({'success': False, 'error': 'Authorization denied for this object'}), 403

    url = get_public_s3_url(object_key)

    if url:
        return jsonify({'success': True, 'url': url})
    else:
        return jsonify({'success': False, 'error': 'Could not generate view URL'}), 500


@api_bp.route('/cloud-terminal/run', methods=['POST'])
def proxy_cloud_terminal_command():
    """
    Proxy a command to the Cerebrium cloud terminal so the browser does not need direct access.
    """
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    data = request.get_json(silent=True) or {}
    command = (data.get('command') or '').strip()
    target_name = (data.get('target') or '').strip()

    if not command:
        return jsonify({'success': False, 'error': '请输入要执行的命令'}), 400

    username = session['username']
    db = load_db()
    user = db.get('users', {}).get(username)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    configs = user.get('cerebrium_configs', [])
    if not configs:
        return jsonify({'success': False, 'error': '未配置云终端环境，请联系管理员添加 GPU 配置'}), 400

    selected_config = None
    if target_name:
        selected_config = next((c for c in configs if c.get('name') == target_name), None)

    # If no target specified or not found, default to first
    if not selected_config:
        if target_name:
             return jsonify({'success': False, 'error': f'未找到名为 {target_name} 的环境配置'}), 404
        selected_config = configs[0]

    target_url = selected_config.get('api_url')
    token = selected_config.get('api_token')

    if not target_url or not token:
        return jsonify({'success': False, 'error': '选定的环境配置不完整（缺少 URL 或 Token）'}), 500

    timeout = current_app.config.get('CEREBRIUM_CLOUD_TERMINAL_TIMEOUT', 60)
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    try:
        remote_response = requests.post(
            target_url,
            headers=headers,
            json={'command': command},
            timeout=timeout
        )
    except requests.RequestException as exc:
        return jsonify({'success': False, 'error': f'请求云终端失败: {exc}'}), 502

    try:
        payload = remote_response.json()
    except ValueError:
        payload = {'raw': remote_response.text}

    response_data = {
        'success': remote_response.ok,
        'status_code': remote_response.status_code,
        'payload': payload,
        'proxy_latency_ms': int(remote_response.elapsed.total_seconds() * 1000)
    }

    if not remote_response.ok:
        response_error = None
        if isinstance(payload, dict):
            response_error = payload.get('error') or payload.get('message')
        response_data['error'] = response_error or '远程服务返回错误'

    status_code = 200 if remote_response.ok else remote_response.status_code
    return jsonify(response_data), status_code


def build_cerebrium_toml(app_name, preset):
    """
    Generate a cerebrium.toml string based on the selected hardware preset.
    """
    docker_line = ""
    if preset.get('docker_image'):
        docker_line = f'\ndocker_base_image_url = "{preset["docker_image"]}"'

    compute_line = ""
    if preset.get("compute"):
        compute_line = f'compute = "{preset.get("compute")}"'

    toml = [
        "[cerebrium.deployment]",
        f'name = "{app_name}"',
        'python_version = "3.12"',
        'disable_auth = true',
        'include = ["./*"]',
        'exclude = [".git", "__pycache__", ".DS_Store"]',
        docker_line,
        "",
        "[cerebrium.hardware]",
        f'cpu = {preset.get("cpu", 2.0)}',
        f'memory = {preset.get("memory", 16.0)}',
        compute_line,
        'provider = "aws"',
        'region = "us-east-1"',
        "",
        "[cerebrium.scaling]",
        "min_replicas = 0",
        "max_replicas = 2",
        "cooldown = 30",
        "replica_concurrency = 1",
    ]
    return "\n".join(line for line in toml if line is not None)


def ensure_cerebrium_cli_available():
    """
    Ensure the cerebrium CLI is available on the VPS.
    """
    if shutil.which('cerebrium'):
        return True, None
    try:
        proc = subprocess.run(
            ['pip', 'install', '-q', '--upgrade', 'cerebrium'],
            capture_output=True,
            text=True,
            timeout=120
        )
        if proc.returncode == 0 and shutil.which('cerebrium'):
            return True, None
        return False, proc.stderr or proc.stdout
    except Exception as exc:
        return False, str(exc)


def decode_project_id(token_value):
    """
    Extract projectId from the JWT payload if present.
    """
    try:
        parts = token_value.split('.')
        if len(parts) < 2:
            return None
        payload_b64 = parts[1]
        pad = '=' * (-len(payload_b64) % 4)
        payload_data = base64.urlsafe_b64decode(payload_b64 + pad)
        payload_json = json.loads(payload_data.decode('utf-8'))
        return payload_json.get('projectId')
    except Exception:
        return None


@api_bp.route('/cloud-terminal/apps', methods=['POST'])
def list_cloud_terminal_apps():
    """
    Lists configured cloud terminal apps from user settings (not probing CLI).
    """
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    username = session['username']
    db = load_db()
    user = db.get('users', {}).get(username)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    configs = user.get('cerebrium_configs', [])
    apps = []
    for cfg in configs:
        apps.append({
            'name': cfg.get('name', 'Unnamed'),
            'url': cfg.get('api_url', ''),
            'full_id': cfg.get('id'), # Using config ID as unique ref
            'status': 'Configured',
            'last_updated': cfg.get('updated_at', cfg.get('created_at'))
        })

    return jsonify({'success': True, 'apps': apps})


IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm', 'm4v', 'mpg', 'mpeg'}

def is_image(filename):
    """Check if a filename has an image extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in IMAGE_EXTENSIONS

def is_video(filename):
    """Check if a filename has a video extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in VIDEO_EXTENSIONS

@api_bp.route('/my_s3_files', methods=['GET'])
def list_my_s3_files():
    """
    Lists files for the currently logged-in user from the S3 bucket.
    """
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    username = session['username']
    files = list_files_for_user(username)

    if files is not None:
        for file in files:
            # Convert datetime objects to ISO 8601 strings
            if 'last_modified' in file and hasattr(file['last_modified'], 'isoformat'):
                file['last_modified'] = file['last_modified'].isoformat()

            file['is_image'] = is_image(file['filename'])
            file['is_video'] = is_video(file['filename'])
            if file['is_image'] or file['is_video']:
                file['preview_url'] = get_public_s3_url(file['key'])
            else:
                file['preview_url'] = None

        return jsonify({'success': True, 'files': files})
    else:
        return jsonify({'success': False, 'error': 'Failed to list files from S3.'}), 500


@api_bp.route('/space/<space_id>/like', methods=['POST'])
def like_space(space_id):
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    db = load_db()
    space = db['spaces'].get(space_id)
    if not space:
        return jsonify({'success': False, 'error': 'Space not found'}), 404

    username = session['username']

    # Initialize liked_by list if it doesn't exist
    if 'liked_by' not in space:
        space['liked_by'] = []

    is_liked = False
    if username in space['liked_by']:
        # User has already liked it, so unlike it
        space['liked_by'].remove(username)
        is_liked = False
    else:
        # User has not liked it, so like it
        space['liked_by'].append(username)
        is_liked = True

    save_db(db)

    return jsonify({
        'success': True,
        'is_liked': is_liked,
        'like_count': len(space['liked_by'])
    })

@api_bp.route('/user-state/selected-file', methods=['POST'])
def save_selected_file():
    """
    Saves the user's selected S3 file key for a specific AI project.
    """
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    data = request.get_json()
    s3_key = data.get('s3_key')
    ai_project_id = data.get('ai_project_id')

    if not all([s3_key, ai_project_id]):
        return jsonify({'success': False, 'error': 'Missing s3_key or ai_project_id'}), 400

    username = session['username']
    db = load_db()

    # Ensure user_states and user-specific state exists
    if 'user_states' not in db:
        db['user_states'] = {}
    if username not in db['user_states']:
        db['user_states'][username] = {}

    # Ensure selected_files dictionary exists
    if 'selected_files' not in db['user_states'][username]:
        db['user_states'][username]['selected_files'] = {}

    db['user_states'][username]['selected_files'][ai_project_id] = s3_key
    save_db(db)

    return jsonify({'success': True, 'message': 'Selection saved.'})


@api_bp.route('/cerebrium/save-result', methods=['POST'])
def save_cerebrium_result():
    """
    Persist the latest GPU card result so it can be restored after refresh.
    """
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    data = request.get_json(silent=True) or {}
    ai_project_id = data.get('ai_project_id')
    output_key = data.get('output_key')
    filename = data.get('filename')
    status = data.get('status', 'completed')
    public_url_override = data.get('public_url')

    if not all([ai_project_id, output_key, filename]):
        return jsonify({'success': False, 'error': 'Missing ai_project_id, output_key or filename'}), 400

    if status not in ('pending', 'completed', 'timeout'):
        status = 'completed'

    username = session['username']
    if not output_key.startswith(f"{username}/"):
        return jsonify({'success': False, 'error': 'Output key does not belong to current user'}), 400

    db = load_db()
    user_states = db.setdefault('user_states', {})
    state = user_states.setdefault(username, {})
    results_map = state.setdefault('cerebrium_results', {})

    public_url = public_url_override or get_public_s3_url(output_key)
    now = datetime.utcnow()
    result_payload = {
        'output_key': output_key,
        'filename': filename,
        'public_url': public_url,
        'status': status,
        'saved_at': now.isoformat(timespec='milliseconds') + 'Z',
        'saved_at_ms': int(now.timestamp() * 1000)
    }
    results_map[ai_project_id] = result_payload
    save_db(db)

    return jsonify({'success': True, 'result': result_payload})

@api_bp.route('/cerebrium/configs', methods=['GET'])
def get_my_cerebrium_configs():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    username = session['username']
    db = load_db()
    user = db.get('users', {}).get(username)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    configs = user.get('cerebrium_configs', [])
    return jsonify({'success': True, 'configs': configs})

@api_bp.route('/cerebrium/s3-context', methods=['GET'])
def get_cerebrium_s3_context():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    username = session['username']
    db = load_db()
    user = db.get('users', {}).get(username)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    if not user.get('cerebrium_configs'):
        return jsonify({'success': False, 'error': 'No Cerebrium GPU assigned'}), 403

    s3_config = get_s3_config()
    if not s3_config:
        return jsonify({'success': False, 'error': 'S3 未配置'}), 500

    endpoint = s3_config.get('S3_ENDPOINT_URL')
    bucket = s3_config.get('S3_BUCKET_NAME')
    access_key = s3_config.get('S3_ACCESS_KEY_ID')
    secret_key = s3_config.get('S3_SECRET_ACCESS_KEY')

    if not all([endpoint, bucket, access_key, secret_key]):
        return jsonify({'success': False, 'error': 'S3 配置不完整'}), 500

    public_base_url = f"{endpoint.rstrip('/')}/{bucket}"

    return jsonify({
        'success': True,
        'context': {
            'endpoint_url': endpoint,
            'bucket_name': bucket,
            'access_key_id': access_key,
            'secret_access_key': secret_key,
            'region': 'auto',
            'public_base_url': public_base_url,
            'username_prefix': username
        }
    })

@api_bp.route('/rename-s3-object', methods=['POST'])
def rename_s3_object_route():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Authentication required'}), 401

    data = request.get_json()
    old_key = data.get('old_key')
    new_filename = data.get('new_filename')

    if not all([old_key, new_filename]):
        return jsonify({'success': False, 'error': 'Missing old_key or new_filename'}), 400

    username = session['username']
    if not old_key.startswith(f"{username}/"):
        return jsonify({'success': False, 'error': 'Authorization denied'}), 403

    # Construct the new key while keeping the same "directory"
    directory = os.path.dirname(old_key)
    safe_new_filename = secure_filename(new_filename)
    new_key = os.path.join(directory, safe_new_filename)

    if old_key == new_key:
        return jsonify({'success': False, 'error': 'New name is the same as the old name'}), 400

    success = rename_s3_object(old_key, new_key)

    if success:
        return jsonify({'success': True, 'message': 'File renamed successfully.'})
    else:
        return jsonify({'success': False, 'error': 'Failed to rename file on S3.'}), 500

def _require_admin_session():
    if not session.get('logged_in') or not session.get('is_admin'):
        return False
    return True

def _get_user_for_admin(username):
    db = load_db()
    user = db.get('users', {}).get(username)
    return db, user

@api_bp.route('/admin/users/<username>/cerebrium-configs', methods=['GET'])
def admin_list_cerebrium_configs(username):
    if not _require_admin_session():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    db, user = _get_user_for_admin(username)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    return jsonify({'success': True, 'configs': user.get('cerebrium_configs', [])})

@api_bp.route('/admin/users/<username>/cerebrium-configs', methods=['POST'])
def admin_add_cerebrium_config(username):
    if not _require_admin_session():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    api_url = (data.get('api_url') or '').strip()
    api_token = (data.get('api_token') or '').strip()

    if not all([name, api_url, api_token]):
        return jsonify({'success': False, 'error': 'Missing name, api_url or api_token'}), 400

    db, user = _get_user_for_admin(username)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    config = {
        'id': str(uuid.uuid4()),
        'name': name,
        'api_url': api_url,
        'api_token': api_token,
        'created_at': datetime.utcnow().isoformat()
    }
    user.setdefault('cerebrium_configs', []).append(config)
    save_db(db)

    return jsonify({'success': True, 'config': config})

@api_bp.route('/admin/users/<username>/cerebrium-configs/<config_id>', methods=['PUT'])
def admin_update_cerebrium_config(username, config_id):
    if not _require_admin_session():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    data = request.get_json() or {}
    db, user = _get_user_for_admin(username)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    configs = user.setdefault('cerebrium_configs', [])
    config = next((c for c in configs if c.get('id') == config_id), None)
    if not config:
        return jsonify({'success': False, 'error': 'Config not found'}), 404

    if 'name' in data:
        config['name'] = data['name'].strip()
    if 'api_url' in data:
        config['api_url'] = data['api_url'].strip()
    if 'api_token' in data:
        config['api_token'] = data['api_token'].strip()
    config['updated_at'] = datetime.utcnow().isoformat()

    save_db(db)
    return jsonify({'success': True, 'config': config})

@api_bp.route('/admin/users/<username>/cerebrium-configs/<config_id>', methods=['DELETE'])
def admin_delete_cerebrium_config(username, config_id):
    if not _require_admin_session():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    db, user = _get_user_for_admin(username)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    configs = user.setdefault('cerebrium_configs', [])
    new_configs = [c for c in configs if c.get('id') != config_id]
    if len(new_configs) == len(configs):
        return jsonify({'success': False, 'error': 'Config not found'}), 404

    user['cerebrium_configs'] = new_configs
    save_db(db)
    return jsonify({'success': True})

@api_bp.route('/admin/backup', methods=['POST'])
def admin_backup():
    if not session.get('logged_in') or not session.get('is_admin'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    result = backup_db()
    return jsonify(result)

@api_bp.route('/chat/messages', methods=['GET'])
def get_chat_messages():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    db = load_db()
    # Return the last 50 messages
    messages = db.get('chat_messages', [])[-50:]
    # Enrich messages with user info
    for msg in messages:
        user_info = db['users'].get(msg['username'], {})
        msg['avatar'] = user_info.get('avatar', 'default.png')

    return jsonify({'success': True, 'messages': messages})

@api_bp.route('/chat/messages', methods=['POST'])
def post_chat_message():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    last_message_time = session.get('last_message_time', 0)
    if time.time() - last_message_time < 10:
        return jsonify({'success': False, 'error': '请稍后再发送消息。'}), 429

    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'success': False, 'error': 'No message provided'}), 400

    message_content = data['message'].strip()
    if not message_content:
        return jsonify({'success': False, 'error': 'Message cannot be empty'}), 400

    db = load_db()

    if db.get('settings', {}).get('chat_is_muted', False) and not session.get('is_admin'):
        return jsonify({'success': False, 'error': '聊天室当前处于禁言状态。'}), 403

    sensitive_words = db.get('sensitive_words', [])
    for word in sensitive_words:
        if word in message_content:
            return jsonify({'success': False, 'error': f'消息包含敏感词: {word}'}), 400

    username = session['username']

    new_message = {
        'id': str(uuid.uuid4()),
        'username': username,
        'content': message_content,
        'timestamp': time.time()
    }

    db['chat_messages'].append(new_message)

    # Archiving logic
    if len(db['chat_messages']) > 99:
        if 'chat_history' not in db:
            db['chat_history'] = []
        # Move the oldest message to history
        db['chat_history'].append(db['chat_messages'].pop(0))

    save_db(db)

    session['last_message_time'] = time.time()

    return jsonify({'success': True, 'message': 'Message posted'})

@api_bp.route('/chat/messages/<message_id>', methods=['DELETE'])
def delete_chat_message(message_id):
    if not session.get('logged_in') or not session.get('is_admin'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    db = load_db()

    initial_len = len(db.get('chat_messages', []))
    db['chat_messages'] = [msg for msg in db.get('chat_messages', []) if msg.get('id') != message_id]

    if len(db['chat_messages']) == initial_len:
        return jsonify({'success': False, 'error': 'Message not found'}), 404

    save_db(db)

    return jsonify({'success': True, 'message': 'Message deleted'})

@api_bp.route('/chat/mute', methods=['POST'])
def toggle_chat_mute():
    if not session.get('logged_in') or not session.get('is_admin'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    db = load_db()

    current_status = db.get('settings', {}).get('chat_is_muted', False)
    db['settings']['chat_is_muted'] = not current_status
    save_db(db)

    new_status = not current_status
    message = '全局禁言已开启。' if new_status else '全局禁言已关闭。'

    return jsonify({'success': True, 'message': message, 'is_muted': new_status})

@api_bp.route('/chat/history', methods=['GET'])
def get_chat_history():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    db = load_db()
    history = db.get('chat_history', [])
    return jsonify({'success': True, 'history': history})

@api_bp.route('/chat/unread-count', methods=['GET'])
def get_unread_chat_count():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    username = session['username']
    db = load_db()
    user = db.get('users', {}).get(username)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    last_read_time = user.get('last_chat_read_time', 0)

    # Count messages newer than the last read time
    unread_count = 0
    for msg in db.get('chat_messages', []):
        # Ensure the message has a timestamp and it's a number
        if isinstance(msg.get('timestamp'), (int, float)) and msg['timestamp'] > last_read_time:
            unread_count += 1

    return jsonify({'success': True, 'unread_count': unread_count})

@api_bp.route('/chat/mark-as-read', methods=['POST'])
def mark_chat_as_read():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    username = session['username']
    db = load_db()
    user = db.get('users', {}).get(username)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    user['last_chat_read_time'] = time.time()
    save_db(db)

    return jsonify({'success': True, 'message': 'Chat marked as read.'})

@api_bp.route('/v1/spaces/run', methods=['POST'])
def run_space_api():
    """
    API endpoint to run a space inference.
    Supports both asynchronous (task_id) and streaming responses.
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing or invalid Authorization header'}), 401

    token = auth_header[7:]
    if not token:
        return jsonify({'error': 'Missing token'}), 401

    db = load_db()
    user = get_user_by_token(token)

    if not user:
        return jsonify({'error': 'Invalid token'}), 403

    username = user['username']

    if db.get('user_states', {}).get(username, {}).get('is_waiting_for_file'):
        return jsonify({'error': 'You already have a task running. Please wait for it to complete.'}), 429

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Missing request body'}), 400

    space_name = data.get('space_name')
    template_name = data.get('gpu_template')
    stream = data.get('stream', False)

    if not all([space_name, template_name]):
        return jsonify({'error': 'Missing required parameters: space_name, gpu_template'}), 400

    space = next((s for s in db.get('spaces', {}).values() if s['name'] == space_name), None)
    if not space:
        return jsonify({'error': f'Space "{space_name}" not found'}), 404

    ai_project_id = space['id']

    template = next((t for t in space.get('templates', {}).values() if t['name'] == template_name), None)
    if not template:
        return jsonify({'error': f'Template "{template_name}" not found in space "{space_name}"'}), 404

    template_id = next((k for k, v in space.get('templates', {}).items() if v['name'] == template_name), None)

    user_api_key = user.get('api_key')
    if not user_api_key:
        return jsonify({'error': 'User API key is missing'}), 500

    server_url = db.get('settings', {}).get('server_domain')
    if not server_url:
        return jsonify({'error': 'Server domain is not configured'}), 500

    base_cmd = template.get("base_command", "")
    full_cmd = base_cmd
    prompt = None

    if template.get('disable_prompt'):
        file_url = data.get('file_url')
        if not file_url:
            return jsonify({'error': 'Missing required parameter: file_url for this space'}), 400

        file_url_lower = file_url.lower()
        if file_url_lower.endswith('.safetensors'):
            arg_name = '--lora'
        elif file_url_lower.endswith('.glb'):
            arg_name = '--input_model'
        else:
            arg_name = '--input_image'
        full_cmd += f' {arg_name} {shlex.quote(file_url)}'
    else:
        prompt = data.get('prompt')
        if not prompt:
            return jsonify({'error': 'Missing required parameter: prompt for this space'}), 400

        sensitive_words = db.get('sensitive_words', [])
        if sensitive_words:
            for word in sensitive_words:
                if word in prompt:
                    return jsonify({'error': f'Your prompt contains a sensitive word: "{word}"'}), 400
        full_cmd += f' --prompt {shlex.quote(prompt)}'

    preset_params = template.get("preset_params", "").strip()
    if preset_params:
        full_cmd += f' {preset_params}'

    predicted_filename = template.get('predicted_output_filename') or predict_output_filename(prompt or '')
    if template.get('disable_prompt') and not template.get('predicted_output_filename'):
        predicted_filename = 'output/output.glb'

    file_ext = os.path.splitext(predicted_filename)[1] or '.png'
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    new_filename = f"{username}_{timestamp}{file_ext}"
    s3_object_name = f"{username}/{new_filename}"

    s3_urls = generate_presigned_url(s3_object_name)
    if not s3_urls:
        return jsonify({'error': 'Could not generate S3 upload URL. Check server configuration.'}), 500

    presigned_url = s3_urls['presigned_url']

    # Set user state to waiting before starting the task or stream
    if 'user_states' not in db:
        db['user_states'] = {}
    db['user_states'][username] = {
        'is_waiting_for_file': True,
        'ai_project_id': ai_project_id,
        'template_id': template_id,
        'start_time': time.time()
    }
    save_db(db) # Save state before starting

    if stream:
        # The generator is responsible for resetting the user's waiting status in its `finally` block
        return Response(tasks.execute_inference_task_stream(
            username, full_cmd, [], user_api_key, server_url,
            template, prompt, None, presigned_url, s3_object_name, predicted_filename
        ), mimetype='text/plain')
    else:
        # Asynchronous response
        task_id = str(uuid.uuid4())
        db['user_states'][username]['task_id'] = task_id # Add task_id for async lookup
        save_db(db)

        thread = threading.Thread(target=tasks.execute_inference_task, args=(
            task_id, username, full_cmd, [], user_api_key, server_url,
            template, prompt, None, presigned_url, s3_object_name, predicted_filename
        ))
        thread.start()

        # Update user stats for async tasks
        user_data = db['users'].get(username, {})
        user_data['run_count'] = user_data.get('run_count', 0) + 1
        user_data['inference_count'] = user_data.get('inference_count', 0) + 1
        save_db(db)

        return jsonify({'task_id': task_id, 'status': 'running'}), 202

@api_bp.route('/v1/task/<task_id>/status', methods=['GET'])
def get_task_status_api(task_id):
    """
    API endpoint to check the status of a specific task.
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing or invalid Authorization header'}), 401

    token = auth_header[7:]
    if not token:
        return jsonify({'error': 'Missing token'}), 401

    user = get_user_by_token(token)
    if not user:
        return jsonify({'error': 'Invalid token'}), 403

    task = tasks.tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    # Security check: Ensure the user requesting the status is the one who created the task
    if task.get('username') != user['username']:
        return jsonify({'error': 'Unauthorized'}), 403

    return jsonify(task)
