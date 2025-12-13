#!/usr/bin/env python3
"""Check and initialize database for websocket space"""
import os
import json
import sqlite3
import uuid

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def check_db_files():
    """Check which database file to use"""
    db_files = [
        os.path.join(SCRIPT_DIR, 'instance', 'database.sqlite'),
        os.path.join(SCRIPT_DIR, 'instance', 'app.db'),
    ]
    
    for db_path in db_files:
        if os.path.exists(db_path):
            print(f"Found database: {db_path}")
            try:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cur.fetchall()
                print(f"  Tables: {tables}")
                conn.close()
                
                if ('app_data',) in tables:
                    return db_path
            except Exception as e:
                print(f"  Error: {e}")
    
    return None

def load_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT value FROM app_data WHERE key = 'main_db'")
    row = cur.fetchone()
    conn.close()
    if row:
        return json.loads(row['value'])
    return {"spaces": {}, "users": {}}

def save_db(db_path, data):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    db_json = json.dumps(data, indent=4, ensure_ascii=False)
    cur.execute("INSERT OR REPLACE INTO app_data (key, value) VALUES (?, ?)", ('main_db', db_json))
    conn.commit()
    conn.close()

def create_websocket_space(db_path, name, description):
    db = load_db(db_path)
    
    # Check if space already exists
    for space_id, space in db.get('spaces', {}).items():
        if space.get('name') == name:
            print(f"Space '{name}' already exists with ID: {space_id}")
            return space_id
    
    # Create new space
    space_id = str(uuid.uuid4())
    
    db.setdefault('spaces', {})[space_id] = {
        'id': space_id,
        'name': name,
        'description': description,
        'card_type': 'websockets',
        'created_at': '2024-12-13T00:00:00Z',
        'websockets_config': {
            'enable_prompt': True,
            'enable_audio': False,
            'enable_video': False,
            'enable_file_upload': False
        },
        'liked_by': [],
        'view_count': 0
    }
    
    save_db(db_path, db)
    print(f"Created WebSocket space '{name}' with ID: {space_id}")
    return space_id

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', default='MockImageGen', help='Space name')
    parser.add_argument('--desc', default='测试用模拟图片生成', help='Description')
    args = parser.parse_args()
    
    print("Checking database files...")
    db_path = check_db_files()
    
    if db_path:
        print(f"\nUsing database: {db_path}")
        create_websocket_space(db_path, args.name, args.desc)
    else:
        print("ERROR: Could not find a valid database with app_data table")
        print("Make sure the Flask app has been run at least once to initialize the database.")
