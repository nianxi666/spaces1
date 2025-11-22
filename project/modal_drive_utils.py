import posixpath
from flask import current_app, session
from .database import load_db


def get_modal_drive_credentials():
    """
    Return (base_url, token) loaded from DB settings with config fallback.
    """
    base_url = current_app.config.get('MODAL_DRIVE_BASE_URL')
    token = current_app.config.get('MODAL_DRIVE_AUTH_TOKEN')

    db = load_db()
    settings = db.get('settings', {})
    base_url = settings.get('modal_drive_base_url') or base_url
    token = settings.get('modal_drive_auth_token') or token

    if base_url:
        base_url = base_url.rstrip('/')
    return base_url, token


def get_drive_username():
    """
    Sanitize current username for drive usage.
    """
    username = session.get('username')
    if not username:
        return None
    safe = username.strip().replace('/', '_').replace('\\', '_')
    return safe or 'user'


def normalize_relative_path(path: str) -> str:
    rel = (path or '').strip().replace('\\', '/')
    rel = rel.lstrip('/')
    if not rel:
        return ''
    normalized = posixpath.normpath(rel)
    if normalized in ('', '.'):
        return ''
    if normalized.startswith('../'):
        raise ValueError('非法路径')
    return normalized


def build_user_full_path(relative_path: str) -> str:
    """
    Build the absolute path inside Modal Drive for current user.
    """
    user_root = get_drive_username()
    if not user_root:
        raise ValueError('无法确定用户网盘')
    rel = normalize_relative_path(relative_path)
    combined = posixpath.normpath(posixpath.join('/', user_root, rel))
    prefix = f'/{user_root}'
    if not combined.startswith(prefix):
        raise ValueError('非法路径')
    return combined.lstrip('/')


def filter_user_items(all_items):
    """
    Reduce /api/all results to current user's namespace and strip the prefix.
    """
    user_root = get_drive_username()
    if not user_root:
        return []

    prefix = f'{user_root}/'
    filtered = []
    for entry in all_items or []:
        path = entry.get('path') or ''
        if path == user_root:
            continue
        if not path.startswith(prefix):
            continue
        rel_path = path[len(prefix):]
        if not rel_path:
            continue
        filtered.append({
            'path': rel_path,
            'is_dir': entry.get('is_dir', False),
            'size': entry.get('size', 0),
            'mtime': entry.get('mtime', 0)
        })
    return filtered


def ensure_share_storage():
    db = load_db()
    shares = db.setdefault('modal_drive_shares', {})
    return db, shares
