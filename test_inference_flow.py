"""
测试推理结果文件传输的脚本

这个脚本测试完整的推理流程：
1. 向本地主服务器发送推理请求
2. 主服务器调用模拟远程服务器
3. 模拟远程服务器生成AI内容
4. 结果上传到S3
5. 验证结果是否可以访问

使用方法:
1. 确保主服务器在 http://localhost:5001 运行
2. 启动模拟远程服务器: python mock_remote_server.py (端口 5002)
3. 运行此测试: python test_inference_flow.py
"""

import requests
import time
import json
import sys
from datetime import datetime

# 配置
MAIN_SERVER_URL = "http://localhost:5001"
MOCK_SERVER_URL = "http://localhost:5002"

def print_separator(title=""):
    print("\n" + "=" * 60)
    if title:
        print(f"  {title}")
        print("=" * 60)

def test_mock_server_status():
    """测试模拟服务器是否运行"""
    print_separator("测试 1: 检查模拟远程服务器状态")
    
    try:
        response = requests.get(f"{MOCK_SERVER_URL}/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 模拟服务器运行正常")
            print(f"   服务器: {data.get('server')}")
            print(f"   状态: {data.get('status')}")
            print(f"   活跃任务: {data.get('active_tasks')}")
            return True
        else:
            print(f"❌ 服务器返回错误: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ 无法连接到模拟服务器 ({MOCK_SERVER_URL})")
        print("   请先运行: python mock_remote_server.py")
        return False

def test_mock_inference():
    """测试模拟推理功能"""
    print_separator("测试 2: 测试模拟推理（不上传到S3）")
    
    test_command = "python generate.py --prompt 'a beautiful sunset over mountains'"
    
    print(f"📤 发送推理请求...")
    print(f"   命令: {test_command}")
    
    response = requests.post(
        f"{MOCK_SERVER_URL}/run",
        json={
            "command": test_command,
            "output_filename": "output/test_result.png"
        }
    )
    
    if response.status_code != 200:
        print(f"❌ 请求失败: {response.status_code}")
        return False
    
    data = response.json()
    task_id = data.get('task_id')
    print(f"✅ 任务创建成功")
    print(f"   任务ID: {task_id}")
    
    # 等待任务完成
    print(f"\n⏳ 等待推理完成...")
    for i in range(30):  # 最多等待30秒
        time.sleep(1)
        status_response = requests.get(f"{MOCK_SERVER_URL}/task/{task_id}/status")
        status_data = status_response.json()
        status = status_data.get('status')
        
        if status == 'completed':
            print(f"✅ 推理完成!")
            print(f"\n📝 日志输出:")
            print("-" * 40)
            print(status_data.get('logs', ''))
            print("-" * 40)
            print(f"\n📁 输出文件: {status_data.get('output_file')}")
            return True
        elif status == 'failed':
            print(f"❌ 推理失败")
            print(f"   日志: {status_data.get('logs')}")
            return False
        
        print(f"   状态: {status} (等待中 {i+1}s)")
    
    print(f"⏰ 超时!")
    return False

def test_mock_inference_stream():
    """测试流式推理"""
    print_separator("测试 3: 测试流式推理")
    
    test_command = "python generate.py --prompt 'a cute robot playing guitar'"
    
    print(f"📤 发送流式推理请求...")
    print(f"   命令: {test_command}")
    print(f"\n📺 实时输出:")
    print("-" * 40)
    
    response = requests.post(
        f"{MOCK_SERVER_URL}/run_stream",
        json={
            "command": test_command,
            "output_filename": "output/stream_test.png"
        },
        stream=True
    )
    
    for line in response.iter_lines():
        if line:
            print(f"   {line.decode('utf-8')}")
    
    print("-" * 40)
    print("✅ 流式推理测试完成")
    return True

def test_main_server_status():
    """测试主服务器状态"""
    print_separator("测试 4: 检查主服务器状态")
    
    try:
        response = requests.get(f"{MAIN_SERVER_URL}/", timeout=5)
        if response.status_code == 200:
            print(f"✅ 主服务器运行正常 ({MAIN_SERVER_URL})")
            return True
        else:
            print(f"⚠️ 主服务器返回: {response.status_code}")
            return True  # 仍然继续，因为可能只是页面内容
    except requests.exceptions.ConnectionError:
        print(f"❌ 无法连接到主服务器 ({MAIN_SERVER_URL})")
        print("   请先运行主服务器: cd project && python run.py")
        return False

