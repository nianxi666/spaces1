# 远程服务器WebSocket集成部署指南

## 🎯 目标

在远程服务器上部署WebSocket Spaces系统，并集成IndexTTS2 WebUI，实现推理请求的远程处理。

---

## 📋 前置条件

- 远程服务器访问权限
- Python 3.7+ (建议使用miniconda3)
- 网络连接正常
- 大约1GB磁盘空间

---

## 🚀 快速部署 (15分钟)

### 第1步: SSH连接到远程服务器

```bash
# 使用提供的凭据连接
sshpass -p 'liu20062020' ssh -p 30022 root4563@root@ssh-ad886e9ff5a8de6117e40aaf616d3884.zlrast8j3bxb@direct.virtaicloud.com

# 或使用screen进行持久会话
sshpass -p 'liu20062020' ssh -p 30022 root4563@root@ssh-ad886e9ff5a8de6117e40aaf616d3884.zlrast8j3bxb@direct.virtaicloud.com

# 在远程服务器上启动screen
screen -S websocket_deployment
```

### 第2步: 克隆WebSocket Spaces代码

```bash
# 进入工作目录
cd /gemini/code

# 克隆或复制WebSocket Spaces代码
# 选项1: 从git克隆
git clone https://github.com/your-repo/websocket-spaces.git
cd websocket-spaces

# 选项2: 从本地复制
# scp -P 30022 -r /path/to/websocket-spaces root4563@...:/gemini/code/
```

### 第3步: 设置Python环境

```bash
# 使用miniconda3创建虚拟环境
/usr/local/miniconda3/bin/python -m venv /gemini/code/ws_env

# 激活虚拟环境
source /gemini/code/ws_env/bin/activate

# 升级pip
pip install --upgrade pip setuptools wheel

# 安装依赖
cd /gemini/code/websocket-spaces
pip install -r requirements.txt
pip install python-socketio python-engineio flask-socketio
```

### 第4步: 启动WebSocket Spaces服务器 (终端1)

```bash
# 激活虚拟环境
source /gemini/code/ws_env/bin/activate

# 进入项目目录
cd /gemini/code/websocket-spaces

# 启动服务器
python run.py

# 预期输出:
# * Running on http://0.0.0.0:5001
```

### 第5步: 创建WebSocket Space (终端2 - 新建screen窗口)

```bash
# 按 Ctrl+A+C 创建新窗口

# 激活虚拟环境
source /gemini/code/ws_env/bin/activate

# 创建测试space
cd /gemini/code/websocket-spaces
python test_websockets.py --setup-space --host http://localhost:5001

# 输出示例:
# ✓ Space created: TestSpace_1704123456
# Now run the mock app with:
#   python mock_app.py --host http://localhost:5001 --spaces "TestSpace_1704123456"
```

**重要**: 复制输出中的space名称供下一步使用

### 第6步: 测试WebSocket客户端 (终端3 - 新建screen窗口)

```bash
# 按 Ctrl+A+C 创建新窗口

# 激活虚拟环境
source /gemini/code/ws_env/bin/activate

# 运行测试客户端 (使用第5步的space名称)
cd /gemini/code/websocket-spaces
python websocket_integration_client.py \
    --host http://localhost:5001 \
    --spaces "TestSpace_1704123456" \
    --verbose

# 预期输出:
# ✓ Socket.IO 连接已建立
# ✓ 注册成功!
# 等待推理请求...
```

### 第7步: 在浏览器中测试

1. 打开浏览器访问: `http://远程服务器IP:5001`
2. 登录 (使用admin账户)
3. 找到刚创建的TestSpace
4. 查看连接状态: 应该显示 ✓ 已连接
5. 提交一个测试请求
6. 查看终端3的输出，应该看到请求被处理

---

## 🔧 集成IndexTTS2 (可选)

如果要集成IndexTTS2 WebUI:

