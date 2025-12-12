#!/usr/bin/env python3
"""
WebSocket Spaces Integration Client
用于将任何应用集成到WebSocket Spaces系统

使用示例:
    from websocket_integration_client import WebSocketSpacesClient
    
    client = WebSocketSpacesClient(
        server_url='http://localhost:5001',
        space_name='MyApp-Space'
    )
    client.connect()
"""

import socketio
import threading
import logging
import uuid
from datetime import datetime
from typing import Callable, Optional, Dict, Any

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class WebSocketSpacesClient:
    """WebSocket Spaces 集成客户端"""
    
    def __init__(
        self,
        server_url: str,
        space_name: str,
        inference_callback: Optional[Callable] = None,
        verbose: bool = False
    ):
        """
        初始化客户端
        
        Args:
            server_url: WebSocket服务器URL (e.g., 'http://localhost:5001')
            space_name: Space名称 (必须与服务器上创建的space名称一致)
            inference_callback: 推理回调函数 (接收请求数据，返回结果)
            verbose: 是否启用详细日志
        """
        self.server_url = server_url.rstrip('/')
        self.space_name = space_name
        self.inference_callback = inference_callback
        self.verbose = verbose
        
        # 连接状态
        self.connected = False
        self.connection_id = None
        self.space_id = None
        
        # 初始化Socket.IO客户端
        self.sio = socketio.Client(
            reconnection=True,
            reconnection_delay=1,
            reconnection_delay_max=5,
            logger=verbose,
            engineio_logger=verbose
        )
        
        # 设置事件处理器
        self._setup_event_handlers()
    
    def _setup_event_handlers(self):
        """设置Socket.IO事件处理器"""
        
        @self.sio.event
        def connect():
            """连接成功处理"""
            logger.info(f"✓ Socket.IO 连接已建立")
            self._send_registration()
        
        @self.sio.event
        def register_response(data):
            """注册响应处理"""
            if data.get('success'):
                self.connected = True
                self.connection_id = data.get('connection_id')
                self.space_id = data.get('space_id')
                logger.info(f"✓ 注册成功!")
                logger.info(f"  Space Name: {self.space_name}")
                logger.info(f"  Space ID: {self.space_id}")
                logger.info(f"  Connection ID: {self.connection_id}")
            else:
                message = data.get('message', 'Unknown error')
                logger.error(f"✗ 注册失败: {message}")
                self.connected = False
        
        @self.sio.event
        def inference_request(data):
            """推理请求处理"""
            request_id = data.get('request_id')
            username = data.get('username')
            payload = data.get('payload', {})
            
            logger.info(f"📥 收到推理请求")
            logger.info(f"  Request ID: {request_id[:12]}...")
            logger.info(f"  Username: {username}")
            
            # 在独立线程中处理推理以避免阻塞
            thread = threading.Thread(
                target=self._process_inference_request,
                args=(request_id, username, payload),
                daemon=True
            )
            thread.start()
        
        @self.sio.event
        def disconnect():
            """断开连接处理"""
            logger.warning("✗ Socket.IO 连接已断开")
            self.connected = False
        
        @self.sio.on('*')
        def catch_all(event, *args):
            """捕获所有事件"""
            if self.verbose:
                logger.debug(f"事件: {event}, 参数: {args}")
    
    def connect(self, timeout: int = 10):
        """
        连接到WebSocket服务器
        
        Args:
            timeout: 连接超时时间(秒)
            
        Raises:
            Exception: 连接失败时抛出异常
        """
        try:
            logger.info(f"🔗 正在连接到 {self.server_url}...")
            self.sio.connect(
                self.server_url,
                transports=['websocket', 'polling'],
                wait_timeout=timeout
            )
            logger.info("✓ Socket.IO 连接成功")
        except Exception as e:
            logger.error(f"✗ 连接失败: {e}")
            raise
    
    def _send_registration(self):
        """发送注册信息"""
        logger.debug(f"📤 发送注册信息...")
        self.sio.emit('register', {'space_name': self.space_name})
    
    def _process_inference_request(
        self,
        request_id: str,
        username: str,
        payload: Dict[str, Any]
    ):
        """
        处理推理请求
        
        Args:
            request_id: 请求ID
            username: 用户名
            payload: 请求数据
        """
        try:
            logger.info(f"🔄 处理推理请求 {request_id[:12]}...")
            
            # 调用用户提供的推理回调
            if self.inference_callback:
                result = self.inference_callback(payload)
                status = 'completed'
            else:
                # 如果没有提供回调，返回模拟结果
                result = {
                    'message': '使用默认模拟结果',
                    'payload': payload
                }
                status = 'completed'
            
            # 发送结果
            self._send_result(request_id, status, result)
            logger.info(f"✓ 推理完成 {request_id[:12]}...")
            
        except Exception as e:
            logger.error(f"✗ 推理失败: {e}")
            self._send_result(request_id, 'failed', {'error': str(e)})
    
    def _send_result(self, request_id: str, status: str, result: Dict[str, Any]):
        """
        发送推理结果
        
        Args:
            request_id: 请求ID
            status: 状态 ('completed' 或 'failed')
            result: 结果数据
        """
        if not self.sio.connected:
            logger.warning("⚠️  WebSocket未连接，无法发送结果")
            return
        
        try:
            self.sio.emit('inference_result', {
                'request_id': request_id,
                'status': status,
                'result': result
            })
            logger.debug(f"📤 结果已发送 {request_id[:12]}...")
        except Exception as e:
            logger.error(f"✗ 发送结果失败: {e}")
    
    def disconnect(self):
        """断开连接"""
        if self.sio.connected:
            self.sio.disconnect()
            logger.info("✓ 已断开WebSocket连接")
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self.connected and self.sio.connected
    
    def wait_for_connection(self, timeout: int = 30) -> bool:
        """
        等待连接建立
        
        Args:
            timeout: 等待超时时间(秒)
            
        Returns:
            如果连接成功返回True，否则返回False
        """
        import time
        start = time.time()
        while time.time() - start < timeout:
            if self.is_connected():
                return True
            time.sleep(0.5)
        return False


