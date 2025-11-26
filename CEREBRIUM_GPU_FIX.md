# Cerebrium GPU 云终端修复文档

## 问题描述

管理员在管理面板为用户 admin 分配了 Cerebrium GPU 云终端配置：
- **地址**: https://api.aws.us-east-1.cerebrium.ai/v4/p-0783839a/cloud-terminal-gpu/run
- **密钥**: JWT token

但是当 admin 用户登录到云终端页面时，**看不到分配的 GPU 配置**。

## 根本原因

系统中存在两个云终端配置加载渠道：

### 1️⃣ 自动探测（仅支持全局配置）
- `project/main.py` 中的 `cloud_terminal()` 函数
- 使用全局的 `CEREBRIUM_PROJECT_ID`
- 探测标准的 `cloud-terminal` 和 `cloud-terminal-gpu` 端点
- 仅当配置了全局项目 ID 时有效

### 2️⃣ 用户个人配置（被忽略）
- 管理员在 `/admin/users/<username>/custom-gpu` 为用户添加配置
- 这些配置存储在 `user['cerebrium_configs']` 中
- 包含用户特定的 API URL 和 Token
- ❌ **但初始页面加载时完全被忽略了**

## 修复方案

### 修改 `project/main.py` 中的 `cloud_terminal()` 函数

**问题代码**：
```python
display_targets = [{'name': target['name'], 'description': '自动探测'} for target in terminal_targets]
```

这只会显示自动探测的目标，不会包含用户个人配置。

**修复代码**：
```python
# Add user's personal Cerebrium configs if logged in
if session.get('logged_in'):
    username = session.get('username')
    user = db.get('users', {}).get(username)
    if user:
        user_configs = user.get('cerebrium_configs', [])
        for cfg in user_configs:
            cfg_name = cfg.get('name', 'Unnamed')
            terminal_targets.append({
                'name': cfg_name,
                'description': '用户自配置'
            })

# Update display targets to preserve descriptions
display_targets = [{'name': target['name'], 'description': target.get('description', '自动探测')} for target in terminal_targets]
```

## 修复后的流程

1. ✅ 页面加载时，`cloud_terminal()` 执行
2. ✅ 自动探测全局配置的 GPU 端点
3. ✅ **新增**：检查已登录用户是否有个人配置
4. ✅ 如果有，将其添加到列表中，标记为"用户自配置"
5. ✅ 前端显示所有可用的目标（自动探测 + 用户自配置）
6. ✅ 用户可以选择任一目标并执行命令

## 用户体验改进

### 修复前
```
云终端页面 → "你的云GPU机器正在启动中，请稍后再来"（即使已配置）
```

### 修复后
```
云终端页面 → 显示：
  - cloud-terminal-gpu (自动探测)
  - admin-gpu-config   (用户自配置) ← 新增
```

## 测试步骤

1. **管理员操作**：
   - 登录管理面板
   - 进入用户 admin 的 GPU 配置管理页面
   - 添加配置：
     - 名称: `admin-gpu-config`
     - API 地址: `https://api.aws.us-east-1.cerebrium.ai/v4/p-0783839a/cloud-terminal-gpu/run`
     - 密钥: `eyJh...` (JWT token)

2. **用户验证**：
   - 用户 admin 登录
   - 访问 `/cloud-terminal` 页面
   - ✅ 应该看到 `admin-gpu-config` 目标在列表中
   - ✅ 点击该目标可执行命令

## 相关代码位置

- **修改文件**: `project/main.py` 第 341-352 行 + 第 381 行
- **API 端点**: `project/api.py` 第 812-836 行 (`list_cloud_terminal_apps`)
- **命令执行**: `project/api.py` 第 659-734 行 (`proxy_cloud_terminal_command`)
- **管理面板**: `project/admin.py` 第 240-309 行 (GPU 配置管理)
- **前端模板**: `project/templates/cloud_terminal.html` 第 223 行 (调用 `list_cloud_terminal_apps`)

## 注意事项

### 为什么还需要 `list_cloud_terminal_apps` API？
- 初始页面加载显示快速列表
- 用户可以点击刷新按钮动态获取最新配置
- API 从用户配置中返回信息

### 如何处理重复配置？
- 如果自动探测找到了 `cloud-terminal-gpu`
- 且用户也配置了名为 `cloud-terminal-gpu` 的配置
- 它们会作为两个单独的选项显示（都可用）

### 性能影响
- 最小化：仅增加了一个用户数据库查询
- 配置数量通常很小（每个用户几个配置）
- 不影响页面加载速度

## 后续改进建议

如果需要进一步改进，可以考虑：

1. **去重**: 检测配置名称重复，显示优先级提示
2. **用户界面**: 在 UI 中区分不同来源的配置
3. **快速切换**: 记住用户上次选择的配置
4. **配置管理**: 在用户个人资料页面快速编辑配置

