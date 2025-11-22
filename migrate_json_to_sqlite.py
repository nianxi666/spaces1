import os
import json
import sys
from flask import Flask
import project.config as config
from project.database import save_db, get_db_path

# Create a Flask app context to access the configuration
app = Flask(__name__)
app.config.from_object(config)
app.instance_path = os.path.join(os.path.dirname(__file__), 'instance')
app.root_path = os.path.join(os.path.dirname(__file__), 'project')

def migrate_json_to_sqlite():
    """Migrate data from a JSON file to the SQLite database."""

    # Path to your existing JSON database
    json_db_path = os.path.join(app.instance_path, 'database.json')

    if not os.path.exists(json_db_path):
        print(f"Error: JSON database file not found at {json_db_path}")
        return False

    try:
        # Load the JSON data
        with open(json_db_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)

        print("Loaded JSON data with:")
        print(f"- {len(json_data.get('users', {}))} users")
        print(f"- {len(json_data.get('spaces', {}))} spaces")
        print(f"- {len(json_data.get('uploaded_files', {}))} uploaded files")
        print(f"- {len(json_data.get('chat_messages', []))} chat messages")

        # Save the data to SQLite within an application context
        print("Migrating data to SQLite...")
        with app.app_context():
            # Ensure the target database file doesn't exist to start fresh
            sqlite_path = get_db_path()
            if os.path.exists(sqlite_path):
                os.remove(sqlite_path)
                print(f"Removed existing SQLite database at {sqlite_path}")

            save_db(json_data)

            print("Migration completed successfully!")
            print(f"Your data has been transferred to {get_db_path()}")
        return True

    except Exception as e:
        print(f"Error during migration: {e}")
        return False

if __name__ == '__main__':
    print("Starting migration from JSON to SQLite...")
    success = migrate_json_to_sqlite()
    if success:
        print("\nMigration completed! You can now run your application with the local SQLite database.")
        print("Note: Your original JSON file remains intact as a backup.")
    else:
        print("\nMigration failed. Please check the error messages above.")
        sys.exit(1)
