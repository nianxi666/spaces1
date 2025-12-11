import os
import subprocess
import shlex
import time
import select
import threading
import queue
import requests
import json
from .database import load_db, save_db
from .utils import predict_output_filename
from project import create_app

# This dictionary will hold the state of all running/completed tasks.
# Note: This is in-memory and will be lost on app restart.
tasks = {}

def _reset_user_waiting_status(api_key):
    """Finds a user by API key and resets their waiting status."""
    if not api_key:
        return

    db = load_db()
    found_user = None
    for username, user_data in db.get('users', {}).items():
        if user_data.get('api_key') == api_key:
            found_user = username
            break

    if found_user and db.get('user_states', {}).get(found_user, {}).get('is_waiting_for_file'):
        db['user_states'][found_user]['is_waiting_for_file'] = False
        save_db(db)
        print(f"Reset waiting status for user: {found_user}")

def execute_inference_task(task_id, username, command, temp_upload_paths, user_api_key, server_url, template, prompt, seed, presigned_url, s3_object_name, predicted_filename):
    """
    Executes the inference task (runs the command).
    Legacy backend task execution.
    Most new types (Remote Inference, NetMind) are handled via frontend direct calls or specific proxy routes.
    This function is kept for backward compatibility if any legacy card types remain,
    but the main logic for Modal/Inferless/Gradio Python has been deprecated and removed.
    """
    app = create_app()
    with app.app_context():
        tasks[task_id] = {'status': 'failed', 'logs': 'This runner type has been deprecated.\n', 'result_files': [], 'username': username}
        _reset_user_waiting_status(user_api_key)

        # Cleanup
        if temp_upload_paths:
            for path in temp_upload_paths:
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass

def execute_inference_task_stream(username, command, temp_upload_paths, user_api_key, server_url, template, prompt, seed, presigned_url, s3_object_name, predicted_filename):
    """
    Deprecated streaming execution.
    """
    yield "--- This runner type has been deprecated. ---\n"
    _reset_user_waiting_status(user_api_key)
    if temp_upload_paths:
        for path in temp_upload_paths:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

def cleanup_expired_files():
    """
    Iterates through uploaded files and deletes them based on their retention period.
    - API uploads: 1 hour
    - Browser uploads: 10 minutes
    """
    try:
        db = load_db()
        current_time = time.time()
        files_to_delete_ids = []

        # It's safer to create a copy of the items to iterate over
        for file_id, file_info in list(db.get('uploaded_files', {}).items()):
            upload_type = file_info.get('upload_type')
            timestamp = file_info.get('timestamp')

            if not upload_type or not timestamp:
                continue

            age = current_time - timestamp

            should_delete = False
            if upload_type == 'api' and age > 3600: # 1 hour
                should_delete = True
            elif upload_type == 'browser' and age > 600: # 10 minutes
                should_delete = True

            if should_delete:
                if os.path.exists(file_info['filepath']):
                    try:
                        os.remove(file_info['filepath'])
                    except OSError as e:
                        print(f"Error deleting file {file_info['filepath']}: {e}")

                files_to_delete_ids.append(file_id)

        if files_to_delete_ids:
            for file_id in files_to_delete_ids:
                if file_id in db['uploaded_files']:
                    del db['uploaded_files'][file_id]
            save_db(db)
            print(f"Cleaned up {len(files_to_delete_ids)} expired files.")

    except Exception as e:
        print(f"An error occurred during file cleanup: {e}")
