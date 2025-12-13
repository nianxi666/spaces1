#!/usr/bin/env python3
"""
Mock Image Generation App for WebSocket Spaces Testing
模拟 AI 文生图的 WebSocket 客户端，用于测试 WebSocket Spaces 功能

使用方法:
    python mock_image_app.py --host http://localhost:5001 --spaces MockImageGen

要求:
    - pip install python-socketio pillow
"""

import socketio
import threading
import logging
import time
import base64
import io
import random
import argparse
from datetime import datetime
from typing import Dict, Any, Optional

# 尝试导入 PIL，如果没有就使用简单的测试数据
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("警告: PIL 未安装，将使用模拟数据代替图片生成")
    print("安装 PIL: pip install Pillow")

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class MockImageGenerator:
    """模拟图片生成器"""
    
    @staticmethod
    def generate_image(prompt: str, width: int = 512, height: int = 512) -> str:
        """
        根据 prompt 生成模拟图片
        
        Args:
            prompt: 用户输入的提示词
            width: 图片宽度
            height: 图片高度
            
        Returns:
            Base64 编码的图片数据
        """
        if not HAS_PIL:
            # 返回一个简单的测试数据
            return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        
        # 创建一个渐变背景的图片
        img = Image.new('RGB', (width, height))
        draw = ImageDraw.Draw(img)
        
        # 随机选择颜色主题
        themes = [
            [(64, 128, 255), (255, 128, 64)],   # 蓝橙
            [(128, 255, 128), (64, 64, 255)],   # 绿蓝
            [(255, 128, 128), (128, 128, 255)], # 红蓝
            [(255, 255, 128), (128, 255, 255)], # 黄青
            [(255, 128, 255), (128, 255, 128)], # 粉绿
        ]
        color1, color2 = random.choice(themes)
        
        # 绘制渐变背景
        for y in range(height):
            ratio = y / height
            r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
            g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
            b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        
        # 添加一些装饰元素
        for _ in range(random.randint(3, 8)):
            x = random.randint(0, width)
            y = random.randint(0, height)
            size = random.randint(20, 80)
            alpha = random.randint(100, 200)
            shape_color = (255, 255, 255, alpha)
            
            # 随机绘制圆形或矩形
            if random.random() > 0.5:
                draw.ellipse([x-size, y-size, x+size, y+size], 
                           outline=(255, 255, 255), width=2)
            else:
                draw.rectangle([x-size, y-size, x+size, y+size], 
                             outline=(255, 255, 255), width=2)
        
        # 添加文字
        try:
            # 尝试使用系统字体
            font = ImageFont.truetype("arial.ttf", 24)
        except:
            font = ImageFont.load_default()
        
        # 截取 prompt 前50个字符显示
        display_text = prompt[:50] + "..." if len(prompt) > 50 else prompt
        
        # 绘制文字背景
        text_bbox = draw.textbbox((0, 0), display_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        padding = 10
        text_x = (width - text_width) // 2
        text_y = height - text_height - padding * 3
        
        draw.rectangle([text_x - padding, text_y - padding, 
                       text_x + text_width + padding, text_y + text_height + padding],
                      fill=(0, 0, 0, 180))
        draw.text((text_x, text_y), display_text, fill=(255, 255, 255), font=font)
        
        # 添加时间戳
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        draw.text((10, 10), f"Generated: {timestamp}", fill=(255, 255, 255), font=font)
        
        # 添加 "MOCK" 水印
        draw.text((width - 80, 10), "MOCK", fill=(255, 255, 255, 128), font=font)
        
        # 转换为 base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f"data:image/png;base64,{img_base64}"


class MockImageApp:
    """模拟图片生成的 WebSocket 客户端"""
    
    def __init__(self, server_url: str, space_name: str, verbose: bool = False):
        self.server_url = server_url.rstrip('/')
        self.space_name = space_name
        self.verbose = verbose
        
        self.connected = False
        self.connection_id = None
        self.space_id = None
        self.request_count = 0
        
        # 创建 Socket.IO 客户端
        self.sio = socketio.Client(
            reconnection=True,
            reconnection_delay=1,
            reconnection_delay_max=5,
            logger=verbose,
            engineio_logger=verbose
        )
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        """设置事件处理器"""
        
        @self.sio.event
        def connect():
            logger.info("✓ 已连接到服务器")
            self._register()
        
        @self.sio.on('register_response')
        def on_register_response(data):
            if data.get('success'):
                self.connected = True
                self.connection_id = data.get('connection_id')
                self.space_id = data.get('space_id')
                logger.info("=" * 50)
                logger.info("✓ 注册成功!")
                logger.info(f"  Space: {self.space_name}")
                logger.info(f"  Space ID: {self.space_id}")
                logger.info(f"  Connection ID: {self.connection_id[:12]}...")
                logger.info("=" * 50)
                logger.info("📡 等待推理请求...")
            else:
                logger.error(f"✗ 注册失败: {data.get('message')}")
                self.connected = False
        
        @self.sio.on('inference_request')
        def on_inference_request(data):
            request_id = data.get('request_id')
            username = data.get('username')
            payload = data.get('payload', {})
            
            self.request_count += 1
            logger.info("-" * 50)
            logger.info(f"📥 收到请求 #{self.request_count}")
            logger.info(f"   Request ID: {request_id[:12]}...")
            logger.info(f"   用户: {username}")
            logger.info(f"   Prompt: {payload.get('prompt', '')[:50]}...")
            
            # 在独立线程中处理
            thread = threading.Thread(
                target=self._process_request,
                args=(request_id, username, payload),
                daemon=True
            )
            thread.start()
        
        @self.sio.event
        def disconnect():
            logger.warning("✗ 与服务器断开连接")
            self.connected = False
    
    def _register(self):
        """发送注册请求"""
        logger.info(f"📤 正在注册到 Space: {self.space_name}...")
        self.sio.emit('register', {'space_name': self.space_name})
    
    def _process_request(self, request_id: str, username: str, payload: dict):
        """处理推理请求"""
        try:
            prompt = payload.get('prompt', 'No prompt provided')
            
            # 模拟处理延迟 (2-5秒)
            delay = random.uniform(2, 5)
            logger.info(f"🔄 正在生成图片... (预计 {delay:.1f} 秒)")
            time.sleep(delay)
            
            # 生成模拟图片
            image_data = MockImageGenerator.generate_image(prompt)
            
            # 构建结果
            result = {
                'type': 'image',
                'image': image_data,
                'prompt': prompt,
                'generated_at': datetime.now().isoformat(),
                'processing_time': f"{delay:.2f}s",
                'model': 'mock-image-gen-v1',
                'resolution': '512x512'
            }
            
            # 发送结果
            self._send_result(request_id, 'completed', result)
            logger.info(f"✓ 请求 #{self.request_count} 完成")
            logger.info("-" * 50)
            
        except Exception as e:
            logger.error(f"✗ 处理失败: {e}")
            self._send_result(request_id, 'failed', {'error': str(e)})
    
    def _send_result(self, request_id: str, status: str, result: dict):
        """发送结果"""
        if self.sio.connected:
            self.sio.emit('inference_result', {
                'request_id': request_id,
                'status': status,
                'result': result
            })
            logger.info(f"📤 已发送结果 (status: {status})")
    
    def connect(self, timeout: int = 10):
        """连接到服务器"""
        try:
            logger.info(f"🔗 正在连接到 {self.server_url}...")
            self.sio.connect(
                self.server_url,
                transports=['websocket', 'polling'],
                wait_timeout=timeout
            )
        except Exception as e:
            logger.error(f"✗ 连接失败: {e}")
            raise
    
    def wait_forever(self):
        """保持运行直到中断"""
        try:
            while True:
                if not self.sio.connected:
                    logger.warning("连接已断开，等待重连...")
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\n⏹️ 收到停止信号")
    
    def disconnect(self):
        """断开连接"""
        if self.sio.connected:
            self.sio.disconnect()
        logger.info("✓ 已断开连接")


def main():
    parser = argparse.ArgumentParser(
        description='Mock Image Generation App - 模拟AI文生图的WebSocket客户端',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python mock_image_app.py --host http://localhost:5001 --spaces MockImageGen
    
在使用前，请确保:
    1. 服务器正在运行 (python run.py)
    2. 已在 admin 面板创建了一个 WebSocket 类型的 Space
    3. Space 名称与 --spaces 参数一致
        """
    )
    parser.add_argument(
        '--host',
        default='http://localhost:5001',
        help='服务器地址 (默认: http://localhost:5001)'
    )
    parser.add_argument(
        '--spaces',
        required=True,
        help='Space 名称 (必须与服务器上的 Space 名称一致)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='显示详细日志'
    )
    
    args = parser.parse_args()
    
    print()
    print("=" * 60)
    print("  🎨 Mock Image Generation App")
    print("  模拟 AI 文生图 WebSocket 客户端")
    print("=" * 60)
    print(f"  服务器: {args.host}")
    print(f"  Space:  {args.spaces}")
    print("=" * 60)
    print()
    
    app = MockImageApp(
        server_url=args.host,
        space_name=args.spaces,
        verbose=args.verbose
    )
    
    try:
        app.connect()
        
        # 等待连接建立
        time.sleep(2)
        
        if app.connected:
            logger.info("按 Ctrl+C 停止")
            app.wait_forever()
        else:
            logger.error("连接失败，请检查:")
            logger.error("  1. 服务器是否正在运行")
            logger.error("  2. Space 名称是否正确")
            logger.error("  3. Space 类型是否为 'websockets'")
    
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"错误: {e}")
    finally:
        app.disconnect()
        print("\n✓ 程序已退出")


if __name__ == '__main__':
    main()
