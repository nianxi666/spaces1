import threading
from flask import request
from flask_socketio import Namespace, emit, join_room, leave_room
from . import socketio
from .database import load_db

# This dictionary will hold the state of our workers
# a simple mapping of space_name to the worker's session ID (sid)
connected_workers = {}
# a mapping of space_name to the worker's status ('idle' or 'busy')
worker_status = {}
# a mapping of space_name to the current task being processed
worker_tasks = {}


def try_dispatch_task(space_id):
    """
    Checks for pending tasks for a given space and dispatches one to an idle worker.
    This function should be called when a new task is added or a worker becomes free.
    """
    from .api import task_queues, task_locks
    with task_locks.get(space_id, threading.Lock()):
        # Check if there's an idle worker and a queued task
        if space_id in worker_status and worker_status[space_id] == 'idle' and space_id in task_queues and task_queues[space_id]:

            task_payload = task_queues[space_id].popleft()
            worker_sid = connected_workers.get(space_id)

            if worker_sid:
                # Update states
                worker_status[space_id] = 'busy'
                worker_tasks[space_id] = task_payload
                task_payload['status'] = 'processing'

                # Notify user that task is starting
                socketio.emit('task_update', {
                    'task_id': task_payload['task_id'],
                    'status': 'processing'
                }, room=f"task_{task_payload['task_id']}")

                # Send task to worker
                emit('new_task', task_payload, room=worker_sid, namespace='/workers')
                print(f"Dispatched task {task_payload['task_id']} to worker {worker_sid} for space {space_id}")


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
        worker_status[space_name] = 'idle'
        join_room(space_name) # Use room for easy targeting

        print(f"Worker {request.sid} authenticated and connected for space '{space_name}'.")
        emit('auth_response', {'success': True, 'message': 'Authentication successful.'})

        # Try to dispatch a task immediately in case there are queued tasks
        try_dispatch_task(space_name)

    def on_disconnect(self):
        """Handle a worker disconnecting."""
        from .api import worker_status, try_dispatch_task

        disconnected_space = None
        for space, sid in list(connected_workers.items()):
            if sid == request.sid:
                disconnected_space = space
                break

        if disconnected_space:
            print(f"Worker for space '{disconnected_space}' disconnected (sid: {request.sid}).")

            # --- Handle Task Failure on Disconnect ---
            if worker_status.get(disconnected_space) == 'busy':
                failed_task = worker_tasks.get(disconnected_space)
                if failed_task:
                    print(f"Task {failed_task['task_id']} failed because worker disconnected.")
                    socketio.emit('task_update', {
                        'task_id': failed_task['task_id'],
                        'status': 'failed',
                        'error': '推理工作节点意外断开连接，请重试。'
                    }, room=f"task_{failed_task['task_id']}")

            # Clean up worker state
            if disconnected_space in connected_workers:
                del connected_workers[disconnected_space]
            if disconnected_space in worker_status:
                del worker_status[disconnected_space]
            if disconnected_space in worker_tasks:
                del worker_tasks[disconnected_space]

            leave_room(disconnected_space)
        else:
            print(f"Unauthenticated worker disconnected (sid: {request.sid}).")

    def on_task_result(self, data):
        """Handle a worker sending back the result of a task."""
        task_id = data.get('task_id')
        result = data.get('result')

        space_name = None
        for name, sid in connected_workers.items():
            if sid == request.sid:
                space_name = name
                break

        if not space_name:
            print(f"Received task result from an unknown worker: {request.sid}")
            return

        original_task = worker_tasks.get(space_name)
        if not original_task or original_task['task_id'] != task_id:
            print(f"Received result for an unexpected task_id: {task_id}. Ignoring.")
            return

        print(f"Received result for task {task_id} from space '{space_name}'")

        # Send the result to the user's room
        socketio.emit('task_update', {
            'task_id': task_id,
            'status': 'completed',
            'result': result
        }, room=f"task_{task_id}")

        # Update worker status and try to dispatch the next task
        worker_status[space_name] = 'idle'
        worker_tasks[space_name] = None
        try_dispatch_task(space_name)

# Register the namespace
socketio.on_namespace(WorkerNamespace('/workers'))

@socketio.on('join_task_room')
def handle_join_task_room(data):
    """
    Allows a client (user's browser) to join a room specific to a task,
    so they can receive updates for it.
    """
    task_id = data.get('task_id')
    if task_id:
        join_room(f"task_{task_id}")
        print(f"Client {request.sid} joined room for task {task_id}")
