# 充值会员系统 - 完整测试指南

## 🧪 测试概览

本指南包含三个层次的测试：
1. **单元测试** - 函数级测试
2. **集成测试** - 模块间测试
3. **端到端测试** - 完整流程测试

---

## 📋 第一部分：单元测试

### 1.1 运行自动化测试脚本

```bash
cd /home/engine/project
python3 test_membership_system.py
```

**预期输出**:
```
============================================================
MEMBERSHIP SYSTEM TEST
============================================================

✓ Database loaded successfully

📋 Current Membership Settings:
   Enabled: False
   Price: $5.0/month
   Duration: 30 days
   Payhip API Key: ✗ Not set
   Payhip Product ID: ✗ Not set

✓ Created test user: test_user_membership

📊 Initial status for test_user_membership:
   Is Member: False
   Days Remaining: 0
   Expired: False

✓ Set test_user_membership as member for 30 days

📊 After setting membership:
   Is Member: True
   Days Remaining: 30
   Expiry Date: 2024-01-15T12:00:00

✓ is_user_member('test_user_membership'): True

✓ Revoked membership for test_user_membership

📊 After revoking membership:
   Is Member: False

💳 Payment History for test_user_membership:
   1. subscription - 30 days - 2024-01-15

✅ ALL TESTS PASSED!
============================================================
```

### 1.2 验证会员函数

在 Python 控制台中测试核心函数：

```python
from project.membership import (
    is_user_member,
    get_user_membership_status,
    set_user_membership,
    is_membership_enabled
)
from project.database import load_db, save_db

# 测试1：检查会员系统是否启用
print("测试1: 会员系统启用状态")
enabled = is_membership_enabled()
print(f"  Result: {enabled}")

# 测试2：检查用户是否是会员
print("\n测试2: 检查用户会员状态")
is_member = is_user_member('testuser')
print(f"  Result: {is_member}")

# 测试3：获取详细会员状态
print("\n测试3: 获取详细会员状态")
status = get_user_membership_status('testuser')
print(f"  Status: {status}")

# 测试4：设置用户为会员
print("\n测试4: 设置用户为会员")
set_user_membership('testuser', 30)
status = get_user_membership_status('testuser')
print(f"  Is Member: {status['is_member']}")
print(f"  Days Remaining: {status['days_remaining']}")
```

---

## 🔌 第二部分：API 端点测试

### 2.1 准备工作

1. **启动应用**:
```bash
cd /home/engine/project
python3 run.py
```

应用应在 `http://localhost:5000` 启动

2. **获取 API Token**:
   - 注册一个测试用户或登录现有用户
   - 查看个人资料页面，复制 API Key

### 2.2 测试 API 端点

#### 测试 1: 获取会员状态

```bash
curl -X GET http://localhost:5000/api/membership/status \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**预期响应**:
```json
{
  "membership_enabled": false,
  "status": {
    "is_member": false,
    "expiry_date": null,
    "days_remaining": 0,
    "expired": false
  }
}
```

#### 测试 2: 生成支付链接（未配置）

```bash
curl -X POST http://localhost:5000/api/membership/renew \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**预期响应**（会员系统未启用或未配置）:
```json
{
  "error": "Membership system is not enabled" / "Failed to create payment link"
}
```

#### 测试 3: 验证 Webhook 端点

```bash
curl -X POST http://localhost:5000/api/membership/webhook/payhip \
  -H "Content-Type: application/json" \
  -H "X-Payhip-Signature: test-signature" \
  -d '{"status": "completed", "metadata": {"username": "testuser"}}'
```

**预期响应**（未配置 API Key）:
```json
{
  "error": "Webhook not configured"
}
```

---

## 👨‍💼 第三部分：Admin 管理功能测试

### 3.1 启用会员系统

1. **登录 Admin 账户**
   - 访问 `http://localhost:5000/login`
   - 使用 Admin 账户登录

2. **导航到会员设置**
   - 进入管理面板
   - 点击紫色"会员系统设置"按钮（应该在导航栏顶部）

3. **配置会员系统**
   - ✅ 勾选"启用会员系统"
   - 验证价格显示为 $5.00
   - 验证期限显示为 30 天
   - 点击"保存设置"
   - 应显示成功提示

### 3.2 快速操作测试

#### 测试 1: 手动设置用户为会员

