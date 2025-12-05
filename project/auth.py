import re
import uuid
import os
import requests
import secrets
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
            'cerebrium_configs': [],
            'is_member': False,
            'member_expiry_date': None,
            'payment_history': []
        }

        # 自动创建用户目录
        user_pan_dir = os.path.join(current_app.instance_path, current_app.config['RESULTS_FOLDER'], username)
        os.makedirs(user_pan_dir, exist_ok=True)

        save_db(db)

        flash('注册成功! 现在可以登录了。', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html')

@auth_bp.route('/auth/github/login')
def github_login():
    github_client_id = current_app.config['GITHUB_CLIENT_ID']
    redirect_uri = url_for('auth.github_callback', _external=True)

    # Force HTTPS if not already (for production behind proxies), unless on localhost
    if redirect_uri.startswith('http://') and '127.0.0.1' not in redirect_uri and 'localhost' not in redirect_uri:
        redirect_uri = redirect_uri.replace('http://', 'https://', 1)

    state = secrets.token_urlsafe(16)
    session['oauth_state'] = state

    url = (
        f"https://github.com/login/oauth/authorize?"
        f"client_id={github_client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"state={state}&"
        f"scope=read:user"
    )
    return redirect(url)

@auth_bp.route('/auth/github/callback')
def github_callback():
    code = request.args.get('code')
    state = request.args.get('state')

    if state != session.get('oauth_state'):
        flash('GitHub 授权状态验证失败，请重试', 'error')
        return redirect(url_for('auth.login'))

    github_client_id = current_app.config['GITHUB_CLIENT_ID']
    github_client_secret = current_app.config['GITHUB_CLIENT_SECRET']

    # 交换 token
    token_url = "https://github.com/login/oauth/access_token"
    headers = {'Accept': 'application/json'}
    data = {
        'client_id': github_client_id,
        'client_secret': github_client_secret,
        'code': code
    }

    response = requests.post(token_url, headers=headers, data=data)
    if response.status_code != 200:
        flash('无法获取 GitHub 访问令牌', 'error')
        return redirect(url_for('auth.login'))

    token_data = response.json()
    access_token = token_data.get('access_token')

    if not access_token:
        flash('GitHub 授权失败', 'error')
        return redirect(url_for('auth.login'))

    # 获取用户信息
    user_url = "https://api.github.com/user"
    user_headers = {
        'Authorization': f'token {access_token}',
        'Accept': 'application/json'
    }

    user_response = requests.get(user_url, headers=user_headers)
    if user_response.status_code != 200:
        flash('无法获取 GitHub 用户信息', 'error')
        return redirect(url_for('auth.login'))

    github_user = user_response.json()
    github_id = str(github_user.get('id'))
    github_login_name = github_user.get('login') # username
    github_avatar = github_user.get('avatar_url')

    db = load_db()

    # 1. 检查是否有用户已经绑定了这个 github_id
    target_username = None
    for username, user_data in db['users'].items():
        if str(user_data.get('github_id', '')) == github_id:
            target_username = username
            break

    # 2. 如果没有绑定，检查用户名冲突并创建/关联用户 (方案 A: 自动改名)
    if not target_username:
        target_username = github_login_name

        # 只有当该用户名已被占用且没有绑定当前 GitHub ID 时才需要改名
        # 如果用户名存在但没有 github_id 字段 (老用户)，我们视为冲突，进行改名
        # 如果用户名存在且有别的 github_id (冲突)，进行改名

        original_username = target_username
        counter = 1
        while target_username in db['users']:
            # 这是一个新用户，但名字被占用了
            target_username = f"{original_username}_gh_{counter}"
            counter += 1

        # 创建新用户
        api_key = str(uuid.uuid4())
        # 生成一个随机密码，GitHub 用户不需要知道这个密码，但为了保持兼容性
        random_password = secrets.token_urlsafe(32)

        db['users'][target_username] = {
            'password_hash': generate_password_hash(random_password),
            'api_key': api_key,
            'has_invitation_code': False,
            'is_linuxdo_user': False,
            'is_github_user': True,
            'github_id': github_id,
            'github_original_login': github_login_name,
            'created_at': datetime.utcnow().isoformat(),
            'deletion_requested': False,
            'avatar': github_avatar if github_avatar else 'default.png',
            'cerebrium_configs': [],
            'is_member': False,
            'member_expiry_date': None,
            'payment_history': []
        }

        # 自动创建用户目录
        user_pan_dir = os.path.join(current_app.instance_path, current_app.config['RESULTS_FOLDER'], target_username)
        os.makedirs(user_pan_dir, exist_ok=True)

        save_db(db)
        flash(f'欢迎! 您的账户 {target_username} 已创建。', 'success')
    else:
        # 老用户登录，更新头像 (可选)
        if github_avatar:
             db['users'][target_username]['avatar'] = github_avatar
             save_db(db)
        flash(f'欢迎回来, {target_username}!', 'success')

    # 执行登录
    user = db['users'][target_username]
    admin_status = user.get('is_admin', False)

    session.permanent = True
    session['logged_in'] = True
    session['username'] = target_username
    session['is_admin'] = admin_status
    session['user_avatar'] = user.get('avatar', 'default.png')

    return redirect(url_for('main.index'))

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
