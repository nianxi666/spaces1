# 订单管理系统 - 快速参考

## 🎯 核心规则一览

| 规则 | 说明 |
|------|------|
| 最多未支付订单数 | 2 个 |
| 订单有效期 | 30 分钟 |
| 自动过期 | 超过30分钟自动关闭 |
| 订单状态 | unpaid, paid, cancelled, expired |

## 📊 订单状态转换

```
unpaid (创建)
  ├─ → paid (支付 或 Admin标记)
  ├─ → cancelled (取消)
  └─ → expired (30分钟无支付)
```

## 🔗 API 快速调用

### 获取用户订单
```bash
curl -X GET http://localhost:5000/api/orders/list \
  -H "Authorization: Bearer {API_KEY}"
```

### 创建新订单
```bash
curl -X POST http://localhost:5000/api/orders/create \
  -H "Authorization: Bearer {API_KEY}"
```

### 取消订单
```bash
curl -X POST http://localhost:5000/api/orders/{ORDER_ID}/cancel \
  -H "Authorization: Bearer {API_KEY}"
```

## 👨‍💼 Admin 快速操作

### 访问订单页面
- URL: `http://localhost:5000/admin/orders`
- 粉红色按钮: "订单管理"

### Admin 端点

| 操作 | 方法 | 路由 |
|------|------|------|
| 列表 | GET | `/admin/orders` |
| 筛选 | GET | `/admin/orders?status={status}` |
| 标记支付 | POST | `/admin/orders/{id}/mark-paid` |
| 取消 | POST | `/admin/orders/{id}/cancel` |

## 📝 核心函数

```python
# membership.py 中的主要函数

create_order(username)                      # 创建订单
get_user_orders(username, status=None)      # 获取用户订单
get_user_pending_orders(username)           # 获取未支付订单
mark_order_paid(order_id)                   # 标记已支付
cancel_order(order_id)                      # 取消订单
auto_close_expired_orders()                 # 自动过期
get_all_orders(filter_status=None)          # 获取所有订单
get_order_statistics()                      # 获取统计
```

## 💡 常见场景

### 场景1: 用户创建订单流程
1. 调用 `POST /api/orders/create` → 获得 order_id 和 payment_url
2. 用户访问 payment_url 支付
3. Webhook 触发 → 自动激活会员
4. 或 Admin 手动标记 → 激活会员

### 场景2: 用户订单已满
1. 用户已有2个未支付订单
2. 尝试创建第3个 → 失败，提示已满
3. 用户选择：
   - 支付已有订单之一
   - 取消已有订单
   - 等待30分钟自动过期

### 场景3: Admin 处理订单
1. 进入订单管理页面
2. 筛选"未支付"订单
3. 对每个订单：
   - 标记支付 → 激活会员
   - 取消 → 用户可重新创建

## 🚀 快速部署检查

- [ ] 订单表初始化 (orders: {})
- [ ] API 端点可访问
- [ ] Admin 页面显示
- [ ] 自动过期逻辑工作
- [ ] 订单数量限制生效
- [ ] Webhook 集成正确

## 🧪 测试命令

```bash
# 测试创建订单
python3 -c "
from project.membership import create_order, get_user_pending_orders
order, err = create_order('testuser')
print(f'订单: {order[\"order_id\"][:8]}')
print(f'未支付: {len(get_user_pending_orders(\"testuser\"))}')
"

# 测试自动过期
python3 -c "
from project.membership import auto_close_expired_orders
count = auto_close_expired_orders()
print(f'过期订单: {count}')
"
```

## 📊 性能数据

| 操作 | 时间复杂度 | 备注 |
|------|----------|------|
| 创建订单 | O(1) | 快速 |
| 查询订单 | O(n) | n=订单总数 |
| 自动过期 | O(n) | 按需触发 |
| 统计信息 | O(n) | 实时计算 |

## 🔐 权限检查

| 操作 | 权限要求 |
|------|---------|
| 创建订单 | 需要登录 + API Key |
| 查询自己的订单 | 需要登录 + API Key |
| 取消自己的订单 | 需要登录 + API Key |
| 查看所有订单 | Admin 权限 |
| 标记订单支付 | Admin 权限 |
| 取消任何订单 | Admin 权限 |

## 🐛 故障排查

| 问题 | 解决方案 |
|------|---------|
| 不能创建订单 | 检查未支付订单是否已满2个 |
| 订单不过期 | 检查系统时间，手动调用自动过期函数 |
| API 返回401 | 检查 API Key 格式和有效性 |
| Admin 页面无数据 | 检查是否有订单，可能都已过期或支付 |

## 📞 需要帮助？

- 详细文档: `ORDERS_MANAGEMENT_GUIDE.md`
- API 文档: `MEMBERSHIP_API_IMPLEMENTATION.md`
- 快速开始: `MEMBERSHIP_QUICK_START.md`

---

**版本**: 1.0  
**最后更新**: 2024年  
**状态**: ✅ 完成