1. 在"快速操作"部分：
   - 用户名输入框输入：`testuser`
   - 天数输入框输入：`30`
   - 点击"设为会员"按钮

2. **预期结果**:
   - 显示成功消息："✓ testuser 已成为会员，有效期 30 天"
   - 输入框清空

#### 测试 2: 取消用户会员资格

1. 在"快速操作"部分：
   - 用户名输入框输入：`testuser`
   - 点击"取消会员"按钮
   - 确认弹窗

2. **预期结果**:
   - 显示成功消息："✓ testuser 的会员资格已取消"

#### 测试 3: 错误处理

1. 输入不存在的用户名：`nonexistentuser`
2. 点击"设为会员"
3. **预期结果**: 显示错误消息："✗ 用户不存在"

### 3.3 用户列表中的会员状态

1. 在 Admin 面板点击"用户管理"
2. 查看用户表格
3. **验证项目**:
   - ✅ 表格中有"会员状态"列
   - ✅ 之前设置为会员的用户显示："✓ 会员"
   - ✅ 其他用户显示："非会员"
   - ✅ 活跃会员下方显示过期日期

---

## 👤 第四部分：用户界面测试

### 4.1 非会员用户视图

1. **以非会员用户登录**
   - 进入 `http://localhost:5000/profile`

2. **验证会员卡片**:
   - ✅ 紫色会员卡片显示
   - ✅ 显示"成为会员"标题
   - ✅ 显示"仅需 $5/月"的说明
   - ✅ 显示"立即购买"按钮

3. **点击"立即购买"按钮**:
   - 如果会员系统启用 + Payhip 配置完成：
     - ✅ 应重定向到 Payhip 支付页面
   - 如果会员系统未完全配置：
     - ✅ 显示错误提示

### 4.2 活跃会员用户视图

1. **Admin 手动设置用户为会员**（如前所述）

2. **以该用户登录进入个人资料**
   - 访问 `http://localhost:5000/profile`

3. **验证会员卡片**:
   - ✅ 紫色会员卡片显示 "活跃" 徽章
   - ✅ 显示"活跃会员"标题
   - ✅ 显示倒计时："会员有效期还有 X 天"
   - ✅ 显示过期日期
   - ✅ "续费会员"按钮可用

### 4.3 过期会员用户视图

1. **在数据库中手动设置用户过期日期**
   ```python
   from project.database import load_db, save_db
   from datetime import datetime, timedelta
   
   db = load_db()
   username = 'testuser'
   yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
   db['users'][username]['member_expiry_date'] = yesterday
   save_db(db)
   ```

2. **用户登录查看个人资料**

3. **验证显示**:
   - ✅ 卡片仍显示但没有"活跃"徽章
   - ✅ 显示"会员已过期"
   - ✅ 显示过期日期
   - ✅ "续费会员"按钮可用

---

## 🔐 第五部分：支付集成测试（可选）

> ⚠️ 需要实际的 Payhip 账户

### 5.1 配置 Payhip 测试环境

1. **登录 Payhip**:
   - 访问 `https://payhip.com`

2. **创建产品**:
   - 产品名称：`Membership - Test`
   - 价格：$5.00
   - 类型：一次性购买或订阅
   - 启用测试模式

3. **获取凭证**:
   - API Key
   - 产品 ID

4. **在 Admin 面板配置**:
   - 启用会员系统
   - 输入 Payhip API Key
   - 输入产品 ID
   - 保存

5. **设置 Webhook**:
   - 在 Payhip 中添加 Webhook URL：
     ```
     https://your-domain.com/api/membership/webhook/payhip
     ```
   - 事件类型：Payment Completed

### 5.2 测试完整支付流程

1. **用户点击购买会员**
   - 页面应重定向到 Payhip
   - ✅ 显示价格 $5.00
   - ✅ 显示产品名称

2. **完成测试支付**
   - 在 Payhip 使用测试卡号
   - 完成支付

3. **验证会员激活**
   - Webhook 应调用系统 API
   - 用户刷新后应显示"活跃会员"
   - 数据库中应记录支付历史

---

## 📊 第六部分：数据库验证

### 6.1 检查数据库结构

```python
from project.database import load_db

db = load_db()

# 检查1：会员设置
print("会员设置:")
print(db.get('membership_settings', {}))

# 检查2：用户会员字段
print("\n用户会员字段:")
user = db['users'].get('testuser', {})
print(f"  is_member: {user.get('is_member')}")
print(f"  member_expiry_date: {user.get('member_expiry_date')}")
print(f"  payment_history: {user.get('payment_history')}")
```

