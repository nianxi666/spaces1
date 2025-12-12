#!/bin/bash

# 完整的WebSocket Spaces测试脚本

set -e  # 出错时停止

echo "========================================"
echo "WebSocket Spaces 完整集成测试"
echo "========================================"
echo ""

# 设置虚拟环境
echo "📦 步骤 1: 设置虚拟环境..."
if [ ! -d "/tmp/ws_test_env" ]; then
    python3 -m venv /tmp/ws_test_env
    source /tmp/ws_test_env/bin/activate
    pip install -q Flask Flask-SocketIO python-socketio python-engineio requests python-engineio
    echo "✅ 虚拟环境创建完成"
else
    source /tmp/ws_test_env/bin/activate
    echo "✅ 虚拟环境已激活"
fi

cd /home/engine/project

# 检查代码完整性
echo ""
echo "📋 步骤 2: 检查代码完整性..."
files_to_check=(
    "project/websocket_manager.py"
    "project/websocket_handler.py"
    "project/templates/space_websockets.html"
    "mock_app.py"
    "test_websockets.py"
)

all_good=true
for file in "${files_to_check[@]}"; do
    if [ -f "$file" ]; then
        size=$(wc -c < "$file")
        echo "  ✓ $file ($size bytes)"
    else
        echo "  ✗ $file (缺失)"
        all_good=false
    fi
done

if [ "$all_good" = false ]; then
    echo ""
    echo "❌ 某些文件缺失！"
    exit 1
fi

# 验证Python代码语法
echo ""
echo "🔍 步骤 3: 验证Python代码语法..."
for file in project/websocket_manager.py project/websocket_handler.py mock_app.py test_websockets.py; do
    if python3 -m py_compile "$file" 2>/dev/null; then
        echo "  ✓ $file"
    else
        echo "  ✗ $file 有语法错误"
        exit 1
    fi
done

# 测试WebSocket管理器导入
echo ""
echo "🧪 步骤 4: 测试关键模块导入..."
python3 << 'EOF'
import sys
sys.path.insert(0, '/home/engine/project')

try:
    # 测试能否导入websocket_manager
    from project.websocket_manager import ws_manager, WebSocketManager, WebSocketConnection
    print("  ✓ websocket_manager 可导入")
except ImportError as e:
    print(f"  ✗ websocket_manager 导入失败: {e}")
    sys.exit(1)

# 验证WebSocketManager有关键方法
manager = WebSocketManager()
methods_to_check = [
    'register_connection',
    'is_space_connected',
    'queue_inference_request',
    'get_request_status',
    'get_connected_spaces'
]

for method in methods_to_check:
    if hasattr(manager, method):
        print(f"  ✓ WebSocketManager.{method} 存在")
    else:
        print(f"  ✗ WebSocketManager.{method} 缺失")
        sys.exit(1)

print("\n✅ 所有关键方法都已实现")
EOF

# 测试mock_app是否可运行
echo ""
echo "🎯 步骤 5: 检查mock_app.py..."
python3 -c "
import sys
sys.path.insert(0, '/home/engine/project')
from mock_app import MockInferenceApp

# 创建实例但不连接
app = MockInferenceApp('http://localhost:5001', 'TestSpace')
print('  ✓ MockInferenceApp 实例化成功')
print(f'  ✓ Host: {app.host}')
print(f'  ✓ Space: {app.space_name}')
"

# 测试test_websockets.py导入
echo ""
echo "🧪 步骤 6: 检查test_websockets.py..."
python3 << 'EOF'
import sys
sys.path.insert(0, '/home/engine/project')

try:
    from test_websockets import WebSocketTester
    print("  ✓ WebSocketTester 可导入")
    
    tester = WebSocketTester('http://localhost:5001', 'testuser', 'testpass')
    print("  ✓ WebSocketTester 实例化成功")
except Exception as e:
    print(f"  ✗ 测试器导入失败: {e}")
    sys.exit(1)
EOF

# 显示最后的总结
echo ""
echo "========================================"
echo "✅ 所有代码验证通过！"
echo "========================================"
echo ""
echo "📝 接下来的步骤:"
echo ""
echo "在3个不同的终端中运行:"
echo ""
echo "  终端1:"
echo "    source /tmp/ws_test_env/bin/activate"
echo "    cd /home/engine/project"
echo "    python run.py"
echo ""
echo "  终端2:"
echo "    source /tmp/ws_test_env/bin/activate"
echo "    cd /home/engine/project"
echo "    python test_websockets.py --setup-space --host http://localhost:5001"
echo ""
echo "  终端3 (在终端2之后，使用space名称):"
echo "    source /tmp/ws_test_env/bin/activate"
echo "    cd /home/engine/project"
echo "    python mock_app.py --host http://localhost:5001 --spaces 'TestSpace_XXXXX' --verbose"
echo ""
echo "  浏览器:"
echo "    http://localhost:5001"
echo ""
echo "========================================"
