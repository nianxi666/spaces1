import os
import uuid
import shlex
import threading
import tempfile
from collections import deque
from datetime import datetime
from zoneinfo import ZoneInfo
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
import secrets
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
from project.netmind_proxy import NetMindClient
from flask import session
from .netmind_config import (
    DEFAULT_NETMIND_RATE_LIMIT_MAX_REQUESTS,
    DEFAULT_NETMIND_RATE_LIMIT_WINDOW_SECONDS,
    get_rate_limit_config
)
from .gpu_allocator import try_allocate_gpu_from_pool
from .sockets import connected_workers
from . import socketio

api_bp = Blueprint('api', __name__, url_prefix='/api')

# --- WebSocket Task Queues ---
# A simple in-memory queue for each space.
# In a production environment, you would use a more robust system like Redis or RabbitMQ.
task_queues = {}
task_locks = {}
# space_name -> {'status': 'idle'|'busy', 'current_task': {}}
worker_status = {}

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

_netmind_rate_limit_history = {}

def _check_netmind_rate_limit(user_identifier, max_requests, window_seconds):
    """
    Simple in-memory rate limiter for NetMind chat API.
    Limits each user to max_requests per window_seconds interval.
    """
    if not user_identifier:
        return True, None

    try:
        max_requests = int(max_requests)
    except (TypeError, ValueError):
        max_requests = DEFAULT_NETMIND_RATE_LIMIT_MAX_REQUESTS

    try:
        window_seconds = int(window_seconds)
    except (TypeError, ValueError):
        window_seconds = DEFAULT_NETMIND_RATE_LIMIT_WINDOW_SECONDS

    if max_requests <= 0:
        return True, None

    history = _netmind_rate_limit_history.setdefault(user_identifier, deque())
    now = time.time()
    window = max(1, window_seconds)

    while history and now - history[0] >= window:
        history.popleft()

    if len(history) >= max_requests:
        retry_after = window - (now - history[0])
        return False, max(1, int(retry_after))

    history.append(now)
    return True, None


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

    username = session.get('username')
    db = load_db()

    # Try to allocate GPU if needed
    # This acts as a "heartbeat" trigger for online users
    if username:
        try_allocate_gpu_from_pool(db, username)

    # Check if chat is enabled
    if not db.get('settings', {}).get('chat_enabled', True) and not session.get('is_admin'):
        return jsonify({'success': False, 'error': 'Chat is disabled'}), 403

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

    if not db.get('settings', {}).get('chat_enabled', True) and not session.get('is_admin'):
        return jsonify({'success': False, 'error': '聊天功能已关闭。'}), 403

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

