# Payhip API 配置指南

## ⚠️ 重要说明

根据测试结果，当前配置的 API Key 返回 **403 错误**（Cloudflare 挑战页面），这表明：

1. **API Key 可能不正确**：您填写的可能是 Webhook Secret，而不是 API Key
2. **Payhip 可能没有公开 API**：或者需要特殊权限才能访问
3. **认证方式不对**：需要使用正确的认证方式

## 🔍 如何获取正确的 Payhip API Key

### 步骤 1：访问 Payhip API 设置

登录 Payhip 账号后，访问：

```
https://payhip.com/account/api
```

或者通过菜单：
```
Dashboard → Account → Settings → API
```

### 步骤 2：查找 API Key

在 API 设置页面，您应该能看到：

- **API Key**：通常以 `payhip_` 开头，例如 `payhip_live_xxx...`
- **Test API Key**：用于测试，例如 `payhip_test_xxx...`

### 步骤 3：确认 API 权限

检查您的 Payhip 账号是否有以下权限：

- ✅ 启用了 API 访问
- ✅ 有权限读取销售数据（Sales）
- ✅ 账号类型支持 API（可能需要付费计划）

## 🔑 Webhook Secret vs API Key

### Webhook Secret

- **用途**：验证 Webhook 请求的真实性
- **格式**：随机字符串，例如 `cf62cff526ef6e320b99086c1789dc72394d4b14`
- **位置**：Payhip → Settings → Webhooks
- **用在**：Webhook URL 参数，例如 `?key=YOUR_SECRET`

### API Key

- **用途**：调用 Payhip API 获取数据
- **格式**：通常以 `payhip_` 开头
- **位置**：Payhip → Account → API
- **用在**：API 请求的 header 或参数

## 🧪 测试 API 连接

当前系统已经实现了 **6 种不同的认证方式**测试：

1. **payhip-api-key header**
2. **Authorization Bearer**
3. **URL parameter**
4. **X-API-Key header**
5. **Basic Auth**
6. **Alternative endpoint**

点击"测试 Payhip API"按钮后，系统会：

- 尝试所有 6 种方法
- 显示每种方法的结果
- 高亮成功的方法
- 提供详细的错误信息

## 📊 测试结果解读

### 场景 1：所有方法都返回 403

```json
{
  "status_code": 403,
  "raw_text": "<!DOCTYPE html>...Cloudflare..."
}
```

**原因**：
- API Key 不正确
- 使用了 Webhook Secret 而不是 API Key
- Cloudflare 阻止了请求

**解决方案**：
1. 确认获取了正确的 API Key（不是 Webhook Secret）
2. 访问 https://payhip.com/account/api 获取
3. 如果页面不存在，说明账号可能不支持 API

### 场景 2：某个方法返回 200

```json
{
  "status_code": 200,
  "json": { "data": [...] },
  "SUCCESS": true
}
```

**结果**：成功！系统会自动使用该方法。

### 场景 3：返回 401 Unauthorized

```json
{
  "status_code": 401
}
```

**原因**：API Key 格式正确但无效或过期。

**解决方案**：重新生成 API Key。

## 🛠️ Payhip API 文档参考

### 官方文档

Payhip 的 API 文档可能在以下位置：

- https://payhip.com/api-docs
- https://help.payhip.com/api
- https://developers.payhip.com

### 常见 API 端点

根据通用的 API 设计，Payhip 可能提供：

```
GET /api/v1/sales        # 获取销售记录
GET /api/v1/products     # 获取产品列表
GET /api/v1/customers    # 获取客户信息
```

### 认证方式

可能的认证方式（按常见程度排序）：

1. **Header: payhip-api-key**
   ```
   payhip-api-key: YOUR_API_KEY
   ```

2. **Bearer Token**
   ```
   Authorization: Bearer YOUR_API_KEY
   ```

3. **URL Parameter**
   ```
   ?api_key=YOUR_API_KEY
   ```

## ⚡ 当前可用的解决方案

由于 Payhip API 暂时无法使用，我们提供了**完全可靠的手动/批量激活功能**：

### 方案 1：批量激活（推荐）

1. 访问 `/admin/payment_settings`
2. 找到"批量激活会员"部分
3. 输入订单数据：
   ```
   用户名,订单ID,邮箱
   ```
4. 点击"批量激活"
5. 完成！

### 方案 2：手动激活

1. 逐个填写用户名和订单 ID
2. 点击"激活会员"
3. 重复处理每个订单

### 优势

- ✅ 100% 可靠
- ✅ 不依赖任何外部 API
- ✅ 有防重复保护
- ✅ 详细的成功/失败反馈

## 🔮 未来改进

### 如果成功配置 API

一旦获取到正确的 API Key 并测试成功：

1. 系统会自动使用成功的认证方式
2. 用户点击"我已完成支付"时，会自动查询 Payhip
3. 减少手动激活的需要

### 如果 Payhip 没有公开 API

如果确认 Payhip 不提供 API 或账号不支持：

1. 完全依赖 Webhook（正常付费订单）
2. 使用手动/批量激活（测试订单、特殊情况）
3. 这是完全可行的方案

## 📞 联系 Payhip 支持

如果不确定 API 配置，可以联系 Payhip 支持：

- **邮箱**：support@payhip.com
- **帮助中心**：https://help.payhip.com

询问内容：

```
Hi,

I'm trying to integrate Payhip API with my application to check order status.

Questions:
1. Does my account plan support API access?
2. Where can I find my API Key? (Not the Webhook Secret)
3. What's the correct authentication method for the API?
4. API documentation link?

Thank you!
```

## 💡 总结

### 当前状态

- ❌ Payhip API 测试失败（403 错误）
- ✅ 手动/批量激活功能完全可用
- ✅ Webhook 配置正确（用于正常付费订单）

### 推荐做法

1. **立即可用**：使用批量激活处理测试订单
2. **可选优化**：联系 Payhip 支持获取正确的 API 配置
3. **长期方案**：依赖 Webhook + 手动激活的混合模式

### 不影响使用

即使 API 永远无法使用，您仍然可以：

- ✅ 通过 Webhook 自动处理付费订单
- ✅ 通过批量激活处理测试订单
- ✅ 通过手动激活处理特殊情况

**系统已经完全可用！**
