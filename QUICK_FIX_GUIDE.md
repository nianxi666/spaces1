# AI 思考功能快速修复指南

## 如果您看不到 AI 的思考过程

### ⚡ 快速检查（2 分钟）

1. **检查您使用的模型**
   - ✅ 支持：`deepseek-ai/DeepSeek-R1`
   - ❌ 不支持：`zai-org/GLM-4.6` 等通用模型
   
2. **打开浏览器开发者工具**
   - 按 `F12` 或 `Ctrl+Shift+I`
   - 切换到 **Network** 标签
   
3. **发送一条消息**
   - 查找 `/api/v1/chat/completions` 请求
   - 点击查看 **Response**
   
4. **寻找 `reasoning_content`**
   - ✅ 有 = 系统工作正常，是模型问题
   - ❌ 没有 = 系统配置问题

### 🔧 根据情况修复

#### 情况 1：看不到思考内容
```bash
# 步骤 1: 更换为支持推理的模型
选择 "deepseek-ai/DeepSeek-R1" 或包含 "R1" 的模型

# 步骤 2: 刷新页面
Ctrl+F5 (完全刷新缓存)

# 步骤 3: 重新提问
问一个复杂问题，如：
"为什么天空是蓝色的？请详细解释"
```

#### 情况 2：浏览器响应中没有 `reasoning_content`
```bash
# 步骤 1: 检查 API 密钥
管理员面板 → NetMind 设置 → 验证 API 密钥有效

# 步骤 2: 检查 Base URL
应该是：https://api.netmind.ai/inference-api/openai/v1

# 步骤 3: 重启应用
sudo systemctl restart your-app
# 或
pkill -f "python run.py"
python run.py
```

#### 情况 3：看到错误信息
```bash
# 在浏览器控制台中查看完整错误
F12 → Console → 查看红色错误

# 常见错误：
- "Rate limit exceeded" = 请稍候再试
- "Invalid API key" = 检查管理员配置
- "Model not found" = 该模型不可用
- "Stream not supported" = 浏览器太旧
```

## 💡 验证功能是否工作

### 测试命令
```bash
# 在项目目录运行
python test_reasoning_support.py

# 应该看到：
# ✓ PASS: api_response
# ✓ PASS: stream_parsing
```

### 浏览器控制台测试
```javascript
// 打开浏览器控制台 (F12) 并运行：
console.log('Testing reasoning support...');

// 应该看到响应中有 reasoning_content 字段
```

## 📊 诊断流程图

```
看不到思考内容
    ↓
是否使用 DeepSeek-R1？
├─ 否 → 改用 R1 模型
│        └─ 再试一次
└─ 是 → 打开浏览器开发者工具 (F12)
         ↓
         API 响应有 reasoning_content？
         ├─ 否 → 检查管理员配置
         │        ├─ API 密钥有效？
         │        ├─ Base URL 正确？
         │        └─ 重启应用
         └─ 是 → 检查前端显示
                  ├─ 浏览器版本太旧？
                  │  └─ 更新浏览器
                  └─ 检查应用日志
                     └─ 报告问题给管理员
```

## 🚨 常见问题速解

| 问题 | 症状 | 解决方案 |
|------|------|--------|
| 模型不支持 | 没有思考内容 | 选择 DeepSeek-R1 |
| 浏览器不支持流式 | "不支持流式输出" | 更新浏览器 |
| API 密钥无效 | API 错误 401/403 | 更新 API 密钥 |
| 网络问题 | 请求超时或中断 | 检查网络连接 |
| 模型过载 | 响应缓慢或失败 | 稍候再试 |

## 📞 获取帮助

### 信息收集清单
收集这些信息后报告问题：
- [ ] 使用的模型名称
- [ ] 浏览器型号和版本
- [ ] 浏览器控制台中的完整错误信息
- [ ] API 响应中是否有 reasoning_content
- [ ] 应用日志的相关部分

### 文档参考
- 详细指南：`DEBUG_REASONING.md`
- 功能说明：`AI_THINKING_SUPPORT.md`
- 实现细节：`IMPLEMENTATION_SUMMARY.md`

## ✅ 成功指标

您会看到：
1. 发送消息后显示"（模型正在思考...）"
2. 思考过程文本出现（通常是中文或英文）
3. 最终答案替换思考内容
4. 浏览器控制台无错误

## ⚡ 一行修复

```bash
# 如果一切都不行，重新配置 API：
# 1. 更新 API 密钥
# 2. 验证 Base URL
# 3. 重启应用
# 4. 刷新浏览器
# 5. 重新尝试
```

---

**需要更多帮助？** 查看完整的故障排查指南：`DEBUG_REASONING.md`

**上次更新**: 2024-11-26
