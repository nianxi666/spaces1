# Eventlet monkey patching must be done first
import eventlet
eventlet.monkey_patch()

from project import create_app
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

# Get the socketio instance if it was created
socketio = getattr(app, 'socketio', None)

if __name__ == '__main__':
    # Setting debug=False is important for production to avoid running the scheduler twice
    print(f"[RUN.PY] socketio object: {socketio}")
    if socketio:
        print("[RUN.PY] Using socketio.run()")
        socketio.run(app, host='0.0.0.0', port=5001, debug=False)
    else:
        print("[RUN.PY] Using app.run() - WebSockets may not work!")
        app.run(host='0.0.0.0', port=5001, debug=False)
