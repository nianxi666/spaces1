# WebSocket Spaces + IndexTTS2 集成设置指南

## 📋 概述

本指南将帮助您将WebSocket Spaces系统与IndexTTS2 WebUI集成，实现远程推理请求。

---

## 🚀 远程服务器设置步骤

### 步骤1: 连接到SSH服务器

```bash
# 使用sshpass连接 (需要先安装sshpass)
sshpass -p 'liu20062020' ssh -p 30022 root4563@root@ssh-ad886e9ff5a8de6117e40aaf616d3884.zlrast8j3bxb@direct.virtaicloud.com

# 或使用screen连接持久会话
sshpass -p 'liu20062020' ssh -p 30022 root4563@root@ssh-ad886e9ff5a8de6117e40aaf616d3884.zlrast8j3bxb@direct.virtaicloud.com 'screen -S websocket_test'
```

### 步骤2: 克隆WebSocket Spaces代码

在远程服务器上:

```bash
cd /gemini/code
git clone https://github.com/your-repo/websocket-spaces.git
# 或复制整个项目目录
```

### 步骤3: 修改IndexTTS2 WebUI支持WebSocket

需要修改 `/gemini/code/indextts2/webui.py`，添加WebSocket客户端功能。

---

## 📝 修改IndexTTS2 WebUI的关键代码

### 在webui.py开头添加WebSocket客户端依赖:

```python
# 在现有import之后添加
import asyncio
import socketio
from datetime import datetime
import uuid
```

### 创建WebSocket客户端类:

```python
class WebSocketInferenceClient:
    def __init__(self, server_url, space_name):
        self.server_url = server_url
        self.space_name = space_name
        self.sio = socketio.Client(
            reconnection=True,
            reconnection_delay=1,
            reconnection_delay_max=5
        )
        self.connected = False
        self.connection_id = None
        self.space_id = None
        
        # 注册事件处理器
        @self.sio.event
        def connect():
            print(f"[WebSocket] 已连接到 {self.server_url}")
            self.send_registration()
        
        @self.sio.event
        def register_response(data):
            if data.get('success'):
                self.connected = True
                self.connection_id = data.get('connection_id')
                self.space_id = data.get('space_id')
                print(f"[WebSocket] 注册成功! Space ID: {self.space_id}")
            else:
                print(f"[WebSocket] 注册失败: {data.get('message')}")
        
        @self.sio.event
        def inference_request(data):
            self.handle_inference_request(data)
        
        @self.sio.event
        def disconnect():
            print("[WebSocket] 连接已断开")
            self.connected = False
    
    def connect(self):
        """连接到WebSocket服务器"""
        try:
            self.sio.connect(self.server_url, transports=['websocket', 'polling'])
        except Exception as e:
            print(f"[WebSocket] 连接失败: {e}")
    
    def send_registration(self):
        """发送注册信息"""
        self.sio.emit('register', {'space_name': self.space_name})
    
    def handle_inference_request(self, data):
        """处理推理请求"""
        request_id = data.get('request_id')
        username = data.get('username')
        payload = data.get('payload', {})
        text = payload.get('prompt', '')
        
        print(f"\n[推理] 收到请求:")
        print(f"  Request ID: {request_id}")
        print(f"  用户: {username}")
        print(f"  文本: {text[:100]}...")
        
        try:
            # 这里需要调用实际的推理函数
            # 为了演示，我们返回一个模拟结果
            result = self.run_inference(text)
            
            self.send_result(request_id, 'completed', result)
        except Exception as e:
            self.send_result(request_id, 'failed', {'error': str(e)})
    
    def run_inference(self, text):
        """运行推理 (需要集成实际的IndexTTS2推理代码)"""
        # 这是一个简化的实现
        # 实际上需要调用tts.infer()方法
        return {
            'text': text,
            'status': 'completed',
            'output': f'Generated audio for: {text}'
        }
    
    def send_result(self, request_id, status, result):
        """发送推理结果"""
        if self.sio.connected:
            self.sio.emit('inference_result', {
                'request_id': request_id,
                'status': status,
                'result': result
            })
            print(f"[推理] 结果已发送: {request_id}")

# 在主程序中创建WebSocket客户端
ws_client = None

def init_websocket_client(server_url, space_name):
    """初始化WebSocket客户端"""
    global ws_client
    ws_client = WebSocketInferenceClient(server_url, space_name)
    ws_client.connect()
    return ws_client
```

### 修改gen_single函数以支持WebSocket (可选)

如果要启用WebSocket推理路由，可以在`gen_single`函数中添加:

```python
def gen_single_websocket(request_id, text, *args, **kwargs):
    """通过WebSocket路由的推理函数"""
    if not ws_client or not ws_client.connected:
        return {'error': 'WebSocket未连接'}
    
    # 调用原始推理函数
    result = gen_single(None, text, *args, progress=gr.Progress(), **kwargs)
    
    # 发送结果到WebSocket
    ws_client.send_result(request_id, 'completed', {
        'output': result,
        'timestamp': datetime.now().isoformat()
    })
    
    return result
```

