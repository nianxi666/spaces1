import os
import json
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request
from datetime import datetime

def format_datetime(value, format='%Y-%m-%d %H:%M'):
    if value:
        try:
            dt_obj = datetime.fromisoformat(value)
            return dt_obj.strftime(format)
        except (ValueError, TypeError):
            return value
    return "N/A"

def create_app(test_config=None):
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, instance_relative_config=True)

    # Load configuration from the project.config module
    app.config.from_object('project.config')

    if test_config is not None:
        # Load the test config if passed in, overriding default config
        app.config.from_mapping(test_config)

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass # Already exists

    # Setup file-based logging
    if not app.debug and not app.testing:
        log_file = os.path.join(app.root_path, '../error.log')
        file_handler = RotatingFileHandler(log_file, maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.ERROR)
        app.logger.addHandler(file_handler)

    # Import and register blueprints
    from . import auth
    app.register_blueprint(auth.auth_bp)

    from . import main
    app.register_blueprint(main.main_bp)

    from . import admin
    app.register_blueprint(admin.admin_bp)

    from . import results
    app.register_blueprint(results.results_bp)

    from . import api
    app.register_blueprint(api.api_bp)

    from . import terminal
    app.register_blueprint(terminal.terminal_bp)

    # Register custom Jinja2 filters
    app.jinja_env.filters['format_datetime'] = format_datetime

    import markdown
    from markupsafe import Markup
    app.jinja_env.filters['markdown'] = lambda text: Markup(markdown.markdown(text, extensions=['fenced_code', 'tables']))

    from .database import load_db, save_db
    from flask import session
    from datetime import timedelta

    @app.before_request
    def before_request_handler():
        # We don't need to run this for static files
        if request.blueprint == 'static' or not request.endpoint:
             return

        if 'username' in session:
            db = load_db()
            user = db.get('users', {}).get(session['username'])
            if user:
                now = datetime.utcnow()
                last_seen_iso = user.get('last_seen')

                update_threshold_seconds = 60 # Only update every 60 seconds

                needs_update = True
                if last_seen_iso:
                    try:
                        last_seen_dt = datetime.fromisoformat(last_seen_iso)
                        if now - last_seen_dt < timedelta(seconds=update_threshold_seconds):
                            needs_update = False
                    except (ValueError, TypeError):
                        pass # If format is invalid, update it anyway

                # Track daily active users
                today_str = now.strftime('%Y-%m-%d')
                if 'daily_active_users' not in db:
                    db['daily_active_users'] = {}

                if today_str not in db['daily_active_users']:
                    db['daily_active_users'][today_str] = []

                if session['username'] not in db['daily_active_users'][today_str]:
                    db['daily_active_users'][today_str].append(session['username'])
                    needs_update = True

                if needs_update:
                    user['last_seen'] = now.isoformat()
                    save_db(db)

    # A context processor to inject settings into all templates
    @app.context_processor
    def inject_settings():
        # Using a try-except block to prevent errors during initial setup
        try:
            settings = load_db().get('settings', {})
            return dict(settings=settings)
        except Exception:
            return dict(settings={})

    from .s3_utils import get_public_s3_url
    @app.context_processor
    def inject_s3_url_processor():
        def to_s3_url(key):
            return get_public_s3_url(key)
        return dict(to_s3_url=to_s3_url)

    # Context processor to inject S3 settings globally
    @app.context_processor
    def inject_s3_settings():
        s3_settings = {}
        S3_CONFIG_FILE = app.config.get('S3_CONFIG_FILE')
        if S3_CONFIG_FILE and os.path.exists(S3_CONFIG_FILE):
            try:
                with open(S3_CONFIG_FILE, 'r') as f:
                    s3_settings = json.load(f)
            except (IOError, json.JSONDecodeError):
                # In case of error, s3_settings remains empty
                pass
        return dict(s3_settings=s3_settings)

    return app