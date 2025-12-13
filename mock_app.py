#!/usr/bin/env python3
"""
Mock Inference App - Simulates a remote computing application
Connects to the website via WebSocket and processes inference requests

Usage:
    python mock_app.py --host http://localhost:5001 --spaces "TestSpace"
    python mock_app.py --host https://example.com --spaces "MySpace" --port 8080

Features:
    - Connects to website via Socket.IO
    - Registers with a specific space
    - Receives inference requests
    - Simulates inference processing
    - Sends results back to website
    - Handles multiple concurrent requests in a queue
    - Graceful shutdown with Ctrl+C
"""

import argparse
import json
import time
import sys
import uuid
import random
import threading
from datetime import datetime
from collections import deque

try:
    import socketio
except ImportError:
    print("ERROR: python-socketio is required")
    print("Install with: pip install python-socketio python-engineio")
    sys.exit(1)


class MockInferenceApp:
    """Mock remote inference app that connects via Socket.IO"""

    def __init__(self, host, space_name, verbose=False):
        self.host = host.rstrip('/')
        self.space_name = space_name
        self.verbose = verbose
        self.connection_id = None
        self.space_id = None
        self.sio = None
        self.running = False
        self.request_queue = deque()
        self.lock = threading.Lock()
        self.processed_count = 0
        self.error_count = 0

    def log(self, level, message):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        prefix = f"[{timestamp}]"
        
        if level == "INFO":
            print(f"{prefix} [INFO] {message}")
        elif level == "SUCCESS":
            print(f"\033[92m{prefix} [✓] {message}\033[0m")
        elif level == "ERROR":
            print(f"\033[91m{prefix} [✗] {message}\033[0m")
        elif level == "REQUEST":
            print(f"\033[94m{prefix} [REQUEST] {message}\033[0m")
        elif level == "RESULT":
            print(f"\033[93m{prefix} [RESULT] {message}\033[0m")
        elif level == "DEBUG":
            if self.verbose:
                print(f"{prefix} [DEBUG] {message}")

    def connect(self):
        """Connect to the website via Socket.IO"""
        self.log("INFO", f"Initializing connection to {self.host}")
        self.log("INFO", f"Space name: {self.space_name}")

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

        @self.sio.on('*')
        def catch_all(event, *args):
            self.log("DEBUG", f"Received event: {event}, args: {args}")

        try:
            self.log("INFO", f"Connecting to {self.host}...")
            self.sio.connect(self.host, transports=['websocket', 'polling'])
            
            # Start request processing thread
            processor_thread = threading.Thread(target=self.process_requests, daemon=True)
            processor_thread.start()
            self.log("INFO", "Request processor started")
            
            # Keep the connection alive
            self.sio.wait()
        except Exception as e:
            self.log("ERROR", f"Connection failed: {e}")
            sys.exit(1)

    def on_connect(self):
        """Called when Socket.IO connection is established"""
        self.log("SUCCESS", "Socket.IO connection established")
        
        # Send registration message
        registration_data = {'space_name': self.space_name}
        self.sio.emit('register', registration_data)
        self.log("INFO", f"Sent registration for space: {self.space_name}")
        self.running = True

    def on_register_response(self, data):
        """Called when registration response is received"""
        if data.get('success'):
            self.connection_id = data.get('connection_id')
            self.space_id = data.get('space_id')
            self.log("SUCCESS", "Registration successful!")
            self.log("INFO", f"Connection ID: {self.connection_id}")
            self.log("INFO", f"Space ID: {self.space_id}")
            self.log("INFO", data.get('message', ''))
        else:
            self.log("ERROR", f"Registration failed: {data.get('message')}")
            self.running = False
            self.sio.disconnect()

    def on_inference_request(self, data):
        """Called when an inference request is received"""
        request_id = data.get('request_id')
        username = data.get('username')
        prompt = data.get('payload', {}).get('prompt', 'N/A')
        
        self.log("REQUEST", f"New inference request received")
        self.log("DEBUG", f"  Request ID: {request_id}")
        self.log("DEBUG", f"  Username: {username}")
        self.log("DEBUG", f"  Prompt: {prompt[:100] if prompt != 'N/A' else 'N/A'}")

        with self.lock:
            self.request_queue.append(data)
        
        self.log("DEBUG", f"  Queue size: {len(self.request_queue)}")

    def on_disconnect(self):
        """Called when the connection is closed"""
        self.log("INFO", "Socket.IO connection disconnected")
        self.running = False

    def process_requests(self):
        """Process inference requests from the queue"""
        self.log("INFO", "Request processor started")

        while True:
            if not self.request_queue:
                time.sleep(0.5)
                continue

            with self.lock:
                if not self.request_queue:
                    continue
                request_data = self.request_queue.popleft()

            try:
                result = self.simulate_inference(request_data)
                self.send_result(result)
                self.processed_count += 1
            except Exception as e:
                self.log("ERROR", f"Failed to process request: {e}")
                self.send_error(request_data.get("request_id"), str(e))
                self.error_count += 1

    def simulate_inference(self, request_data):
        """Simulate inference processing"""
        request_id = request_data.get('request_id')
        username = request_data.get('username')
        prompt = request_data.get('payload', {}).get('prompt', '')

        self.log("INFO", f"Starting inference for request {request_id[:8]}...")

        # Simulate processing time between 1-5 seconds
        processing_time = random.uniform(1, 5)
        steps = int(processing_time * 2)
        
        for i in range(steps):
            time.sleep(0.5)
            progress = int((i + 1) / steps * 100)
            if progress % 25 == 0:
                self.log("DEBUG", f"  Progress: {progress}%")

        # Generate mock result
        models = ['gpt-4-turbo', 'claude-3-opus', 'llama-2-70b', 'mistral-7b']
        result = {
            'request_id': request_id,
            'status': 'completed',
            'result': {
                'text_output': f"[{models[random.randint(0, 3)]}] Generated response for prompt: '{prompt[:50]}{'...' if len(prompt) > 50 else ''}'\n\nThis is a simulated inference result.",
                'confidence': round(random.uniform(0.8, 1.0), 3),
                'model_used': models[random.randint(0, 3)],
                'processing_time_seconds': round(processing_time, 2),
                'tokens_used': random.randint(50, 500),
                'timestamp': datetime.utcnow().isoformat(),
            }
        }

        self.log("SUCCESS", f"Inference completed for request {request_id[:8]} in {processing_time:.1f}s")
        return result

    def send_result(self, result):
        """Send inference result back to the server"""
        if self.sio and self.running:
            try:
                self.sio.emit('inference_result', result)
                request_id = result.get('request_id')
                self.log("RESULT", f"Result sent for request {request_id[:8]}")
            except Exception as e:
                self.log("ERROR", f"Failed to send result: {e}")

    def send_error(self, request_id, error_message):
        """Send error message back to the server"""
        if self.sio and self.running:
            try:
                error_response = {
                    'request_id': request_id,
                    'status': 'failed',
                    'result': {
                        'error': error_message,
                    }
                }
                self.sio.emit('inference_result', error_response)
                self.log("ERROR", f"Error sent for request {request_id[:8]}: {error_message}")
            except Exception as e:
                self.log("ERROR", f"Failed to send error response: {e}")

    def shutdown(self):
        """Gracefully shutdown the app"""
        self.log("INFO", "Shutting down...")
        self.log("INFO", f"Statistics: {self.processed_count} processed, {self.error_count} errors")
        self.running = False
        if self.sio:
            self.sio.disconnect()
        self.log("SUCCESS", "Goodbye!")


def main():
    parser = argparse.ArgumentParser(
        description="Mock WebSocket Inference App - Simulates remote inference processing"
    )
    parser.add_argument(
        "--host",
        required=True,
        help="Website domain/URL (e.g., http://localhost:5001 or https://example.com)",
    )
    parser.add_argument(
        "--spaces",
        required=True,
        help="Space name to connect to (must match exactly)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging",
    )

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("  Mock WebSocket Inference App")
    print("=" * 70)
    print(f"  Host: {args.host}")
    print(f"  Space: {args.spaces}")
    print(f"  Verbose: {args.verbose}")
    print("=" * 70)
    print()

    app = MockInferenceApp(args.host, args.spaces, args.verbose)

    try:
        app.connect()
    except KeyboardInterrupt:
        print("\n")
        app.shutdown()
    except Exception as e:
        app.log("ERROR", f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
