#!/usr/bin/env python3
"""Simple WebSocket connection test with detailed logging"""
import socketio
import time

sio = socketio.Client(logger=True, engineio_logger=True)

@sio.event
def connect():
    print(">>> CONNECTED to server")
    print(">>> Sending register event...")
    sio.emit('register', {'space_name': 'MockImageGen'})

@sio.on('register_response')
def on_register_response(data):
    print(">>> REGISTER RESPONSE:", data)
    if data.get('success'):
        print(">>> SUCCESS! Waiting for inference requests...")
    else:
        print(">>> FAILED:", data.get('message'))

@sio.event
def disconnect():
    print(">>> DISCONNECTED from server")

@sio.on('*')
def catch_all(event, *args):
    print(f">>> EVENT: {event}, ARGS: {args}")

if __name__ == '__main__':
    print("Testing WebSocket connection to http://localhost:5001")
    print("Space name: MockImageGen")
    print("-" * 50)
    
    try:
        sio.connect('http://localhost:5001', transports=['websocket', 'polling'])
        time.sleep(5)  # Wait for registration response
    except Exception as e:
        print(f">>> ERROR: {e}")
    finally:
        if sio.connected:
            sio.disconnect()
        print(">>> Test complete")
