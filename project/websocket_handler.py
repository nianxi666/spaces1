"""
WebSocket handler for remote app connections
Handles connection registration, message routing, and request processing
"""

import json
import logging
from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from .websocket_manager import ws_manager
from .database import load_db

socketio = None


def init_websocket(app):
    """Initialize WebSocket support for the Flask app"""
    global socketio
    print("[WS INIT] === Initializing WebSocket support ===")
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
    print(f"[WS INIT] SocketIO created with eventlet mode: {socketio}")
    
    # Store mapping of session IDs to space IDs
    app.ws_connections = {}
    
    @socketio.on('connect')
    def handle_connect():
        print(f"[WS] === CLIENT CONNECTED: sid={request.sid} ===")
    
    @socketio.on('register')
    def handle_register(data):
        """Handle registration of a remote app"""
        try:
            space_name = data.get('space_name')
            print(f"[WS] === REGISTER REQUEST: space_name='{space_name}' ===")
            
            if not space_name:
                emit('register_response', {
                    'success': False,
                    'message': 'space_name is required'
                })
                return
            
            # Find space by name in database
            db = load_db()
            space_id = None
            space_count = 0
            
            # Debug logging with print for visibility
            all_spaces = db.get('spaces', {})
            print(f"[WS] Total spaces in DB: {len(all_spaces)}")
            for sid, space in all_spaces.items():
                print(f"[WS]   - name='{space.get('name')}' type='{space.get('card_type')}'")
            
            for sid, space in db.get('spaces', {}).items():
                if space.get('name') == space_name and space.get('card_type') == 'websockets':
                    space_id = sid
                    space_count += 1
                    print(f"[WS] MATCH FOUND: space_id={sid}")
        except Exception as e:
            print(f"[WS] ERROR in handle_register: {e}")
            import traceback
            traceback.print_exc()
            emit('register_response', {'success': False, 'message': f'Server error: {e}'})
            return
        
        if space_count > 1:
            emit('register_response', {
                'success': False,
                'message': f'Multiple spaces with name "{space_name}" found. Please use unique space names.'
            })
            disconnect()
            return
        
        if not space_id:
            emit('register_response', {
                'success': False,
                'message': f'Space "{space_name}" not found or is not a WebSocket space'
            })
            disconnect()
            return
        
        # Register the connection
        success, connection_id = ws_manager.register_connection(space_id, space_name, request.sid)
        
        if success:
            app.ws_connections[request.sid] = space_id
            join_room(f'space_{space_id}')
            emit('register_response', {
                'success': True,
                'connection_id': connection_id,
                'space_id': space_id,
                'message': f'Successfully connected to space "{space_name}"'
            })
            logging.info(f"Remote app connected to space: {space_name} (ID: {space_id})")
        else:
            emit('register_response', {
                'success': False,
                'message': connection_id  # Error message from ws_manager
            })
            disconnect()
    
    @socketio.on('inference_result')
    def handle_inference_result(data):
        """Handle inference result from remote app"""
        request_id = data.get('request_id')
        status = data.get('status')
        result = data.get('result')
        
        if request_id:
            ws_manager.update_request_status(request_id, status, result)
            logging.info(f"Inference result received for request: {request_id}")
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle disconnection of remote app"""
        sid = request.sid
        if sid in app.ws_connections:
            space_id = app.ws_connections[sid]
            ws_manager.unregister_connection(space_id)
            leave_room(f'space_{space_id}')
            del app.ws_connections[sid]
            logging.info(f"Remote app disconnected from space: {space_id}")

    return socketio


def send_inference_request(space_id, request_data):
    """Send an inference request to a connected remote app via WebSocket"""
    if socketio:
        socketio.emit(
            'inference_request',
            request_data,
            room=f'space_{space_id}'
        )
