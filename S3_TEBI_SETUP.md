# S3/Tebi 存储桶配置指南

## 概述

此文档说明如何配置 S3 兼容存储服务（如 Tebi）以支持头像上传、文件存储和其他 S3 操作。

## 已配置信息

### Tebi 存储桶配置

**s3_config.json** 已配置以下值：

```json
{
    "S3_ENDPOINT_URL": "https://s3.tebi.io",
    "S3_ACCESS_KEY_ID": "YxWVUUhcFT6lGi9c",
    "S3_SECRET_ACCESS_KEY": "UkN7jF9L0P8XAqPcGOdjl3wi5SQ1d87st80fqC4A",
    "S3_BUCKET_NAME": "driver"
}
```

## 安全说明

⚠️ **重要**: `s3_config.json` 包含敏感凭证，已添加到 `.gitignore` 中以防止意外提交到版本控制。

### 支持的配置方式

系统现在支持通过以下方式配置 S3：

1. **环境变量**（优先级最高）：
   ```bash
   export S3_ENDPOINT_URL="https://s3.tebi.io"
   export S3_ACCESS_KEY_ID="your_access_key"
   export S3_SECRET_ACCESS_KEY="your_secret_key"
   export S3_BUCKET_NAME="your_bucket_name"
   ```

2. **s3_config.json 文件**（备用）：
   - 位置：项目根目录的 `s3_config.json`
   - 格式：JSON 文件，包含上述四个键

## 功能

配置完成后，以下功能将正常工作：

### ✅ 头像功能
- 用户可以从 S3 存储桶中选择或上传头像
- 头像在导航栏和个人资料页面中正确显示
- GitHub OAuth 用户的头像可以从 GitHub 或 S3 加载

### ✅ 文件管理
- 用户可以浏览 S3 存储桶中的个人文件
- 支持文件重命名
- 生成预签名 URL 用于安全的文件上传/下载

### ✅ 推理输出
- 模型推理结果自动上传到 S3
- 用户可以在"结果"页面查看和管理 S3 文件

## 系统流程

### 头像加载流程

1. 用户登录后，头像 URL 存储在 `session['user_avatar']` 中
2. 在模板中，`{{ session.user_avatar }}` 直接显示 URL
3. URL 格式：
   - GitHub 用户：`https://avatars.githubusercontent.com/u/...`
   - S3 用户头像：`https://s3.tebi.io/driver/username/avatar.png`

### 文件上传流程

1. 用户请求上传文件
2. `generate_presigned_url()` 生成 S3 上传 URL
3. 浏览器使用 PUT 请求上传文件到 S3
4. 上传完成后，文件 URL 保存到数据库

## 验证配置

### 快速检查

查看 Flask 应用日志，确认以下信息：

```
✓ S3_ENDPOINT_URL: https://s3.tebi.io
✓ S3_BUCKET_NAME: driver
```

### 使用测试脚本

```bash
python3 test_s3_connection.py
```

此脚本将：
- ✓ 验证 `s3_config.json` 存在且格式正确
- ✓ 验证所有必需的键都已填充（非占位符）
- ✓ 尝试连接到 S3 并列出可用存储桶
- ✓ 验证目标存储桶可访问

## 故障排除

### 头像无法加载

**症状**：头像位置显示为空或默认图像

**解决方案**：
1. 验证 `s3_config.json` 中的值是否正确
2. 检查网络连接到 Tebi 端点
3. 验证 IAM 凭证是否有访问权限
4. 查看浏览器开发者工具中的网络选项卡，查看 HTTP 错误

### S3 连接失败

**症状**：API 返回 500 错误或"S3 未配置"

**解决方案**：
1. 确保 `s3_config.json` 存在于项目根目录
2. 验证 JSON 格式有效（使用 `python3 -m json.tool s3_config.json`）
3. 检查凭证是否正确
4. 确保 boto3 已安装：`pip install boto3`

### 文件上传失败

**症状**：预签名 URL 生成失败或上传被拒绝

**解决方案**：
1. 验证存储桶名称是否正确
2. 检查 IAM 凭证是否有 `s3:GetObject`、`s3:PutObject` 权限
3. 验证存储桶策略允许来自应用程序的访问

## 相关文件

- `s3_config.json` - S3 配置文件（git 忽略）
- `project/s3_utils.py` - S3 操作的核心模块
- `project/config.py` - Flask 应用配置
- `test_s3_connection.py` - 连接测试脚本
- `.gitignore` - 包含 `s3_config.json` 以防止凭证泄露

## 更多信息

- [Tebi 文档](https://docs.tebi.io/)
- [boto3 S3 文档](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html)
