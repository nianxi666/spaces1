# -*- coding: utf-8 -*-
"""
Modal Drive Utilities
用于 Modal Drive（无限容量网盘）功能的工具函数
"""

import os
from flask import session
from .database import load_db, save_db


def get_modal_drive_credentials():
    """
    获取 Modal Drive 的凭据配置
    
    Returns:
        tuple: (base_url, token) 或 (None, None) 如果未配置
    """
    db = load_db()
    modal_drive_config = db.get('modal_drive_config', {})
    
    base_url = modal_drive_config.get('base_url', '').strip()
    token = modal_drive_config.get('token', '').strip()
    
    if not base_url or not token:
        return None, None
    
    return base_url, token


def get_drive_username():
    """
    获取当前用户的网盘用户名
    
    Returns:
        str: 用户名，如果未登录则返回 None
    """
    if not session.get('logged_in'):
        return None
    
    username = session.get('username')
    if not username:
        return None
    
    # 可以在这里添加用户名映射逻辑
    # 例如：使用 s3_folder_name 或其他自定义字段
    db = load_db()
    user_data = db.get('users', {}).get(username, {})
    
    # 优先使用 s3_folder_name，如果没有则使用 username
    drive_username = user_data.get('s3_folder_name') or username
    
    return drive_username


def build_user_full_path(relative_path):
    """
    构建用户的完整路径（在网盘中）
    
    Args:
        relative_path: 相对路径（用户提供的路径）
    
    Returns:
        str: 完整路径（包含用户目录前缀）
    
    Raises:
        ValueError: 如果路径无效
    """
    username = get_drive_username()
    if not username:
        raise ValueError('无法确定用户目录')
    
    # 规范化相对路径
    relative_path = normalize_relative_path(relative_path)
    
    # 构建完整路径：username/relative_path
    if relative_path:
        full_path = f"{username}/{relative_path}"
    else:
        full_path = username
    
    return full_path


def normalize_relative_path(path):
    """
    规范化相对路径
    
    Args:
        path: 原始路径
    
    Returns:
        str: 规范化后的路径
    
    Raises:
        ValueError: 如果路径包含非法字符或试图访问父目录
    """
    if not path:
        return ''
    
    # 移除前后空格
    path = path.strip()
    
    # 移除开头的斜杠
    path = path.lstrip('/')
    
    # 检查路径遍历攻击
    if '..' in path:
        raise ValueError('路径不能包含 ".."')
    
    # 检查绝对路径
    if os.path.isabs(path):
        raise ValueError('不支持绝对路径')
    
    # 规范化路径分隔符（统一使用 /）
    path = path.replace('\\', '/')
    
    # 移除多余的斜杠
    parts = [p for p in path.split('/') if p]
    path = '/'.join(parts)
    
    return path


def filter_user_items(items):
    """
    过滤网盘项目列表，只返回当前用户的文件
    
    Args:
        items: 所有项目的列表
    
    Returns:
        list: 过滤后的项目列表
    """
    username = get_drive_username()
    if not username:
        return []
    
    user_prefix = f"{username}/"
    filtered = []
    
    for item in items:
        path = item.get('path', '')
        
        # 只保留属于当前用户的项目
        if path.startswith(user_prefix):
            # 移除用户名前缀，只保留相对路径
            relative_path = path[len(user_prefix):]
            
            # 创建新的项目副本，包含相对路径
            filtered_item = item.copy()
            filtered_item['relative_path'] = relative_path
            filtered_item['display_path'] = relative_path or '/'
            
            filtered.append(filtered_item)
    
    return filtered


def ensure_share_storage():
    """
    确保数据库中存在分享存储结构
    
    Returns:
        tuple: (db, shares) - 数据库对象和分享字典
    """
    db = load_db()
    
    if 'modal_drive_shares' not in db:
        db['modal_drive_shares'] = {}
    
    shares = db['modal_drive_shares']
    
    return db, shares


def get_user_quota_info(username=None):
    """
    获取用户的配额信息
    
    Args:
        username: 用户名，如果为 None 则使用当前登录用户
    
    Returns:
        dict: 配额信息 {'used': bytes, 'total': bytes, 'unlimited': bool}
    """
    if username is None:
        username = get_drive_username()
    
    if not username:
        return {'used': 0, 'total': 0, 'unlimited': False}
    
    # Modal Drive 通常是无限容量，这里返回默认值
    # 如果需要实际配额，需要调用 Modal Drive API
    return {
        'used': 0,
        'total': -1,  # -1 表示无限
        'unlimited': True
    }


def validate_filename(filename):
    """
    验证文件名是否合法
    
    Args:
        filename: 文件名
    
    Returns:
        bool: 是否合法
    
    Raises:
        ValueError: 如果文件名非法，抛出异常并说明原因
    """
    if not filename:
        raise ValueError('文件名不能为空')
    
    # 禁止的字符
    forbidden_chars = ['<', '>', ':', '"', '|', '?', '*', '\0']
    for char in forbidden_chars:
        if char in filename:
            raise ValueError(f'文件名不能包含字符: {char}')
    
    # 禁止的文件名
    forbidden_names = [
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    ]
    
    name_without_ext = filename.rsplit('.', 1)[0].upper()
    if name_without_ext in forbidden_names:
        raise ValueError(f'文件名 "{filename}" 是保留名称')
    
    # 文件名长度限制
    if len(filename) > 255:
        raise ValueError('文件名过长（最多255个字符）')
    
    return True
