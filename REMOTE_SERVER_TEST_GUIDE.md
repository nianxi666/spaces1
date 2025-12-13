# 远程服务器WebSocket Spaces完整测试指南

## 🎯 目标

在远程服务器上部署和测试WebSocket Spaces系统，验证所有功能正常工作。

---

## 📋 前置条件

- ✅ SSH访问权限
- ✅ Python 3.7+
- ✅ miniconda3或Python venv
- ✅ 网络连接正常

---

## 🚀 快速远程部署 (20分钟)

### 第1步：SSH连接到远程服务器

```bash
# 使用提供的凭据连接
sshpass -p 'liu20062020' ssh -p 30022 root4563@root@ssh-ad886e9ff5a8de6117e40aaf616d3884.zlrast8j3bxb@direct.virtaicloud.com

# 或者手动输入密码
ssh -p 30022 root4563@root@ssh-ad886e9ff5a8de6117e40aaf616d3884.zlrast8j3bxb@direct.virtaicloud.com
# 密码: liu20062020
```

**连接成功后，您应该看到远程服务器的shell提示符。**

### 第2步：准备项目目录

```bash
# 进入工作目录
cd /gemini/code

# 创建项目目录
mkdir -p websocket-spaces
cd websocket-spaces

# 查看目录
ls -la
```

### 第3步：创建Python虚拟环境

```bash
# 使用Python venv创建虚拟环境
python3 -m venv ws_env

# 激活虚拟环境
source ws_env/bin/activate

# 验证激活成功
which python
python --version
```

**验证：您应该看到venv的Python路径。**

### 第4步：安装依赖

```bash
# 升级pip
pip install --upgrade pip setuptools wheel

# 安装WebSocket Spaces所需的所有依赖
pip install \
    Flask \
    Flask-SocketIO \
    Flask-Babel \
    python-socketio \
    python-engineio \
    requests \
    APScheduler \
    psutil \
    boto3 \
    markdown
```

**验证：最后应该看到"Successfully installed"消息。**

### 第5步：复制项目文件

您有两个选择：

**选项A：从git克隆（如果有git）**
```bash
cd /gemini/code/websocket-spaces
git clone https://github.com/your-repo/websocket-spaces .
```

**选项B：从本地复制**
```bash
# 在本地终端运行
sshpass -p 'liu20062020' scp -P 30022 -r /home/engine/project/* \
  root4563@root@ssh-ad886e9ff5a8de6117e40aaf616d3884.zlrast8j3bxb@direct.virtaicloud.com:/gemini/code/websocket-spaces/
```

### 第6步：启动screen会话（用于多终端）

```bash
# 启动screen
screen -S websocket_test

# 您现在在screen内的第一个窗口
# 创建新窗口的快捷键：Ctrl+A+C
# 列出所有窗口：Ctrl+A+W
# 切换到窗口N：Ctrl+A+N
# 分离会话：Ctrl+A+D
```

---

## 🧪 完整测试流程

### 终端1: 启动WebSocket服务器

```bash
# 激活虚拟环境
source /gemini/code/websocket-spaces/ws_env/bin/activate

# 进入项目目录
cd /gemini/code/websocket-spaces

# 启动服务器
python run.py

# 预期输出:
# * Running on http://0.0.0.0:5001
# WebSocket support enabled
```

**验证：看到"Running on"消息说明服务器启动成功。**

在screen中按`Ctrl+A+C`创建新窗口继续测试。

---

### 终端2: 创建测试WebSocket Space

```bash
# 激活虚拟环境
source /gemini/code/websocket-spaces/ws_env/bin/activate

# 进入项目目录
cd /gemini/code/websocket-spaces

# 创建测试space
python test_websockets.py --setup-space --host http://localhost:5001

# 预期输出示例:
# ✓ Space created: TestSpace_1704123456
# Now run the mock app with:
#   python mock_app.py --host http://localhost:5001 --spaces "TestSpace_1704123456"
```

**关键：复制输出中的space名称（例如：TestSpace_1704123456），供下一步使用。**

在screen中按`Ctrl+A+C`创建新窗口继续。

---

### 终端3: 启动模拟应用