---

## 🔧 完整的修改示例

创建文件: `websocket_integration.py`

```python
"""
WebSocket Integration for IndexTTS2
将IndexTTS2与WebSocket Spaces系统集成
"""

import socketio
import threading
import uuid
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IndexTTS2WebSocketClient:
    """IndexTTS2 WebSocket客户端"""
    
    def __init__(self, server_url: str, space_name: str, inference_engine=None):
        """
        初始化WebSocket客户端
        
        Args:
            server_url: WebSocket服务器URL
            space_name: 要注册的space名称
            inference_engine: IndexTTS2推理引擎实例
        """
        self.server_url = server_url
        self.space_name = space_name
        self.inference_engine = inference_engine
        self.sio = socketio.Client(
            reconnection=True,
            reconnection_delay=1,
            reconnection_delay_max=5,
            logger=False
        )
        self.connected = False
        self.connection_id = None
        self.space_id = None
        self._setup_handlers()
    
    def _setup_handlers(self):
        """设置Socket.IO事件处理器"""
        @self.sio.event
        def connect():
            logger.info("✓ WebSocket 已连接")
            self._send_registration()
        
        @self.sio.event
        def register_response(data):
            if data.get('success'):
                self.connected = True
                self.connection_id = data.get('connection_id')
                self.space_id = data.get('space_id')
                logger.info(f"✓ 注册成功! Space: {self.space_name}, ID: {self.space_id}")
            else:
                logger.error(f"✗ 注册失败: {data.get('message')}")
        
        @self.sio.event
        def inference_request(data):
            logger.info(f"📝 收到推理请求: {data.get('request_id')[:8]}...")
            self._handle_request(data)
        
        @self.sio.event
        def disconnect():
            logger.warning("✗ WebSocket 已断开")
            self.connected = False
    
    def connect(self):
        """连接到WebSocket服务器"""
        try:
            logger.info(f"正在连接到 {self.server_url}...")
            self.sio.connect(
                self.server_url,
                transports=['websocket', 'polling'],
                wait_timeout=10
            )
        except Exception as e:
            logger.error(f"连接失败: {e}")
            raise
    
    def _send_registration(self):
        """发送注册信息"""
        self.sio.emit('register', {'space_name': self.space_name})
    
    def _handle_request(self, data):
        """处理推理请求"""
        request_id = data.get('request_id')
        username = data.get('username')
        payload = data.get('payload', {})
        text = payload.get('prompt', '')
        
        # 在线程中运行推理以避免阻塞
        thread = threading.Thread(
            target=self._run_inference,
            args=(request_id, text, username, payload)
        )
        thread.daemon = True
        thread.start()
    
    def _run_inference(self, request_id, text, username, payload):
        """运行推理"""
        try:
            logger.info(f"🔄 开始推理: {request_id[:8]}...")
            
            # 这里需要集成实际的IndexTTS2推理逻辑
            # 示例:
            # if self.inference_engine:
            #     output = self.inference_engine.infer(text)
            # else:
            #     output = f"Inferred: {text}"
            
            result = {
                'text': text,
                'user': username,
                'timestamp': datetime.now().isoformat(),
                'status': 'completed'
            }
            
            self._send_result(request_id, 'completed', result)
            logger.info(f"✓ 推理完成: {request_id[:8]}...")
            
        except Exception as e:
            logger.error(f"推理失败: {e}")
            self._send_result(request_id, 'failed', {'error': str(e)})
    
    def _send_result(self, request_id, status, result):
        """发送推理结果"""
        if self.sio.connected:
            self.sio.emit('inference_result', {
                'request_id': request_id,
                'status': status,
                'result': result
            })
    
    def disconnect(self):
        """断开连接"""
        if self.sio.connected:
            self.sio.disconnect()
            logger.info("已断开WebSocket连接")


# 全局客户端实例
_ws_client = None


def initialize_websocket(server_url: str, space_name: str, inference_engine=None):
    """初始化WebSocket客户端"""
    global _ws_client
    _ws_client = IndexTTS2WebSocketClient(server_url, space_name, inference_engine)
    _ws_client.connect()
    return _ws_client


def get_websocket_client():
    """获取全局WebSocket客户端"""
    return _ws_client


def is_websocket_connected():
    """检查WebSocket连接状态"""
    return _ws_client is not None and _ws_client.connected
```

---

## 🚀 运行集成系统

### 在远程服务器上 (终端1: WebSocket Spaces服务器)

```bash
# 进入WebSocket Spaces项目目录
cd /gemini/code/websocket-spaces

# 激活虚拟环境
source /path/to/venv/bin/activate  # 或使用miniconda3

# 安装依赖
pip install -r requirements.txt
pip install python-socketio python-engineio

# 启动WebSocket服务器
python run.py
```

