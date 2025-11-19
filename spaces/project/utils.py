import re
from flask import current_app
from .database import load_db

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
