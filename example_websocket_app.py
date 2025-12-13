#!/usr/bin/env python3
"""
示例 WebSocket App - 模拟远程计算机上的推理app.py
这是一个演示性的脚本，展示如何连接到website并处理推理请求

使用方式:
    python example_websocket_app.py --host https://example.com --spaces "MySpace"

要求:
    pip install python-socketio python-engineio requests
"""

import argparse
import json
import time
import sys
import uuid
import random
import threading
from datetime import datetime

try:
    import socketio
    import requests
except ImportError:
    print("Error: Required packages not found.")
    print("Please install: pip install python-socketio python-engineio requests")
    sys.exit(1)


class WebSocketApp:
    """Remote inference app that connects via WebSocket"""

    def __init__(self, host, space_name):
        self.host = host.rstrip('/')
        self.space_name = space_name
        self.connection_id = None
        self.sio = None
        self.running = False
        self.request_queue = []
        self.lock = threading.Lock()

    def connect(self):
        """Connect to the website via WebSocket"""
        print(f"[INFO] Initializing connection...")
        print(f"[INFO] Host: {self.host}")
        print(f"[INFO] Space name: {self.space_name}")

        # Create Socket.IO client
        self.sio = socketio.Client(
            reconnection=True,
            reconnection_delay=1,
            reconnection_delay_max=5,
            reconnection_attempts=5
        )

        @self.sio.event
        def connect():
            self.on_connect()

        @self.sio.event
        def register_response(data):
            self.on_register_response(data)

        @self.sio.event
        def inference_request(data):
            self.on_inference_request(data)

        @self.sio.event
        def disconnect():
            self.on_disconnect()

        try:
            print(f"[INFO] Connecting to {self.host}...")
            self.sio.connect(self.host)
            
            # Start request processing thread
            threading.Thread(target=self.process_requests, daemon=True).start()
            
            # Keep the connection alive
            self.sio.wait()
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
            sys.exit(1)

    def on_connect(self):
        """Called when Socket.IO connection is established"""
        print("[SUCCESS] Socket.IO connection established")
        
        # Send registration message
        self.sio.emit('register', {
            'space_name': self.space_name
        })
        print(f"[INFO] Sent registration for space: {self.space_name}")
        self.running = True

    def on_register_response(self, data):
        """Called when registration response is received"""
        if data.get('success'):
            self.connection_id = data.get('connection_id')
            print(f"[SUCCESS] Registration successful!")
            print(f"[INFO] Connection ID: {self.connection_id}")
            print(f"[INFO] Space ID: {data.get('space_id')}")
            print(f"[INFO] {data.get('message')}")
        else:
            print(f"[ERROR] Registration failed: {data.get('message')}")
            self.running = False
            self.sio.disconnect()

    def on_inference_request(self, data):
        """Called when an inference request is received"""
        print(f"\n[REQUEST] New inference request received")
        print(f"  Request ID: {data.get('request_id')}")
        print(f"  Username: {data.get('username')}")
        print(f"  Prompt: {data.get('payload', {}).get('prompt', 'N/A')}")

        with self.lock:
            self.request_queue.append(data)

    def on_disconnect(self):
        """Called when the connection is closed"""
        print("[INFO] Socket.IO connection disconnected")
        self.running = False

    def process_requests(self):
        """Process inference requests from the queue"""
        print("[INFO] Request processor started")

        while self.running:
            if not self.request_queue:
                time.sleep(0.5)
                continue

            with self.lock:
                if not self.request_queue:
                    continue
                request_data = self.request_queue.pop(0)

            try:
                result = self.simulate_inference(request_data)
                self.send_result(result)
            except Exception as e:
                print(f"[ERROR] Failed to process request: {e}")
                self.send_error(request_data.get("request_id"), str(e))

    def simulate_inference(self, request_data):
        """Simulate inference processing"""
        request_id = request_data.get("request_id")
        username = request_data.get("username")
        prompt = request_data.get("payload", {}).get("prompt", "")

        print(f"\n[PROCESSING] Starting inference...")
        print(f"  Request ID: {request_id}")

        # Simulate processing time
        processing_time = random.uniform(2, 5)
        print(f"  Processing time: {processing_time:.1f}s")

        for i in range(int(processing_time * 2)):
            time.sleep(0.5)
            print(f"  Progress: {int((i + 1) / (processing_time * 2) * 100)}%")

        # Generate mock result
        result = {
            "type": "inference_result",
            "request_id": request_id,
            "username": username,
            "status": "completed",
            "result": {
                "text_output": f"Inference result for prompt: '{prompt[:50]}...'",
                "confidence": round(random.uniform(0.8, 1.0), 3),
                "processing_time": processing_time,
                "timestamp": datetime.utcnow().isoformat(),
                "model_version": "1.0",
            },
        }

        print(f"[SUCCESS] Inference completed!")
        return result

    def send_result(self, result):
        """Send inference result back to the server"""
        if self.sio and self.running:
            try:
                self.sio.emit('inference_result', result)
                print(f"[SENT] Result sent for request: {result.get('request_id')}")
            except Exception as e:
                print(f"[ERROR] Failed to send result: {e}")

    def send_error(self, request_id, error_message):
        """Send error message back to the server"""
        if self.sio and self.running:
            try:
                error_response = {
                    "request_id": request_id,
                    "status": "failed",
                    "result": {
                        "error": error_message,
                    },
                }
                self.sio.emit('inference_result', error_response)
                print(f"[SENT] Error sent for request: {request_id}")
            except Exception as e:
                print(f"[ERROR] Failed to send error response: {e}")

    def shutdown(self):
        """Gracefully shutdown the app"""
        print("\n[INFO] Shutting down...")
        self.running = False
        if self.sio:
            self.sio.disconnect()
        print("[INFO] Goodbye!")


def main():
    parser = argparse.ArgumentParser(
        description="WebSocket Inference App - Connect to a website and handle inference requests"
    )
    parser.add_argument(
        "--host",
        required=True,
        help="Website domain (e.g., https://example.com)",
    )
    parser.add_argument(
        "--spaces",
        required=True,
        help="Space name to connect to",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("WebSocket Inference App")
    print("=" * 60)
    print(f"Host: {args.host}")
    print(f"Space: {args.spaces}")
    print("=" * 60)
    print()

    app = WebSocketApp(args.host, args.spaces)

    try:
        app.connect()
    except KeyboardInterrupt:
        print("\n")
        app.shutdown()
    except Exception as e:
        print(f"[FATAL] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
