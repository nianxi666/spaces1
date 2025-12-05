# 订单管理系统 - 完整指南

## 📋 概述

充值会员系统现已支持完整的订单管理功能，包括：
- ✅ 订单创建和跟踪
- ✅ 订单状态管理（未支付、已支付、已取消、已过期）
- ✅ 自动过期关闭（30分钟无支付）
- ✅ 用户订单数量限制（最多2个未支付）
- ✅ Admin 订单管理面板
- ✅ API 端点支持

---

## 🔄 订单生命周期

```
创建订单 (unpaid)
    ↓
    ├─→ 用户支付 → 标记支付 (paid) → 激活会员 ✓
    ├─→ 用户取消 → 取消订单 (cancelled)
    ├─→ 30分钟未支付 → 自动过期 (expired)
    └─→ Admin 取消 → 取消订单 (cancelled)
```

---

## 📊 订单字段说明

```python
{
    'order_id': 'uuid',           # 唯一订单ID
    'username': 'string',          # 用户名
    'status': 'unpaid|paid|cancelled|expired',  # 订单状态
    'created_at': 'ISO 8601',      # 创建时间
    'expires_at': 'ISO 8601',      # 过期时间（创建后30分钟）
    'paid_at': 'ISO 8601|null',    # 支付时间
    'payment_url': 'url|null',     # Payhip 支付链接
    'price': 'float|null',         # 金额
    'currency': 'USD'              # 货币
}
```

---

## 🎯 用户订单数量限制

**规则**: 普通用户最多可以有 **2 个未支付的订单**

### 场景

1. **可以创建订单**:
   - 用户有 0 个未支付订单 ✅
   - 用户有 1 个未支付订单 ✅

2. **不能创建订单**:
   - 用户已有 2 个未支付订单 ❌
   - 错误提示: "已有 2 个未支付订单，最多只能有 2 个"

### 解决方案

用户可以通过以下方式减少未支付订单数量：

1. **支付已有订单** - 等待支付成功
2. **手动取消订单** - 调用 API 取消
3. **等待自动过期** - 30分钟后订单自动关闭

---

## ⏰ 自动过期机制

### 如何工作

1. 订单创建时，`expires_at` 设置为创建时间 + 30分钟
2. 用户每次查询订单时，系统自动检查是否有过期未支付订单
3. Admin 进入订单管理页面时也会自动检查
4. 过期订单自动标记为 `expired` 状态

### 代码实现

```python
def auto_close_expired_orders():
    """自动关闭超过30分钟未支付的订单"""
    db = load_db()
    now = datetime.utcnow()
    closed_count = 0
    
    for order_id, order in db.get('orders', {}).items():
        if order.get('status') != 'unpaid':
            continue
        
        try:
            expires_at = datetime.fromisoformat(order.get('expires_at', ''))
            if now >= expires_at:
                order['status'] = 'expired'  # 自动过期
                closed_count += 1
        except (ValueError, TypeError):
            pass
    
    if closed_count > 0:
        save_db(db)
    
    return closed_count
```

---

## 🛠️ API 端点

### 1. 获取用户订单列表

**端点**: `GET /api/orders/list`

**请求头**:
```
Authorization: Bearer {api_key}
```

**响应**:
```json
{
  "success": true,
  "orders": [
    {
      "order_id": "123e4567-e89b-12d3-a456-426614174000",
      "username": "testuser",
      "status": "unpaid",
      "created_at": "2024-01-15T10:00:00",
      "expires_at": "2024-01-15T10:30:00",
      "paid_at": null,
      "payment_url": "https://payhip.com/...",
      "price": 5.0,
      "currency": "USD"
    }
  ]
}
```

### 2. 创建新订单

**端点**: `POST /api/orders/create`

**请求头**:
```
Authorization: Bearer {api_key}
```

**响应**:
```json
{
  "success": true,
  "order": {
    "order_id": "123e4567-e89b-12d3-a456-426614174000",
    "username": "testuser",
    "status": "unpaid",
    "created_at": "2024-01-15T10:00:00",
    "expires_at": "2024-01-15T10:30:00",
    "payment_url": "https://payhip.com/...",
    ...
  }
}
```

**错误示例**:
```json
{
  "error": "已有 2 个未支付订单，最多只能有 2 个"
}
```

