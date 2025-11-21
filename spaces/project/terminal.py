import argparse
import shlex
import uuid
from datetime import datetime
from flask import Blueprint, request, Response, current_app
from werkzeug.security import check_password_hash, generate_password_hash
from .database import load_db, save_db
from .utils import slugify

terminal_bp = Blueprint('terminal', __name__, url_prefix='/terminal')

def is_admin(password):
    """Checks if the provided password matches the admin password."""
    admin_user = load_db().get('users', {}).get('admin')
    if admin_user and 'password' in admin_user:
        return check_password_hash(admin_user['password'], password)
    # Fallback for initial setup or if admin user is not in db
    return password == current_app.config.get('ADMIN_PASSWORD', 'default_admin_pass')

@terminal_bp.route('/admin', methods=['POST'])
def terminal_admin():
    """
    Main entry point for terminal commands.
    Parses commands and dispatches them to handlers.
    """
    admin_password = request.form.get('admin_password')
    if not is_admin(admin_password):
        return Response("Error: Unauthorized.", status=401, mimetype='text/plain')

    command_str = request.form.get('command', '')
    if not command_str:
        return Response("Error: 'command' field is required.", status=400, mimetype='text/plain')

    try:
        # Use shlex to safely split the command string like a shell
        command_parts = shlex.split(command_str)
    except ValueError as e:
        return Response(f"Error parsing command: {e}", status=400, mimetype='text/plain')

    # Create the top-level parser
    parser = argparse.ArgumentParser(
        prog="pumpkinai-admin",
        description="Terminal admin interface.",
        exit_on_error=False # Prevent SystemExit on parsing errors
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands', required=True)

    # --- Define subparsers for each command ---
    users_parser = subparsers.add_parser('users', help='Manage users')
    articles_parser = subparsers.add_parser('articles', help='Manage articles')
    announcement_parser = subparsers.add_parser('announcement', help='Manage announcements')

    # --- Users subparsers ---
    users_parser.add_argument('--list', action='store_true', help='List all users')
    users_parser.add_argument('--create', nargs=2, metavar=('USERNAME', 'PASSWORD'), help='Create a new user')
    users_parser.add_argument('--delete', type=str, metavar='USERNAME', help='Delete a user by username')
    users_parser.add_argument('--grant-admin', type=str, metavar='USERNAME', help='Grant admin privileges to a user')
    users_parser.add_argument('--revoke-admin', type=str, metavar='USERNAME', help='Revoke admin privileges from a user')

    # --- Articles subparsers ---
    articles_parser.add_argument('--list', action='store_true', help='List all articles')
    articles_parser.add_argument('--create', nargs=2, metavar=('TITLE', 'CONTENT'), help='Create a new article')
    articles_parser.add_argument('--delete', type=str, help='Delete an article by its ID')

    # --- Announcement subparsers ---
    announcement_parser.add_argument('--show', action='store_true', help='Show the current announcement')
    announcement_parser.add_argument('--set', nargs='+', metavar=('KEY', 'VALUE'), help='Set an announcement property (e.g., --set title "New Title" enabled True)')

    try:
        args, unknown = parser.parse_known_args(command_parts)

        # Dispatch to command handlers
        if args.command == 'users':
            output = handle_users_command(args)
        elif args.command == 'articles':
            output = handle_articles_command(args)
        elif args.command == 'announcement':
            output = handle_announcement_command(args)
        else:
            # This case should not be reached if 'required=True' is set for subparsers
            output = parser.format_help()

    except argparse.ArgumentError as e:
        # Catches errors from argparse, like missing required arguments
        output = f"Command error: {e}\n\n{parser.format_help()}"

    return Response(output, mimetype='text/plain')

def handle_users_command(args):
    """Handles all user-related terminal commands."""
    db = load_db()
    users = db.get('users', {})

    if args.list:
        if not users:
            return "No users found."

        output = "Users:\n"
        for username, data in users.items():
            is_admin = " (admin)" if data.get('is_admin') else ""
            output += f"- {username}{is_admin}\n"
        return output

    if args.create:
        username, password = args.create
        if username in users:
            return f"Error: User '{username}' already exists."

        users[username] = {
            'password_hash': generate_password_hash(password),
            'is_admin': False
        }
        save_db(db)
        return f"User '{username}' created successfully."

    if args.delete:
        username_to_delete = args.delete
        if username_to_delete in users:
            del users[username_to_delete]
            save_db(db)
            return f"User '{username_to_delete}' deleted successfully."
        else:
            return f"Error: User '{username_to_delete}' not found."

    if args.grant_admin:
        username = args.grant_admin
        if username in users:
            users[username]['is_admin'] = True
            save_db(db)
            return f"Admin privileges granted to '{username}'."
        else:
            return f"Error: User '{username}' not found."

    if args.revoke_admin:
        username = args.revoke_admin
        if username in users:
            users[username]['is_admin'] = False
            save_db(db)
            return f"Admin privileges revoked from '{username}'."
        else:
            return f"Error: User '{username}' not found."

    return "No user command specified. Use --list, --create, --delete, --grant-admin, or --revoke-admin."

def handle_articles_command(args):
    """Handles all article-related terminal commands."""
    db = load_db()
    if 'articles' not in db:
        db['articles'] = {}

    if args.list:
        articles = db['articles']
        if not articles:
            return "No articles found."

        output = "Articles:\n"
        for article_id, data in articles.items():
            output += f"- ID: {article_id}, Title: {data.get('title', 'N/A')}\n"
        return output

    if args.create:
        title, content = args.create
        new_id = str(uuid.uuid4())
        slug = slugify(title)

        all_slugs = {a.get('slug') for a in db.get('articles', {}).values()}
        if slug in all_slugs:
            slug = f"{slug}-{new_id[:4]}"

        db['articles'][new_id] = {
            'id': new_id,
            'title': title,
            'content': content,
            'slug': slug,
            'author': 'admin',
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
        }
        save_db(db)
        return f"Article '{title}' created with ID: {new_id}"

    if args.delete:
        article_id_to_delete = args.delete
        if article_id_to_delete in db['articles']:
            del db['articles'][article_id_to_delete]
            save_db(db)
            return f"Article with ID '{article_id_to_delete}' deleted successfully."
        else:
            return f"Error: Article with ID '{article_id_to_delete}' not found."

    return "No article command specified. Use --list, --create, or --delete."

def handle_announcement_command(args):
    """Handles all announcement-related terminal commands."""
    db = load_db()
    announcement = db.get('announcement', {})

    if args.show:
        if not announcement:
            return "No announcement set."

        output = "Current Announcement:\n"
        for key, value in announcement.items():
            output += f"- {key}: {value}\n"
        return output

    if args.set:
        key_value_pairs = args.set
        if len(key_value_pairs) % 2 != 0:
            return "Error: --set requires an even number of arguments (key value pairs)."

        for i in range(0, len(key_value_pairs), 2):
            key = key_value_pairs[i]
            value = key_value_pairs[i+1]

            # Basic type conversion for boolean values
            if value.lower() in ['true', 't', 'yes', 'y']:
                announcement[key] = True
            elif value.lower() in ['false', 'f', 'no', 'n']:
                announcement[key] = False
            else:
                announcement[key] = value

        db['announcement'] = announcement
        save_db(db)
        return "Announcement updated successfully."

    return "No announcement command specified. Use --show or --set."
