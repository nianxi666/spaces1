import os
import subprocess
import shlex
import time
import select
from .database import load_db, save_db
from .utils import predict_output_filename
from project import create_app

# This dictionary will hold the state of all running/completed tasks.
# Note: This is in-memory and will be lost on app restart.
# For persistence, a more robust solution like Redis or a database would be needed.
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
    Executes the inference command, captures logs, and handles result upload directly to S3.
    This version includes logic to retry with a new key if a limit is reached.
    """
    app = create_app()
    with app.app_context():
        tasks[task_id] = {'status': 'running', 'logs': f'Executing: {command}\n', 'result_files': [], 'username': username}
        max_retries = 1
        retry_count = 0

        try:
            while retry_count <= max_retries:
                # If predicted_filename contains a path separator, use it as is.
                # Otherwise, prepend the default 'output/' directory.
                if '/' in predicted_filename:
                    remote_output_filepath = predicted_filename
                else:
                    remote_output_filepath = f"output/{predicted_filename}"

                # New curl command to upload directly to S3
                # We need to quote the URL to handle special characters
                quoted_presigned_url = shlex.quote(presigned_url)
                curl_cmd = f'curl -X PUT -T {shlex.quote(remote_output_filepath)} {quoted_presigned_url}'

                inner_command_parts = []
                if template.get('sub_command'):
                    sub_cmd = template['sub_command'].strip()
                    if sub_cmd:
                        inner_command_parts.append(sub_cmd)
                        if not sub_cmd.endswith('&&'):
                            inner_command_parts.append('&&')
                inner_command_parts.append(command)
                inner_command_parts.append('&&')
                inner_command_parts.append(curl_cmd)
                final_inner_command_str = " ".join(inner_command_parts)

                # The final command string is passed as a single argument.
                # The remote shell will handle parsing the inner quotes.
                # We wrap with double quotes for safety.
                command_runner = template.get('command_runner', 'inferless')
                entrypoint_script = template.get('entrypoint_script', 'app.py')

                # Main executable command (modal, inferless, etc.)
                if command_runner == 'modal':
                    main_executable_cmd = f'modal run {entrypoint_script} --command "{final_inner_command_str}"'
                elif command_runner == 'shell':
                    # Use the raw command directly, no wrapper
                    # For shell runner, 'command' usually contains the full script invocation.
                    # We might ignore sub_command or just append them.
                    # Here we treat 'command' as the main thing to run.
                    # If the template has 'base_command', api.py constructs 'full_cmd'.
                    # So 'command' here IS the full command (e.g. "python3 script.py --prompt ...")
                    # We skip the "inner_command_parts" logic effectively because 'final_inner_command_str'
                    # is built from 'command' + 'curl'.
                    # If the runner script handles upload, we don't need 'curl'.
                    # BUT 'final_inner_command_str' HAS curl appended.
                    # If we use 'shell', we might not want 'curl' if the script does it.
                    # However, to be generic, we let it execute.
                    # If 'call_remote_api.py' saves to local disk, then 'curl' uploads it.
                    # So:
                    main_executable_cmd = final_inner_command_str
                else:
                    main_executable_cmd = (f'inferless remote-run {entrypoint_script} -c inferless-runtime-config.yaml --command "{final_inner_command_str}"')

                # Force line-buffering on the main executable command
                buffered_main_cmd = f"stdbuf -oL {main_executable_cmd}"

                # Combine with pre-command if it exists
                full_command = buffered_main_cmd
                if template.get('pre_command'):
                    pre_cmd = template['pre_command'].strip()
                    if pre_cmd:
                        if not pre_cmd.endswith('&&'):
                            pre_cmd += ' && '
                        full_command = pre_cmd + buffered_main_cmd

                tasks[task_id]['logs'] += f'Attempt {retry_count + 1}: Executing command: {full_command}\n'
                tasks[task_id]['logs'] += f'Predicted output filename: {predicted_filename}\n'

                process = subprocess.Popen(
                    full_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding='utf-8', errors='replace', bufsize=1, universal_newlines=True
                )

                limit_reached = False
                if command_runner == 'modal':
                    for line in process.stdout:
                        tasks[task_id]['logs'] += line
                        if "limit reached" in line.lower():
                            tasks[task_id]['logs'] += "\n--- 'Limit reached' detected in modal task. ---\n"
                            limit_reached = True
                            # Don't break, let the modal task finish, but we have flagged it.
                else:
                     for line in process.stdout:
                        tasks[task_id]['logs'] += line


                process.wait()

                if limit_reached:
                    retry_count += 1
                    if retry_count <= max_retries:
                        tasks[task_id]['logs'] += "Attempting to switch key and retry.\n"
                        try:
                            with open('key.txt', 'r+') as f:
                                lines = f.readlines()
                                if not lines:
                                    tasks[task_id]['logs'] += "key.txt is empty. Cannot switch key. Aborting.\n"
                                    break

                                new_key_command = lines.pop(0).strip()
                                if not new_key_command:
                                    tasks[task_id]['logs'] += "Empty line in key.txt. Cannot switch key. Aborting.\n"
                                    break

                                tasks[task_id]['logs'] += f"Executing new key command: {new_key_command}\n"
                                key_change_process = subprocess.run(
                                    new_key_command, shell=True, capture_output=True, text=True
                                )
                                tasks[task_id]['logs'] += key_change_process.stdout
                                tasks[task_id]['logs'] += key_change_process.stderr

                                if key_change_process.returncode != 0:
                                    tasks[task_id]['logs'] += "Failed to execute key change command. Aborting.\n"
                                    break

                                f.seek(0)
                                f.writelines(lines)
                                f.truncate()
                                tasks[task_id]['logs'] += "Successfully switched key. Retrying the command.\n"
                                # Continue to the next iteration of the while loop
                                continue

                        except FileNotFoundError:
                            tasks[task_id]['logs'] += "key.txt not found. Cannot switch key. Aborting.\n"
                            break
                        except Exception as e:
                            tasks[task_id]['logs'] += f"An error occurred while handling key.txt: {e}\n"
                            break
                    else:
                        tasks[task_id]['logs'] += "Limit reached on retry. No more attempts left.\n"
                        tasks[task_id]['status'] = 'failed'
                        _reset_user_waiting_status(user_api_key)
                        break

                # If we are here, it means no limit was reached, or retries are exhausted.
                # Check the process return code.
                if process.returncode != 0:
                    tasks[task_id]['status'] = 'failed'
                    tasks[task_id]['logs'] += f"\n--- ERROR: Process finished with exit code {process.returncode} ---\n"
                    tasks[task_id]['logs'] += "Check the command logs. The remote file may not have been generated, or the API key/domain may be invalid.\n"
                    _reset_user_waiting_status(user_api_key)
                else:
                    tasks[task_id]['logs'] += "\n--- Task completed. Result uploaded to S3. ---\n"
                    tasks[task_id]['result_files'] = [s3_object_name] # Store the S3 object key
                    tasks[task_id]['status'] = 'completed'

                break # Exit the while loop

        except Exception as e:
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['logs'] += f"\n--- PYTHON EXCEPTION: {str(e)} ---"
            _reset_user_waiting_status(user_api_key)
        finally:
            if temp_upload_paths:
                for path in temp_upload_paths:
                    if path and os.path.exists(path):
                        try:
                            os.remove(path)
                        except OSError as e:
                            tasks[task_id]['logs'] += f"\nWARNING: Could not delete temp file {path}: {e}"

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
        # In a real app, you'd want more robust logging here
        print(f"An error occurred during file cleanup: {e}")

def execute_inference_task_stream(username, command, temp_upload_paths, user_api_key, server_url, template, prompt, seed, presigned_url, s3_object_name, predicted_filename):
    """
    Executes the inference command and streams logs back to the caller.
    """
    app = create_app()
    with app.app_context():
        try:
            # Simplified command construction for streaming
            if '/' in predicted_filename:
                remote_output_filepath = predicted_filename
            else:
                remote_output_filepath = f"output/{predicted_filename}"

            quoted_presigned_url = shlex.quote(presigned_url)
            curl_cmd = f'curl -X PUT -T {shlex.quote(remote_output_filepath)} {quoted_presigned_url}'

            inner_command_parts = []
            if template.get('sub_command'):
                sub_cmd = template['sub_command'].strip()
                if sub_cmd:
                    inner_command_parts.append(sub_cmd)
                    if not sub_cmd.endswith('&&'):
                        inner_command_parts.append('&&')
            inner_command_parts.append(command)
            inner_command_parts.append('&&')
            inner_command_parts.append(curl_cmd)
            final_inner_command_str = " ".join(inner_command_parts)

            command_runner = template.get('command_runner', 'inferless')
            entrypoint_script = template.get('entrypoint_script', 'app.py')

            # Main executable command (modal, inferless, etc.)
            if command_runner == 'modal':
                main_executable_cmd = f'modal run {entrypoint_script} --command "{final_inner_command_str}"'
            elif command_runner == 'shell':
                main_executable_cmd = final_inner_command_str
            else:
                main_executable_cmd = (f'inferless remote-run {entrypoint_script} -c inferless-runtime-config.yaml --command "{final_inner_command_str}"')

            # Force line-buffering on the main executable command
            buffered_main_cmd = f"stdbuf -oL {main_executable_cmd}"

            # Combine with pre-command if it exists
            full_command = buffered_main_cmd
            if template.get('pre_command'):
                pre_cmd = template['pre_command'].strip()
                if pre_cmd:
                    if not pre_cmd.endswith('&&'):
                        pre_cmd += ' && '
                    full_command = pre_cmd + buffered_main_cmd

            yield f"--- Starting Task ---\n"
            yield f"Executing command: {full_command}\n"

            process = subprocess.Popen(
                full_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace', bufsize=1, universal_newlines=True
            )

            # Use select for non-blocking reads with a timeout for heartbeats
            while process.poll() is None:
                readable, _, _ = select.select([process.stdout], [], [], 10.0)
                if readable:
                    line = process.stdout.readline()
                    if line:
                        yield line
                    else: # End of stream
                        break
                else:
                    # select timed out, send a heartbeat (newline)
                    yield "\n"

            # Read any remaining lines after the process has finished
            for line in process.stdout:
                yield line

            process.wait()

            if process.returncode != 0:
                yield f"\n--- ERROR: Process finished with exit code {process.returncode} ---\n"
            else:
                yield "\n--- Task completed. Result uploaded to S3. ---\n"
                yield f"Result S3 Object Key: {s3_object_name}\n"

        except Exception as e:
            yield f"\n--- PYTHON EXCEPTION: {str(e)} ---\n"
        finally:
            # Ensure user status is always reset and temp files are cleaned up
            _reset_user_waiting_status(user_api_key)
            if temp_upload_paths:
                for path in temp_upload_paths:
                    if path and os.path.exists(path):
                        try:
                            os.remove(path)
                        except OSError as e:
                            yield f"\nWARNING: Could not delete temp file {path}: {e}\n"
            yield "\n--- End of Stream ---"
