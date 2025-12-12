# -*- coding: utf-8 -*-
"""
WebSocket 上传处理端点 - 服务器端代码

将此代码添加到您的 Flask 应用中，用于接收来自远程 webui.py 的 WebSocket 上传

需要安装: pip install flask-socketio

使用方法:
1. 将此文件导入到您的 Flask 应用
2. 在主应用中初始化 SocketIO
3. 配置 S3 存储桶
"""

import os
import uuid
import base64
import time
from flask import Blueprint, request, current_app
from flask_socketio import emit, disconnect

# 存储进行中的上传任务
active_uploads = {}

# 上传超时时间（秒）
UPLOAD_TIMEOUT = 300  # 5分钟


def create_ws_upload_blueprint(socketio, s3_utils):
    """
    创建 WebSocket 上传蓝图
    
    Args:
        socketio: Flask-SocketIO 实例
        s3_utils: S3 工具模块（需要有 upload_file_to_s3 和 get_public_s3_url 函数）
    """
    
    ws_bp = Blueprint('ws_upload', __name__)
    
    @socketio.on('connect', namespace='/ws/upload')
    def handle_connect():
        """处理 WebSocket 连接"""
        # 验证 API Key
        api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not api_key:
            emit('error', {'message': 'Missing API key'})
            disconnect()
            return
        
        # 验证 API Key（您需要实现这个函数）
        from .database import load_db
        db = load_db()
        
        user = None
        for username, user_data in db.get('users', {}).items():
            if user_data.get('api_key') == api_key:
                user = username
                break
        
        if not user:
            emit('error', {'message': 'Invalid API key'})
            disconnect()
            return
        
        # 存储用户信息到会话
        request.sid_user = user
        print(f"[WS Upload] User {user} connected")
        emit('connected', {'message': 'Connected successfully', 'user': user})
    
    @socketio.on('disconnect', namespace='/ws/upload')
    def handle_disconnect():
        """处理断开连接"""
        user = getattr(request, 'sid_user', 'unknown')
        print(f"[WS Upload] User {user} disconnected")
        
        # 清理该用户未完成的上传
        to_delete = []
        for upload_id, upload_info in active_uploads.items():
            if upload_info.get('user') == user:
                to_delete.append(upload_id)
        
        for upload_id in to_delete:
            cleanup_upload(upload_id)
    
    @socketio.on('start_upload', namespace='/ws/upload')
    def handle_start_upload(data):
        """
        开始上传
        
        期望数据:
        {
            "filename": "output.wav",
            "file_size": 12345,
            "content_type": "audio/wav"
        }
        """
        user = getattr(request, 'sid_user', None)
        if not user:
            emit('error', {'status': 'error', 'error': 'Not authenticated'})
            return
        
        filename = data.get('filename')
        file_size = data.get('file_size', 0)
        content_type = data.get('content_type', 'application/octet-stream')
        
        if not filename:
            emit('error', {'status': 'error', 'error': 'Missing filename'})
            return
        
        # 创建上传 ID
        upload_id = str(uuid.uuid4())
        
        # 创建临时文件路径
        temp_dir = os.path.join(current_app.instance_path, 'ws_uploads')
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"{upload_id}_{filename}")
        
        # 存储上传信息
        active_uploads[upload_id] = {
            'user': user,
            'filename': filename,
            'file_size': file_size,
            'content_type': content_type,
            'temp_path': temp_path,
            'received_bytes': 0,
            'chunks': [],
            'start_time': time.time(),
            'file_handle': open(temp_path, 'wb')
        }
        
        print(f"[WS Upload] Started upload {upload_id} for {user}: {filename} ({file_size} bytes)")
        
        emit('ready', {
            'status': 'ready',
            'upload_id': upload_id,
            'message': 'Ready to receive chunks'
        })
    
    @socketio.on('upload_chunk', namespace='/ws/upload')
    def handle_upload_chunk(data):
        """
        接收上传块
        
        期望数据:
        {
            "upload_id": "xxx",
            "chunk_index": 0,
            "data": "base64_encoded_data",
            "is_last": false
        }
        """
        upload_id = data.get('upload_id')
        chunk_index = data.get('chunk_index', 0)
        chunk_data_b64 = data.get('data', '')
        is_last = data.get('is_last', False)
        
        if upload_id not in active_uploads:
            emit('error', {'status': 'error', 'error': 'Invalid upload ID'})
            return
        
        upload_info = active_uploads[upload_id]
        
        # 检查超时
        if time.time() - upload_info['start_time'] > UPLOAD_TIMEOUT:
            cleanup_upload(upload_id)
            emit('error', {'status': 'error', 'error': 'Upload timeout'})
            return
        
        try:
            # 解码 base64 数据
            chunk_data = base64.b64decode(chunk_data_b64)
            
            # 写入临时文件
            upload_info['file_handle'].write(chunk_data)
            upload_info['received_bytes'] += len(chunk_data)
            upload_info['chunks'].append(chunk_index)
            
            # 计算进度
            progress = 0
            if upload_info['file_size'] > 0:
                progress = int((upload_info['received_bytes'] / upload_info['file_size']) * 100)
            
            emit('chunk_ack', {
                'status': 'ok',
                'chunk_index': chunk_index,
                'received_bytes': upload_info['received_bytes'],
                'progress': progress
            })
            
        except Exception as e:
            emit('error', {'status': 'error', 'error': f'Chunk error: {str(e)}'})
    
    @socketio.on('complete_upload', namespace='/ws/upload')
    def handle_complete_upload(data):
        """
        完成上传并转存到 S3
        
        期望数据:
        {
            "upload_id": "xxx"
        }
        """
        upload_id = data.get('upload_id')
        
        if upload_id not in active_uploads:
            emit('error', {'status': 'error', 'error': 'Invalid upload ID'})
            return
        
        upload_info = active_uploads[upload_id]
        user = upload_info['user']
        filename = upload_info['filename']
        temp_path = upload_info['temp_path']
        content_type = upload_info['content_type']
        
        try:
            # 关闭文件句柄
            upload_info['file_handle'].close()
            
            # 生成 S3 对象名
            timestamp = time.strftime('%Y%m%d%H%M%S')
            s3_object_name = f"{user}/{timestamp}_{filename}"
            
            print(f"[WS Upload] Uploading to S3: {s3_object_name}")
            
            # 上传到 S3
            success = s3_utils.upload_file_to_s3(temp_path, s3_object_name, content_type)
            
            if success:
                # 获取公共 URL
                public_url = s3_utils.get_public_s3_url(s3_object_name)
                
                print(f"[WS Upload] Upload complete: {public_url}")
                
                emit('upload_complete', {
                    'status': 'success',
                    'public_url': public_url,
                    's3_object_name': s3_object_name
                })
            else:
                emit('error', {'status': 'error', 'error': 'S3 upload failed'})
            
        except Exception as e:
            print(f"[WS Upload] Error completing upload: {e}")
            emit('error', {'status': 'error', 'error': str(e)})
        
        finally:
            # 清理
            cleanup_upload(upload_id)
    
    @socketio.on('cancel_upload', namespace='/ws/upload')
    def handle_cancel_upload(data):
        """取消上传"""
        upload_id = data.get('upload_id')
        
        if upload_id in active_uploads:
            cleanup_upload(upload_id)
            emit('cancelled', {'status': 'cancelled', 'upload_id': upload_id})
        else:
            emit('error', {'status': 'error', 'error': 'Invalid upload ID'})
    
    def cleanup_upload(upload_id):
        """清理上传任务"""
        if upload_id not in active_uploads:
            return
        
        upload_info = active_uploads[upload_id]
        
        try:
            # 关闭文件句柄
            if upload_info.get('file_handle'):
                try:
                    upload_info['file_handle'].close()
                except:
                    pass
            
            # 删除临时文件
            temp_path = upload_info.get('temp_path')
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
            
        except Exception as e:
            print(f"[WS Upload] Cleanup error: {e}")
        
        finally:
            del active_uploads[upload_id]
    
    # 定期清理超时的上传
    def cleanup_expired_uploads():
        """清理超时的上传任务"""
        current_time = time.time()
        to_delete = []
        
        for upload_id, upload_info in active_uploads.items():
            if current_time - upload_info['start_time'] > UPLOAD_TIMEOUT:
                to_delete.append(upload_id)
        
        for upload_id in to_delete:
            print(f"[WS Upload] Cleaning up expired upload: {upload_id}")
            cleanup_upload(upload_id)
    
    return ws_bp, cleanup_expired_uploads


# ===== 集成示例 =====
"""
在您的 Flask 应用 __init__.py 中添加以下代码:

from flask import Flask
from flask_socketio import SocketIO
from .ws_upload_handler import create_ws_upload_blueprint
from . import s3_utils

socketio = SocketIO()

def create_app():
    app = Flask(__name__)
    
    # 初始化 SocketIO
    socketio.init_app(app, cors_allowed_origins="*")
    
    # 创建 WebSocket 上传蓝图
    ws_bp, cleanup_func = create_ws_upload_blueprint(socketio, s3_utils)
    app.register_blueprint(ws_bp)
    
    # 设置定期清理任务
    import threading
    def periodic_cleanup():
        import time
        while True:
            time.sleep(60)  # 每分钟检查一次
            with app.app_context():
                cleanup_func()
    
    cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
    cleanup_thread.start()
    
    return app
"""