```bash
# 激活虚拟环境
source /gemini/code/websocket-spaces/ws_env/bin/activate

# 进入项目目录
cd /gemini/code/websocket-spaces

# 启动模拟应用（使用第2步的space名称）
python mock_app.py --host http://localhost:5001 --spaces "TestSpace_1704123456" --verbose

# 预期输出:
# ✓ Socket.IO connection established
# ✓ Registration successful!
# Connection ID: abc123def456
# [INFO] Request processor started
```

**验证：看到"Registration successful!"说明连接成功。**

---

### 终端4: 在浏览器中测试（本地机器）

```bash
# 在您的本地机器浏览器中访问远程服务器
http://远程服务器IP:5001

# 或者如果有公网DNS
http://your-remote-domain.com:5001
```

**步骤：**
1. 使用admin用户登录
2. 找到"TestSpace_1704123456"
3. 应该看到"✓ 已连接"或"✓ Connected"
4. 在表单中输入提示词
5. 点击"发送请求"或"Submit Request"
6. 在终端3的mock_app窗口中应该看到处理消息
7. 结果应该返回到浏览器页面

---

## 🔍 测试验证清单

在完成上述步骤后，确保以下所有项都通过了：

### 连接测试
- [ ] 终端1：服务器成功启动（显示"Running on http://0.0.0.0:5001"）
- [ ] 终端2：space成功创建（显示"Space created: TestSpace_XXX"）
- [ ] 终端3：模拟应用连接成功（显示"Registration successful!"）
- [ ] 浏览器：可以访问网站（http://remote-ip:5001）

### 功能测试
- [ ] 网站显示连接状态为"✓ 已连接"或"✓ Connected"
- [ ] 可以在表单中输入文本
- [ ] 点击提交按钮后请求被接受
- [ ] 终端3显示"[REQUEST] New inference request received"
- [ ] 终端3显示推理处理进度
- [ ] 终端3显示"[RESULT] Result sent"
- [ ] 浏览器页面显示返回的结果

### 多并发测试
- [ ] 打开3个浏览器标签页
- [ ] 从3个标签页分别发送请求
- [ ] 所有请求都被处理
- [ ] 所有用户都收到结果

### 断开重连测试
- [ ] 在终端3按Ctrl+C停止模拟应用
- [ ] 浏览器刷新后显示"✗ 未连接"或"✗ Not Connected"
- [ ] 重启终端3的模拟应用
- [ ] 浏览器刷新后显示"✓ 已连接"
- [ ] 可以再次发送请求

---

## 📊 测试性能检查

### 在终端1（服务器）查看日志

```bash
# 在运行run.py的终端中，可以看到：
# [2024-01-08 12:00:00] [INFO] Remote app connected to space: TestSpace_1704123456
# [2024-01-08 12:00:05] [INFO] WebSocket request received
```

### 在终端3（模拟应用）查看性能

```bash
# 查看日志中的处理时间
[2024-01-08 12:00:05] [✓] Inference completed in 2.3s
```

### 性能基准
| 操作 | 预期时间 |
|------|--------|
| 连接建立 | < 1s |
| 请求传输 | < 200ms |
| 推理处理 | 1-5s (模拟) |
| 结果返回 | < 200ms |

---

## 🐛 远程测试故障排除

### 问题1: "Connection refused"

**症状**: 无法连接到http://remote-ip:5001

**原因**: 服务器未运行或防火墙阻止

**解决**:
```bash
# 检查服务器是否运行
ps aux | grep "python run.py"

# 检查端口
netstat -tlnp | grep 5001

# 检查防火墙
sudo ufw status
sudo ufw allow 5001/tcp  # 如果需要
```

### 问题2: "WebSocket连接失败"

**症状**: 模拟应用显示连接失败

**原因**: 可能是space名称不匹配

**解决**:
```bash
# 确认space名称完全匹配（大小写敏感）
# 重新运行create space命令获取准确的space名称
python test_websockets.py --setup-space --host http://localhost:5001
```

### 问题3: 请求未被处理

**症状**: 发送请求后没有看到处理消息

**原因**: 模拟应用未正确连接

**解决**:
```bash
# 检查终端3的输出是否显示"Registration successful"
# 检查连接状态是否为已连接
# 检查请求是否真的发送了（检查浏览器console）
```

