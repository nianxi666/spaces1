import argparse
import socketio
import time
import sys

# --- Standard Client Setup ---
sio = socketio.Client()

@sio.event
def connect():
    print("Connection established. Sending authentication...")
    # Once connected, we send our credentials
    sio.emit('authenticate', {
        'space_name': ARGS.space_name,
        'token': ARGS.token
    }, namespace='/workers')

@sio.event
def disconnect():
    print("Disconnected from server.")

# --- Custom Namespace Events ---

@sio.on('auth_response', namespace='/workers')
def on_auth_response(data):
    """Handle the server's response to our authentication attempt."""
    if data.get('success'):
        print(f"Successfully authenticated as worker for space: '{ARGS.space_name}'")
        print("Waiting for tasks...")
    else:
        print(f"Authentication failed: {data.get('message')}")
        print("Disconnecting.")
        sio.disconnect()
        sys.exit(1) # Exit with an error code

@sio.on('new_task', namespace='/workers')
def on_new_task(data):
    """Handle a new task received from the server."""
    task_id = data.get('task_id')
    inputs = data.get('inputs', {})
    print(f"\n--- Received New Task ---")
    print(f"  Task ID: {task_id}")
    print(f"  Inputs: {inputs}")

    # Simulate processing time
    processing_time = 10
    print(f"Simulating processing for {processing_time} seconds...")
    for i in range(processing_time):
        time.sleep(1)
        print(f".", end='', flush=True)
    print("\nProcessing complete.")

    # Prepare the result
    result = {
        'text': f"Processed result for prompt: '{inputs.get('text', 'N/A')}'",
        'output_files': []
    }

    # If there was an image input, pretend we generated an image output
    if 'image_url' in inputs:
        result['image_url'] = 'https://i.imgur.com/g27tN6s.jpeg' # A placeholder image

    print(f"Sending result back to server...")

    # Send the result back
    sio.emit('task_result', {
        'task_id': data.get('task_id'),
        'user_sid': data.get('user_sid'),
        'result': result
    }, namespace='/workers')

    print("Result sent. Waiting for next task...")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="WebSocket Worker Client for PumpkinAI.")
    parser.add_argument('--host', type=str, required=True, help="The server host URL (e.g., http://127.0.0.1:5001)")
    parser.add_argument('--space-name', type=str, required=True, help="The name of the Space this worker is for.")
    parser.add_argument('--token', type=str, required=True, help="The authentication token for the Space.")

    ARGS = parser.parse_args()

    try:
        # Connect to the server
        sio.connect(ARGS.host, namespaces=['/workers'])

        # Wait for events
        sio.wait()

    except socketio.exceptions.ConnectionError as e:
        print(f"Connection failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        print("Worker client shut down.")
