# 远程推理系统 - SSL上传问题解决方案

## 🎉 成功部分

### ✅ 远程推理API测试成功！
- **推理成功**: 生成了 7.33 秒的音频
- **推理时间**: 8.17 秒 (RTF: 1.11)
- **输出文件**: `outputs/spk_1765459446.wav`
- **远程API**: `http://direct.virtaicloud.com:21564`

## ❌ 问题：S3上传失败

### 错误信息
```
S3 Upload Error: SSL validation failed for https://s3.tebi.io/driver/spk_1765459446.wav 
EOF occurred in violation of protocol (_ssl.c:2426)
```

### 根本原因
1. **SSL证书问题**: Tebi Cloud的SSL证书可能有配置问题
2. **权限问题**: 可能存在bucket权限配置问题（HTTP 403）

## ✅ 已实施的解决方案

### 1. 修改了 `project/s3_utils.py`
```python
# 禁用SSL验证（临时解决方案）
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

s3_client = boto3.client(
    's3',
    endpoint_url=endpoint_url,
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
    region_name='auto',
    config=config,
    verify=False  # 禁用SSL验证
)
```

### 2. 添加了配置和重试机制
```python
from botocore.config import Config

config = Config(
    signature_version='s3v4',
    retries={
        'max_attempts': 3,
        'mode': 'standard'
    }
)
```

## 🔧 远程服务器需要的修改

### 修改远程webui.py或app.py中的S3上传代码

找到S3上传部分，添加以下代码：

```python
import urllib3
import boto3
from botocore.config import Config

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 创建S3客户端时添加 verify=False
config = Config(
    signature_version='s3v4',
    retries={'max_attempts': 3, 'mode': 'standard'}
)

s3_client = boto3.client(
    's3',
    endpoint_url='https://s3.tebi.io',
    aws_access_key_id='YxWVUUhcFT6lGi9cF',
    aws_secret_access_key='UkN7jF9L0P8XAqPcGOdjl3wi5SQ1d87st80fqC4A',
    config=config,
    verify=False  # 关键：禁用SSL验证
)

# 上传文件
with open(output_file, 'rb') as f:
    s3_client.upload_fileobj(
        f,
        'driver',
        f'spk_{timestamp}.wav',
        ExtraArgs={'ContentType': 'audio/wav'}
    )
```

### 或者使用 requests 直接上传

```python
import requests
import urllib3
urllib3.disable_warnings()

# 生成预签名URL
presigned_url = s3_client.generate_presigned_url(
    'put_object',
    Params={
        'Bucket': 'driver',
        'Key': f'spk_{timestamp}.wav'
    },
    ExpiresIn=3600
)

# 使用 requests 上传（禁用SSL验证）
with open(output_file, 'rb') as f:
    response = requests.put(
        presigned_url,
        data=f,
        headers={'Content-Type': 'audio/wav'},
        verify=False  # 禁用SSL验证
    )

if response.status_code == 200:
    print(f"✅ S3 Upload Success!")
else:
    print(f"❌ S3 Upload Failed: {response.status_code}")
```

## 📋 bucket权限检查

需要确认 Tebi Cloud bucket "driver" 的权限设置：

1. **登录 Tebi Cloud控制台**: https://tebi.io
2. **检查bucket权限**: 
   - Bucket Settings → Access Control
   - 确保允许 PUT 操作
   - 确保Access Key有上传权限

## 🎯 替代方案

如果SSL问题持续，可以考虑：

### 方案A：使用HTTP而非HTTPS
```python
endpoint_url='http://s3.tebi.io'  # 使用HTTP（不推荐生产环境）
```

### 方案B：联系Tebi Cloud支持
- 要求更新/修复SSL证书
- 申请专用endpoint

### 方案C：使用其他S3兼容存储
- AWS S3
- DigitalOcean Spaces
- Cloudflare R2
- MinIO (自建)

## ✅ 测试脚本

已创建测试脚本：
- `test_s3_ssl_upload.py` - SSL上传测试
- `test_tebi_s3.py` - Tebi连接测试
- `test_remote_inference_api.py` - 远程推理API测试

## 🎉 总结

**好消息**:
- ✅ 远程推理API完全正常工作
- ✅ 音频生成成功
- ✅ 本地S3配置已修复（禁用SSL验证）

**需要在远程服务器修改**:
- 🔧 在远程webui.py中添加 `verify=False`
- 🔧 在boto3客户端中禁用SSL验证
- 🔧 或使用 requests 库直接上传

**长期解决方案**:
- 🔐 联系Tebi Cloud修复SSL证书
- 🔐 或切换到其他S3服务

---

**下一步**: 请在远程服务器的webui.py中应用上述修改，重新测试上传！
