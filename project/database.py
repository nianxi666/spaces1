import os
import json
import uuid
import sqlite3
from datetime import datetime
from flask import current_app
from .netmind_config import (
    DEFAULT_NETMIND_RATE_LIMIT_MAX_REQUESTS,
    DEFAULT_NETMIND_RATE_LIMIT_WINDOW_SECONDS,
    sanitize_rate_limit_max_requests,
    sanitize_rate_limit_window
)

def get_db_path():
    """Constructs the full path to the SQLite database file within the instance folder."""
    return os.path.join(current_app.instance_path, current_app.config['DB_FILE'])

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row # This allows accessing columns by name
    return conn

def init_db_schema():
    """Initializes the database schema if it doesn't exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_data (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        conn.commit()

def load_db():
    """Loads the entire application data from the SQLite database."""
    init_db_schema() # Ensure table exists
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM app_data WHERE key = 'main_db';")
        row = cursor.fetchone()
        if row:
            return json.loads(row['value'])
    return get_default_db_structure()

def save_db(data):
    """Saves the entire application data to the SQLite database."""
    init_db_schema() # Ensure table exists
    db_json = json.dumps(data, indent=4, ensure_ascii=False)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO app_data (key, value) VALUES (?, ?);", ('main_db', db_json))
        conn.commit()

def get_default_db_structure():
    """Returns the default structure for a new database."""
    return {
        "users": {},
        "orders": {},
        "spaces": {},
        "settings": {},
        "uploaded_files": {},
        "categories": [],
        "chat_messages": [],
        "chat_history": [],
        "articles": {},
        "invitation_codes": {},
        "modal_drive_shares": {},
        "announcement": {
            "enabled": False,
            "title": "",
            "content": "",
            "type": "info",
            "show_on_homepage": False,
            "show_on_projects": False
        },
        "chat_announcement": {
            "enabled": False,
            "content": "",
            "type": "info"
        },
        "terminal_announcement": {
            "enabled": False,
            "content": "",
            "type": "info"
        },
        "user_states": {},
        "daily_active_users": {},
        "sensitive_words": [],
        "gpu_pool": [],
        "netmind_settings": {
            "keys": [],
            "blacklist": [],
            "ad_suffix": "",
            "ad_enabled": False,
            "enable_alias_mapping": False,
            "base_url": "https://api.netmind.ai/inference-api/openai/v1",
            "model_aliases": {},
            "rate_limit_window_seconds": DEFAULT_NETMIND_RATE_LIMIT_WINDOW_SECONDS,
            "rate_limit_max_requests": DEFAULT_NETMIND_RATE_LIMIT_MAX_REQUESTS
        },
        "payment_settings": {
            "enabled": False,
            "gumroad_app_id": "",
            "gumroad_app_secret": "",
            "gumroad_access_token": "",
            "gumroad_product_url": "",
            "gumroad_webhook_secret": ""
        }
    }

def init_db():
    """Initializes the database file and necessary folders if they don't exist."""
    # Create instance folder if it doesn't exist
    try:
        os.makedirs(current_app.instance_path)
    except OSError:
        pass # Already exists

    # Create other necessary folders inside the instance folder
    for folder_key in ['UPLOAD_FOLDER', 'OUTPUT_FOLDER', 'RESULTS_FOLDER']:
        folder_path = os.path.join(current_app.instance_path, current_app.config[folder_key])
        os.makedirs(folder_path, exist_ok=True)

    # The covers folder is in the static directory, not instance folder
    covers_path = os.path.join(current_app.root_path, current_app.config['COVER_FOLDER'])
    os.makedirs(covers_path, exist_ok=True)

    # Initialize SQLite schema
    init_db_schema()

    # Load the database and check for necessary default values
    db = load_db()

    # Initialize settings
    if 'settings' not in db:
        db['settings'] = {}
    if 'uploaded_files' not in db:
        db['uploaded_files'] = {}
    if 'chat_messages' not in db:
        db['chat_messages'] = []
    if 'server_domain' not in db['settings'] or not db['settings']['server_domain']:
        db['settings']['server_domain'] = 'https://pumpkinai.it.com'
    if 'chat_is_muted' not in db['settings']:
        db['settings']['chat_is_muted'] = False
    if 'ads_enabled' not in db['settings']:
        db['settings']['ads_enabled'] = True
    if 'adsterra_enabled' not in db['settings']:
        db['settings']['adsterra_enabled'] = True
    if 'monetag_enabled' not in db['settings']:
        db['settings']['monetag_enabled'] = True
    if 'richads_enabled' not in db['settings']:
        db['settings']['richads_enabled'] = True

    # Add a default Space if none exist
    if not db.get('spaces'):
        default_space_id = str(uuid.uuid4())
        default_template_id = str(uuid.uuid4())
        db['spaces'] = {
            default_space_id: {
                "id": default_space_id,
                "name": "Default Space",
                "card_type": "standard",
                "cover": "default.png",
                "base_command": 'echo "Hello from default space"',
                "params": "--seed {{seed}}",
                "preset_params": "",
                "description": "This is a default space. The admin can edit it.",
                "pre_command": "",
                "sub_command": "",
                "force_upload": False,
                "templates": {
                    default_template_id: {
                        "id": default_template_id,
                        "name": "Default Template",
                        "command_runner": "inferless",
                        "entrypoint_script": "app.py",
                        "pre_command": "",
                        "sub_command": "",
                        "base_command": "echo 'Hello from default template'",
                        "preset_params": "",
                        "params": [],
                        "timeout": 300,
                        "force_upload": False,
                        "requires_invitation_code": False
                    }
                }
            }
        }

    # Ensure all existing spaces have the 'preset_params' and 'force_upload' fields
    for space_id, space_data in db.get('spaces', {}).items():
        if 'preset_params' not in space_data:
            db['spaces'][space_id]['preset_params'] = ""
        if 'force_upload' not in space_data:
            db['spaces'][space_id]['force_upload'] = False
        if 'card_type' not in space_data:
            db['spaces'][space_id]['card_type'] = 'standard'
        if 'cerebrium_timeout_seconds' not in space_data:
            db['spaces'][space_id]['cerebrium_timeout_seconds'] = 300
        if space_data.get('card_type') == 'netmind':
            upstream_key = space_data.get('netmind_upstream_model')
            if not upstream_key:
                db['spaces'][space_id]['netmind_upstream_model'] = space_data.get('netmind_model', '') or ''

    # Ensure all users have an avatar and last_chat_read_time
    for username, user_data in db.get('users', {}).items():
        if 'avatar' not in user_data:
            user_data['avatar'] = 'default.png'
        if 'last_chat_read_time' not in user_data:
            user_data['last_chat_read_time'] = 0
        if 'cerebrium_configs' not in user_data:
            user_data['cerebrium_configs'] = []
        if 'first_api_use_date' not in user_data:
            user_data['first_api_use_date'] = None
        if 'last_check_in_date' not in user_data:
            user_data['last_check_in_date'] = None
        if 'check_in_history' not in user_data:
            user_data['check_in_history'] = []
        if 'last_username_change_date' not in user_data:
            user_data['last_username_change_date'] = None
        if 's3_folder_name' not in user_data:
            user_data['s3_folder_name'] = username

    # Initialize articles if they don't exist
    if 'articles' not in db:
        db['articles'] = {}

    # Initialize categories if they don't exist
    if 'categories' not in db or not db['categories']:
        db['categories'] = [
            {"id": str(uuid.uuid4()), "name": "所有ai项目", "icon": "🎃"},
            {"id": str(uuid.uuid4()), "name": "BotAI", "icon": "🤖"},
            {"id": str(uuid.uuid4()), "name": "Artify", "icon": "🎨"},
            {"id": str(uuid.uuid4()), "name": "MusicGen", "icon": "🎵"},
            {"id": str(uuid.uuid4()), "name": "Writer", "icon": "📝"},
            {"id": str(uuid.uuid4()), "name": "Ideas", "icon": "💡"}
        ]

    # Initialize invitation_codes if they don't exist
    if 'invitation_codes' not in db:
        db['invitation_codes'] = {}

    # Initialize announcement if it doesn't exist
    if 'announcement' not in db:
        db['announcement'] = get_default_db_structure()['announcement']

    if 'chat_announcement' not in db:
        db['chat_announcement'] = get_default_db_structure()['chat_announcement']

    if 'terminal_announcement' not in db:
        db['terminal_announcement'] = get_default_db_structure()['terminal_announcement']

    # Initialize user_states if they don't exist
    if 'user_states' not in db:
        db['user_states'] = {}

    # Initialize daily_active_users if they don't exist
    if 'daily_active_users' not in db:
        db['daily_active_users'] = {}

    # Initialize sensitive_words if they don't exist
    if 'sensitive_words' not in db:
        db['sensitive_words'] = []

    # Initialize gpu_pool if it doesn't exist
    if 'gpu_pool' not in db:
        db['gpu_pool'] = []

    # Initialize netmind_settings if they don't exist
    if 'netmind_settings' not in db:
        db['netmind_settings'] = {
            'keys': [],
            'ad_suffix': '',
            'ad_enabled': False,
            'enable_alias_mapping': False,
            'base_url': 'https://api.netmind.ai/inference-api/openai/v1', # Default NetMind base URL
            'model_aliases': {},
            'rate_limit_window_seconds': DEFAULT_NETMIND_RATE_LIMIT_WINDOW_SECONDS,
            'rate_limit_max_requests': DEFAULT_NETMIND_RATE_LIMIT_MAX_REQUESTS
        }
    else:
        netmind_settings = db['netmind_settings']
        if 'model_aliases' not in netmind_settings:
            netmind_settings['model_aliases'] = {}
        if 'blacklist' not in netmind_settings:
            netmind_settings['blacklist'] = []
        if 'ad_enabled' not in netmind_settings:
            netmind_settings['ad_enabled'] = False
        if 'enable_alias_mapping' not in netmind_settings:
            netmind_settings['enable_alias_mapping'] = False
        current_window = netmind_settings.get('rate_limit_window_seconds')
        current_limit = netmind_settings.get('rate_limit_max_requests')
        netmind_settings['rate_limit_window_seconds'] = sanitize_rate_limit_window(
            current_window,
            fallback=DEFAULT_NETMIND_RATE_LIMIT_WINDOW_SECONDS
        )
        netmind_settings['rate_limit_max_requests'] = sanitize_rate_limit_max_requests(
            current_limit,
            fallback=DEFAULT_NETMIND_RATE_LIMIT_MAX_REQUESTS
        )

    # Initialize payment_settings if they don't exist
    if 'payment_settings' not in db:
        db['payment_settings'] = get_default_db_structure()['payment_settings']

    if 'orders' not in db:
        db['orders'] = {}

    # Ensure user structure compatibility (Pro fields)
    for user_data in db.get('users', {}).values():
        if 'is_pro' not in user_data:
            user_data['is_pro'] = False
        if 'membership_status' not in user_data:
            user_data['membership_status'] = 'free' # free, pro
        if 'membership_expiry' not in user_data:
            user_data['membership_expiry'] = None
        if 'gumroad_subscriber_id' not in user_data:
            user_data['gumroad_subscriber_id'] = None

    save_db(db)

def backup_db():
    """Backs up the current SQLite database file with a timestamp."""
    db_path = get_db_path()
    backup_dir = os.path.join(current_app.instance_path, 'backups')
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"db_backup_{timestamp}.sqlite"
    backup_path = os.path.join(backup_dir, backup_filename)

    try:
        # Copy the SQLite database file
        import shutil
        shutil.copy2(db_path, backup_path)
        return {"success": True, "message": f"Database backed up to {backup_path}"}
    except Exception as e:
        return {"success": False, "message": str(e)}
