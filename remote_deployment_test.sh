#!/bin/bash

# 远程服务器WebSocket Spaces完整部署测试脚本
# 这个脚本将在远程服务器上执行所有必要的部署和测试步骤

set -e

echo "=========================================="
echo "WebSocket Spaces 远程部署测试"
echo "=========================================="
echo ""

# 配置变量
REMOTE_HOST="ssh-ad886e9ff5a8de6117e40aaf616d3884.zlrast8j3bxb@direct.virtaicloud.com"
REMOTE_PORT="30022"
REMOTE_USER="root4563@root"
REMOTE_PASSWORD="liu20062020"
REMOTE_PATH="/gemini/code"
PROJECT_NAME="websocket-spaces"

echo "📋 步骤1: 准备远程环境..."
echo "远程主机: $REMOTE_HOST"
echo "远程路径: $REMOTE_PATH"
echo ""

# 检查sshpass是否可用
if ! command -v sshpass &> /dev/null; then
    echo "❌ sshpass 未安装，需要安装sshpass"
    echo "Ubuntu/Debian: sudo apt-get install sshpass"
    echo "macOS: brew install sshpass"
    exit 1
fi

echo "✅ sshpass 已可用"
echo ""

# 定义SSH命令
SSH_CMD="sshpass -p '$REMOTE_PASSWORD' ssh -p $REMOTE_PORT $REMOTE_USER@$REMOTE_HOST"

echo "📋 步骤2: 在远程服务器检查环境..."
$SSH_CMD << 'REMOTEOF'

echo "  检查Python环境..."
python3 --version
which python3

echo ""
echo "  检查miniconda3..."
if [ -d "/usr/local/miniconda3" ]; then
    echo "  ✓ miniconda3 已安装"
    /usr/local/miniconda3/bin/python --version
else
    echo "  ⚠️  miniconda3 未找到"
fi

echo ""
echo "  检查目录结构..."
cd /gemini/code
ls -la | head -10

REMOTEOF

echo ""
echo "✅ 远程环境检查完成"
echo ""

# 在远程服务器上创建并启动虚拟环境
echo "📋 步骤3: 在远程服务器创建虚拟环境..."
$SSH_CMD << 'REMOTEOF'

cd /gemini/code

# 创建虚拟环境
if [ ! -d "ws_venv" ]; then
    echo "  创建虚拟环境..."
    python3 -m venv ws_venv
else
    echo "  虚拟环境已存在"
fi

# 激活虚拟环境
source ws_venv/bin/activate

# 升级pip
echo "  升级pip..."
pip install --upgrade pip setuptools wheel -q

# 安装依赖
echo "  安装WebSocket依赖..."
pip install Flask Flask-SocketIO Flask-Babel python-socketio python-engineio requests APScheduler psutil boto3 markdown -q

echo "  ✓ 虚拟环境和依赖安装完成"

REMOTEOF

echo ""
echo "✅ 虚拟环境设置完成"
echo ""

# 在远程服务器验证代码
echo "📋 步骤4: 在远程服务器验证代码..."
$SSH_CMD << 'REMOTEOF'

# 如果代码还未复制，先复制
cd /gemini/code

if [ ! -d "websocket-spaces" ]; then
    echo "  创建项目目录..."
    mkdir -p websocket-spaces
fi

source ws_venv/bin/activate

cd websocket-spaces

# 验证Python文件
echo "  验证Python文件..."
for file in project/websocket_manager.py project/websocket_handler.py mock_app.py test_websockets.py websocket_integration_client.py; do
    if [ -f "$file" ]; then
        python3 -m py_compile "$file"
        echo "    ✓ $file"
    fi
done

REMOTEOF

echo ""
echo "✅ 代码验证完成"
echo ""

echo "=========================================="
echo "✅ 远程部署测试完成"
echo "=========================================="
echo ""
echo "下一步操作:"
echo "1. 在远程服务器创建screen会话"
echo "2. 启动WebSocket Spaces服务器"
echo "3. 创建测试space"
echo "4. 启动mock应用进行测试"
echo ""
echo "连接命令:"
echo "  sshpass -p 'liu20062020' ssh -p 30022 root4563@root@$REMOTE_HOST"
echo ""