### 3. 取消订单

**端点**: `POST /api/orders/{order_id}/cancel`

**请求头**:
```
Authorization: Bearer {api_key}
```

**响应**:
```json
{
  "success": true,
  "message": "Order cancelled successfully"
}
```

**错误情况**:
- 订单不存在: 404
- 未授权（不是订单所有者）: 403
- 订单已支付或已取消: 400

---

## 👨‍💼 Admin 管理界面

### 访问方式

1. 登录 Admin 账户
2. 进入管理面板
3. 点击粉红色"订单管理"按钮
4. 或直接访问: `http://localhost:5000/admin/orders`

### 功能

#### 📊 订单统计

显示实时统计数据：
- **总订单数** - 所有订单数量
- **未支付** - 待支付订单数
- **已支付** - 已完成支付的订单数
- **已取消** - 已取消的订单数
- **已过期** - 已过期的订单数

#### 🔍 订单筛选

按状态筛选订单：
- 全部 - 显示所有订单
- 未支付 - 只显示未支付订单
- 已支付 - 只显示已支付订单
- 已取消 - 只显示已取消订单
- 已过期 - 只显示已过期订单

#### ⚙️ 订单操作

对于**未支付的订单**，Admin 可以：

1. **标记支付** - 手动标记订单为已支付
   - 自动激活用户会员资格
   - 更新 `paid_at` 时间戳
   - 订单状态变为 `paid`

2. **取消** - 取消未支付的订单
   - 订单状态变为 `cancelled`
   - 用户可以创建新订单

### 订单表列

| 列 | 说明 |
|------|------|
| 订单ID | 唯一标识符（前8位显示，完整ID在下方） |
| 用户 | 创建订单的用户名 |
| 状态 | 订单当前状态 |
| 创建时间 | 订单创建的时间 |
| 过期时间 | 订单失效的时间（通常为创建时间+30分钟） |
| 支付时间 | 订单支付完成的时间 |
| 操作 | 可用的操作按钮 |

---

## 💾 Admin 路由

### 获取订单列表

**路由**: `GET /admin/orders`

**参数**:
- `status` (可选) - 按状态筛选: `unpaid`, `paid`, `cancelled`, `expired`

**示例**:
```
/admin/orders
/admin/orders?status=unpaid
/admin/orders?status=paid
```

### 标记订单已支付

**路由**: `POST /admin/orders/{order_id}/mark-paid`

**返回**:
```json
{
  "success": true,
  "message": "订单 xxx 已标记为已支付"
}
```

### 取消订单

**路由**: `POST /admin/orders/{order_id}/cancel`

**返回**:
```json
{
  "success": true,
  "message": "订单 xxx 已取消"
}
```

---

## 📱 用户体验流程

### 用户购买会员

1. **查看待支付订单**
   ```bash
   curl -X GET http://localhost:5000/api/orders/list \
     -H "Authorization: Bearer {api_key}"
   ```

2. **创建新订单**
   ```bash
   curl -X POST http://localhost:5000/api/orders/create \
     -H "Authorization: Bearer {api_key}"
   ```

3. **获取支付链接**
   - 响应中包含 `payment_url`
   - 用户访问链接进行支付

4. **支付完成**
   - Payhip Webhook 自动激活会员
   - 或 Admin 手动标记为已支付

5. **取消订单**（可选）
   ```bash
   curl -X POST http://localhost:5000/api/orders/{order_id}/cancel \
     -H "Authorization: Bearer {api_key}"
   ```

---

## 🔧 核心函数说明

### 在 `project/membership.py` 中

#### 创建订单
```python
def create_order(username):
    """创建新订单
    
    返回: (order, error)
    - 成功: (order_dict, None)
    - 失败: (None, error_message)
    
    检查: 用户最多2个未支付订单
    """
```

#### 获取用户订单
```python
def get_user_orders(username, status=None):
    """获取用户的订单
    
    参数:
    - username: 用户名
    - status: 可选，筛选状态 (unpaid/paid/cancelled/expired)
    
    返回: 订单列表，按创建时间倒序
    """
```

#### 标记订单已支付
```python
def mark_order_paid(order_id, username=None):
    """标记订单为已支付
    
    - 更新订单状态为 'paid'
    - 自动激活用户会员资格
    - 记录支付时间
    
    返回: True/False
    """
```

