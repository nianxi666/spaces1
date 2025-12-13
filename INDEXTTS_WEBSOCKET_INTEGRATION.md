# IndexTTS WebUI与WebSocket Spaces集成指南

## 📋 概述

这个指南说明如何将IndexTTS2 WebUI与WebSocket Spaces系统集成，使IndexTTS可以通过WebSocket连接到中央服务器，接收推理请求。

---

## 🔧 两种模式

### 模式1: 本地模式（默认）

```bash
python webui.py --port 7860 --host 0.0.0.0
```

- IndexTTS在本地Gradio界面运行
- 不连接到WebSocket Spaces
- 推理结果仅保存在本地

### 模式2: WebSocket模式（新增）

```bash
python indextts_websocket_webui.py \
    --port 7860 \
    --host 0.0.0.0 \
    --websocket-server http://websocket-spaces-server:5001 \
    --websocket-space MyIndexTTS \
    --websocket-mode
```

- IndexTTS通过WebSocket连接到WebSocket Spaces服务器
- 接收来自中央服务器的推理请求
- 推理结果返回到中央服务器
- 支持多用户请求和排队

---

## 🚀 快速开始

### 前提条件

1. **WebSocket Spaces服务器已启动**
   ```bash
   # 在另一个服务器/终端启动
   cd /path/to/websocket-spaces
   python run.py  # 端口5001
   ```

2. **已创建IndexTTS WebSocket Space**
   ```bash
   python test_websockets.py --setup-space --host http://localhost:5001
   # 记下输出的space名称，如: TestSpace_IndexTTS_1704123456
   ```

3. **索引TTS环境已准备**
   - 模型已下载到 `/gemini/pretrain/IndexTTS-2`
   - 所有依赖已安装

### 步骤1: 复制修改后的WebUI文件

```bash
cd /gemini/code/indextts2

# 复制支持WebSocket的webui
cp /path/to/indextts_websocket_webui.py webui_ws.py

# 或替换原始文件（保存备份）
cp webui.py webui_original.py
cp indextts_websocket_webui.py webui.py
```

### 步骤2: 安装WebSocket依赖

```bash
pip install python-socketio python-engineio
```

### 步骤3: 启动WebSocket模式

```bash
# 使用WebSocket模式启动
python webui.py \
    --port 7860 \
    --host 0.0.0.0 \
    --websocket-server http://localhost:5001 \
    --websocket-space TestSpace_IndexTTS \
    --websocket-mode \
    --verbose
```

**预期输出:**
```
======================================================================
IndexTTS WebUI with WebSocket Support
======================================================================
✓ WebSocket Mode Enabled
  Server: http://localhost:5001
  Space: TestSpace_IndexTTS
  Connected: True
🚀 Starting Gradio server on 0.0.0.0:7860
======================================================================
```

### 步骤4: 验证连接

在浏览器中访问 `http://localhost:7860` 并观察：
- UI顶部应该显示绿色 "🟢 WebSocket Connected (TestSpace_IndexTTS)"
- 或点击 "刷新连接状态" 按钮查看连接状态

---

## 📝 使用场景

### 场景1: 本地使用

```bash
# 仅在本地使用Gradio UI
python webui.py --port 7860 --host 0.0.0.0
```

用途: 本地测试和开发

### 场景2: 通过中央服务器远程使用

**终端1 - WebSocket Spaces服务器:**
```bash
cd /path/to/websocket-spaces
python run.py
```

**终端2 - IndexTTS WebSocket模式:**
```bash
cd /gemini/code/indextts2
python webui.py \
    --websocket-server http://localhost:5001 \
    --websocket-space MyIndexTTS \
    --websocket-mode
```

**终端3或浏览器 - 提交请求:**
访问 `http://websocket-spaces-server:5001`，找到 "MyIndexTTS" space，提交推理请求。

IndexTTS会自动接收请求并处理。

### 场景3: 多个IndexTTS实例

在不同的远程机器上运行多个IndexTTS实例，都连接到同一个WebSocket Spaces服务器：

**机器1:**
```bash
python webui.py \
    --port 7860 \
    --websocket-server http://central-server:5001 \
    --websocket-space IndexTTS-GPU1 \
    --websocket-mode
```