### 第1步: 复制集成文件

```bash
cd /gemini/code/indextts2

# 复制websocket_integration_client.py
cp /gemini/code/websocket-spaces/websocket_integration_client.py .
```

### 第2步: 修改webui.py

在webui.py文件的开头添加:

```python
# 在其他import之后添加
from websocket_integration_client import WebSocketSpacesClient

# 在创建tts对象之后，demo定义之前添加:
# 初始化WebSocket客户端
ws_client = WebSocketSpacesClient(
    server_url='http://localhost:5001',
    space_name='IndexTTS2-App',
    inference_callback=None,  # 将在后面定义
    verbose=False
)

try:
    ws_client.connect()
except Exception as e:
    print(f"警告: WebSocket连接失败: {e}")
    ws_client = None
```

### 第3步: 启动修改后的IndexTTS2 (终端4 - 新建screen窗口)

```bash
# 按 Ctrl+A+C 创建新窗口

# 进入IndexTTS2目录
cd /gemini/code/indextts2

# 使用miniconda3的python启动
/usr/local/miniconda3/bin/python webui.py \
    --port 7860 \
    --host 0.0.0.0 \
    --model_dir /gemini/pretrain/IndexTTS-2

# 预期输出:
# ✓ Socket.IO 连接已建立
# ✓ 注册成功!
# Running on http://0.0.0.0:7860
```

### 第4步: 验证集成

1. 访问: `http://远程服务器IP:5001`
2. 找到"IndexTTS2-App" space
3. 查看连接状态: 应该显示 ✓ 已连接
4. 在WebUI上提交请求并验证处理

---

## 📊 Screen窗口管理

### 查看所有窗口

```bash
# 列出当前会话中的所有窗口
screen -ls

# 在screen中查看窗口列表
Ctrl+A+W
```

### 切换窗口

```bash
# 按照编号切换
Ctrl+A+0  # 窗口0
Ctrl+A+1  # 窗口1
Ctrl+A+2  # 窗口2
```

### 创建新窗口

```bash
# 在screen中
Ctrl+A+C
```

### 分离/重新连接

```bash
# 分离当前session
Ctrl+A+D

# 重新连接
screen -r websocket_deployment
```

---

## 🧪 测试清单

### 基本连接测试