#### 取消订单
```python
def cancel_order(order_id):
    """取消未支付的订单
    
    - 只能取消状态为 'unpaid' 的订单
    - 变更状态为 'cancelled'
    
    返回: True/False
    """
```

#### 自动过期
```python
def auto_close_expired_orders():
    """自动关闭30分钟未支付的订单
    
    - 检查所有 'unpaid' 订单
    - 如果 now >= expires_at，标记为 'expired'
    
    返回: 关闭的订单数量
    """
```

#### 获取订单统计
```python
def get_order_statistics():
    """获取订单统计信息
    
    返回:
    {
        'total_orders': 总数,
        'unpaid': 未支付数,
        'paid': 已支付数,
        'cancelled': 已取消数,
        'expired': 已过期数,
        'total_revenue': 总收入
    }
    """
```

---

## 🧪 测试流程

### 1. 创建订单

```bash
# 用户创建第一个订单
curl -X POST http://localhost:5000/api/orders/create \
  -H "Authorization: Bearer user_api_key"

# 响应应包含 order_id 和 payment_url
```

### 2. 验证订单数量限制

```bash
# 创建第二个订单 - 应成功
curl -X POST http://localhost:5000/api/orders/create \
  -H "Authorization: Bearer user_api_key"

# 尝试创建第三个订单 - 应失败
curl -X POST http://localhost:5000/api/orders/create \
  -H "Authorization: Bearer user_api_key"
# 响应: {"error": "已有 2 个未支付订单，最多只能有 2 个"}
```

### 3. 取消订单

```bash
# 取消一个订单
curl -X POST http://localhost:5000/api/orders/{order_id}/cancel \
  -H "Authorization: Bearer user_api_key"

# 现在可以创建新订单了
curl -X POST http://localhost:5000/api/orders/create \
  -H "Authorization: Bearer user_api_key"
```

### 4. Admin 操作

```bash
# 访问订单管理页面
# http://localhost:5000/admin/orders

# 筛选未支付订单
# http://localhost:5000/admin/orders?status=unpaid

# 手动标记为已支付
# 在 UI 中点击"标记支付"按钮
```

### 5. 自动过期测试

```python
# 手动触发过期检查（用于测试）
from project.membership import auto_close_expired_orders
auto_close_expired_orders()

# 或在用户查询时自动触发
curl -X GET http://localhost:5000/api/orders/list \
  -H "Authorization: Bearer user_api_key"
```

---

## ⚡ 最佳实践

### 为用户

1. **及时支付** - 订单30分钟后自动过期
2. **妥善管理** - 不要同时创建多个订单
3. **及时取消** - 不需要的订单应立即取消

### 为 Admin

1. **定期检查** - 监控订单管理页面
2. **及时处理** - 手动标记已支付或取消
3. **备份数据** - 定期备份数据库

---

## 🐛 常见问题

### Q: 为什么不能创建订单？
**A**: 可能有以下原因：
- 已有 2 个未支付订单
- 会员系统未启用
- Payhip 未配置

### Q: 订单什么时候过期？
**A**: 创建后 30 分钟未支付时自动过期

### Q: 过期的订单可以恢复吗？
**A**: 不能。用户需要创建新订单

### Q: Admin 可以手动激活会员吗？
**A**: 可以。两种方式：
1. 标记订单为已支付（自动激活）
2. 在会员设置中直接设置用户为会员

### Q: 支付完成后多久激活会员？
**A**: 
- 如果配置了 Webhook：立即激活
- 如果 Admin 手动标记：立即激活
- 如果只支付了但没配置：需要 Admin 手动标记

---

## 📈 性能考虑

1. **自动过期** - 在用户查询或 Admin 访问时触发，无后台任务
2. **订单查询** - O(n) 复杂度，通常很快
3. **大量订单** - 建议定期清理过期订单

---

## 🔐 安全考虑

1. **订单隔离** - 用户只能操作自己的订单
2. **API 认证** - 所有端点需要有效的 API Key
3. **Admin 保护** - 订单管理需要 Admin 权限
4. **Webhook 验证** - Payhip Webhook 签名验证

---

**更新日期**: 2024年  
**版本**: 1.0  
**状态**: ✅ 完成
