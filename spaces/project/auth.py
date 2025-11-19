import re
import uuid
import os
from flask import (
    Blueprint, render_template, request, redirect, url_for, session, flash, current_app
)
from werkzeug.security import generate_password_hash, check_password_hash
from .database import load_db, save_db
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = load_db()
        user = db['users'].get(username)
        if user and check_password_hash(user['password_hash'], password):
            admin_status = user.get('is_admin', False)
            print(f"--- 登录诊断信息 ---")
            print(f"用户 '{username}' 正在登录。")
            print(f"从数据库读取到的 is_admin 状态是: {admin_status}")
            print(f"--------------------")
            session.permanent = True  # Make the session permanent
            session['logged_in'] = True
            session['username'] = username
            session['is_admin'] = admin_status
            session['user_avatar'] = user.get('avatar', 'default.png')
            flash('登录成功!', 'success')
            return redirect(url_for('main.index'))
        else:
            return render_template('login.html', error='无效的凭据')
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = load_db()

        if username in db['users']:
            return render_template('register.html', error='用户名已存在')
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            return render_template('register.html', error='用户名只能包含字母、数字和下划线')

        api_key = str(uuid.uuid4())
        db['users'][username] = {
            'password_hash': generate_password_hash(password),
            'api_key': api_key,
            'has_invitation_code': False,
            'is_linuxdo_user': False,
            'is_github_user': False,
            'created_at': datetime.utcnow().isoformat(),
            'deletion_requested': False,
            'avatar': 'default.png',
            'cerebrium_configs': []
        }

        # 自动创建用户目录
        user_pan_dir = os.path.join(current_app.instance_path, current_app.config['RESULTS_FOLDER'], username)
        os.makedirs(user_pan_dir, exist_ok=True)

        save_db(db)

        flash('注册成功! 现在可以登录了。', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html')

@auth_bp.route('/delete_account', methods=['POST'])
def delete_account():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    username = session.get('username')
    db = load_db()

    if username and username in db['users']:
        db['users'][username]['deletion_requested'] = True
        save_db(db)
        flash('您的删除请求已提交，管理员将进行审核。', 'success')
        session.clear()
        return redirect(url_for('auth.login'))

    flash('无法处理您的请求。', 'error')
    return redirect(url_for('main.index'))

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('您已退出登录。', 'success')
    return redirect(url_for('auth.login'))