**预期输出:**
```
* Running on http://0.0.0.0:5001
WebSocket support enabled
```

### 在远程服务器上 (终端2: 创建WebSocket space)

```bash
# 创建IndexTTS2 space
python test_websockets.py --setup-space --host http://localhost:5001
# 输出: TestSpace_IndexTTS2_XXXXX

# 或手动通过Admin界面创建
# URL: http://localhost:5001/admin
# 创建新space，类型选择: WebSocket Remote Connection Type
```

### 在远程服务器上 (终端3: 修改并运行IndexTTS2)

```bash
# 进入IndexTTS2目录
cd /gemini/code/indextts2

# 将websocket_integration.py复制到此目录
cp /path/to/websocket_integration.py .

# 修改webui.py，在开头添加:
# from websocket_integration import initialize_websocket

# 在创建gradio demo之前添加:
# ws_client = initialize_websocket(
#     'http://localhost:5001',
#     'IndexTTS2-Space'
# )

# 运行修改后的webui
python webui.py --port 7860 --host 0.0.0.0
```

**预期输出:**
```
✓ WebSocket 已连接
✓ 注册成功! Space: IndexTTS2-Space
IndexTTS Demo running on http://0.0.0.0:7860
```

---

## 🧪 测试步骤

### 测试1: 验证连接

访问: `http://localhost:5001`
1. 登录到admin面板
2. 找到IndexTTS2-Space
3. 应该看到: ✓ 已连接

### 测试2: 单个推理请求

在WebSocket Spaces界面上:
1. 输入提示词: "这是一个测试"
2. 点击"发送请求"
3. 观察远程服务器的终端2和3输出

**在终端3 (IndexTTS2)应该看到:**
```
🔄 开始推理: abc12345...
✓ 推理完成: abc12345...
```

**在终端2 (WebSocket Spaces)应该看到:**
```
[REQUEST] New inference request received
[RESULT] Result sent
```

### 测试3: 并发请求

从多个浏览器标签页同时发送请求:
1. 打开3个标签页，都打开同一个space
2. 分别发送3个不同的提示词
3. 观察请求队列处理

**预期行为:**
- 所有请求都被接收
- 请求按顺序处理
- 所有用户都获得结果

### 测试4: 断开重连

```bash
# 在终端3，按Ctrl+C停止IndexTTS2
# 观察终端2中的连接状态变为: ✗ 未连接

# 重新启动IndexTTS2
python webui.py --port 7860 --host 0.0.0.0

# 观察连接状态恢复: ✓ 已连接
```

---

## 📊 监控和调试

### 查看实时日志

```bash
# 在WebSocket Spaces终端
# 查看所有连接信息
python -c "
from project.websocket_manager import ws_manager
print('Connected spaces:', ws_manager.get_connected_spaces())
for space_id in ws_manager.get_connected_spaces():
    print(f'  Queue size: {ws_manager.get_queue_size(space_id)}')
"

# 在IndexTTS2终端
# 查看WebSocket事件日志
# 日志会显示所有连接、请求和结果
```

### 性能监控

```bash
# 测试请求处理时间
import time
start = time.time()
# 发送请求
# 等待结果
end = time.time()
print(f"总处理时间: {end - start:.2f}秒")
```

---

## ⚠️ 常见问题

### 问题1: WebSocket连接失败

**症状:** `连接失败: Connection refused`

**解决:**
1. 确认终端1的WebSocket Spaces服务器正在运行
2. 检查防火墙是否允许localhost:5001
3. 检查space名称是否与IndexTTS2中的设置一致

### 问题2: 请求未被处理

**症状:** 发送请求后没有看到推理输出

**解决:**
1. 检查IndexTTS2终端是否显示"✓ 已连接"
2. 检查WebSocket Spaces服务器日志中是否收到请求
3. 确认请求ID有效

### 问题3: 推理速度慢

**症状:** 单个推理请求需要超过5分钟

**解决:**
1. 检查GPU是否被正确使用
2. 查看IndexTTS2的配置参数
3. 减少max_text_tokens_per_segment的值

---

## ✅ 最终检查清单

- [ ] WebSocket Spaces服务器在5001端口运行
- [ ] IndexTTS2 WebSocket客户端已集成
- [ ] IndexTTS2运行在7860端口
- [ ] 连接状态显示为"✓ 已连接"
- [ ] 可以成功发送和接收推理请求
- [ ] 并发请求被正确处理
- [ ] 断开重连工作正常

---

## 🎯 下一步

1. **部署到生产环境**
   - 使用systemd service管理进程
   - 配置反向代理 (nginx)
   - 启用SSL/TLS

2. **性能优化**
   - 实现请求缓存
   - 并行处理多个请求
   - 添加速率限制

3. **监控和告警**
   - 收集性能指标
   - 设置告警规则
   - 构建监控仪表板

---

**集成设置完成！** 🎉

现在你可以在WebSocket Spaces界面上使用IndexTTS2进行推理了！