- [ ] 终端1: 服务器运行正常 (http://localhost:5001 可访问)
- [ ] 终端2: Space创建成功
- [ ] 终端3: 客户端连接成功并显示"✓ 注册成功"
- [ ] 浏览器: 可以看到连接状态为"✓ 已连接"

### 功能测试

- [ ] 可以在Web界面提交请求
- [ ] 请求在终端3显示为已处理
- [ ] 多个并发请求都被正确处理
- [ ] 应用断开后重新连接自动恢复

### IndexTTS2集成测试 (如果启用)

- [ ] 终端4: IndexTTS2启动成功
- [ ] 网页显示"IndexTTS2-App"连接状态为"✓ 已连接"
- [ ] 在IndexTTS2 Web界面可以生成音频
- [ ] 通过WebSocket发送的请求也能处理

---

## 🔍 故障排除

### 问题1: 连接被拒绝

**症状**: `Connection refused` 或 `无法连接`

**解决方案**:
```bash
# 检查服务器是否运行
ps aux | grep "python run.py"

# 检查端口是否被占用
netstat -tlnp | grep 5001

# 如果被占用，杀死进程
pkill -f "python run.py"

# 重新启动服务器
python run.py
```

### 问题2: WebSocket连接失败

**症状**: "Socket.IO 连接已建立" 但 "✗ 注册失败"

**解决方案**:
```bash
# 检查space名称是否完全匹配 (大小写敏感)
python test_websockets.py --setup-space

# 检查服务器日志中的错误信息
# 在终端1查看日志输出
```

### 问题3: 无法访问Web界面

**症状**: 浏览器无法连接到 http://remote-ip:5001

**解决方案**:
```bash
# 检查防火墙规则
sudo ufw status

# 如果需要，开放端口
sudo ufw allow 5001/tcp
sudo ufw allow 7860/tcp

# 检查是否在0.0.0.0上监听
netstat -tlnp | grep LISTEN
```

### 问题4: 请求未被处理

**症状**: 提交请求后看不到处理输出

**解决方案**:
```bash
# 确保客户端显示"✓ 注册成功"
# 检查客户端是否仍在运行
ps aux | grep websocket_integration_client

# 重启客户端
python websocket_integration_client.py --host http://localhost:5001 --spaces "YOUR-SPACE"
```

---

## 📈 性能监控

### 监控连接和请求

```bash
# 在Python REPL中
python3 << 'EOF'
import sys
sys.path.insert(0, '/gemini/code/websocket-spaces')

from project.websocket_manager import ws_manager

# 查看连接的spaces
spaces = ws_manager.get_connected_spaces()
print(f"已连接的spaces: {spaces}")

# 查看每个space的队列大小
for space_id in spaces:
    queue_size = ws_manager.get_queue_size(space_id)
    print(f"  {space_id}: {queue_size} 个请求在队列中")
EOF
```

### 监控请求状态

```bash
# 查看特定请求的状态
python3 << 'EOF'
import sys
sys.path.insert(0, '/gemini/code/websocket-spaces')

from project.websocket_manager import ws_manager

# 获取请求状态
request_id = "YOUR-REQUEST-ID"
status = ws_manager.get_request_status(request_id)
print(f"请求状态: {status}")
EOF
```

---

## 🔒 安全建议

1. **更改默认密码**
   ```bash
   # 在Web管理界面更改管理员密码
   ```

2. **配置HTTPS**
   ```bash
   # 使用Nginx反向代理 + Let's Encrypt SSL
   sudo apt-get install nginx certbot python3-certbot-nginx
   ```

3. **限制访问**
   ```bash
   # 使用防火墙限制IP访问
   sudo ufw allow from 192.168.1.0/24 to any port 5001
   ```

4. **备份数据**
   ```bash
   # 定期备份数据库
   cp -r instance/ instance_backup_$(date +%Y%m%d)/
   ```

---

## 📚 常用命令速查

```bash
# 激活虚拟环境
source /gemini/code/ws_env/bin/activate

# 启动WebSocket服务器
cd /gemini/code/websocket-spaces && python run.py

# 创建space
cd /gemini/code/websocket-spaces && python test_websockets.py --setup-space

# 运行测试客户端
cd /gemini/code/websocket-spaces && python websocket_integration_client.py --spaces "YOUR-SPACE"

# 查看运行的进程
ps aux | grep python

# 查看监听的端口
netstat -tlnp | grep LISTEN

# 查看日志
tail -f /gemini/code/websocket-spaces/error.log
```

---

## ✅ 最终检查清单

在认为部署完成前，确保以下所有项都已完成:

- [ ] WebSocket Spaces服务器在5001端口运行
- [ ] 可以成功创建WebSocket space
- [ ] 客户端可以连接并注册
- [ ] Web界面显示连接状态为"✓ 已连接"
- [ ] 可以提交和处理推理请求
- [ ] 多个并发请求都被正确处理
- [ ] 应用断开后可以自动重新连接
- [ ] (可选) IndexTTS2集成正常工作

---

## 🎯 下一步

1. **生产部署**
   - 使用systemd service管理进程
   - 配置日志收集和监控
   - 设置备份和恢复策略

2. **性能优化**
   - 启用多进程workers
   - 配置缓存机制
   - 优化数据库查询

3. **监控和告警**
   - 集成Prometheus监控
   - 设置日志告警
   - 建立性能仪表板

---

**部署完成！** 🎉

您现在可以在远程服务器上使用WebSocket Spaces系统了！

