# Remote Inference Refactoring - Progress Report

## 已完成的工作 (Completed Work)

### 1. 创建了新的远程推理模块
- **文件**: `project/remote_inference.py`
- **功能**:
  - 使用 curl 发送请求（不暴露 API 地址）
  - 支持队列管理
  - 支持音频上传和prompt功能
  - 提供管理员模板代码生成功能

### 2. 数据库迁移
- **文件**: `project/database.py`
- **更改**:
  - 移除 `modal_drive_shares` from default structure
  - 将 `cerebrium_configs` 重命名为 `remote_inference_configs`
  - 将 card_type `cerebrium` 自动迁移为 `remote_inference`
  - 添加 `remote_inference_timeout_seconds` 字段
  - 自动迁移旧的 `cerebrium_timeout_seconds` 数据

### 3. 管理界面更新
- **文件**: `project/templates/add_edit_space.html`
- **更改**:
  - 移除 "标准命令型 (Inferless/Modal)" 选项文字中的Inferless/Modal
  - 将 "自定义 GPU API 型" 更名为 "远程推理型 (Remote Inference)"
  - 更新超时字段名称
  - 移除模板中的 Inferless/Modal 命令运行器选项
  - 仅保留 "Remote Gradio (远程推理)" 和 "自定义命令"

- **文件**: `project/admin.py`
- **更改**:
  - 更新字段名称从 `cerebrium_timeout_minutes` 到 `remote_inference_timeout_minutes`
  - 更新所有相关的数据库保存逻辑

## 待完成的工作 (Remaining Work)

### 1. 移除 Modal Drive 相关代码
需要删除或注释以下文件/功能:
- `project/modal_drive_utils.py` - 整个文件
- `project/admin.py` 中的 `manage_modal_drive_settings` 路由
- `project/templates/admin_modal_drive.html` 模板
- `project/results.py` 中与 modal_drive 相关的路由和函数

### 2. 移除云终端相关代码
需要删除或注释:
- `project/cloud_terminal_source/` 目录（如果存在）
- `project/terminal.py` 中的云终端相关功能
- `project/templates/cloud_terminal.html` 模板
- 导航栏中的云终端链接

### 3. 移除 Modal/Inferless 执行逻辑
需要更新 `project/tasks.py`:
- 移除 `command_runner == 'modal'` 的分支
- 移除 `command_runner == 'inferless'` 的分支
- 添加 `command_runner == 'gradio_client'` 的新逻辑（使用远程推理模块）

### 4. 更新 API 端点
需要更新 `project/api.py`:
- 将 `save_custom_gpu_result` 重命名为 `save_remote_inference_result`
- 将 `get_my_custom_gpu_configs` 重命名为 `get_my_remote_inference_configs`
- 将 `get_custom_gpu_s3_context` 重命名为 `get_remote_inference_s3_context`
- 更新相关的admin API端点名称

### 5. 更新前端视图
需要更新 `project/main.py`:
- 将 `custom_gpu_configs` 重命名为 `remote_inference_configs`
- 将 `last_custom_gpu_result` 重命名为 `last_remote_inference_result`
- 将 `custom_gpu_timeout_seconds` 重命名为 `remote_inference_timeout_seconds`

### 6. 更新前端模板
需要更新 `project/templates/ai_project_view.html`:
- 将所有 `custom_gpu` 相关的变量和元素ID重命名为 `remote_inference`
- 将 `space_card_type == 'cerebrium'` 改为 `space_card_type == 'remote_inference'`
- 更新JavaScript中的变量名和URL

### 7. 集成音频生成模板
需要创建:
- 音频生成示例的集成代码
- Admin面板中的模板查看/复制功能
- 提供完整的webui.py集成示例

## 音频生成模板使用说明

### 管理员集成代码（已在 remote_inference.py 中提供）

管理员可以通过以下方式获取模板代码:

```python
from project.remote_inference import get_admin_template_code

# 获取音频生成模板
audio_template = get_admin_template_code('audio_generation')

# 获取通用模板
generic_template = get_admin_template_code('custom')
```

### 集成到 webui.py 的步骤:

1. 复制模板代码到webui.py
2. 更新 `REMOTE_API_URL` 为实际的远程API地址
3. 在Gradio界面中调用 `process_remote_inference` 函数
4. 配置好音频上传和参数

### 特点:
- ✅ 使用 curl 命令（隐藏API地址）
- ✅ 支持音频文件上传
- ✅ 支持prompt功能
- ✅ 支持队列管理
- ✅ 通用模板，适配任何webui

## 下一步建议

1. **立即执行**: 完成上述"待完成的工作"第1-6项
2. **测试**: 确保数据库迁移正确，旧的cerebrium配置能正确迁移到remote_inference
3. **清理**: 删除所有未使用的modal/inferless/云终端相关文件
4. **文档**: 为管理员编写如何使用新的远程推理类型的说明文档

## 注意事项

- 所有数据库更改都包含了向后兼容的迁移逻辑
- 现有的 netmind 聊天型卡片不受影响
- 远程推理模块使用 subprocess 调用 curl，需要确保系统安装了 curl
- 模板代码是通用的，不需要为不同的webui编写不同的集成代码
