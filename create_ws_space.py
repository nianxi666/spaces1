from project import create_app
from project.database import load_db, save_db
import uuid

app = create_app()

with app.app_context():
    db = load_db()
    if 'spaces' not in db:
        db['spaces'] = {}

    space_id = str(uuid.uuid4())
    auth_token = str(uuid.uuid4())

    db['spaces'][space_id] = {
        'id': space_id,
        'name': 'TestWS',
        'card_type': 'websocket',
        'auth_token': auth_token,
        'allowed_input_types': ['text'],
        'allowed_output_types': ['text']
    }
    save_db(db)
    print(f"Space ID: {space_id}")
    print(f"Auth Token: {auth_token}")
