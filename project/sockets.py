from flask import request
from flask_socketio import Namespace, emit, join_room, leave_room
from . import socketio
from .database import load_db

# This dictionary will hold the state of our workers
# a simple mapping of space_name to the worker's session ID (sid)
connected_workers = {}

class WorkerNamespace(Namespace):
    def on_connect(self):
        """Handle a new worker connecting."""
        print(f"Worker trying to connect with sid: {request.sid}")

    def on_authenticate(self, data):
        """Authenticate the worker."""
        space_name = data.get('space_name')
        token = data.get('token')

        if not all([space_name, token]):
            print(f"Authentication failed for {request.sid}: missing space_name or token")
            emit('auth_response', {'success': False, 'message': 'Missing space_name or token.'})
            return False # False disconnects the client

        db = load_db()
        space = next((s for s in db.get('spaces', {}).values() if s['name'] == space_name), None)

        if not space:
            print(f"Authentication failed for {request.sid}: space '{space_name}' not found.")
            emit('auth_response', {'success': False, 'message': f"Space '{space_name}' not found."})
            return False

        if space.get('card_type') != 'websocket':
            print(f"Authentication failed for {request.sid}: space '{space_name}' is not a WebSocket space.")
            emit('auth_response', {'success': False, 'message': 'Not a WebSocket space.'})
            return False

        if space.get('auth_token') != token:
            print(f"Authentication failed for {request.sid}: invalid token for space '{space_name}'.")
            emit('auth_response', {'success': False, 'message': 'Invalid token.'})
            return False

        # --- Authentication Successful ---

        # Check if another worker is already connected for this space
        if space_name in connected_workers:
            print(f"Authentication failed for {request.sid}: space '{space_name}' already has a connected worker.")
            emit('auth_response', {'success': False, 'message': 'A worker is already connected for this space.'})
            return False

        # Store the worker's state
        connected_workers[space_name] = request.sid
        join_room(space_name) # Use room for easy targeting

        print(f"Worker {request.sid} authenticated and connected for space '{space_name}'.")
        emit('auth_response', {'success': True, 'message': 'Authentication successful.'})

        # TODO: Potentially trigger sending a queued task if one exists for this space

    def on_disconnect(self):
        """Handle a worker disconnecting."""
        from .api import worker_status, try_dispatch_task

        disconnected_space = None
        for space, sid in list(connected_workers.items()):
            if sid == request.sid:
                disconnected_space = space
                break

        if disconnected_space:
            del connected_workers[disconnected_space]
            leave_room(disconnected_space)
            print(f"Worker for space '{disconnected_space}' disconnected (sid: {request.sid}).")

            # --- Handle Task Failure on Disconnect ---
            status = worker_status.get(disconnected_space)
            if status and status.get('status') == 'busy':
                failed_task = status.get('current_task')
                if failed_task and failed_task.get('user_sid'):
                    print(f"Task {failed_task['task_id']} failed because worker disconnected.")
                    socketio.emit('task_status', {
                        'status': 'failed',
                        'error': '推理工作节点意外断开连接，请重试。'
                    }, room=failed_task['user_sid'])

            # Reset worker status and try to process next task in queue
            worker_status[disconnected_space] = {'status': 'idle', 'current_task': None}
            try_dispatch_task(disconnected_space)

        else:
            print(f"Unauthenticated worker disconnected (sid: {request.sid}).")

    def on_task_result(self, data):
        """Handle a worker sending back the result of a task."""
        task_id = data.get('task_id')
        user_sid = data.get('user_sid')
        result = data.get('result')

        # Find the space this worker belongs to
        space_name = None
        for name, sid in connected_workers.items():
            if sid == request.sid:
                space_name = name
                break

        if not space_name:
            print(f"Received task result from an unknown worker: {request.sid}")
            return

        print(f"Received result for task {task_id} from space '{space_name}'")

        # Send the result to the user
        if user_sid:
            socketio.emit('task_result', {'task_id': task_id, 'result': result}, room=user_sid)

        # Update worker status and try to dispatch the next task
        from .api import worker_status, try_dispatch_task
        worker_status[space_name] = {'status': 'idle', 'current_task': None}
        try_dispatch_task(space_name)

# Register the namespace
socketio.on_namespace(WorkerNamespace('/workers'))
