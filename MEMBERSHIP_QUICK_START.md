# 会员系统快速开始指南

## 📋 概览

这个会员系统允许用户购买$5/月的订阅会员资格，所有支付通过 Payhip 平台处理。

## 🚀 快速开始

### 1️⃣ Admin 配置（首次使用）

1. 以 Admin 用户身份登录
2. 进入管理面板 → 找到紫色的"会员系统设置"按钮
3. 启用会员系统：勾选"启用会员系统"
4. 在 Payhip 获取：
   - 访问 https://payhip.com
   - 获取 API Key（在设置中）
   - 创建一个产品用于会员（设置价格 $5.00）
   - 复制产品 ID
5. 填入表单：
   - Payhip API Key
   - Payhip 产品 ID
   - 确认价格 ($5.00)
   - 确认有效期 (30 天)
6. 点击"保存设置"

### 2️⃣ 配置 Webhook（Payhip端）

1. 在 Payhip 中进入产品设置
2. 找到 Webhook 配置部分
3. 添加 Webhook URL：
   ```
   https://your-domain.com/api/membership/webhook/payhip
   ```
4. 选择事件类型：Payment Completed
5. 保存配置

### 3️⃣ 用户购买流程

1. 用户访问 `/profile`
2. 看到紫色的"会员系统"卡片
3. 点击"立即购买"
4. 被重定向到 Payhip 支付页面
5. 完成支付
6. Payhip 通知系统，用户自动获得会员资格

## 🛠️ Admin 快速操作

### 手动设置会员资格

在 Admin 会员设置页面的"快速操作"部分：

**设为会员**:
```
用户名: john_doe
天数: 30
点击"设为会员"按钮
```

**取消会员**:
```
用户名: john_doe
点击"取消会员"按钮
```

### 查看会员用户

1. 进入 Admin → 用户管理
2. 表格中有"会员状态"列
3. 绿色徽章 ✓ 会员 = 活跃会员
4. 灰色徽章 非会员 = 未购买

## 📱 用户界面

### 个人资料页面 (`/profile`)

用户会看到会员卡片，显示：
- 当前会员状态
- 有效期倒计时（活跃会员时）
- 续费/购买按钮

**活跃会员**:
```
✓ 活跃会员
会员有效期还有 10 天
[续费会员] 按钮
```

**非会员**:
```
成为会员
仅需 $5/月，享受无限制访问和更多权益。
[立即购买] 按钮
```

## 🔌 API 使用

### 检查会员状态

```bash
curl -X GET http://localhost:5000/api/membership/status \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**响应**:
```json
{
  "membership_enabled": true,
  "status": {
    "is_member": true,
    "expiry_date": "2024-01-15T12:00:00",
    "days_remaining": 10,
    "expired": false
  }
}
```

### 生成支付链接

```bash
curl -X POST http://localhost:5000/api/membership/renew \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**响应**:
```json
{
  "payment_link": "https://payhip.com/checkout/...",
  "message": "Payment link created successfully"
}
```

## ⚙️ 配置选项

在 Admin 面板修改：
- **价格**: 每月价格（默认 $5）
- **有效期**: 单次购买的天数（默认 30）
- **Payhip API Key**: 来自 Payhip 的 API 密钥
- **Payhip 产品 ID**: 创建的会员产品 ID

## 🔍 故障排查

### 问题：用户购买后没有自动获得会员资格

**解决步骤**:
1. 检查 Payhip API Key 是否正确输入
2. 检查产品 ID 是否正确
3. 验证 Webhook URL 在 Payhip 中是否配置
4. 检查 Webhook URL 是否可公网访问（HTTPS）
5. 查看服务器日志是否有 webhook 错误

### 问题：无法创建支付链接

**可能原因**:
1. 会员系统未启用 → 在 Admin 面板启用
2. Payhip API Key 为空 → 输入有效的 API Key
3. 产品 ID 为空 → 输入有效的产品 ID
4. Payhip API 调用失败 → 检查网络和 API Key 有效性

### 问题：无法在 Admin 面板手动设置会员

**检查**:
1. 用户名是否存在
2. 天数是否在 1-3650 之间
3. 浏览器控制台是否有 JavaScript 错误

## 📊 监控

### 查看会员统计

访问 Admin 用户管理页面，可以看到：
- 每个用户的会员状态
- 会员过期日期
- 支付历史（在用户详情中）

### 手动检查

在 Admin 快速操作部分输入用户名后，可以：
- 查看是否成功设置会员
- 查看是否成功取消会员

## 🚨 重要注意

1. **HTTPS**: 生产环境必须使用 HTTPS
2. **API Key 安全**: 不要在代码中硬编码或提交到版本控制
3. **备份**: 定期备份数据库（包含支付历史）
4. **监控**: 定期检查 webhook 日志

## 📞 获取帮助

- 完整文档: `MEMBERSHIP_API_IMPLEMENTATION.md`
- 测试脚本: `test_membership_system.py`
- Payhip 文档: https://payhip.com/help
