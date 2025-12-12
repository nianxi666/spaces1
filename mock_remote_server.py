"""
模拟远程推理服务器 - 用于测试推理结果文件能否正常传输回来

这个脚本模拟远程GPU服务器的行为：
1. 接收推理请求（命令）
2. 模拟AI生成内容（创建假的输出文件）
3. 将结果上传到S3
4. 返回执行结果

运行方式: python mock_remote_server.py
默认端口: 5002
"""

import os
import time
import uuid
import json
import random
import threading
from flask import Flask, request, jsonify, Response, send_from_directory
from werkzeug.utils import secure_filename
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import io

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mock-remote-server-secret-key'

# 模拟的输出目录
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'mock_output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 存储任务状态
mock_tasks = {}

def generate_mock_image(prompt, width=512, height=512):
    """
    生成一个模拟的AI图像
    """
    # 创建一个渐变背景的图像
    img = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(img)
    
    # 生成渐变色背景
    for y in range(height):
        r = int(100 + (155 * y / height))
        g = int(50 + (100 * y / height))
        b = int(150 + (105 * (1 - y / height)))
        for x in range(width):
            x_factor = x / width
            final_r = int(r * (1 - x_factor) + (255 - r) * x_factor)
            final_g = int(g * (1 - x_factor) + (200 - g) * x_factor)
            final_b = int(b * (1 - x_factor) + (100 - b) * x_factor)
            draw.point((x, y), fill=(final_r, final_g, final_b))
    
    # 在图像上添加文字
    try:
        # 尝试使用默认字体
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    
    # 添加提示词信息
    text_lines = [
        "🎨 Mock AI Generated Image",
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Prompt: {prompt[:50]}..." if len(prompt) > 50 else f"Prompt: {prompt}",
        f"Size: {width}x{height}",
        "✅ This is a test image"
    ]
    
    y_offset = 20
    for line in text_lines:
        # 绘制文字阴影
        draw.text((22, y_offset + 2), line, fill=(0, 0, 0), font=font)
        # 绘制文字
        draw.text((20, y_offset), line, fill=(255, 255, 255), font=font)
        y_offset += 30
    
    # 添加装饰边框
    for i in range(3):
        draw.rectangle(
            [i, i, width - 1 - i, height - 1 - i],
            outline=(255, 215, 0)  # 金色边框
        )
    
    return img


def generate_mock_3d_file(prompt):
    """
    生成一个模拟的3D文件（简单的GLB文件头）
    实际上这不是有效的GLB文件，只是用于测试传输
    """
    # 创建一个简单的占位内容
    content = {
        "type": "mock_3d_model",
        "prompt": prompt,
        "generated_at": datetime.now().isoformat(),
        "message": "This is a mock 3D file for testing purposes"
    }
    return json.dumps(content, indent=2).encode('utf-8')


def generate_mock_video():
    """
    生成一个模拟的视频内容（实际是一些二进制数据）
    """
    # 生成一些随机数据作为模拟视频
    header = b"MOCK_VIDEO_FILE\x00\x00\x00\x00"
    data = os.urandom(1024 * 10)  # 10KB 的随机数据
    return header + data


