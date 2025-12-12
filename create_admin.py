from project import create_app
from project.database import load_db, save_db
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    db = load_db()
    if 'users' not in db:
        db['users'] = {}
    db['users']['testadmin'] = {
        'password_hash': generate_password_hash('password'),
        'is_admin': True,
        'username': 'testadmin',
        's3_folder_name': 'testadmin',
        'check_in_history': []
    }
    save_db(db)
    print("Admin user 'testadmin' created successfully.")
