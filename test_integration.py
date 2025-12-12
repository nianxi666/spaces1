#!/usr/bin/env python3
"""
WebSocket Spaces 集成测试脚本

用于测试WebSocket Spaces与第三方应用的集成

使用示例:
    python test_integration.py --host http://localhost:5001 --spaces MyApp --mode client
    python test_integration.py --host http://localhost:5001 --spaces MyApp --mode server
"""

import argparse
import logging
import time
import sys
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def test_client_mode(server_url: str, space_name: str, num_requests: int = 3):
    """
    测试客户端模式 - 运行WebSocket客户端
    
    Args:
        server_url: WebSocket服务器URL
        space_name: Space名称
        num_requests: 要发送的请求数
    """
    logger.info("="*60)
    logger.info("WebSocket Spaces 客户端集成测试")
    logger.info("="*60)
    logger.info(f"服务器: {server_url}")
    logger.info(f"Space: {space_name}")
    logger.info("")
    
    # 导入客户端
    from websocket_integration_client import WebSocketSpacesClient
    
    # 定义推理函数
    def inference_function(payload):
        """模拟推理函数"""
        prompt = payload.get('prompt', 'No prompt')
        logger.info(f"  📝 输入: {prompt[:60]}...")
        
        # 模拟处理时间
        time.sleep(1)
        
        return {
            'input': prompt,
            'output': f'推理结果: {prompt}',
            'processed_at': datetime.now().isoformat(),
            'model': 'SimulatedModel-v1'
        }
    
    # 创建客户端
    client = WebSocketSpacesClient(
        server_url=server_url,
        space_name=space_name,
        inference_callback=inference_function,
        verbose=False
    )
    
    try:
        # 连接
        logger.info("正在连接...")
        client.connect()
        
        # 等待连接建立
        if not client.wait_for_connection(timeout=10):
            logger.error("✗ 连接超时！")
            return False
        
        logger.info("✓ 客户端已连接并注册！")
        logger.info("")
        logger.info("等待推理请求...")
        logger.info("提示: 在网站上发送请求到此space")
        logger.info("")
        
        # 保持运行直到中断
        try:
            while client.is_connected():
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\n⏹️  收到停止信号")
        
        return True
    
    except Exception as e:
        logger.error(f"✗ 错误: {e}")
        return False
    finally:
        client.disconnect()


def test_server_mode(server_url: str, space_name: str):
    """
    测试服务器模式 - 模拟WebSocket Spaces服务器
    
    Args:
        server_url: 要运行的本地服务器地址
        space_name: Space名称
    """
    logger.info("="*60)
    logger.info("WebSocket Spaces 服务器测试模式")
    logger.info("="*60)
    logger.info(f"将启动服务器: {server_url}")
    logger.info("")
    
    # 这里会运行Flask应用
    from project import create_app
    
    app = create_app()
    
    logger.info("✓ Flask应用已创建")
    logger.info(f"启动服务器在 {server_url}...")
    logger.info("")
    logger.info("Web界面: http://localhost:5001")
    logger.info("Admin面板: http://localhost:5001/admin")
    logger.info("")
    
    # 运行服务器
    socketio = getattr(app, 'socketio', None)
    if socketio:
        socketio.run(app, host='0.0.0.0', port=5001, debug=False)
    else:
        app.run(host='0.0.0.0', port=5001, debug=False)


def test_end_to_end(server_url: str, space_name: str):
    """
    端到端测试 - 模拟完整的推理流程
    
    Args:
        server_url: WebSocket服务器URL
        space_name: Space名称
    """
    logger.info("="*60)
    logger.info("WebSocket Spaces 端到端测试")
    logger.info("="*60)
    logger.info("")
    
    import requests
    
    # 步骤1: 创建test space
    logger.info("📋 步骤 1: 创建测试space")
    logger.info("-"*60)
    
    try:
        response = requests.post(
            f"{server_url}/admin/space/add",
            data={
                'name': space_name,
                'description': 'WebSocket集成测试space',
                'cover': 'default.png',
                'card_type': 'websockets',
                'ws_enable_prompt': 'on'
            },
            timeout=5
        )
        logger.info(f"✓ Space创建请求已发送 (状态: {response.status_code})")
    except Exception as e:
        logger.error(f"✗ 无法创建space: {e}")
        return False
    
    logger.info("")
    
    # 步骤2: 启动客户端
    logger.info("📋 步骤 2: 启动WebSocket客户端")
    logger.info("-"*60)
    
    from websocket_integration_client import WebSocketSpacesClient
    
    def mock_inference(payload):
        prompt = payload.get('prompt', '')
        logger.info(f"  ⚙️  执行推理: {prompt[:40]}...")
        time.sleep(1)
        return {'output': f'Result for: {prompt}'}
    
    client = WebSocketSpacesClient(
        server_url=server_url,
        space_name=space_name,
        inference_callback=mock_inference
    )
    
    try:
        client.connect()
        if not client.wait_for_connection(timeout=10):
            logger.error("✗ 客户端连接失败")
            return False
        
        logger.info(f"✓ 客户端已连接")
        logger.info("")
        
        # 步骤3: 发送测试请求
        logger.info("📋 步骤 3: 发送测试请求")
        logger.info("-"*60)
        
        logger.info("ℹ️  在网站上向 {} 发送请求".format(space_name))
        logger.info("ℹ️  网址: http://localhost:5001")
        logger.info("")
        
        # 等待请求
        logger.info("⏳ 等待请求 (10秒超时)...")
        start = time.time()
        request_received = False
        
        while time.time() - start < 10:
            time.sleep(0.5)
            if not client.is_connected():
                break
        
        logger.info("")
        logger.info("="*60)
        logger.info("✓ 测试完成!")
        logger.info("="*60)
        
        return True
    
    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        return False
    finally:
        client.disconnect()


def main():
    parser = argparse.ArgumentParser(
        description='WebSocket Spaces 集成测试'
    )
    parser.add_argument(
        '--host',
        default='http://localhost:5001',
        help='WebSocket服务器URL (默认: http://localhost:5001)'
    )
    parser.add_argument(
        '--spaces',
        default='TestApp',
        help='Space名称 (默认: TestApp)'
    )
    parser.add_argument(
        '--mode',
        choices=['client', 'server', 'e2e'],
        default='client',
        help='测试模式: client=客户端, server=服务器, e2e=端到端'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='启用详细日志'
    )
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 运行相应的测试
    if args.mode == 'client':
        success = test_client_mode(args.host, args.spaces)
    elif args.mode == 'server':
        success = test_server_mode(args.host, args.spaces)
    elif args.mode == 'e2e':
        success = test_end_to_end(args.host, args.spaces)
    else:
        success = False
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

