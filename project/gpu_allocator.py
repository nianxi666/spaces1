import uuid
import time
from .database import save_db

def try_allocate_gpu_from_pool(db, username):
    """
    Attempts to allocate a GPU from the pool to the specified user.
    Returns True if allocated, False otherwise.
    """
    # 1. Check if user exists and needs a GPU
    user = db.get('users', {}).get(username)
    if not user:
        return False

    # Check if user already has any GPU config
    if user.get('cerebrium_configs'):
        return False

    # 2. Check if pool has available GPUs
    pool = db.get('gpu_pool', [])
    if not pool:
        return False

    # 3. Allocate: Pop the first one
    gpu_config = pool.pop(0) # FIFO

    # 4. Add to user configs
    # The pool structure has 'name', 'api_url', 'api_token', 'id'
    # The user config structure expects 'name', 'api_url', 'api_token', 'id', 'created_at'

    # We can reuse the same object, maybe update 'created_at' to reflect assignment time
    gpu_config['created_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    # Remove 'added_at' if it exists to clean up
    gpu_config.pop('added_at', None)

    if 'cerebrium_configs' not in user:
        user['cerebrium_configs'] = []

    user['cerebrium_configs'].append(gpu_config)

    # 5. Send system message to chat
    if db.get('settings', {}).get('chat_enabled', True):
        # Bilingual message
        gpu_name = gpu_config.get('name', 'Cloud GPU')
        msg_content = (
            f"系统自动分配 System Allocation:\n"
            f"已为用户 @{username} 分配 {gpu_name}。\n"
            f"Allocated {gpu_name} to @{username}."
        )

        new_message = {
            'id': str(uuid.uuid4()),
            'username': 'System', # System sender
            'content': msg_content,
            'timestamp': time.time(),
            'avatar': 'default.png' # Ensure system has an avatar or handle it in frontend
        }

        # If 'System' isn't a real user, we might want to fake the avatar in frontend or add a System user.
        # Ideally, we should check if 'System' user exists or just let the frontend handle missing user.
        # But 'username' field in chat usually links to user profile.
        # Let's use 'Admin' or a dedicated system name. 'System' is fine if frontend handles it.
        # Given existing code, let's look at how Admin sends messages.

        if 'chat_messages' not in db:
            db['chat_messages'] = []

        db['chat_messages'].append(new_message)

        # Archiving logic
        if len(db['chat_messages']) > 99:
            if 'chat_history' not in db:
                db['chat_history'] = []
            db['chat_history'].append(db['chat_messages'].pop(0))

    # 6. Save DB
    save_db(db)
    return True
