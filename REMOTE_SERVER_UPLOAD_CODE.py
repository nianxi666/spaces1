"""
远程服务器上传代码 - 替换现有的 upload_to_s3 函数

将这段代码替换到远程服务器的 webui.py 或 app.py 中
"""

import requests
import os

# 配置
RELAY_API_URL = "https://your-website.com/api/relay-to-s3"  # 替换为您的网站地址
API_KEY = "YOUR_API_KEY_HERE"  # 替换为实际的API Key

def upload_to_relay_server(file_path, object_name=None):
    """
    上传文件到中转服务器，服务器会自动转存到S3并删除本地副本
    
    Args:
        file_path: 本地文件路径
        object_name: 在S3中的文件名（如果为None则使用原文件名）
    
    Returns:
        str: S3公共URL，如果失败则返回None
    """
    if object_name is None:
        object_name = os.path.basename(file_path)
    
    try:
        # 准备文件上传
        with open(file_path, 'rb') as f:
            files = {'file': (object_name, f, 'audio/wav')}
            headers = {'Authorization': f'Bearer {API_KEY}'}
            
            # 发送到中转服务器
            print(f"Uploading {object_name} to relay server...")
            response = requests.post(
                RELAY_API_URL,
                files=files,
                headers=headers,
                timeout=300  # 5分钟超时
            )
        
        # 检查响应
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                public_url = data.get('public_url')
                print(f"✅ Uploaded to S3: {public_url}")
                return public_url
            else:
                print(f"❌ Upload failed: {data.get('error')}")
                return None
        else:
            print(f"❌ HTTP Error {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Upload Error: {e}")
        return None


# ===== 使用示例 =====
# 在 gen_single 函数的最后，替换原来的 upload_to_s3 调用：

# 旧代码（删除）:
# upload_to_s3(output)

# 新代码（使用）:
# s3_url = upload_to_relay_server(output)
# if s3_url:
#     print(f"File available at: {s3_url}")
# else:
#     print("Upload to S3 failed, but file saved locally")


# ===== 完整集成代码 =====
"""
在 gen_single 函数的末尾，找到这一行:
    # Upload to S3
    upload_to_s3(output)

替换为:
    # Upload to relay server (will forward to S3)
    s3_url = upload_to_relay_server(output)
    if s3_url:
        print(f"✅ File uploaded to S3: {s3_url}")
    else:
        print("⚠️ S3 upload failed, file saved locally at: {output}")
    
    return gr.update(value=output, visible=True)
"""
