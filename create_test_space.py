import uuid
from project.database import load_db, save_db
from project import create_app

def create_websocket_space():
    app = create_app()
    with app.app_context():
        db = load_db()

        # Ensure the 'spaces' dictionary exists
        if 'spaces' not in db:
            db['spaces'] = {}

        space_name = "Test WebSocket Space"
        space_id = str(uuid.uuid4())
        auth_token = str(uuid.uuid4())

        new_space = {
            'id': space_id,
            'name': space_name,
            'description': 'A space for testing WebSocket connections.',
            'card_type': 'websocket',
            'auth_token': auth_token,
            'allowed_input_types': ['text', 'image'],
            'allowed_output_types': ['text', 'image'],
            'templates': {}
        }

        db['spaces'][space_id] = new_space
        save_db(db)

        print(f"Space Name: {space_name}")
        print(f"Auth Token: {auth_token}")

if __name__ == '__main__':
    create_websocket_space()
