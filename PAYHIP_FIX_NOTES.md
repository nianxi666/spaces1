# Payhip 支付检测问题修复说明

## 问题描述

当用户使用 100% 优惠码在 Payhip 完成支付后，点击"我已完成支付"按钮时，系统显示"尚未查询到最新订单，请稍等片刻再试"。

### 根本原因

Payhip 在处理 100% 折扣订单时，可能不会触发 Webhook 通知，或者 Webhook 数据格式与正常付费订单不同。这导致系统无法接收到订单信息，因此在用户点击确认时找不到订单记录。

## 解决方案

### 1. 增强 Webhook 日志记录

在 `project/api.py` 的 `payhip_webhook` 函数中添加了详细的日志记录：

- 记录所有接收到的原始数据（包括 headers、query params、body）
- 记录解析后的数据结构
- 记录从多个可能的字段中提取 username 的过程
- 记录所有错误和成功情况

这样管理员可以通过日志了解：
- Webhook 是否被调用
- 数据格式是什么样的
- 为什么 username 提取失败（如果有）

### 2. 改进数据提取逻辑

增强了从 Webhook 数据中提取信息的能力：

- 尝试多个可能的字段名：`transaction_id`, `id`, `sale_id`
- 尝试多个可能的金额字段：`price`, `amount`, `total_price`
- 改进了 custom_variables 的解析，支持多种格式
- 添加了从扁平化字段名中提取 username 的逻辑（例如 `checkout_custom_variables[username]`）

### 3. 添加 Payhip API 主动查询功能

最重要的改进：当本地数据库中找不到最近的订单时，系统会主动调用 Payhip API 查询订单：

1. 检查本地数据库中是否有最近 15 分钟内的订单
2. 如果没有，且配置了 Payhip API Key，则调用 Payhip API
3. 在 API 返回的销售记录中查找当前用户的订单
4. 如果找到 1 小时内的订单，立即处理：
   - 更新用户会员时长（+30 天）
   - 记录订单到数据库
   - 返回成功响应

这样即使 Webhook 没有触发，用户点击"我已完成支付"时也能成功激活会员。

### 4. 订单去重机制

为防止同一订单被重复处理（例如 Webhook 重试、用户多次点击），系统在两个地方都添加了去重检查：

1. **Webhook 处理**：接收到订单时，先检查 transaction_id 是否已存在
2. **API 查询处理**：通过 API 查询到订单时，也检查是否已处理过

去重逻辑：
- 如果订单已存在，记录警告日志并返回成功（不会重复增加会员时长）
- 每个订单都标记来源（`webhook` 或 `payhip_api`）便于追踪

### 5. 管理面板增加 API Key 配置

在支付设置页面（`/admin/payment_settings`）添加了 "Payhip API Key" 配置项：

- 管理员可以在 Payhip 后台的 "Settings → API" 中获取 API Key
- 填写后系统将能够主动查询订单
- 这是可选配置，不影响正常的 Webhook 流程

## 修改的文件

1. **project/api.py**
   - 增强 `payhip_webhook` 函数的日志和数据提取
   - 改进 `check_payment_status` 函数，添加 Payhip API 查询

2. **project/admin.py**
   - 更新 `manage_payment_settings` 函数，支持保存 `payhip_api_key`

3. **project/templates/admin_payment_settings.html**
   - 添加 Payhip API Key 输入框

## 使用指南

### 管理员配置步骤

1. 访问 `/admin/payment_settings`
2. 填写现有配置：
   - Payhip 商品链接
   - Webhook 验证密钥
3. **新增：获取并填写 Payhip API Key**：
   - 登录 Payhip 后台
   - 进入 Settings → API
   - 复制 API Key
   - 粘贴到"Payhip API Key"字段
4. 保存设置

### 用户使用流程

1. 用户点击"立即支付"，跳转到 Payhip
2. 用户输入邮箱，使用优惠码完成支付
3. 支付成功后返回网站
4. 点击"我已完成支付"按钮
5. 系统自动检测：
   - 优先检查本地订单记录（来自 Webhook）
   - 如果没有，调用 Payhip API 查询
   - 找到订单后立即激活会员

### 测试建议

1. **正常支付测试**：使用真实支付（或测试支付）确认 Webhook 正常工作
2. **优惠码测试**：使用 100% 优惠码，确认 API 查询功能正常
3. **日志检查**：查看应用日志，确认 Webhook 和 API 调用的详细信息

## 技术细节

### Payhip API 端点

```
GET https://payhip.com/api/v1/sales
Headers:
  payhip-api-key: <YOUR_API_KEY>
  Accept: application/json
```

### 订单匹配逻辑

在 API 返回的销售记录中，通过以下方式匹配用户：

1. 检查 `checkout_custom_variables.username`
2. 检查其他包含 "username" 的字段
3. 验证订单时间（1 小时内）

### 日志级别

- `INFO`: 正常流程（接收 Webhook、处理订单、API 查询）
- `WARNING`: 可恢复的异常（API 调用失败等）
- `ERROR`: 需要关注的错误（数据格式错误、用户不存在等）

## 向后兼容性

- 所有修改都是向后兼容的
- 现有的 Webhook 流程不受影响
- API Key 是可选配置，不填写不影响现有功能
- 数据库结构没有变化，只是添加了可选字段

## 故障排查

如果问题仍然存在，请检查：

1. **日志文件**：查看详细的 Webhook 和 API 调用日志
2. **Payhip 后台**：确认 Webhook 是否配置正确
3. **API Key**：确认 API Key 是否有效
4. **订单时间**：系统只识别 1 小时内的订单（可根据需要调整）
5. **用户名传递**：确认支付链接包含正确的 `?checkout_custom_variables[username]=xxx`

## 未来改进建议

1. 支持更灵活的时间窗口配置（当前固定为 1 小时）
2. 添加管理员手动处理订单的界面
3. 支持订单状态的实时推送（WebSocket）
4. 添加订单统计和报表功能
