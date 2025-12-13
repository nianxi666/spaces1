import json
import uuid
import threading
from datetime import datetime
from collections import deque
from flask import current_app

class WebSocketConnection:
    """Represents a single WebSocket connection from a remote app.py"""
    def __init__(self, space_id, space_name, session_id):
        self.connection_id = str(uuid.uuid4())
        self.space_id = space_id
        self.space_name = space_name
        self.session_id = session_id  # Socket.IO session ID
        self.connected_at = datetime.utcnow().isoformat()
        self.request_queue = deque()
        self.is_processing = False
        self.last_heartbeat = datetime.utcnow()

class WebSocketManager:
    """Manages all WebSocket connections from remote apps"""
    
    def __init__(self):
        self.connections = {}  # {space_id: WebSocketConnection}
        self.spaces_config = {}  # {space_id: space_config}
        self.lock = threading.Lock()
        self.request_history = {}  # {request_id: {user, space_id, status, result, created_at}}
    
    def register_connection(self, space_id, space_name, ws):
        """Register a new WebSocket connection"""
        with self.lock:
            # Check if space_name is unique in the system
            existing_space = self.connections.get(space_id)
            if existing_space:
                return False, "Space already has a connected app"
            
            connection = WebSocketConnection(space_id, space_name, ws)
            self.connections[space_id] = connection
            return True, connection.connection_id
    
    def unregister_connection(self, space_id):
        """Unregister a WebSocket connection"""
        with self.lock:
            if space_id in self.connections:
                del self.connections[space_id]
                return True
            return False
    
    def get_connection(self, space_id):
        """Get a connection by space_id"""
        with self.lock:
            return self.connections.get(space_id)
    
    def is_space_connected(self, space_id):
        """Check if a space has an active connection"""
        with self.lock:
            return space_id in self.connections
    
    def queue_inference_request(self, space_id, request_id, username, payload):
        """Queue an inference request for a space"""
        with self.lock:
            connection = self.connections.get(space_id)
            if not connection:
                return False, "Space not connected"
            
            request_data = {
                'request_id': request_id,
                'username': username,
                'payload': payload,
                'created_at': datetime.utcnow().isoformat(),
                'status': 'queued'
            }
            
            connection.request_queue.append(request_data)
            self.request_history[request_id] = request_data
            return True, request_id
    
    def get_next_request(self, space_id):
        """Get the next request in queue for a space"""
        with self.lock:
            connection = self.connections.get(space_id)
            if not connection or not connection.request_queue:
                return None
            
            request_data = connection.request_queue.popleft()
            request_data['status'] = 'processing'
            return request_data
    
    def update_request_status(self, request_id, status, result=None):
        """Update the status of a request"""
        with self.lock:
            if request_id in self.request_history:
                self.request_history[request_id]['status'] = status
                if result:
                    self.request_history[request_id]['result'] = result
                self.request_history[request_id]['updated_at'] = datetime.utcnow().isoformat()
                return True
            return False
    
    def get_request_status(self, request_id):
        """Get the status of a request"""
        with self.lock:
            if request_id in self.request_history:
                return self.request_history[request_id]
            return None
    
    def get_connected_spaces(self):
        """Get list of all connected spaces"""
        with self.lock:
            return list(self.connections.keys())
    
    def get_queue_size(self, space_id):
        """Get the number of requests in queue for a space"""
        with self.lock:
            connection = self.connections.get(space_id)
            if connection:
                return len(connection.request_queue)
            return 0
    
    def get_queue_list(self, space_id):
        """Get list of requests in queue with usernames"""
        with self.lock:
            connection = self.connections.get(space_id)
            if not connection:
                return []
            queue_list = []
            for i, req in enumerate(connection.request_queue):
                queue_list.append({
                    'position': i + 1,
                    'username': req.get('username', 'anonymous'),
                    'request_id': req.get('request_id', '')[:8],
                    'status': req.get('status', 'queued')
                })
            return queue_list

# Global instance
ws_manager = WebSocketManager()
