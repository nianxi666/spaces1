#!/usr/bin/env python3
"""
Mock Remote App for WebSocket Spaces Testing

This script simulates a remote inference server that connects to the 
website via WebSocket and processes inference requests.

Usage:
    python mock_remote_app.py --host http://localhost:5001 --spaces my-space-name

"""
import argparse
import json
import time
import random
import sys

try:
    import socketio
except ImportError:
    print("Error: python-socketio is not installed.")
    print("Please install it with: pip install python-socketio[client]")
    sys.exit(1)


def create_mock_result(data):
    """Generate a mock inference result based on input data."""
    prompt = data.get('prompt', '')
    has_audio = 'audio' in data
    has_video = 'video' in data
    
    result = {
        'type': 'text',
        'message': f'Successfully processed your request!',
        'details': {
            'prompt_received': prompt[:100] if prompt else None,
            'audio_received': has_audio,
            'video_received': has_video,
            'processing_time_ms': random.randint(100, 2000),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
    }
    
    # Simulate different result types based on input
    if has_audio:
        result['type'] = 'audio_process'
        result['message'] = f'Audio processed successfully! Duration: {random.randint(1, 60)} seconds'
    elif has_video:
        result['type'] = 'video_process'
        result['message'] = f'Video processed successfully! Frames: {random.randint(100, 1000)}'
    elif prompt:
        result['type'] = 'text_generate'
        result['message'] = f'Generated response for: "{prompt[:50]}..."'
        result['generated_text'] = f"This is a mock response to your prompt. Original prompt was: {prompt}"
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description='Mock Remote App for WebSocket Spaces Testing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python mock_remote_app.py --host http://localhost:5001 --spaces test-space
    python mock_remote_app.py --host https://pumpkinai.it.com --spaces my-ai-model
        """
    )
    parser.add_argument(
        '--host', 
        required=True, 
        help='Website host URL (e.g., http://localhost:5001)'
    )
    parser.add_argument(
        '--spaces', 
        required=True, 
        help='Name of the Space to connect to'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=2.0,
        help='Simulated processing delay in seconds (default: 2.0)'
    )
    
    args = parser.parse_args()
    
    host = args.host.rstrip('/')
    space_name = args.spaces
    processing_delay = args.delay
    
    print(f"\n{'='*60}")
    print(f"  Mock Remote App for WebSocket Spaces")
    print(f"{'='*60}")
    print(f"  Host:  {host}")
    print(f"  Space: {space_name}")
    print(f"  Delay: {processing_delay}s")
    print(f"{'='*60}\n")
    
    # Create Socket.IO client
    sio = socketio.Client(
        reconnection=True,
        reconnection_attempts=5,
        reconnection_delay=2
    )
    
    connected = False
    registered = False
    
    @sio.event
    def connect():
        nonlocal connected
        connected = True
        print(f"[✓] Connected to WebSocket server")
        print(f"[...] Registering as remote for space: {space_name}")
        sio.emit('register_remote', {'space_name': space_name})
    
    @sio.event
    def disconnect():
        nonlocal connected, registered
        connected = False
        registered = False
        print(f"\n[✗] Disconnected from server")
        print(f"    Attempting to reconnect...")
    
    @sio.on('register_result')
    def on_register_result(data):
        nonlocal registered
        if data.get('success'):
            registered = True
            print(f"[✓] Successfully registered for space: {data.get('space_name')}")
            print(f"    Message: {data.get('message')}")
            print(f"\n[...] Waiting for inference requests...\n")
        else:
            print(f"\n[✗] Registration failed!")
            print(f"    Error: {data.get('error')}")
            print(f"\n    Exiting...\n")
            sio.disconnect()
            sys.exit(1)
    
    @sio.on('inference_request')
    def on_inference_request(data):
        request_id = data.get('request_id')
        user = data.get('user')
        request_data = data.get('data', {})
        
        print(f"\n{'─'*50}")
        print(f"[→] Received inference request")
        print(f"    Request ID: {request_id}")
        print(f"    User: {user}")
        print(f"    Data: {json.dumps(request_data, ensure_ascii=False, indent=2)[:200]}...")
        
        # Simulate processing time
        print(f"[...] Processing (simulating {processing_delay}s delay)...")
        time.sleep(processing_delay)
        
        # Generate mock result
        try:
            result = create_mock_result(request_data)
            print(f"[✓] Processing complete!")
            print(f"    Result type: {result.get('type')}")
            
            # Send result back
            sio.emit('inference_result', {
                'request_id': request_id,
                'success': True,
                'result': result
            })
            print(f"[→] Result sent to server")
            
        except Exception as e:
            print(f"[✗] Processing error: {str(e)}")
            sio.emit('inference_result', {
                'request_id': request_id,
                'success': False,
                'error': str(e)
            })
        
        print(f"{'─'*50}\n")
        print(f"[...] Waiting for next request...\n")
    
    # Connect to server
    print(f"[...] Connecting to {host}...")
    
    try:
        sio.connect(host, transports=['websocket', 'polling'])
        
        # Keep running
        print(f"\nPress Ctrl+C to stop the server\n")
        sio.wait()
        
    except socketio.exceptions.ConnectionError as e:
        print(f"\n[✗] Connection failed: {e}")
        print(f"    Please check:")
        print(f"    1. The host URL is correct: {host}")
        print(f"    2. The server is running and accessible")
        print(f"    3. WebSocket support is enabled on the server")
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n\n[!] Interrupted by user")
        if sio.connected:
            sio.disconnect()
        print(f"[✓] Disconnected. Goodbye!\n")
        sys.exit(0)


if __name__ == '__main__':
    main()
