# -*- coding: utf-8 -*-
"""
WebSocket Upload Test Script

This script tests the WebSocket upload functionality by:
1. Starting a mock WebSocket server
2. Simulating file uploads from the client
3. Verifying the upload process

Run: python test_ws_upload.py
"""

import os
import sys
import json
import base64
import time
import threading
import uuid
from datetime import datetime

# Mock WebSocket server for testing
try:
    from flask import Flask
    from flask_socketio import SocketIO, emit
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    print("Flask-SocketIO not available. Install with: pip install flask-socketio")

# WebSocket client for testing
try:
    import websocket
    WEBSOCKET_CLIENT_AVAILABLE = True
except ImportError:
    WEBSOCKET_CLIENT_AVAILABLE = False
    print("websocket-client not available. Install with: pip install websocket-client")


# ===== Mock WebSocket Server =====

def create_mock_ws_server():
    """Create a mock WebSocket server for testing"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret-key'
    socketio = SocketIO(app, cors_allowed_origins="*")
    
    # Store uploads in memory for testing
    uploads = {}
    output_dir = os.path.join(os.path.dirname(__file__), 'ws_test_output')
    os.makedirs(output_dir, exist_ok=True)
    
    @socketio.on('connect', namespace='/ws/upload')
    def handle_connect():
        print(f"[Server] Client connected")
        emit('connected', {'message': 'Connected successfully'})
    
    @socketio.on('disconnect', namespace='/ws/upload')
    def handle_disconnect():
        print(f"[Server] Client disconnected")
    
    @socketio.on('start_upload', namespace='/ws/upload')
    def handle_start_upload(data):
        upload_id = str(uuid.uuid4())
        filename = data.get('filename', 'unknown')
        file_size = data.get('file_size', 0)
        
        temp_path = os.path.join(output_dir, f"{upload_id}_{filename}")
        
        uploads[upload_id] = {
            'filename': filename,
            'file_size': file_size,
            'temp_path': temp_path,
            'received_bytes': 0,
            'file_handle': open(temp_path, 'wb')
        }
        
        print(f"[Server] Started upload {upload_id}: {filename} ({file_size} bytes)")
        emit('ready', {'status': 'ready', 'upload_id': upload_id})
    
    @socketio.on('upload_chunk', namespace='/ws/upload')
    def handle_upload_chunk(data):
        upload_id = data.get('upload_id')
        chunk_data_b64 = data.get('data', '')
        chunk_index = data.get('chunk_index', 0)
        
        if upload_id not in uploads:
            emit('error', {'status': 'error', 'error': 'Invalid upload ID'})
            return
        
        upload_info = uploads[upload_id]
        
        try:
            chunk_data = base64.b64decode(chunk_data_b64)
            upload_info['file_handle'].write(chunk_data)
            upload_info['received_bytes'] += len(chunk_data)
            
            progress = 0
            if upload_info['file_size'] > 0:
                progress = int((upload_info['received_bytes'] / upload_info['file_size']) * 100)
            
            emit('chunk_ack', {
                'status': 'ok',
                'chunk_index': chunk_index,
                'received_bytes': upload_info['received_bytes'],
                'progress': progress
            })
        except Exception as e:
            emit('error', {'status': 'error', 'error': str(e)})
    
    @socketio.on('complete_upload', namespace='/ws/upload')
    def handle_complete_upload(data):
        upload_id = data.get('upload_id')
        
        if upload_id not in uploads:
            emit('error', {'status': 'error', 'error': 'Invalid upload ID'})
            return
        
        upload_info = uploads[upload_id]
        
        try:
            upload_info['file_handle'].close()
            
            # Simulate S3 upload (just keep the file locally for testing)
            final_path = upload_info['temp_path']
            public_url = f"http://localhost:5003/files/{os.path.basename(final_path)}"
            
            print(f"[Server] Upload complete: {final_path}")
            print(f"[Server] File size: {upload_info['received_bytes']} bytes")
            
            emit('upload_complete', {
                'status': 'success',
                'public_url': public_url,
                's3_object_name': f"test_user/{upload_info['filename']}"
            })
            
            del uploads[upload_id]
            
        except Exception as e:
            emit('error', {'status': 'error', 'error': str(e)})
    
    return app, socketio


# ===== WebSocket Client Test =====

class WebSocketUploadTestClient:
    """Test client for WebSocket uploads"""
    
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = None
        self.connected = False
        self.responses = []
        
    def connect(self):
        """Connect to the WebSocket server"""
        import socketio as sio_client
        self.sio = sio_client.Client()
        
        @self.sio.on('connected', namespace='/ws/upload')
        def on_connected(data):
            print(f"[Client] Connected: {data}")
            self.connected = True
        
        @self.sio.on('ready', namespace='/ws/upload')
        def on_ready(data):
            print(f"[Client] Server ready: {data}")
            self.responses.append(('ready', data))
        
        @self.sio.on('chunk_ack', namespace='/ws/upload')
        def on_chunk_ack(data):
            progress = data.get('progress', 0)
            print(f"[Client] Chunk acknowledged: {progress}%", end='\r')
            self.responses.append(('chunk_ack', data))
        
        @self.sio.on('upload_complete', namespace='/ws/upload')
        def on_complete(data):
            print(f"\n[Client] Upload complete: {data}")
            self.responses.append(('complete', data))
        
        @self.sio.on('error', namespace='/ws/upload')
        def on_error(data):
            print(f"[Client] Error: {data}")
            self.responses.append(('error', data))
        
        try:
            self.sio.connect(self.ws_url, namespaces=['/ws/upload'])
            time.sleep(1)  # Wait for connection
            return self.connected
        except Exception as e:
            print(f"[Client] Connection failed: {e}")
            return False
    
    def upload_file(self, file_path):
        """Upload a file via WebSocket"""
        if not self.connected:
            print("[Client] Not connected")
            return False
        
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        print(f"[Client] Uploading {filename} ({file_size} bytes)")
        
        # Start upload
        self.sio.emit('start_upload', {
            'filename': filename,
            'file_size': file_size,
            'content_type': 'application/octet-stream'
        }, namespace='/ws/upload')
        
        time.sleep(0.5)  # Wait for ready response
        
        # Find upload_id from responses
        upload_id = None
        for resp_type, resp_data in self.responses:
            if resp_type == 'ready':
                upload_id = resp_data.get('upload_id')
                break
        
        if not upload_id:
            print("[Client] Did not receive upload_id")
            return False
        
        # Send file in chunks
        chunk_size = 64 * 1024  # 64KB
        chunk_index = 0
        
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                
                chunk_b64 = base64.b64encode(chunk).decode('utf-8')
                
                self.sio.emit('upload_chunk', {
                    'upload_id': upload_id,
                    'chunk_index': chunk_index,
                    'data': chunk_b64,
                    'is_last': len(chunk) < chunk_size
                }, namespace='/ws/upload')
                
                chunk_index += 1
                time.sleep(0.05)  # Small delay between chunks
        
        time.sleep(0.5)  # Wait for last ack
        
        # Complete upload
        self.sio.emit('complete_upload', {'upload_id': upload_id}, namespace='/ws/upload')
        
        time.sleep(1)  # Wait for completion
        
        # Check result
        for resp_type, resp_data in self.responses:
            if resp_type == 'complete':
                print(f"[Client] Success! URL: {resp_data.get('public_url')}")
                return True
            elif resp_type == 'error':
                print(f"[Client] Failed: {resp_data.get('error')}")
                return False
        
        return False
    
    def disconnect(self):
        """Disconnect from the server"""
        if self.sio:
            self.sio.disconnect()


def run_server():
    """Run the test server"""
    if not FLASK_AVAILABLE:
        print("Cannot run server: Flask-SocketIO not installed")
        return
    
    app, socketio = create_mock_ws_server()
    print("[Server] Starting on http://localhost:5003")
    socketio.run(app, host='0.0.0.0', port=5003, debug=False, use_reloader=False)


def run_tests():
    """Run the upload tests"""
    print("\n" + "=" * 50)
    print(" WebSocket Upload Test")
    print("=" * 50)
    
    # Create a test file
    test_file = os.path.join(os.path.dirname(__file__), 'ws_test_file.bin')
    test_size = 256 * 1024  # 256 KB
    
    print(f"\nCreating test file ({test_size} bytes)...")
    with open(test_file, 'wb') as f:
        f.write(os.urandom(test_size))
    print(f"Test file created: {test_file}")
    
    # Wait for server to start
    print("\nWaiting for server to start...")
    time.sleep(2)
    
    # Try to connect and upload
    try:
        import socketio as sio_client
        
        client = WebSocketUploadTestClient('http://localhost:5003')
        
        if client.connect():
            print("\n[Test] Connected to server")
            
            # Upload test file
            success = client.upload_file(test_file)
            
            if success:
                print("\n[PASS] Upload test passed!")
            else:
                print("\n[FAIL] Upload test failed")
            
            client.disconnect()
        else:
            print("\n[FAIL] Could not connect to server")
    
    except ImportError:
        print("\n[SKIP] python-socketio not installed for client test")
        print("       Install with: pip install python-socketio")
    except Exception as e:
        print(f"\n[ERROR] Test error: {e}")
    
    finally:
        # Cleanup test file
        if os.path.exists(test_file):
            os.remove(test_file)
    
    print("\n" + "=" * 50)


def main():
    print("\nWebSocket Upload Test Suite")
    print("=" * 50)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    if not FLASK_AVAILABLE:
        print("[ERROR] Flask-SocketIO not installed")
        print("        Run: pip install flask-socketio")
        return
    
    # Start server in background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Run tests
    run_tests()
    
    print("\nDone!")


if __name__ == '__main__':
    main()
