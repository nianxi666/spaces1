# 会员系统支付 API 实现指南

## 概述
这是一个完整的会员系统实现，支持通过 Payhip 平台进行支付处理，用户可以购买按月订阅的会员资格。

## 系统架构

### 数据库结构

#### 新增全局设置 (`membership_settings`)
```json
{
  "enabled": false,
  "price_usd": 5.0,
  "duration_days": 30,
  "payhip_api_key": "",
  "payhip_product_id": ""
}
```

#### 用户字段扩展
每个用户现在包含以下会员相关字段：
- `is_member`: 布尔值，表示用户是否是活跃会员
- `member_expiry_date`: ISO 格式的过期日期字符串
- `payment_history`: 支付历史数组，记录所有交易

## API 端点

### 1. 获取会员状态
**端点**: `GET /api/membership/status`
**认证**: Bearer Token (API Key)
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

### 2. 续费/购买会员
**端点**: `POST /api/membership/renew`
**认证**: Bearer Token (API Key)
**响应**:
```json
{
  "payment_link": "https://payhip.com/checkout/...",
  "message": "Payment link created successfully"
}
```

### 3. Payhip Webhook 处理
**端点**: `POST /api/membership/webhook/payhip`
**头部**: 
- `X-Payhip-Signature`: Payhip 签名
**请求体**:
```json
{
  "status": "completed",
  "metadata": {
    "username": "user123"
  }
}
```

## 管理功能

### Admin 面板
访问 `/admin/membership_settings` 可以：
1. 启用/禁用会员系统
2. 配置价格和有效期
3. 输入 Payhip API 密钥和产品ID
4. 手动为用户设置/取消会员资格

### 快速操作
在 Admin 面板的快速操作部分，可以：
- 设为会员: `POST /admin/membership/set_member/<username>/<days>`
- 取消会员: `POST /admin/membership/revoke_member/<username>`

## Payhip 配置步骤

### 1. 获取 API 密钥
- 访问 [Payhip](https://payhip.com)
- 登录您的账户
- 进入设置 → API/Webhook 设置
- 获取 API Key

### 2. 创建产品
- 在 Payhip 创建新产品
- 设置名称: "Monthly Membership"
- 设置价格: $5.00
- 获取产品ID

### 3. 配置 Webhook
- 在 Admin 面板中设置好 API Key 和产品ID
- Webhook URL: `https://your-domain.com/api/membership/webhook/payhip`
- Payhip 将在支付完成时调用此端点

## 前端集成

### 个人资料页面
用户可以在 `/profile` 页面看到：
- 当前会员状态
- 有效期倒计时
- 续费/购买按钮

### 按钮函数
```javascript
purchaseMembership()  // 打开支付链接
renewMembership()     // 续费会员
```

## 会员权限检查

### 在代码中检查会员资格
```python
from membership import is_user_member, get_user_membership_status

# 检查用户是否是活跃会员
if is_user_member(username):
    # 授予会员权限
    pass

# 获取详细状态
status = get_user_membership_status(username)
if status['is_member'] and status['days_remaining'] > 0:
    # 执行会员操作
    pass
```

## 支付流程

1. 用户点击"购买会员"或"续费会员"按钮
2. 前端调用 `/api/membership/renew` 端点
3. 后端创建 Payhip 支付链接并返回
4. 用户被重定向到 Payhip 支付页面
5. 用户完成支付
6. Payhip 调用 webhook 端点通知系统
7. 系统验证签名并更新用户的会员状态
8. 用户自动获得会员权限

## 会员状态管理

### 自动过期检查
会员状态通过 `member_expiry_date` 字段自动管理。系统会在以下情况检查过期：
- 用户查看个人资料
- API 调用检查会员状态
- Admin 查看用户列表

### 手动管理
Admin 可以：
- 手动设置用户为会员（指定天数）
- 手动取消用户的会员资格
- 查看用户的支付历史

## 安全性考虑

### Webhook 验证
- 所有 Webhook 请求都通过 HMAC-SHA256 签名验证
- 使用 `payhip_api_key` 作为密钥
- 确保只处理验证通过的请求

### API 认证
- 所有会员 API 端点都需要有效的 Bearer Token
- Token 使用用户的 API Key

### 敏感信息
- Payhip API Key 存储在数据库中
- 在 Admin 页面中显示为密码输入框
- 在日志中应避免输出

## 测试

### 测试会员功能
1. Admin 面板手动设置用户为会员
2. 用户查看个人资料，应显示活跃会员
3. 观察会员状态在过期日期后自动更新

### 测试支付流程（使用 Payhip 测试模式）
1. 在 Payhip 中启用测试模式
2. 用户点击购买会员
3. 完成 Payhip 测试支付
4. 验证用户自动获得会员资格

## 部署注意事项

1. **HTTPS**: 生产环境必须使用 HTTPS
2. **API Key**: 安全存储 Payhip API Key，不要提交到版本控制
3. **Webhook URL**: 必须是公网可访问的 HTTPS URL
4. **备份**: 定期备份包含支付历史的数据库
5. **监控**: 监控 webhook 调用，记录所有支付事件

## 常见问题

### Q: 如何更改会员价格？
A: 在 `/admin/membership_settings` 中修改 `price_usd` 字段

### Q: 如何更改有效期？
A: 在 `/admin/membership_settings` 中修改 `duration_days` 字段

### Q: 支付失败怎么办？
A: 用户需要重新尝试，或联系 Payhip 支持。Admin 可以手动添加会员资格。

### Q: 如何禁用会员系统？
A: 在 `/admin/membership_settings` 中关闭 `enabled` 开关。用户界面中的会员卡片将不显示。

### Q: 用户支付后没有自动获得会员资格？
A: 检查：
1. Webhook URL 是否正确配置
2. Payhip API Key 是否正确
3. Webhook 日志中是否有错误
4. 用户元数据中是否包含用户名

## 扩展建议

1. **邮件通知**: 会员过期前发送提醒邮件
2. **自动续费**: 支持自动续费选项
3. **团队计划**: 支持多个用户的团队会员
4. **试用期**: 提供免费试用期
5. **多种支付方式**: 集成 Stripe、PayPal 等其他支付平台