**机器2:**
```bash
python webui.py \
    --port 7860 \
    --websocket-server http://central-server:5001 \
    --websocket-space IndexTTS-GPU2 \
    --websocket-mode
```

用户可以选择向不同的IndexTTS实例发送请求，实现负载均衡。

---

## 🔌 WebSocket连接配置

### 命令行参数

```bash
python webui.py \
    --websocket-server <URL>      # WebSocket服务器URL
    --websocket-space <NAME>      # Space名称（必须在服务器上创建）
    --websocket-mode              # 启用WebSocket模式
    --verbose                     # 详细日志
    --port 7860                   # Gradio端口
    --host 0.0.0.0                # Gradio主机
    --model_dir <PATH>            # 模型目录
    --fp16                        # 使用FP16推理
    --deepspeed                   # 使用DeepSpeed加速
    --cuda_kernel                 # 使用CUDA内核
```

### 必需参数（WebSocket模式）

1. `--websocket-server` - WebSocket服务器的URL
   - 示例: `http://192.168.1.100:5001`
   - 示例: `http://your-domain.com:5001`

2. `--websocket-space` - Space的名称
   - 必须与服务器上创建的space名称完全匹配
   - 大小写敏感
   - 示例: `IndexTTS-Room1`

3. `--websocket-mode` - 启用WebSocket模式的标志
   - 如果不加这个标志，即使配置了其他参数也不会启用WebSocket

---

## 🧪 测试WebSocket集成

### 测试1: 验证连接

```bash
# 启动WebSocket模式
python webui.py \
    --websocket-server http://localhost:5001 \
    --websocket-space TestSpace_IndexTTS \
    --websocket-mode \
    --verbose
```

在日志中应该看到：
```
[INFO] Connecting to WebSocket server: http://localhost:5001
[INFO] WebSocket connected
[INFO] Successfully registered with space: TestSpace_IndexTTS
[INFO] Connection ID: abc123def456
```

### 测试2: 测试推理请求

