#!/usr/bin/env python3
"""
Complete WebSocket Test Script

This script:
1. Creates a test WebSocket Space in the database
2. Runs a mock remote inference server
3. Tests the complete upload and receive flow
"""
import sys
import os
import time
import json
import threading
import uuid

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import socketio
except ImportError:
    print("Error: python-socketio is not installed.")
    print("Run: pip install python-socketio[client]")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("Error: requests is not installed.")
    print("Run: pip install requests")
    sys.exit(1)


def create_test_space():
    """Create a WebSocket test space in the database."""
    from project import create_app
    from project.database import load_db, save_db
    
    app = create_app()
    with app.app_context():
        db = load_db()
        
        # Check if already exists
        for sid, space in db.get('spaces', {}).items():
            if space.get('name') == 'ws-test-space':
                print(f"[✓] Test space already exists: {sid}")
                return sid
        
        # Create new test space
        space_id = 'ws-test-' + str(uuid.uuid4())[:8]
        db['spaces'][space_id] = {
            'id': space_id,
            'name': 'ws-test-space',
            'description': 'WebSocket Test Space for testing',
            'cover': 'default.png',
            'cover_type': 'image',
            'card_type': 'websocket',
            'ws_enable_prompt': True,
            'ws_enable_audio': True,
            'ws_enable_video': True,
            'ws_max_queue_size': 10,
            'templates': {}
        }
        save_db(db)
        print(f"[✓] Created test space: {space_id}")
        return space_id


class MockRemoteServer:
    """Mock remote inference server that connects via WebSocket."""
    
    def __init__(self, host, space_name):
        self.host = host
        self.space_name = space_name
        self.sio = socketio.Client(reconnection=False)
        self.connected = False
        self.registered = False
        self.received_requests = []
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        @self.sio.event
        def connect():
            self.connected = True
            print(f"[Mock Server] Connected to {self.host}")
            self.sio.emit('register_remote', {'space_name': self.space_name})
        
        @self.sio.event
        def disconnect():
            self.connected = False
            self.registered = False
            print(f"[Mock Server] Disconnected")
        
        @self.sio.on('register_result')
        def on_register_result(data):
            if data.get('success'):
                self.registered = True
                print(f"[Mock Server] ✓ Registered for space: {self.space_name}")
            else:
                print(f"[Mock Server] ✗ Registration failed: {data.get('error')}")
        
        @self.sio.on('inference_request')
        def on_inference_request(data):
            request_id = data.get('request_id')
            user = data.get('user')
            request_data = data.get('data', {})
            
            print(f"\n[Mock Server] ═══════════════════════════════════════")
            print(f"[Mock Server] 收到推理请求!")
            print(f"[Mock Server] Request ID: {request_id}")
            print(f"[Mock Server] User: {user}")
            print(f"[Mock Server] Data: {json.dumps(request_data, ensure_ascii=False, indent=2)[:300]}")
            
            self.received_requests.append({
                'request_id': request_id,
                'user': user,
                'data': request_data,
                'time': time.time()
            })
            
            # Simulate processing
            print(f"[Mock Server] Processing...")
            time.sleep(1)
            
            # Send result back
            result = {
                'type': 'test_result',
                'message': f'成功处理请求! Prompt: {request_data.get("prompt", "N/A")[:50]}',
                'processed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'has_audio': 'audio' in request_data,
                'has_video': 'video' in request_data
            }
            
            self.sio.emit('inference_result', {
                'request_id': request_id,
                'success': True,
                'result': result
            })
            
            print(f"[Mock Server] ✓ 结果已发送!")
            print(f"[Mock Server] ═══════════════════════════════════════\n")
    
    def start(self):
        """Start the mock server (connect to main server)."""
        try:
            print(f"[Mock Server] Connecting to {self.host}...")
            self.sio.connect(self.host, transports=['websocket', 'polling'])
            return True
        except Exception as e:
            print(f"[Mock Server] Connection failed: {e}")
            return False
    
    def wait(self):
        """Wait for connection events."""
        self.sio.wait()
    
    def stop(self):
        """Stop the mock server."""
        if self.sio.connected:
            self.sio.disconnect()