def simulate_inference(task_id, command, presigned_url, output_filename):
    """
    模拟推理过程
    """
    try:
        mock_tasks[task_id]['status'] = 'running'
        mock_tasks[task_id]['logs'] = f"[Mock Server] Starting inference...\n"
        mock_tasks[task_id]['logs'] += f"[Mock Server] Command: {command}\n"
        
        # 从命令中提取 prompt
        prompt = "default prompt"
        if '--prompt' in command:
            parts = command.split('--prompt')
            if len(parts) > 1:
                prompt_part = parts[1].strip()
                # 提取引号中的内容
                if prompt_part.startswith("'"):
                    end_idx = prompt_part.find("'", 1)
                    if end_idx > 0:
                        prompt = prompt_part[1:end_idx]
                elif prompt_part.startswith('"'):
                    end_idx = prompt_part.find('"', 1)
                    if end_idx > 0:
                        prompt = prompt_part[1:end_idx]
                else:
                    prompt = prompt_part.split()[0] if prompt_part else "default"
        
        mock_tasks[task_id]['logs'] += f"[Mock Server] Extracted prompt: {prompt}\n"
        
        # 模拟推理延迟 (2-5秒)
        delay = random.uniform(2, 5)
        mock_tasks[task_id]['logs'] += f"[Mock Server] Simulating inference for {delay:.2f} seconds...\n"
        time.sleep(delay)
        
        # 确定输出文件类型
        ext = os.path.splitext(output_filename)[1].lower()
        
        # 创建输出目录
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # 根据文件类型生成不同的内容
        if ext in ['.png', '.jpg', '.jpeg']:
            mock_tasks[task_id]['logs'] += f"[Mock Server] Generating mock image...\n"
            img = generate_mock_image(prompt)
            
            if ext == '.png':
                img.save(output_path, 'PNG')
            else:
                img.save(output_path, 'JPEG', quality=95)
            
            mock_tasks[task_id]['logs'] += f"[Mock Server] Image saved to {output_path}\n"
            
        elif ext == '.glb':
            mock_tasks[task_id]['logs'] += f"[Mock Server] Generating mock 3D model...\n"
            content = generate_mock_3d_file(prompt)
            with open(output_path, 'wb') as f:
                f.write(content)
            mock_tasks[task_id]['logs'] += f"[Mock Server] 3D model saved to {output_path}\n"
            
        elif ext in ['.mp4', '.webm']:
            mock_tasks[task_id]['logs'] += f"[Mock Server] Generating mock video...\n"
            content = generate_mock_video()
            with open(output_path, 'wb') as f:
                f.write(content)
            mock_tasks[task_id]['logs'] += f"[Mock Server] Video saved to {output_path}\n"
            
        else:
            # 默认生成文本文件
            mock_tasks[task_id]['logs'] += f"[Mock Server] Generating default output file...\n"
            content = f"""
Mock Output File
================
Generated at: {datetime.now().isoformat()}
Prompt: {prompt}
File type: {ext}
Task ID: {task_id}

This is a mock output file generated for testing purposes.
"""
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        # 如果提供了预签名URL，上传文件到S3
        if presigned_url:
            mock_tasks[task_id]['logs'] += f"[Mock Server] Uploading to S3...\n"
            mock_tasks[task_id]['logs'] += f"[Mock Server] Presigned URL: {presigned_url[:100]}...\n"
            
            try:
                with open(output_path, 'rb') as f:
                    file_content = f.read()
                
                # 使用 PUT 请求上传到 S3
                response = requests.put(presigned_url, data=file_content)
                
                if response.status_code in [200, 201, 204]:
                    mock_tasks[task_id]['logs'] += f"[Mock Server] ✅ Upload successful! Status: {response.status_code}\n"
                else:
                    mock_tasks[task_id]['logs'] += f"[Mock Server] ⚠️ Upload response: {response.status_code} - {response.text[:200]}\n"
                    
            except Exception as e:
                mock_tasks[task_id]['logs'] += f"[Mock Server] ❌ Upload error: {str(e)}\n"
        
        mock_tasks[task_id]['status'] = 'completed'
        mock_tasks[task_id]['output_file'] = output_path
        mock_tasks[task_id]['logs'] += f"[Mock Server] ✅ Task completed successfully!\n"
        
    except Exception as e:
        mock_tasks[task_id]['status'] = 'failed'
        mock_tasks[task_id]['logs'] += f"[Mock Server] ❌ Error: {str(e)}\n"


@app.route('/')
def index():
    """首页 - 显示服务器状态"""
    return jsonify({
        'server': 'Mock Remote Inference Server',
        'status': 'running',
        'version': '1.0.0',
        'endpoints': {
            '/run': 'POST - 运行推理任务',
            '/task/<task_id>/status': 'GET - 获取任务状态',
            '/tasks': 'GET - 获取所有任务列表',
            '/output/<path:filename>': 'GET - 下载输出文件'
        },
        'active_tasks': len(mock_tasks)
    })


@app.route('/run', methods=['POST'])
def run_inference():
    """
    接收推理请求并启动模拟推理
    
    请求格式可以是 JSON 或 form-data:
    {
        "command": "python generate.py --prompt 'a cute cat'",
        "presigned_url": "https://s3.example.com/bucket/file?...",
        "output_filename": "output/result.png"
    }
    """
    # 获取请求数据
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.to_dict()
    
    command = data.get('command', '')
    presigned_url = data.get('presigned_url', '')
    output_filename = data.get('output_filename', 'output/output.png')
    
    if not command:
        return jsonify({'error': 'Missing command parameter'}), 400
    
    # 创建任务
    task_id = str(uuid.uuid4())
    mock_tasks[task_id] = {
        'status': 'pending',
        'logs': '',
        'output_file': None,
        'created_at': datetime.now().isoformat(),
        'command': command
    }
    
    # 在后台线程中运行推理
    thread = threading.Thread(
        target=simulate_inference,
        args=(task_id, command, presigned_url, output_filename)
    )
    thread.start()
    
    return jsonify({
        'task_id': task_id,
        'message': 'Inference task started',
        'status_url': f'/task/{task_id}/status'
    })