1. 在浏览器中访问 WebSocket Spaces服务器 (http://localhost:5001)
2. 登录并找到 "TestSpace_IndexTTS"
3. 确认连接状态显示为 "✓ 已连接"
4. 输入文本提示词，点击提交
5. IndexTTS WebUI应该显示处理日志
6. 结果应该返回到网站

### 测试3: 并发请求

从WebSocket Spaces网站同时提交多个推理请求，IndexTTS应该依次处理。

---

## 📊 日志和调试

### 启用详细日志

```bash
python webui.py \
    --websocket-server http://localhost:5001 \
    --websocket-space TestSpace \
    --websocket-mode \
    --verbose
```

详细日志会显示：
- WebSocket事件
- 连接/断开消息
- 推理请求接收
- 处理进度

### 查看WebSocket连接状态

在WebUI中点击 "刷新连接状态" 按钮，Textbox会显示：
- `✓ WebSocket 已连接到 SpaceName` - 已连接
- `✗ WebSocket 连接中或已断开...` - 未连接
- `ℹ️  本地模式` - 未启用WebSocket

### 常见问题诊断

**问题: 无法连接到服务器**
```
日志显示: Failed to connect to WebSocket: Connection refused
```
解决:
1. 确认WebSocket Spaces服务器正在运行 (`python run.py`)
2. 确认服务器地址和端口正确
3. 检查防火墙是否允许连接

**问题: 注册失败**
```
日志显示: Registration failed: Space not found
```
解决:
1. 确认space名称完全匹配（大小写敏感）
2. 确认space已在服务器上创建
3. 确认space类型是"WebSocket"

**问题: 连接已建立但无法接收请求**
```
日志显示: WebSocket connected, Registration successful
但没有接收到推理请求
```
解决:
1. 检查WebUI是否真正在监听请求
2. 查看WebSocket Spaces服务器日志
3. 检查浏览器console中是否有错误

---

## 🔄 自动重连

WebSocket客户端已配置自动重连：
- 重连延迟: 1秒（初始）
- 最大延迟: 5秒
- 重连条件: 连接断开时自动重连

断开后：
1. WebUI UI会显示 "🟡 WebSocket Connecting..." 或 "🔴 Local Mode"
2. 自动尝试重新连接
3. 重新连接成功后会回到 "🟢 WebSocket Connected"

---

## 💾 保存和部署

### 保存配置

创建启动脚本 `start_indextts_websocket.sh`:

```bash
#!/bin/bash

cd /gemini/code/indextts2

# 激活虚拟环境（如果使用）
# source venv/bin/activate

# 启动WebSocket模式
python webui.py \
    --websocket-server http://websocket-server:5001 \
    --websocket-space IndexTTS-Space \
    --websocket-mode \
    --port 7860 \
    --host 0.0.0.0 \
    --model_dir /gemini/pretrain/IndexTTS-2 \
    --verbose
```

### 使用Screen运行（持久化）

```bash
# 创建新的screen会话
screen -S indextts

# 在screen中运行
bash start_indextts_websocket.sh

# 分离会话: Ctrl+A+D
# 重新连接: screen -r indextts
```

### 使用Systemd（生产环境）

创建 `/etc/systemd/system/indextts.service`:

```ini
[Unit]
Description=IndexTTS WebSocket Service
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/gemini/code/indextts2
ExecStart=/usr/bin/python3 webui.py \
    --websocket-server http://websocket-server:5001 \
    --websocket-space IndexTTS-Space \
    --websocket-mode
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动:
```bash
sudo systemctl start indextts
sudo systemctl enable indextts  # 开机自启
```

---

## 🎯 最佳实践

1. **Space命名**
   - 使用清晰的命名约定: `IndexTTS-GPU1`, `IndexTTS-HighQuality`
   - 避免使用特殊字符或空格

2. **错误处理**
   - 启用 `--verbose` 以便调试
   - 监控日志以快速发现问题

3. **性能优化**
   - 使用 `--fp16` 降低内存占用
   - 使用 `--deepspeed` 加速推理
   - 根据GPU选择合适的参数

4. **监控**
   - 定期检查WebSocket连接状态
   - 监控服务器日志
   - 设置告警机制

---

## 📞 故障排除

### 常见错误和解决方案

| 错误 | 原因 | 解决方案 |
|------|------|--------|
| Connection refused | 服务器未运行 | 启动WebSocket Spaces服务器 |
| Space not found | Space名称错误 | 检查并确认space名称 |
| socketio not available | 未安装socketio | `pip install python-socketio` |
| Multiple spaces found | 多个同名space | 删除重复的space |
| Connection timeout | 网络问题 | 检查网络和防火墙 |

### 获取帮助

1. 查看日志: `--verbose` 标志
2. 检查服务器日志
3. 参考 WebSocket Spaces 文档
4. 检查网络连接

---

## 📈 监控和指标

WebSocket集成提供以下监控点：

1. **连接状态**: 已连接/未连接
2. **Connection ID**: 唯一标识符
3. **推理请求计数**: 已接收的请求数
4. **处理时间**: 每个请求的处理时间
5. **错误日志**: 所有错误和警告

---

## 🎓 高级主题

### 自定义推理回调

可以修改 `gen_single` 函数以集成WebSocket回调：

```python
def gen_single(..., *args, progress=gr.Progress()):
    # ... 现有代码 ...
    
    output = tts.infer(...)
    
    # 如果在WebSocket模式，发送结果回服务器
    if ws_client and ws_client.is_connected():
        request_id = generate_request_id()  # 需要实现
        ws_client.send_result(request_id, 'completed', {
            'audio_path': output,
            'timestamp': datetime.now().isoformat()
        })
    
    return gr.update(value=output, visible=True)
```

### 处理多个Space

可以修改代码以支持连接到多个space或动态切换space。

---

## ✅ 验证清单

启用WebSocket集成后，确保：

- [ ] 依赖已安装
- [ ] WebSocket Spaces服务器正在运行
- [ ] Space已在服务器上创建
- [ ] IndexTTS WebUI已启动
- [ ] WebSocket连接已建立
- [ ] UI显示连接状态
- [ ] 可以从网站发送推理请求
- [ ] IndexTTS正确接收和处理请求

---

**准备好与WebSocket Spaces集成了！** 🚀

