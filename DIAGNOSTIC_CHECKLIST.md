# AI 思考内容诊断检查清单

## 🔍 问题：在聊天中看不到 AI 的思考过程

按照以下步骤逐一排查问题。

---

## ✅ 第一步：验证模型支持

### 问题：您使用的模型是否支持推理？

**只有这些模型支持推理：**
- ✅ `deepseek-ai/DeepSeek-R1` - 明确支持思考过程
- ✅ 其他标记为"推理"或"reasoning"的模型

**不支持推理的模型：**
- ❌ `zai-org/GLM-4.6` - 普通模型，不返回reasoning_content
- ❌ `gpt-3.5-turbo` - 普通聊天模型
- ❌ 大多数通用模型

### 检查方法：
```bash
# 在聊天界面查看可用模型列表
# 寻找包含 "R1" 或 "reasoning" 的模型
```

**结果：**
- [ ] 已选择支持推理的模型
- [ ] 模型列表中没有推理模型（需要联系管理员）

---

## ✅ 第二步：检查 API 配置

### 问题：管理员配置的 NetMind API 是否正确？

### 检查项：

1. **API 密钥有效性**
   ```bash
   # 在管理后台检查
   设置 → NetMind 配置 → API Keys
   ```
   - [ ] API 密钥已填写
   - [ ] API 密钥不是测试密钥（不是 FAKE_*）
   - [ ] API 密钥未过期

2. **Base URL 正确性**
   ```
   应该是：https://api.netmind.ai/inference-api/openai/v1
   或类似的有效 NetMind URL
   ```
   - [ ] Base URL 填写正确
   - [ ] Base URL 不是 localhost 或内部 IP
   - [ ] Base URL 以 /v1 结尾

3. **网络连接**
   ```bash
   # 测试服务器到 API 的连接
   curl -I https://api.netmind.ai/inference-api/openai/v1/models
   ```
   - [ ] 能够连接到 NetMind API
   - [ ] 防火墙没有阻止出站连接

---

## ✅ 第三步：检查浏览器网络请求

### 打开浏览器开发者工具：
- Windows/Linux: `F12` 或 `Ctrl+Shift+I`
- macOS: `Cmd+Option+I`

### 步骤：
1. **打开 Network 标签**
2. **在聊天中发送消息**
3. **查找 `/api/v1/chat/completions` 请求**
4. **点击该请求 → Response 标签**

### 检查 API 响应：

#### 对于流式请求，应该看到类似的数据：
```
data: {"choices":[{"delta":{"reasoning_content":"Let me think..."}}]}
data: {"choices":[{"delta":{"content":"..."}}]}
```

#### 检查清单：
- [ ] API 请求返回 200（成功）
- [ ] 响应包含 `"reasoning_content"` 字段
- [ ] 响应中有 `"content"` 字段
- [ ] 响应格式有效（能看到 `data: {JSON}`）

### 如果看不到 reasoning_content：

**可能的原因：**

1. **API 返回错误**
   - 状态码 401/403 - API 密钥无效
   - 状态码 404 - 模型不存在
   - 状态码 429 - 速率限制

2. **API 返回的数据不包含 reasoning_content**
   - 这表示 NetMind API 本身不返回
   - 检查是否使用的是正确的模型
   - 检查 API 是否支持该模型

---

## ✅ 第四步：检查服务器日志

### 查看应用日志：
```bash
# 对于 systemd 服务
journalctl -u your-app-service -f

# 对于直接运行的应用
# 查看控制台输出

# 查找这些关键词：
# - "NetMind API"
# - "reasoning_content"
# - "Exception"
# - "Error"
```

### 关键日志信息：

**良好迹象：**
```
✓ Found reasoning_content via direct attribute
✓ Added reasoning_content to response dict
```

**问题迹象：**
```
✗ No reasoning_content found
✗ API Error: 401 Unauthorized
✗ Exception while processing
```

---

## ✅ 第五步：浏览器控制台检查

### 打开浏览器控制台：
- Windows/Linux: `F12` → Console
- macOS: `Cmd+Option+I` → Console

