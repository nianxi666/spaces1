import requests
import asyncio
import socketio
import argparse
import uuid

# 全局变量，用于在 WebSocket 事件处理函数中设置
task_result = None
task_update = None
is_connected = asyncio.Event()

# 创建 Socket.IO 客户端实例
sio = socketio.AsyncClient()

@sio.event
async def connect():
    """连接成功时调用的事件处理函数"""
    print("客户端连接成功")
    is_connected.set()

@sio.on('task_update')
async def on_task_update(data):
    """接收到任务更新时调用的事件处理函数"""
    global task_update
    print(f"收到任务更新: {data}")
    task_update = data
    # 如果任务完成或失败，断开连接以结束脚本
    if data.get('status') in ['completed', 'failed']:
        await sio.disconnect()

@sio.on('task_result')
async def on_task_result(data):
    """接收到任务最终结果时调用的事件处理函数"""
    global task_result
    print(f"收到最终任务结果: {data}")
    task_result = data
    await sio.disconnect() # 收到最终结果后断开连接

@sio.event
async def disconnect():
    """断开连接时调用的事件处理函数"""
    print("客户端已断开连接")

async def listen_for_task_updates(host, task_id):
    """连接到 WebSocket 并监听特定任务的更新"""
    try:
        # 连接到服务器，不指定命名空间
        await sio.connect(host, transports=['websocket'])
        await is_connected.wait()
        # 加入与任务 ID 对应的房间
        await sio.emit('join_task_room', {'task_id': task_id})
        print(f"已加入任务房间: {task_id}")

        # 等待结果，设置超时
        try:
            await asyncio.wait_for(sio.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            print("等待任务结果超时")
    except Exception as e:
        print(f"WebSocket 连接或监听时发生错误: {e}")
    finally:
        if sio.connected:
            await sio.disconnect()

def submit_task(host, space_id, payload):
    """通过 HTTP POST 请求提交任务"""
    url = f"{host}/api/space/{space_id}/submit_task"
    try:
        # Create a session to handle cookies
        s = requests.Session()
        # Perform a dummy login to get the session cookie
        s.post(f"{host}/login", data={'username': 'testadmin', 'password': 'password'})
        response = s.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"提交任务失败: {e}")
        # 尝试打印更详细的错误信息
        if e.response is not None:
            try:
                print(f"响应内容: {e.response.json()}")
            except ValueError:
                print(f"响应文本: {e.response.text}")
        return None

def main():
    parser = argparse.ArgumentParser(description="提交任务并使用 WebSocket 验证结果")
    parser.add_argument('--host', type=str, required=True, help="服务器的 URL (例如 http://127.0.0.1:5001)")
    parser.add_argument('--space_id', type=str, required=True, help="要提交任务的 Space ID")
    args = parser.parse_args()

    # 1. 提交任务
    unique_prompt = f"这是一个唯一的测试提示 {uuid.uuid4()}"
    payload = {
        'inputs': {
            'text': unique_prompt
        },
        'some_other_param': 'value123'
    }

    print(f"正在向 Space {args.space_id} 提交任务...")
    submission_response = submit_task(args.host, args.space_id, payload)

    if not submission_response or 'task_id' not in submission_response:
        print("任务提交失败，无法获取 task_id")
        return

    task_id = submission_response['task_id']
    print(f"任务提交成功，Task ID: {task_id}")

    # 2. 监听 WebSocket 更新
    print("\n正在连接 WebSocket 以监听任务更新...")
    asyncio.run(listen_for_task_updates(args.host, task_id))

    # 3. 验证结果
    print("\n--- 验证 ---")
    if task_update:
        print(f"最终的任务更新状态: {task_update.get('status')}")
        if task_update.get('status') == 'completed':
            print("测试成功：任务状态为 'completed'")
            result_output = task_update.get('result', {}).get('output', '')
            if unique_prompt in result_output:
                 print("测试成功：任务结果中包含了唯一的提示")
            else:
                 print("测试失败：任务结果中未找到唯一的提示")
        else:
            print(f"测试失败：任务最终状态为 '{task_update.get('status')}'")
    else:
        print("测试失败：未收到任何任务更新")


if __name__ == '__main__':
    main()