@api_bp.route('/chat/toggle_enabled', methods=['POST'])
def toggle_chat_enabled():
    if not session.get('logged_in') or not session.get('is_admin'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    db = load_db()
    # Default to True if not set
    current_status = db.get('settings', {}).get('chat_enabled', True)

    if 'settings' not in db:
        db['settings'] = {}

    db['settings']['chat_enabled'] = not current_status
    save_db(db)

    new_status = not current_status
    message = '聊天功能已开启。' if new_status else '聊天功能已关闭。'

    return jsonify({'success': True, 'message': message, 'chat_enabled': new_status})

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


@api_bp.route('/user/status', methods=['GET'])
def get_user_status():
    """
    API endpoint to get the current user's status (e.g., membership).
    Used for frontend polling after recharge.
    """
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    username = session['username']
    db = load_db()
    user = db.get('users', {}).get(username)

    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    return jsonify({
        'success': True,
        'username': username,
        'is_pro': user.get('is_pro', False),
        'membership_expiry': user.get('membership_expiry')
    })


# No prefix needed since it's under api_bp which has url_prefix='/api'
# So the route is /api/v1/chat/completions
@api_bp.route('/v1/chat/completions', methods=['POST'])
def netmind_chat_completions():
    """
    OpenAI-compatible endpoint for NetMind chat completions.
    Authenticated via PumpkinAI User Bearer Token.
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

    db = load_db()

    # Daily check-in validation logic
    beijing_tz = ZoneInfo("Asia/Shanghai")
    today_str = datetime.now(beijing_tz).strftime('%Y-%m-%d')
    username = user['username']
    user_data = db['users'].get(username, {})

    if user_data.get('first_api_use_date') is None:
        # First time using the API, record the date
        user_data['first_api_use_date'] = today_str
        save_db(db)
    else:
        # Not the first time, check for check-in
        if user_data.get('first_api_use_date') != today_str:
            if user_data.get('last_check_in_date') != today_str:
                return jsonify({'error': '您需要完成今日签到才能继续使用API，请前往个人资料页面签到。'}), 403

    max_requests, window_seconds = get_rate_limit_config(db.get('netmind_settings'))
    allowed, retry_after = _check_netmind_rate_limit(user['username'], max_requests, window_seconds)
    if not allowed:
        per_minute = max_requests
        if window_seconds and window_seconds != 60 and max_requests > 0:
            per_minute = max(1, int(max_requests * 60 / window_seconds))
        return jsonify({
            'error': 'Rate limit exceeded. Please wait before sending more requests.',
            'retry_after_seconds': retry_after,
            'limit_per_window': max_requests,
            'window_seconds': window_seconds,
            'limit_per_minute': per_minute
        }), 429

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Missing request body'}), 400

    messages = data.get('messages')
    model = data.get('model')
    stream = data.get('stream', False)
    max_tokens = data.get('max_tokens')
    functions = data.get('functions')
    function_call = data.get('function_call')
    tools = data.get('tools')
    tool_choice = data.get('tool_choice')

    if max_tokens is not None:
        try:
            max_tokens = int(max_tokens)
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid max_tokens value'}), 400
        if max_tokens <= 0:
            return jsonify({'error': 'max_tokens must be greater than zero'}), 400

    if not messages or not model:
        return jsonify({'error': 'Missing required parameters: messages, model'}), 400

    # Security/Rate Limiting could go here

    extra_params = {}
    if functions is not None:
        extra_params['functions'] = functions
    if function_call is not None:
        extra_params['function_call'] = function_call
    if tools is not None:
        extra_params['tools'] = tools
    if tool_choice is not None:
        extra_params['tool_choice'] = tool_choice
    if not extra_params:
        extra_params = None

    client = NetMindClient()

    try:
        response = client.chat_completion(
            db,
            messages,
            model,
            stream=stream,
            max_tokens=max_tokens,
            extra_params=extra_params
        )

        if stream:
            resp = Response(
                stream_with_context(response),
                mimetype='text/event-stream'
            )
            resp.headers['Cache-Control'] = 'no-cache, no-transform'
            resp.headers['Connection'] = 'keep-alive'
            resp.headers['X-Accel-Buffering'] = 'no'
            return resp
        else:
            # For sync response, OpenAI object needs to be serialized to JSON
            # response is a ChatCompletion object from openai library
            return jsonify(json.loads(response.model_dump_json()))

    except Exception as e:
        import traceback
        traceback.print_exc()
        # If it's an OpenAI API error with a status code, return that
        if hasattr(e, 'status_code') and e.status_code:
            return jsonify({'error': str(e)}), e.status_code
        return jsonify({'error': str(e)}), 500

@api_bp.route('/space/<space_id>/submit_task', methods=['POST'])
def submit_task(space_id):
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': '请先登录'}), 401

    username = session['username']
    db = load_db()
    space = db.get('spaces', {}).get(space_id)

    if not space:
        return jsonify({'success': False, 'error': 'Space not found'}), 404

    if space.get('card_type') != 'websocket':
        return jsonify({'success': False, 'error': 'This space does not support WebSocket tasks'}), 400

    # --- Prepare Task Data ---
    task_id = str(uuid.uuid4())
    inputs = {}

    # Process text inputs
    if 'text' in space.get('allowed_input_types', []):
        prompt = request.form.get('prompt')
        if prompt:
            inputs['text'] = prompt

    # Process file uploads (streaming to S3)
    if 'file' in request.files:
        file = request.files['file']
        if file.filename:
            # Construct a unique filename in S3
            safe_filename = secure_filename(file.filename)
            s3_key = f"{username}/uploads/{uuid.uuid4().hex[:8]}_{safe_filename}"

            # Since we're streaming, we need to get the S3 client
            # This logic might need to be more robust depending on your s3_utils setup
            try:
                from .s3_utils import s3_client, get_s3_config
                config = get_s3_config()
                bucket_name = config.get('S3_BUCKET_NAME')
                if not bucket_name:
                    raise ValueError("S3 bucket name not configured.")

                s3 = s3_client()
                s3.upload_fileobj(
                    file.stream,
                    bucket_name,
                    s3_key,
                    ExtraArgs={'ContentType': file.content_type}
                )

                file_url = get_public_s3_url(s3_key)
                if not file_url:
                     return jsonify({'success': False, 'error': 'File uploaded, but could not get public URL'}), 500

                # Determine input type based on file extension
                ext = os.path.splitext(safe_filename)[1].lower()
                if ext in ['.wav', '.mp3', '.ogg']:
                    inputs['audio_url'] = file_url
                elif ext in ['.png', '.jpg', '.jpeg', '.webp']:
                    inputs['image_url'] = file_url
                else:
                    inputs['file_url'] = file_url # Generic file

            except Exception as e:
                current_app.logger.error(f"S3 streaming upload failed: {e}")
                return jsonify({'success': False, 'error': f'File upload failed: {e}'}), 500

    if not inputs:
        return jsonify({'success': False, 'error': 'No valid inputs provided for this task.'}), 400

    # --- Add to Queue ---
    space_name = space['name']
    task = {
        'task_id': task_id,
        'user_sid': request.form.get('user_sid'), # Client needs to send its Socket.IO SID
        'username': username,
        'inputs': inputs
    }

    lock = task_locks.setdefault(space_name, threading.Lock())
    with lock:
        queue = task_queues.setdefault(space_name, deque())
        queue.append(task)

    # Announce new task to user via their SID
    if task['user_sid']:
        queue_position = len(queue)
        socketio.emit('task_status', {
            'status': 'queued',
            'position': queue_position,
            'total': queue_position
        }, room=task['user_sid'])

    # Try to dispatch the task immediately
    try_dispatch_task(space_name)

    return jsonify({'success': True, 'task_id': task_id, 'status': 'queued'})

def try_dispatch_task(space_name):
    lock = task_locks.get(space_name)
    if not lock:
        return

    with lock:
        queue = task_queues.get(space_name, deque())
        worker_sid = connected_workers.get(space_name)

        status = worker_status.get(space_name, {})
        is_busy = status.get('status') == 'busy'

        if not queue or not worker_sid or is_busy:
            return

        task = queue.popleft()
        worker_status[space_name] = {'status': 'busy', 'current_task': task}

        # Emit 'new_task' to the specific worker
        socketio.emit('new_task', task, room=worker_sid, namespace='/workers')

        # Notify the user that their task is now processing
        if task.get('user_sid'):
            socketio.emit('task_status', {'status': 'processing'}, room=task.get('user_sid'))

        # Notify other users in the queue about their updated position
        for i, queued_task in enumerate(queue):
            if queued_task.get('user_sid'):
                socketio.emit('task_status', {
                    'status': 'queued',
                    'position': i + 1,
                    'total': len(queue)
                }, room=queued_task.get('user_sid'))