# 示例使用
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='WebSocket Spaces 集成客户端示例'
    )
    parser.add_argument(
        '--host',
        default='http://localhost:5001',
        help='WebSocket服务器URL'
    )
    parser.add_argument(
        '--spaces',
        default='TestApp-Space',
        help='Space名称'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='启用详细日志'
    )
    
    args = parser.parse_args()
    
    # 定义推理回调函数
    def my_inference(payload):
        """示例推理函数"""
        prompt = payload.get('prompt', '')
        
        logger.info(f"  执行推理: {prompt[:50]}...")
        
        # 模拟推理处理
        import time
        time.sleep(2)
        
        return {
            'input': prompt,
            'output': f'推理完成: {prompt}',
            'timestamp': datetime.now().isoformat(),
            'status': 'success'
        }
    
    # 创建和连接客户端
    client = WebSocketSpacesClient(
        server_url=args.host,
        space_name=args.spaces,
        inference_callback=my_inference,
        verbose=args.verbose
    )
    
    try:
        logger.info("="*60)
        logger.info("WebSocket Spaces 集成客户端启动")
        logger.info("="*60)
        
        # 连接到服务器
        client.connect()
        
        # 等待连接建立
        if client.wait_for_connection():
            logger.info("✓ 客户端已准备好！等待推理请求...")
            logger.info("按 Ctrl+C 停止")
            
            # 保持连接
            try:
                while client.is_connected():
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("\n⏹️  收到停止信号...")
        else:
            logger.error("✗ 连接超时")
    
    except KeyboardInterrupt:
        logger.info("\n⏹️  收到停止信号...")
    except Exception as e:
        logger.error(f"✗ 错误: {e}")
    finally:
        client.disconnect()
        logger.info("✓ 客户端已关闭")

