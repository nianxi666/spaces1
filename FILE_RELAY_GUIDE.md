# 🎯 文件中转到S3方案 - 完整指南

## 📋 方案说明

**问题**: 远程服务器直接上传到Tebi Cloud S3时出现SSL错误

**解决方案**: 
1. 远程服务器 → 上传文件到您的网站
2. 您的网站 → 立即转存到S3
3. 您的网站 → 删除临时文件（不占用VPS硬盘空间）

## ✅ 已完成的工作

### 1. 在您的网站添加了中转API (`project/api.py`)

新增endpoint: `/api/relay-to-s3`

**功能**:
- ✅ 接收远程服务器上传的文件
- ✅ 立即转存到Tebi Cloud S3
- ✅ 删除本地临时文件
- ✅ 返回S3公共URL
- ✅ 不占用VPS硬盘空间

**使用方法**:
```bash
curl -X POST https://your-website.com/api/relay-to-s3 \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@/path/to/file.wav"
```

**返回**:
```json
{
  "success": true,
  "message": "File relayed to S3 successfully",
  "s3_key": "spk_1765459446.wav",
  "public_url": "https://s3.tebi.io/driver/spk_1765459446.wav",
  "filename": "spk_1765459446.wav"
}
```

## 🔧 远程服务器需要修改的代码

### 步骤1: 替换上传函数

在远程服务器的 `webui.py` 或 `app.py` 中，找到 `upload_to_s3` 函数，替换为：

```python
import requests
import os

# 配置 - 替换为您的实际值
RELAY_API_URL = "https://your-website.com/api/relay-to-s3"
API_KEY = "在您的网站后台获取API Key"

def upload_to_relay_server(file_path, object_name=None):
    """
    上传文件到中转服务器，服务器会自动转存到S3
    """
    if object_name is None:
        object_name = os.path.basename(file_path)
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (object_name, f, 'audio/wav')}
            headers = {'Authorization': f'Bearer {API_KEY}'}
            
            print(f"Uploading {object_name} to relay server...")
            response = requests.post(
                RELAY_API_URL,
                files=files,
                headers=headers,
                timeout=300
            )
        
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
```

### 步骤2: 修改调用代码

在 `gen_single` 函数的末尾，找到：

```python
# 旧代码（删除）
upload_to_s3(output)
```

替换为：

```python
# 新代码
s3_url = upload_to_relay_server(output)
if s3_url:
    print(f"✅ File uploaded to S3: {s3_url}")
else:
    print("⚠️ S3 upload failed, file saved locally at: {output}")
```

### 步骤3: 删除旧的S3上传代码

可以删除或注释掉原来的 `upload_to_s3` 函数和boto3相关配置：

```python
# 不再需要这些
# S3_ENDPOINT_URL = ...
# S3_ACCESS_KEY_ID = ...
# S3_SECRET_ACCESS_KEY = ...
# S3_BUCKET_NAME = ...

# 不再需要boto3
# import boto3
```

## 📊 流程对比

### ❌ 旧流程（有问题）
```
远程服务器 ---(SSL错误)--X--> Tebi Cloud S3
```

### ✅ 新流程（工作正常）
```
远程服务器 
    ↓ (HTTP POST文件)
您的网站API (/api/relay-to-s3)
    ↓ (保存临时文件)
    ↓ (上传到S3)
    ↓ (删除临时文件)
    ↓ (返回S3 URL)
Tebi Cloud S3
```

## 🎯 优势

1. ✅ **解决SSL问题** - 绕过远程服务器的SSL证书验证问题
2. ✅ **不占用VPS硬盘** - 文件立即转存并删除
3. ✅ **使用已配置的S3** - 利用您本地已修复的S3连接
4. ✅ **统一管理** - 所有文件通过您的网站统一管理
5. ✅ **API认证** - 使用API Key保护endpoint

## 🔐 安全性

- ✅ 需要有效的API Key才能上传
- ✅ 文件名安全处理
- ✅ 临时文件自动清理
- ✅ 错误处理完善

## 📝 配置说明

### 获取API Key

1. 登录您的网站
2. 进入个人资料页面
3. 复制您的API Key
4. 在远程服务器代码中替换 `API_KEY = "YOUR_API_KEY_HERE"`

### 设置网站地址

在远程服务器代码中替换：
```python
RELAY_API_URL = "https://your-website.com/api/relay-to-s3"
```

改为实际的网站地址，例如：
```python
RELAY_API_URL = "https://pumpkinai.it.com/api/relay-to-s3"
```

## 🧪 测试

### 1. 本地测试网站API

```bash
curl -X POST https://your-website.com/api/relay-to-s3 \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@test.wav"
```

### 2. 远程服务器测试

运行一次推理，查看日志：
```
Uploading spk_xxx.wav to relay server...
✅ Uploaded to S3: https://s3.tebi.io/driver/spk_xxx.wav
```

## 🎉 完成！

修改完成后：
1. ✅ 远程推理正常工作
2. ✅ 音频生成成功
3. ✅ 文件自动上传到S3
4. ✅ VPS硬盘不被占用
5. ✅ SSL问题完全解决

---

## 📞 相关文件

- 网站端API: `project/api.py` (已完成)
- 远程服务器代码: `REMOTE_SERVER_UPLOAD_CODE.py` (模板)
- S3配置: `s3_config.json` (已完成)
- S3工具: `project/s3_utils.py` (已修复SSL)

**下一步**: 在远程服务器应用上述代码修改！