def test_user_submission(host, space_name, session_cookie=None):
    """Test submitting a request as a user."""
    print("\n[User Test] ═══════════════════════════════════════")
    print("[User Test] 模拟用户提交推理请求...")
    
    # First check status
    status_url = f"{host}/ws/status/{space_name}"
    try:
        resp = requests.get(status_url)
        status = resp.json()
        print(f"[User Test] Space 状态: online={status.get('online')}, queue={status.get('queue_length')}")
        
        if not status.get('online'):
            print("[User Test] ✗ 远程服务器不在线，无法测试提交")
            return False
    except Exception as e:
        print(f"[User Test] ✗ 获取状态失败: {e}")
        return False
    
    # Submit request
    submit_url = f"{host}/ws/submit/{space_name}"
    test_data = {
        'prompt': '这是一个测试提示词 - Test prompt at ' + time.strftime('%H:%M:%S'),
    }
    
    cookies = {'session': session_cookie} if session_cookie else {}
    
    try:
        resp = requests.post(submit_url, json=test_data, cookies=cookies)
        result = resp.json()
        
        if result.get('success'):
            request_id = result.get('request_id')
            position = result.get('queue_position')
            print(f"[User Test] ✓ 请求已提交!")
            print(f"[User Test]   Request ID: {request_id}")
            print(f"[User Test]   Queue Position: {position}")
            
            # Poll for result
            print("[User Test] 等待结果...")
            for i in range(10):
                time.sleep(1)
                result_url = f"{host}/ws/result/{request_id}"
                resp = requests.get(result_url)
                result_data = resp.json()
                
                if result_data.get('status') == 'completed':
                    print(f"[User Test] ✓ 收到结果!")
                    print(f"[User Test]   Result: {json.dumps(result_data.get('result'), ensure_ascii=False, indent=2)}")
                    print("[User Test] ═══════════════════════════════════════\n")
                    return True
                elif result_data.get('status') == 'failed':
                    print(f"[User Test] ✗ 处理失败: {result_data.get('result')}")
                    return False
                else:
                    print(f"[User Test]   状态: {result_data.get('status')}, 位置: {result_data.get('queue_position')}")
            
            print("[User Test] ✗ 超时，未收到结果")
            return False
        else:
            print(f"[User Test] ✗ 提交失败: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"[User Test] ✗ 请求失败: {e}")
        return False


def main():
    HOST = "http://localhost:5001"
    SPACE_NAME = "ws-test-space"
    
    print("\n" + "="*60)
    print("  WebSocket 完整测试")
    print("="*60 + "\n")
    
    # Step 1: Create test space
    print("[Step 1] 创建测试 Space...")
    try:
        space_id = create_test_space()
    except Exception as e:
        print(f"[Step 1] ✗ 创建失败: {e}")
        print("[Info] 请确保主服务器正在运行")
        return
    
    # Step 2: Start mock remote server
    print("\n[Step 2] 启动模拟远程服务器...")
    mock_server = MockRemoteServer(HOST, SPACE_NAME)
    
    if not mock_server.start():
        print("[Step 2] ✗ 无法连接到主服务器")
        return
    
    # Wait for registration
    time.sleep(2)
    
    if not mock_server.registered:
        print("[Step 2] ✗ 注册失败")
        mock_server.stop()
        return
    
    # Step 3: Test user submission (without session - will fail with 401)
    print("\n[Step 3] 测试用户提交 (未登录，预期返回401)...")
    
    # This will fail because we're not logged in
    # But it tests the endpoint is working
    submit_url = f"{HOST}/ws/submit/{SPACE_NAME}"
    try:
        resp = requests.post(submit_url, json={'prompt': 'test'})
        if resp.status_code == 401:
            print("[Step 3] ✓ 正确返回 401 未授权")
        else:
            print(f"[Step 3] 响应: {resp.status_code} - {resp.text[:100]}")
    except Exception as e:
        print(f"[Step 3] ✗ 请求失败: {e}")
    
    # Step 4: Check WebSocket status
    print("\n[Step 4] 检查 WebSocket 状态...")
    try:
        resp = requests.get(f"{HOST}/ws/status/{SPACE_NAME}")
        status = resp.json()
        print(f"[Step 4] ✓ 状态: {json.dumps(status, indent=2)}")
        
        if status.get('online'):
            print("[Step 4] ✓ 远程服务器显示在线!")
        else:
            print("[Step 4] ✗ 远程服务器显示离线")
    except Exception as e:
        print(f"[Step 4] ✗ 获取状态失败: {e}")
    
    # Keep running to receive requests
    print("\n" + "="*60)
    print("  模拟远程服务器正在运行")
    print("  - 访问 http://localhost:5001/ai_project/[space_id] 测试")
    print("  - 或使用浏览器登录后提交请求")
    print("  按 Ctrl+C 停止")
    print("="*60 + "\n")
    
    try:
        mock_server.wait()
    except KeyboardInterrupt:
        print("\n[Info] 收到中断信号，停止服务器...")
    finally:
        mock_server.stop()
        print("[Info] 测试完成!")


if __name__ == '__main__':
    main()