@app.route('/run_stream', methods=['POST'])
def run_inference_stream():
    """
    流式运行推理并实时返回日志
    """
    # 获取请求数据
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.to_dict()
    
    command = data.get('command', '')
    presigned_url = data.get('presigned_url', '')
    output_filename = data.get('output_filename', 'output/output.png')
    
    if not command:
        return jsonify({'error': 'Missing command parameter'}), 400
    
    def generate():
        task_id = str(uuid.uuid4())
        mock_tasks[task_id] = {
            'status': 'running',
            'logs': '',
            'output_file': None,
            'created_at': datetime.now().isoformat(),
            'command': command
        }
        
        yield f"[Mock Server] Task ID: {task_id}\n"
        yield f"[Mock Server] Command: {command}\n"
        yield f"[Mock Server] Starting inference...\n"
        
        # 从命令中提取 prompt
        prompt = "default prompt"
        if '--prompt' in command:
            parts = command.split('--prompt')
            if len(parts) > 1:
                prompt_part = parts[1].strip()
                if prompt_part.startswith("'"):
                    end_idx = prompt_part.find("'", 1)
                    if end_idx > 0:
                        prompt = prompt_part[1:end_idx]
        
        yield f"[Mock Server] Extracted prompt: {prompt}\n"
        
        # 模拟推理过程
        for i in range(5):
            yield f"[Mock Server] Processing step {i+1}/5...\n"
            time.sleep(0.5)
        
        # 生成输出文件
        ext = os.path.splitext(output_filename)[1].lower()
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        if ext in ['.png', '.jpg', '.jpeg']:
            yield f"[Mock Server] Generating mock image...\n"
            img = generate_mock_image(prompt)
            if ext == '.png':
                img.save(output_path, 'PNG')
            else:
                img.save(output_path, 'JPEG', quality=95)
        else:
            yield f"[Mock Server] Generating mock output...\n"
            with open(output_path, 'w') as f:
                f.write(f"Mock output for: {prompt}")
        
        yield f"[Mock Server] Output saved to: {output_path}\n"
        
        # 上传到S3
        if presigned_url:
            yield f"[Mock Server] Uploading to S3...\n"
            try:
                with open(output_path, 'rb') as f:
                    response = requests.put(presigned_url, data=f)
                if response.status_code in [200, 201, 204]:
                    yield f"[Mock Server] ✅ Upload successful!\n"
                else:
                    yield f"[Mock Server] ⚠️ Upload status: {response.status_code}\n"
            except Exception as e:
                yield f"[Mock Server] ❌ Upload error: {e}\n"
        
        yield f"[Mock Server] ✅ Task completed!\n"
        mock_tasks[task_id]['status'] = 'completed'
        mock_tasks[task_id]['output_file'] = output_path
    
    return Response(generate(), mimetype='text/plain')


@app.route('/task/<task_id>/status')
def task_status(task_id):
    """获取任务状态"""
    task = mock_tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    return jsonify({
        'task_id': task_id,
        'status': task['status'],
        'logs': task['logs'],
        'output_file': task.get('output_file'),
        'created_at': task.get('created_at')
    })


@app.route('/tasks')
def list_tasks():
    """列出所有任务"""
    return jsonify({
        'tasks': [
            {
                'task_id': tid,
                'status': task['status'],
                'created_at': task.get('created_at')
            }
            for tid, task in mock_tasks.items()
        ]
    })


@app.route('/output/<path:filename>')
def download_output(filename):
    """下载输出文件"""
    return send_from_directory(OUTPUT_DIR, filename)


@app.route('/clear_tasks', methods=['POST'])
def clear_tasks():
    """清除所有任务"""
    global mock_tasks
    mock_tasks = {}
    return jsonify({'message': 'All tasks cleared'})


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Mock Remote Inference Server")
    print("=" * 60)
    print(f"📁 Output directory: {OUTPUT_DIR}")
    print("🌐 Starting server on http://localhost:5002")
    print()
    print("Available endpoints:")
    print("  GET  /              - Server status")
    print("  POST /run           - Start inference task")
    print("  POST /run_stream    - Start inference with streaming output")
    print("  GET  /task/<id>/status - Get task status")
    print("  GET  /tasks         - List all tasks")
    print("  GET  /output/<file> - Download output file")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5002, debug=True)