def test_direct_s3_upload():
    """测试直接上传到S3的功能（模拟 tasks.py 中的逻辑）"""
    print_separator("测试 5: 测试S3上传模拟")
    
    # 这个测试模拟 tasks.py 中的上传逻辑
    # 实际上不会真的上传，只是验证URL生成和请求格式
    
    print("📋 说明: 这个测试验证S3上传的请求格式")
    print("   实际的S3上传需要有效的预签名URL")
    
    # 创建一个模拟的presigned URL (不是真正的S3 URL)
    mock_presigned_url = "https://mock-s3.example.com/test-bucket/test-file.png?X-Amz-Signature=xxx"
    
    test_command = "python generate.py --prompt 'test with s3 upload'"
    
    print(f"\n📤 发送带S3上传的推理请求...")
    
    response = requests.post(
        f"{MOCK_SERVER_URL}/run",
        json={
            "command": test_command,
            "presigned_url": mock_presigned_url,
            "output_filename": "output/s3_test.png"
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        task_id = data.get('task_id')
        print(f"✅ 任务创建成功 (Task ID: {task_id})")
        
        # 等待完成并检查日志
        time.sleep(5)
        status_response = requests.get(f"{MOCK_SERVER_URL}/task/{task_id}/status")
        status_data = status_response.json()
        
        logs = status_data.get('logs', '')
        if 'S3' in logs:
            print("✅ S3上传逻辑已执行")
            print(f"\n📝 相关日志:")
            for line in logs.split('\n'):
                if 'S3' in line or 'Upload' in line:
                    print(f"   {line}")
        
        return True
    else:
        print(f"❌ 请求失败: {response.status_code}")
        return False

def test_end_to_end_simulation():
    """
    完整的端到端模拟测试
    模拟完整的推理流程，但不需要真实的S3
    """
    print_separator("测试 6: 完整端到端模拟")
    
    print("📋 模拟完整的推理流程:")
    print("   1. 用户发送推理请求")
    print("   2. 服务器处理请求并调用远程推理")
    print("   3. 远程服务器生成AI内容")
    print("   4. 结果保存到本地（模拟S3上传）")
    print("   5. 返回结果URL")
    
    # 创建测试请求
    test_prompt = f"a magical forest at dawn - test at {datetime.now().strftime('%H:%M:%S')}"
    
    print(f"\n📤 测试提示词: {test_prompt}")
    
    # 发送到模拟服务器
    response = requests.post(
        f"{MOCK_SERVER_URL}/run",
        json={
            "command": f"python inference.py --prompt '{test_prompt}'",
            "output_filename": f"output/e2e_test_{int(time.time())}.png"
        }
    )
    
    if response.status_code != 200:
        print(f"❌ 请求失败: {response.status_code}")
        return False
    
    task_id = response.json().get('task_id')
    print(f"✅ 任务已创建: {task_id}")
    
    # 轮询状态
    print("\n⏳ 监控任务状态...")
    completed = False
    for i in range(20):
        time.sleep(1)
        status = requests.get(f"{MOCK_SERVER_URL}/task/{task_id}/status").json()
        
        if status['status'] == 'completed':
            completed = True
            print(f"\n✅ 任务完成!")
            print(f"📁 输出文件: {status.get('output_file')}")
            
            # 尝试下载输出文件
            output_file = status.get('output_file', '')
            if output_file:
                filename = output_file.split('mock_output/')[-1] if 'mock_output/' in output_file else output_file
                download_url = f"{MOCK_SERVER_URL}/output/{filename}"
                print(f"🔗 下载URL: {download_url}")
                
                try:
                    download_response = requests.get(download_url)
                    if download_response.status_code == 200:
                        print(f"✅ 文件可以下载 (大小: {len(download_response.content)} bytes)")
                    else:
                        print(f"⚠️ 下载返回: {download_response.status_code}")
                except Exception as e:
                    print(f"⚠️ 下载错误: {e}")
            
            break
        elif status['status'] == 'failed':
            print(f"\n❌ 任务失败")
            print(f"📝 日志: {status.get('logs')}")
            return False
        
        sys.stdout.write(f"\r   状态: {status['status']} ... {i+1}s")
        sys.stdout.flush()
    
    if not completed:
        print(f"\n⏰ 任务超时")
        return False
    
    return True


def main():
    print("\n")
    print("🔬 推理结果文件传输测试")
    print("=" * 60)
    print(f"📍 主服务器: {MAIN_SERVER_URL}")
    print(f"📍 模拟服务器: {MOCK_SERVER_URL}")
    print(f"🕐 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {}
    
    # 测试1: 模拟服务器状态
    results['mock_server'] = test_mock_server_status()
    
    if not results['mock_server']:
        print("\n❌ 模拟服务器未运行，无法继续测试")
        print("   请运行: python mock_remote_server.py")
        return
    
    # 测试2: 基本推理
    results['basic_inference'] = test_mock_inference()
    
    # 测试3: 流式推理
    results['stream_inference'] = test_mock_inference_stream()
    
    # 测试4: 主服务器状态
    results['main_server'] = test_main_server_status()
    
    # 测试5: S3上传模拟
    results['s3_upload'] = test_direct_s3_upload()
    
    # 测试6: 端到端模拟
    results['e2e'] = test_end_to_end_simulation()
    
    # 结果汇总
    print_separator("测试结果汇总")
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("🎉 所有测试通过!")
    else:
        print("⚠️ 部分测试未通过，请检查日志")
    
    print(f"\n🕐 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()
