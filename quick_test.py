# -*- coding: utf-8 -*-
from project import create_app
from project.database import load_db, init_db

app = create_app()
app.config['TESTING'] = True

with app.app_context():
    init_db()
    db = load_db()
    spaces = db.get('spaces', {})
    
    if not spaces:
        print("No spaces found!")
    else:
        first_id = list(spaces.keys())[0]
        first_space = spaces[first_id]
        print(f"Space ID: {first_id}")
        print(f"Space name: {first_space.get('name')}")
        print(f"Card type: {first_space.get('card_type')}")
        
        # 测试访问
        with app.test_client() as client:
            try:
                response = client.get(f'/ai_project/{first_id}')
                print(f"\nStatus: {response.status_code}")
                
                if response.status_code == 500:
                    error_text = response.data.decode('utf-8', errors='ignore')
                    if "Traceback" in error_text:
                        # 提取traceback
                        lines = error_text.split('\\n')
                        for i, line in enumerate(lines):
                            if 'Traceback' in line:
                                print('\n'.join(lines[i:min(i+30, len(lines))]))
                                break
                    else:
                        print(error_text[:1000])
            except Exception as e:
                print(f"Exception: {e}")
                import traceback
                traceback.print_exc()
