import os
from datetime import timedelta

# --- Flask App Configuration ---
SECRET_KEY = os.environ.get('SECRET_KEY') or b'\x8a\x9b\x1f\xda\x0c\xd7\x8e\x9a\xf1\x1b\x1f\x9e\xee\x8f\x1c\x8a\x8f\x9b\xec\x9f\x1a\x9e\x8c\xbf'
PERMANENT_SESSION_LIFETIME = timedelta(days=30)
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB

# --- Directory and File Configuration ---
# Note: These are relative to the instance folder, which Flask will manage.
# The application factory will ensure these directories exist.
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
RESULTS_FOLDER = 'results'
DB_FILE = 'database.sqlite' # 使用SQLite数据库文件

# --- Static Folder Configuration ---
# This path is relative to the 'project' package directory.
# Flask's default is 'static', so we specify a more nested path.
COVER_FOLDER = os.path.join('static', 'covers')

# --- Other Configurations ---
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi', 'zip', 'rar'}

# --- GitHub OAuth Configuration ---
GITHUB_CLIENT_ID = os.environ.get('GITHUB_CLIENT_ID', 'Ov23lienZj9B97kiR5xZ')
GITHUB_CLIENT_SECRET = os.environ.get('GITHUB_CLIENT_SECRET', '628d402ff78e879514e98be504a6634e0cbe9d20')

# --- LinuxDo OAuth Configuration ---
LINUXDO_CLIENT_ID = os.environ.get('LINUXDO_CLIENT_ID', 'your_linuxdo_client_id')
LINUXDO_CLIENT_SECRET = os.environ.get('LINUXDO_CLIENT_SECRET', 'your_linuxdo_client_secret')

# --- S3 Configuration ---
import json
S3_CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', 's3_config.json')
S3_ENDPOINT_URL = os.environ.get('S3_ENDPOINT_URL')
S3_ACCESS_KEY_ID = os.environ.get('S3_ACCESS_KEY_ID')
S3_SECRET_ACCESS_KEY = os.environ.get('S3_SECRET_ACCESS_KEY')
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')

MODAL_DRIVE_BASE_URL = os.environ.get('MODAL_DRIVE_BASE_URL')
MODAL_DRIVE_AUTH_TOKEN = os.environ.get('MODAL_DRIVE_AUTH_TOKEN')

if os.path.exists(S3_CONFIG_FILE):
    try:
        with open(S3_CONFIG_FILE, 'r') as f:
            s3_config = json.load(f)
            # Only override env vars if s3_config.json values are present
            S3_ENDPOINT_URL = S3_ENDPOINT_URL or s3_config.get('S3_ENDPOINT_URL')
            S3_ACCESS_KEY_ID = S3_ACCESS_KEY_ID or s3_config.get('S3_ACCESS_KEY_ID')
            S3_SECRET_ACCESS_KEY = S3_SECRET_ACCESS_KEY or s3_config.get('S3_SECRET_ACCESS_KEY')
            S3_BUCKET_NAME = S3_BUCKET_NAME or s3_config.get('S3_BUCKET_NAME')
    except Exception:
        pass

# --- Cloud Terminal Configuration ---
try:
    CEREBRIUM_CLOUD_TERMINAL_TIMEOUT = float(os.environ.get('CEREBRIUM_CLOUD_TERMINAL_TIMEOUT', '60'))
except (TypeError, ValueError):
    CEREBRIUM_CLOUD_TERMINAL_TIMEOUT = 60.0

CLOUD_TERMINAL_SOURCE_DIR = os.environ.get(
    'CLOUD_TERMINAL_SOURCE_DIR',
    os.path.join(os.path.dirname(__file__), 'cloud_terminal_source')
)
try:
    CLOUD_TERMINAL_DEPLOY_TIMEOUT = int(os.environ.get('CLOUD_TERMINAL_DEPLOY_TIMEOUT', '900'))
except (TypeError, ValueError):
    CLOUD_TERMINAL_DEPLOY_TIMEOUT = 900

CEREBRIUM_PROJECT_ID = os.environ.get('CEREBRIUM_PROJECT_ID')
