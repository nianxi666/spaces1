
import paramiko
import time
import os
import argparse

# Default configuration for the remote server
DEFAULT_HOSTNAME = 'direct.virtaicloud.com'
DEFAULT_PORT = 30022
DEFAULT_USERNAME = 'root4563@root@ssh-ad886e9ff5a8de6117e40aaf616d3884.zlrast8j3bxb'

# Remote paths and settings
REMOTE_WORK_DIR = '/gemini/code/index-tts/'
PYTHON_PATH = '/root/miniconda3/bin/python'

def setup_remote_server(password, s3_access_key, s3_secret_key,
                        hostname=DEFAULT_HOSTNAME, port=DEFAULT_PORT, username=DEFAULT_USERNAME,
                        bucket_name='driver', s3_endpoint='http://s3.tebi.io'):
    """
    Connects to the remote server, kills existing instances, and starts the webui in a screen session.
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"Connecting to {hostname}:{port}...")
        client.connect(hostname, port=port, username=username, password=password)

        print("Killing old webui processes...")
        client.exec_command("pkill -f webui.py")
        time.sleep(2)
        # Force kill if needed
        client.exec_command("pkill -9 -f webui.py")

        # Wipe dead screens
        client.exec_command("screen -wipe")

        print("Starting new screen session 'webui'...")

        # Construct environment variables string
        env_vars = (
            f"export S3_ACCESS_KEY_ID='{s3_access_key}'; "
            f"export S3_SECRET_ACCESS_KEY='{s3_secret_key}'; "
            f"export S3_BUCKET_NAME='{bucket_name}'; "
            f"export S3_ENDPOINT_URL='{s3_endpoint}'; "
        )

        # Command to run in screen
        run_cmd = f"{env_vars} {PYTHON_PATH} webui.py"
        # Screen command
        screen_cmd = f"cd {REMOTE_WORK_DIR} && screen -dmS webui bash -c \"{run_cmd}\""

        print(f"Executing: {screen_cmd}")
        client.exec_command(screen_cmd)
        time.sleep(5)

        # Verify
        stdin, stdout, stderr = client.exec_command("ps aux | grep webui.py | grep -v grep")
        status = stdout.read().decode().strip()

        if status:
            print("Remote WebUI started successfully.")
            print(status)
        else:
            print("Failed to start Remote WebUI. Check remote logs.")

        client.close()

    except Exception as e:
        print(f"SSH Connection Failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Setup remote WebUI with S3 keys.')
    parser.add_argument('--password', required=True, help='SSH Password')
    parser.add_argument('--s3-access-key', required=True, help='S3 Access Key')
    parser.add_argument('--s3-secret-key', required=True, help='S3 Secret Key')
    parser.add_argument('--hostname', default=DEFAULT_HOSTNAME, help='Remote Hostname')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Remote Port')
    parser.add_argument('--username', default=DEFAULT_USERNAME, help='SSH Username')
    parser.add_argument('--bucket-name', default='driver', help='S3 Bucket Name')
    parser.add_argument('--s3-endpoint', default='http://s3.tebi.io', help='S3 Endpoint URL (HTTP recommended for this env)')

    args = parser.parse_args()

    setup_remote_server(
        password=args.password,
        s3_access_key=args.s3_access_key,
        s3_secret_key=args.s3_secret_key,
        hostname=args.hostname,
        port=args.port,
        username=args.username,
        bucket_name=args.bucket_name,
        s3_endpoint=args.s3_endpoint
    )