### 6.2 验证数据初始化

```python
from project.database import load_db

db = load_db()

# 验证所有用户都有会员字段
for username, user_data in db.get('users', {}).items():
    assert 'is_member' in user_data, f"{username} 缺少 is_member"
    assert 'member_expiry_date' in user_data, f"{username} 缺少 member_expiry_date"
    assert 'payment_history' in user_data, f"{username} 缺少 payment_history"

print("✓ 所有用户字段检查通过")

# 验证会员设置存在
assert 'membership_settings' in db, "缺少 membership_settings"
settings = db['membership_settings']
assert 'enabled' in settings, "缺少 enabled"
assert 'price_usd' in settings, "缺少 price_usd"
assert 'duration_days' in settings, "缺少 duration_days"

print("✓ 会员设置检查通过")
```

---

## ✅ 测试清单

### 单元测试
- [ ] 运行 `test_membership_system.py` 通过
- [ ] 会员状态检查函数工作正常
- [ ] 会员设置初始化正确

### API 测试
- [ ] GET /api/membership/status 返回正确数据
- [ ] POST /api/membership/renew 处理请求
- [ ] POST /api/membership/webhook/payhip 验证 webhook

### Admin 测试
- [ ] 会员设置页面显示正确
- [ ] 启用/禁用会员系统有效
- [ ] 快速操作设置用户为会员工作
- [ ] 快速操作取消用户会员工作
- [ ] 用户列表显示会员状态列

### UI 测试
- [ ] 非会员用户看到"立即购买"按钮
- [ ] 活跃会员看到"续费会员"按钮
- [ ] 过期会员看到"续费会员"按钮
- [ ] 会员状态倒计时显示正确
- [ ] 支付成功后自动激活会员

### 数据验证
- [ ] 新用户创建时有会员字段
- [ ] 支付历史正确记录
- [ ] 过期检查正确计算

---

## 🐛 常见问题排查

### 问题 1: 会员卡片不显示

**可能原因**:
- ❌ 会员系统未启用
- ❌ 模板未正确传递 `membership_enabled` 参数
- ❌ 模板中有语法错误

**解决方案**:
```python
# 检查 profile 路由是否正确传递参数
from project.main import profile
import inspect
print(inspect.getsource(profile))
```

### 问题 2: API 返回 401 错误

**可能原因**:
- ❌ API Key 格式错误
- ❌ API Key 前缀不正确（应为 "Bearer "）

**解决方案**:
```bash
# 确保使用正确的格式
curl -X GET http://localhost:5000/api/membership/status \
  -H "Authorization: Bearer abc123def456..."
```

### 问题 3: 支付链接创建失败

**可能原因**:
- ❌ Payhip API Key 未设置或错误
- ❌ 产品 ID 无效
- ❌ Payhip API 服务不可用

**解决方案**:
```python
# 测试 Payhip 连接
from project.membership import create_payhip_payment_link
link = create_payhip_payment_link('testuser')
print(f"Payment link: {link}")
```

---

## 📝 测试报告模板

记录测试结果：

```
# 测试日期: 2024-01-15
# 测试环境: localhost:5000

## 单元测试
- ✅/❌ test_membership_system.py: PASS/FAIL
- ✅/❌ 会员函数: PASS/FAIL

## API 测试
- ✅/❌ GET /api/membership/status: PASS/FAIL
- ✅/❌ POST /api/membership/renew: PASS/FAIL
- ✅/❌ POST /api/membership/webhook/payhip: PASS/FAIL

## Admin 测试
- ✅/❌ 会员设置页面: PASS/FAIL
- ✅/❌ 快速操作: PASS/FAIL
- ✅/❌ 用户列表: PASS/FAIL

## UI 测试
- ✅/❌ 非会员视图: PASS/FAIL
- ✅/❌ 活跃会员视图: PASS/FAIL
- ✅/❌ 过期会员视图: PASS/FAIL

## 总体结果: PASS/FAIL

## 备注:
...
```

---

## 🚀 下一步

测试通过后：
1. 部署到测试服务器
2. 进行烟雾测试（smoke testing）
3. 负载测试
4. 安全审计
5. 部署到生产环境

---

**更新日期**: 2024年
**版本**: 1.0
