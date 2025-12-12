"""
WebSocket Server Module for Remote Inference Connections

This module handles WebSocket connections from remote app.py clients
and manages inference request queues for each Space.
"""
import time
import uuid
from collections import deque
from datetime import datetime
from flask import Blueprint, request, session
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from .database import load_db, save_db

# Global SocketIO instance - will be set in create_app
socketio = None

# Active remote connections: {space_name: {"sid": socket_id, "connected_at": timestamp}}
active_connections = {}

# User request queues: {space_name: deque([{"request_id": str, "user": str, "data": dict, "submitted_at": float}])}
request_queues = {}

# Pending results: {request_id: {"space_name": str, "user": str, "status": str, "result": any}}
pending_results = {}

# User socket mapping for pushing results: {username: [sid1, sid2, ...]}
user_sockets = {}

ws_bp = Blueprint('websocket', __name__, url_prefix='/ws')


def init_socketio(app):
    """Initialize SocketIO with the Flask app."""
    global socketio
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
    register_handlers(socketio)
    return socketio


def get_socketio():
    """Get the SocketIO instance."""
    return socketio


def is_space_online(space_name):
    """Check if a space has an active remote connection."""
    return space_name in active_connections


def get_space_connection_info(space_name):
    """Get connection info for a space."""
    return active_connections.get(space_name)


def get_queue_position(space_name, request_id):
    """Get the queue position for a request."""
    if space_name not in request_queues:
        return -1
    queue = request_queues[space_name]
    for i, req in enumerate(queue):
        if req['request_id'] == request_id:
            return i + 1  # 1-indexed position
    return -1


def get_queue_length(space_name):
    """Get the current queue length for a space."""
    if space_name not in request_queues:
        return 0
    return len(request_queues[space_name])


def submit_inference_request(space_name, username, data):
    """
    Submit an inference request to the queue.
    Returns (success, request_id or error_message, queue_position)
    """
    if not is_space_online(space_name):
        return False, "远程服务器不在线", 0
    
    # Get max queue size from space settings
    db = load_db()
    space = None
    for sid, s in db.get('spaces', {}).items():
        if s.get('name') == space_name:
            space = s
            break
    
    max_queue = 10
    if space:
        max_queue = space.get('ws_max_queue_size', 10) or 10
    
    # Initialize queue if needed
    if space_name not in request_queues:
        request_queues[space_name] = deque()
    
    queue = request_queues[space_name]
    
    # Check queue limit
    if len(queue) >= max_queue:
        return False, f"队列已满，最多 {max_queue} 人排队", 0
    
    # Create request
    request_id = str(uuid.uuid4())
    request_data = {
        'request_id': request_id,
        'user': username,
        'data': data,
        'submitted_at': time.time()
    }
    
    queue.append(request_data)
    position = len(queue)
    
    # Store pending result
    pending_results[request_id] = {
        'space_name': space_name,
        'user': username,
        'status': 'queued',
        'result': None,
        'queue_position': position
    }
    
    # If this is the first in queue, send to remote immediately
    if position == 1:
        _send_to_remote(space_name, request_data)
    
    return True, request_id, position


def get_pending_result(request_id):
    """Get the status of a pending request."""
    return pending_results.get(request_id)


def _send_to_remote(space_name, request_data):
    """Send a request to the remote app.py."""
    if space_name not in active_connections:
        return False
    
    sid = active_connections[space_name]['sid']
    pending_results[request_data['request_id']]['status'] = 'processing'
    
    socketio.emit('inference_request', {
        'request_id': request_data['request_id'],
        'user': request_data['user'],
        'data': request_data['data']
    }, room=sid)
    
    return True


def _process_next_in_queue(space_name):
    """Process the next request in queue after one completes."""
    if space_name not in request_queues:
        return
    
    queue = request_queues[space_name]
    if len(queue) > 0:
        next_request = queue[0]
        _send_to_remote(space_name, next_request)
        
        # Update queue positions for all waiting users
        for i, req in enumerate(queue):
            if req['request_id'] in pending_results:
                pending_results[req['request_id']]['queue_position'] = i + 1


