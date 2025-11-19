



import os
from project import create_app
from project.database import load_db, save_db, init_db
from werkzeug.security import generate_password_hash
import uuid
from datetime import datetime

def grant_admin_privileges(username='admin'):
    """
    Initializes the database and grants admin privileges to the specified user.
    If the user does not exist, it creates them with admin rights.
    """
    app = create_app()

    with app.app_context():
        # Initialize the database to ensure it's set up correctly
        init_db()

        db = load_db()

        # Check if the user exists
        if username in db['users']:
            # Grant admin privileges by setting the flag
            db['users'][username]['is_admin'] = True
            save_db(db)
            print(f"成功为现有用户 '{username}' 授予了管理员权限。")
        else:
            # If the user doesn't exist, create them with admin privileges
            print(f"未找到用户 '{username}'。正在创建一个新的管理员用户...")

            # 设置一个默认密码，您之后应该修改它
            password = 'admin'
            password_hash = generate_password_hash(password)

            db['users'][username] = {
                'password_hash': password_hash,
                'api_key': str(uuid.uuid4()),
                'has_invitation_code': False,
                'is_linuxdo_user': False,
                'is_github_user': False,
                'created_at': datetime.utcnow().isoformat(),
                'deletion_requested': False,
                'avatar': 'default.png',
                'is_admin': True  # Directly set admin privileges upon creation
            }
            save_db(db)
            print(f"成功创建了新的管理员用户 '{username}'。初始密码是 '{password}'。")


if __name__ == '__main__':
    admin_username = 'admin'
    print(f"正在尝试为用户 '{admin_username}' 授予管理员权限...")
    grant_admin_privileges(admin_username)