### 检查是否有错误：
- 红色错误消息表示有问题
- JavaScript 错误可能导致前端无法处理响应

### 常见错误：

1. **"当前浏览器不支持流式输出"**
   - 原因：浏览器版本过旧
   - 解决：更新浏览器到最新版本

2. **Network 错误或 CORS 错误**
   - 原因：请求被服务器或防火墙阻止
   - 解决：检查服务器配置

3. **JSON 解析错误**
   - 原因：响应数据格式不正确
   - 解决：检查 API 返回的数据

---

## ✅ 第六步：测试 API 直接调用

### 使用 curl 测试 API：
```bash
curl "https://your-domain.com/api/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_USER_TOKEN" \
  -d '{
    "model": "deepseek-ai/DeepSeek-R1",
    "messages": [{"role": "user", "content": "explain physics"}],
    "stream": false,
    "max_tokens": 1024
  }'
```

### 查看响应中是否有 `reasoning_content`：
```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "...",
      "reasoning_content": "..."  // ← 应该有这个
    }
  }]
}
```

### 检查清单：
- [ ] API 返回 200 状态码
- [ ] 响应包含 `reasoning_content` 字段
- [ ] 数据格式有效

---

## ✅ 第七步：检查前端代码

### 确认前端代码正确处理 reasoning_content：

在浏览器控制台运行：
```javascript
// 打开浏览器控制台 (F12)

// 检查是否能解析 SSE 数据
const testData = 'data: {"choices":[{"delta":{"reasoning_content":"test"}}]}';
console.log('Test data:', testData);

// 检查前端 extractDeltaText 函数是否存在
console.log('extractDeltaText function:', typeof extractDeltaText);
```

---

## ✅ 第八步：完整诊断流程

### 按顺序检查：

```
1. 模型支持？ (第一步)
   ├─ Yes → 继续
   └─ No → 使用 R1 模型

2. API 配置正确？ (第二步)
   ├─ Yes → 继续
   └─ No → 更新配置

3. API 返回 reasoning_content？ (第三、四步)
   ├─ Yes → 继续
   └─ No → 检查 API 和网络

4. 浏览器能解析吗？ (第五、七步)
   ├─ Yes → 应该看到思考内容
   └─ No → 更新浏览器或清除缓存

5. 仍未显示？ (第六步)
   └─ 直接测试 API
   └─ 收集日志信息
   └─ 联系管理员
```

---

## 📋 诊断数据收集

如果问题仍未解决，请收集以下信息供管理员参考：

### 必需信息：
- [ ] 使用的模型名称：`_______`
- [ ] 浏览器型号和版本：`_______`
- [ ] 操作系统：`_______`
- [ ] 消息发送时间：`_______`

### 浏览器信息：
- [ ] Network 标签中 API 响应的前 500 个字符
- [ ] 浏览器 Console 中的错误信息（如有）
- [ ] Network 标签中请求的完整 URL

### 服务器信息：
- [ ] 应用日志中关于该请求的部分
- [ ] 错误堆栈跟踪（如有）
- [ ] API 密钥是否有效（不要泄露完整密钥）

---

## 🔧 快速修复方案

| 问题 | 快速修复 |
|------|---------|
| 选错模型 | 选择包含"R1"的模型 |
| API 密钥无效 | 在管理后台更新密钥 |
| 浏览器不支持 | 更新浏览器 (Chrome 90+, Firefox 88+) |
| 缓存问题 | Ctrl+F5 (Windows) 或 Cmd+Shift+R (Mac) |
| 仍无法解决 | 重启应用并清除缓存 |

---

## 📞 获取帮助

**问题已排查但仍未解决？**

1. 收集上述诊断数据
2. 查看相关文档：
   - `AI_THINKING_SUPPORT.md` - 功能说明
   - `WHY_NO_THINKING_VISIBLE.md` - 问题分析
   - `IMPLEMENTATION_SUMMARY.md` - 实现细节
3. 联系系统管理员

---

**最后更新**: 2024-11-26
**文档版本**: 1.0