def register_handlers(sio):
    """Register all WebSocket event handlers."""
    
    @sio.on('connect')
    def handle_connect():
        """Handle new WebSocket connections."""
        print(f"[WS] New connection: {request.sid}")
    
    @sio.on('disconnect')
    def handle_disconnect():
        """Handle WebSocket disconnections."""
        sid = request.sid
        print(f"[WS] Disconnected: {sid}")
        
        # Check if this was a remote app.py connection
        for space_name, conn_info in list(active_connections.items()):
            if conn_info['sid'] == sid:
                del active_connections[space_name]
                print(f"[WS] Remote disconnected from space: {space_name}")
                
                # Mark all pending requests for this space as failed
                if space_name in request_queues:
                    for req in request_queues[space_name]:
                        if req['request_id'] in pending_results:
                            pending_results[req['request_id']]['status'] = 'failed'
                            pending_results[req['request_id']]['result'] = '远程服务器断开连接'
                    request_queues[space_name].clear()
                break
        
        # Check if this was a user connection
        for username, sids in list(user_sockets.items()):
            if sid in sids:
                sids.remove(sid)
                if not sids:
                    del user_sockets[username]
                break
    
    @sio.on('register_remote')
    def handle_register_remote(data):
        """
        Handle remote app.py registration.
        Expected data: {"space_name": "my-space"}
        """
        sid = request.sid
        space_name = data.get('space_name', '').strip()
        
        if not space_name:
            emit('register_result', {'success': False, 'error': 'Space名称不能为空'})
            disconnect()
            return
        
        # Check if space name is already connected
        if space_name in active_connections:
            emit('register_result', {
                'success': False, 
                'error': f'Space "{space_name}" 已有连接，请使用不同的名称或等待现有连接断开'
            })
            disconnect()
            return
        
        # Verify space exists in database
        db = load_db()
        space_found = False
        spaces = db.get('spaces', {})
        for space_id in list(spaces.keys()):
            space = spaces[space_id]
            if space.get('name') == space_name and space.get('card_type') == 'websocket':
                space_found = True
                break
        
        if not space_found:
            emit('register_result', {
                'success': False,
                'error': f'未找到名为 "{space_name}" 的 WebSocket 类型 Space'
            })
            disconnect()
            return
        
        # Register the connection
        active_connections[space_name] = {
            'sid': sid,
            'connected_at': datetime.utcnow().isoformat()
        }
        
        # Initialize queue
        if space_name not in request_queues:
            request_queues[space_name] = deque()
        
        join_room(f'space_{space_name}')
        
        emit('register_result', {
            'success': True,
            'message': f'成功连接到 Space "{space_name}"',
            'space_name': space_name
        })
        
        print(f"[WS] Remote registered for space: {space_name}")
    
    @sio.on('register_user')
    def handle_register_user(data):
        """
        Handle user registration for receiving results.
        Expected data: {"username": "user123"}
        """
        sid = request.sid
        username = data.get('username', '').strip()
        
        if not username:
            emit('user_register_result', {'success': False, 'error': '用户名不能为空'})
            return
        
        if username not in user_sockets:
            user_sockets[username] = []
        
        if sid not in user_sockets[username]:
            user_sockets[username].append(sid)
        
        emit('user_register_result', {'success': True})
    
    @sio.on('inference_result')
    def handle_inference_result(data):
        """
        Handle inference result from remote app.py.
        Expected data: {"request_id": "...", "success": True/False, "result": {...}, "error": "..."}
        """
        request_id = data.get('request_id')
        success = data.get('success', False)
        result = data.get('result')
        error = data.get('error')
        
        if request_id not in pending_results:
            print(f"[WS] Unknown request_id: {request_id}")
            return
        
        pending = pending_results[request_id]
        space_name = pending['space_name']
        username = pending['user']
        
        # Update result status
        pending['status'] = 'completed' if success else 'failed'
        pending['result'] = result if success else error
        
        # Remove from queue
        if space_name in request_queues:
            queue = request_queues[space_name]
            request_queues[space_name] = deque([r for r in queue if r['request_id'] != request_id])
        
        # Notify user via WebSocket if connected
        if username in user_sockets:
            for user_sid in user_sockets[username]:
                sio.emit('inference_complete', {
                    'request_id': request_id,
                    'success': success,
                    'result': result,
                    'error': error
                }, room=user_sid)
        
        # Process next in queue
        _process_next_in_queue(space_name)
        
        print(f"[WS] Result received for request {request_id}: success={success}")


# HTTP Routes for user interactions
@ws_bp.route('/submit/<space_name>', methods=['POST'])
def submit_request(space_name):
    """Submit an inference request via HTTP."""
    from flask import jsonify
    
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': '请先登录'}), 401
    
    username = session.get('username')
    data = request.get_json() or {}
    
    success, result, position = submit_inference_request(space_name, username, data)
    
    if success:
        return jsonify({
            'success': True,
            'request_id': result,
            'queue_position': position
        })
    else:
        return jsonify({'success': False, 'error': result}), 400


@ws_bp.route('/status/<space_name>')
def get_status(space_name):
    """Get the status of a space and optionally a request."""
    from flask import jsonify
    
    request_id = request.args.get('request_id')
    
    response = {
        'online': is_space_online(space_name),
        'queue_length': get_queue_length(space_name)
    }
    
    if request_id:
        pending = get_pending_result(request_id)
        if pending:
            response['request'] = {
                'status': pending['status'],
                'queue_position': pending.get('queue_position', 0),
                'result': pending.get('result')
            }
    
    return jsonify(response)


@ws_bp.route('/result/<request_id>')
def get_result(request_id):
    """Get the result of a specific request."""
    from flask import jsonify
    
    pending = get_pending_result(request_id)
    
    if not pending:
        return jsonify({'success': False, 'error': '请求不存在'}), 404
    
    return jsonify({
        'success': True,
        'status': pending['status'],
        'result': pending.get('result'),
        'queue_position': pending.get('queue_position', 0)
    })