### 问题4: 模拟应用处理缓慢

**症状**: 请求处理需要很长时间

**原因**: 可能是系统资源紧张

**解决**:
```bash
# 检查系统资源
top  # 查看CPU和内存使用
free -h  # 查看内存
df -h  # 查看磁盘空间
```

---

## 📈 监控和日志

### 查看WebSocket服务器日志

```bash
# 在服务器运行的终端中，查看实时日志
# 可以看到所有连接、请求和错误信息

# 也可以查看日志文件
tail -f error.log
```

### 查看模拟应用日志

```bash
# 运行时使用--verbose标志获得更详细的日志
python mock_app.py --host http://localhost:5001 --spaces "TestSpace_XXX" --verbose

# 日志会显示所有WebSocket事件
```

### 检查数据库状态

```bash
# 查看已连接的spaces
python3 << 'EOF'
import sys
sys.path.insert(0, '/gemini/code/websocket-spaces')
from project.websocket_manager import ws_manager
print("Connected spaces:", ws_manager.get_connected_spaces())
EOF
```

---

## 🎯 完整测试脚本

创建文件 `test_remote.sh` 并运行：

```bash
#!/bin/bash

# 远程服务器自动化测试脚本

echo "=========================================="
echo "WebSocket Spaces 远程测试"
echo "=========================================="

# 设置环境
source ws_env/bin/activate
cd /gemini/code/websocket-spaces

# 验证
python3 << 'PYEOF'
import sys
sys.path.insert(0, '.')

print("\n✅ 远程环境验证:")
print("  Python:", sys.version)
print("  Path:", sys.executable)

# 验证模块导入
try:
    from project.websocket_manager import WebSocketManager
    print("  ✓ WebSocketManager 导入成功")
except ImportError as e:
    print(f"  ✗ 导入失败: {e}")
    sys.exit(1)

# 验证功能
manager = WebSocketManager()
success, conn_id = manager.register_connection('test', 'test', 'sess')
if success:
    print("  ✓ 连接注册成功")
else:
    print("  ✗ 连接注册失败")
    sys.exit(1)

print("\n✅ 远程环境就绪!")

PYEOF
```

---

## ✅ 最终检查清单

完成远程部署测试前，确保：

- [ ] SSH连接成功
- [ ] 虚拟环境已创建和激活
- [ ] 所有依赖已安装
- [ ] 项目文件已复制
- [ ] 服务器启动成功
- [ ] space已创建
- [ ] 模拟应用已连接
- [ ] 浏览器可以访问
- [ ] 所有功能都可以正常工作
- [ ] 日志显示正确的操作顺序

---

## 🎓 远程测试后的操作

### 1. 验证成功

如果所有测试都通过，您已经成功地：
- ✅ 在远程服务器上部署了WebSocket Spaces
- ✅ 验证了所有核心功能
- ✅ 测试了WebSocket连接
- ✅ 确认了请求处理流程

### 2. 生产部署准备

接下来可以考虑：
- 配置systemd service自动启动
- 设置nginx反向代理
- 启用SSL/TLS
- 配置自动备份
- 设置监控和告警

### 3. 集成第三方应用

可以使用提供的 `websocket_integration_client.py` 来集成：
- IndexTTS2
- 其他AI推理应用
- 自定义业务应用

---

## 📞 快速参考

### 常用命令

```bash
# 进入项目
cd /gemini/code/websocket-spaces

# 激活虚拟环境
source ws_env/bin/activate

# 启动服务器
python run.py

# 创建space
python test_websockets.py --setup-space --host http://localhost:5001

# 启动模拟应用
python mock_app.py --host http://localhost:5001 --spaces "MySpace" --verbose

# 查看日志
tail -f error.log
```

### Screen会话管理

```bash
# 创建新会话
screen -S websocket_test

# 列出所有会话
screen -ls

# 连接到会话
screen -r websocket_test

# 在会话中创建新窗口
Ctrl+A+C

# 切换窗口
Ctrl+A+N (下一个)
Ctrl+A+P (上一个)
Ctrl+A+0-9 (特定窗口)

# 分离会话
Ctrl+A+D
```

---

**现在您可以在远程服务器上进行完整的WebSocket Spaces测试！** 🚀

