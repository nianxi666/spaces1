import re
from datetime import datetime
from flask import current_app
from .database import load_db, save_db

def update_pro_status(user, db=None):
    """
    Checks if the user's Pro membership has expired.
    If expired, sets is_pro to False.
    Returns True if user is Pro, False otherwise.
    """
    if not user:
        return False

    is_pro = user.get('is_pro', False)
    if not is_pro:
        return False

    expiry_str = user.get('membership_expiry')
    if not expiry_str:
        # If is_pro is True but no expiry, it might be a permanent manual grant or legacy.
        # We can decide to keep it or force expiry.
        # For now, let's assume if no expiry is set but is_pro is True, they stay Pro (Legacy/Admin grant).
        return True

    try:
        expiry_date = datetime.fromisoformat(expiry_str)
        if datetime.utcnow() > expiry_date:
            user['is_pro'] = False
            # Only save if we have the db reference, otherwise caller needs to handle save
            if db:
                save_db(db)
            return False
    except ValueError:
        pass

    return True

def get_user_by_token(token):
    """
    Retrieves a user from the database based on their API token.
    """
    db = load_db()
    for username, user_data in db.get('users', {}).items():
        if user_data.get('api_key') == token:
            # Return a copy of the user data along with the username
            return {'username': username, **user_data}
    return None

def allowed_file(filename):
    """Allows any file to be uploaded."""
    return True

def predict_output_filename(prompt, seed=None):
    """
    Always predicts 'output.png' as the filename, as requested by the user.
    """
    return "output.png"

def slugify(text):
    """
    Convert a string to a URL-friendly slug.
    Example: "Hello World! 123" -> "hello-world-123"
    """
    if not text:
        return ""
    # Convert to lowercase
    text = text.lower()
    # Replace non-alphanumeric characters with a hyphen
    text = re.sub(r'[^a-z0-9]+', '-', text)
    # Remove leading/trailing hyphens
    return text.strip('-')
