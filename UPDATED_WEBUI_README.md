# 📝 更新后的 webui.py 配置说明

## 文件位置
`updated_webui.py` - 在 spaces1 目录中

## 🔧 使用步骤

### 1. 修改配置（重要！必须修改）

在文件开头找到这两行，替换为实际值：

```python
RELAY_API_URL = "https://your-website.com/api/relay-to-s3"  # 替换为您的网站地址
API_KEY = "YOUR_API_KEY_HERE"  # 替换为您的API Key
```

**示例**：
```python
RELAY_API_URL = "https://pumpkinai.it.com/api/relay-to-s3"
API_KEY = "abc123def456ghi789"  # 从网站个人资料获取
```

### 2. 上传到远程服务器

将 `updated_webui.py` 上传到远程服务器，替换原来的 `webui.py`

### 3. 安装依赖（如果还没有）

```bash
pip install requests
```

### 4. 重启服务

```bash
# 如果使用screen
screen -r
# 按 Ctrl+C 停止旧进程
python webui.py --port 7860 --host 0.0.0.0

# 或者直接重启
```

## 📋 主要修改内容

### 1. 添加了新的上传函数

```python
def upload_to_relay_server(file_path, object_name=None):
    """上传到中转服务器，自动转存S3"""
    # 使用 requests 上传文件
    # 返回 S3 公共URL
```

### 2. 修改了 gen_single 函数

**旧代码（已删除）**：
```python
# Upload to S3
upload_to_s3(output)
```

**新代码（第219-224行）**：
```python
# ===== 修改：使用中转服务器上传 =====
s3_url = upload_to_relay_server(output)
if s3_url:
    print(f"✅ File uploaded to S3: {s3_url}")
else:
    print(f"⚠️ S3 upload failed, file saved locally at: {output}")
# ===== 修改结束 =====
```

### 3. 删除了旧的S3配置

不再需要：
- ~~boto3~~
- ~~S3_ENDPOINT_URL~~
- ~~S3_ACCESS_KEY_ID~~  
- ~~S3_SECRET_ACCESS_KEY~~
- ~~S3_BUCKET_NAME~~

## ✅ 优势

1. **解决SSL问题** - 不再直接连接Tebi Cloud
2. **不占VPS硬盘** - 文件通过中转立即上传
3. **简化配置** - 只需配置网站API地址和Key
4. **统一管理** - 所有文件通过您的网站管理

## 🧪 测试

运行一次推理，查看日志输出：

```
>> wav file saved to: outputs/spk_1765459446.wav
📤 Uploading spk_1765459446.wav to relay server...
✅ Uploaded to S3: https://s3.tebi.io/driver/spk_1765459446.wav
```

## ❌ 如果失败

### 检查清单：

1. ✅ RELAY_API_URL 是否正确？
2. ✅ API_KEY 是否有效？
3. ✅ 网站API endpoint是否可访问？
4. ✅ requests库是否已安装？

### 常见错误：

- **401 Unauthorized**: API Key错误或格式不对
- **403 Forbidden**: API Key无效
- **500 Internal Server Error**: 网站端S3配置问题
- **Connection refused**: 网站地址错误或网络不通

## 📞 获取API Key

1. 访问您的网站
2. 登录管理员账户
3. 进入个人资料页面
4. 复制显示的API Key
5. 粘贴到 `API_KEY = "这里"`

## 🚀 完成！

修改配置后，直接使用即可。每次推理都会自动：
1. 生成音频文件
2. 上传到您的网站
3. 网站转存到S3
4. 返回S3公共URL
5. 本地和网站都不保留文件

**完全不占用硬盘空间！** 🎉
