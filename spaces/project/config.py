import os
from datetime import timedelta

# --- Flask App Configuration ---
SECRET_KEY = b'\x8a\x9b\x1f\xda\x0c\xd7\x8e\x9a\xf1\x1b\x1f\x9e\xee\x8f\x1c\x8a\x8f\x9b\xec\x9f\x1a\x9e\x8c\xbf'
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
GITHUB_CLIENT_ID = 'Ov23liV6gfkow8BmfuWD'
GITHUB_CLIENT_SECRET = '47b29514faa4b8e72dc2c5eefcb2d432842e2ac9'

# --- LinuxDo OAuth Configuration ---
LINUXDO_CLIENT_ID = 'pv66FXkfUEthBlidZtLIoKs6fkSB3hRq'
LINUXDO_CLIENT_SECRET = 'HOrPv6Uo4IhWCTaBDO44eDxQIZhxFBL4'

# --- S3 Configuration ---
import json
S3_CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', 's3_config.json')
S3_ENDPOINT_URL = None
S3_ACCESS_KEY_ID = None
S3_SECRET_ACCESS_KEY = None
S3_BUCKET_NAME = None

if os.path.exists(S3_CONFIG_FILE):
    with open(S3_CONFIG_FILE, 'r') as f:
        s3_config = json.load(f)
        S3_ENDPOINT_URL = s3_config.get('S3_ENDPOINT_URL')
        S3_ACCESS_KEY_ID = s3_config.get('S3_ACCESS_KEY_ID')
        S3_SECRET_ACCESS_KEY = s3_config.get('S3_SECRET_ACCESS_KEY')
        S3_BUCKET_NAME = s3_config.get('S3_BUCKET_NAME')

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
