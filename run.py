from project import create_app, socketio
from project.database import init_db, backup_db
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = create_app()

# Initialize the database within the application context
with app.app_context():
    init_db()

# Scheduler for automatic database backups
def run_backup():
    with app.app_context():
        backup_db()

scheduler = BackgroundScheduler()
scheduler.add_job(func=run_backup, trigger="interval", days=1)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

if __name__ == '__main__':
    # Use socketio.run to support WebSocket connections.
    # allow_unsafe_werkzeug=True is required for debug mode with Werkzeug > 2.2
    # In a production environment, you would use a proper WSGI server like Gunicorn or uWSGI.
    socketio.run(app, host='0.0.0.0', port=5001, debug=False, allow_unsafe_werkzeug=True)
