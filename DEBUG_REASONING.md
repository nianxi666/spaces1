# AI 思考功能调试指南

如果您在聊天界面看不到 AI 的思考内容，请按照本指南进行排查。

## 快速检查清单

- [ ] 使用的模型是否支持推理？（例如：DeepSeek-R1）
- [ ] API 密钥是否有效？
- [ ] 浏览器是否显示任何错误？
- [ ] 检查了浏览器控制台吗？

## 第一步：验证模型支持

### 什么模型支持推理？

目前只有特定模型支持 `reasoning_content` 字段：

- ✓ **deepseek-ai/DeepSeek-R1** - 明确支持
- ✗ **zai-org/GLM-4.6** - 不支持推理
- ✗ **其他通用模型** - 通常不支持

**重要**：您必须选择一个支持推理的模型才能看到思考过程。

### 如何查看支持的模型？

1. 在聊天界面查看可用的模型列表
2. 选择包含 "R1" 或 "reasoning" 的模型
3. 如果没有这样的模型，请联系管理员添加 DeepSeek-R1

## 第二步：检查浏览器控制台

打开浏览器开发者工具查看网络请求：

1. **打开开发者工具**
   - Windows/Linux: `F12` 或 `Ctrl+Shift+I`
   - macOS: `Cmd+Option+I`

2. **切换到 Network 标签**

3. **发送一条消息**

4. **查找 API 请求**
   - 寻找对 `/api/v1/chat/completions` 的请求
   - 查看响应内容（Response 标签）

5. **检查响应中是否有 reasoning_content**
   
   对于流式响应，应该看到类似的数据：
   ```
   data: {"id":"chatcmpl-...","choices":[{"delta":{"reasoning_content":"..."},...}]}
   data: {"id":"chatcmpl-...","choices":[{"delta":{"content":"..."},...}]}
   ```

## 第三步：检查服务器日志

如果您有服务器访问权限，查看应用日志：

```bash
# 查看最近的日志
tail -f /var/log/app.log

# 寻找这些关键信息：
# 1. API 调用日志
NetMind API call with model: deepseek-ai/DeepSeek-R1

# 2. 流式响应开始
Chunk 1: {"choices":[{"delta":{...}}

# 3. 错误信息
# 如果有 Exception 或 Error 消息
```

## 第四步：验证 API 配置

检查管理员面板中的 NetMind 设置：

1. **Base URL** - 应该是 `https://api.netmind.ai/inference-api/openai/v1`
2. **API 密钥** - 必须有效且未过期
3. **模型别名** - 确保模型正确映射

### 测试 API 连接

使用 curl 测试 API：

```bash
curl "https://api.netmind.ai/inference-api/openai/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "deepseek-ai/DeepSeek-R1",
    "messages": [{"role": "user", "content": "1+1=?"}],
    "stream": false,
    "max_tokens": 512
  }'
```

查看响应中是否有 `reasoning_content` 字段。

## 第五步：前端调试

### 在浏览器控制台中执行 JavaScript 代码

打开浏览器控制台（F12 -> Console）并运行：

```javascript
// 检查是否有 fetch 错误
fetch('/api/v1/chat/completions', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + document.querySelector('[value*="api_key"]')?.value || 'YOUR_KEY'
    },
    body: JSON.stringify({
        model: 'deepseek-ai/DeepSeek-R1',
        messages: [{role: 'user', content: 'test'}],
        stream: true
    })
}).then(r => {
    if (!r.ok) {
        console.error('API Error:', r.status, r.statusText);
        return;
    }
    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    const readChunk = () => {
        reader.read().then(({done, value}) => {
            if (done) return;
            const text = decoder.decode(value, {stream: true});
            console.log('Stream chunk:', text);
            readChunk();
        });
    };
    readChunk();
}).catch(e => console.error('Fetch error:', e));
```

## 常见问题排查

### 问题：看不到任何输出

**可能原因**：
- [ ] 网络连接有问题
- [ ] API 密钥无效
- [ ] 模型不存在

**解决方案**：
1. 检查网络连接
2. 重新检查 API 密钥
3. 验证模型名称

### 问题：看到"当前浏览器不支持流式输出"

**可能原因**：
- 浏览器不支持 ReadableStream API
- 浏览器版本太旧

**解决方案**：
- 使用现代浏览器（Chrome、Firefox、Safari 最新版本）
- 尝试在隐身模式中使用

### 问题：只看到内容，没有思考过程

**可能原因**：
- 模型不支持推理
- API 没有返回 reasoning_content
- 前端没有正确解析

**解决方案**：
1. 确认使用的是 DeepSeek-R1 等支持推理的模型
2. 查看浏览器开发者工具中的响应
3. 检查前端代码中的 `extractDeltaText` 函数

### 问题：思考过程显示不完整

**可能原因**：
- 流式传输中断
- Token 限制
- 网络延迟

**解决方案**：
1. 检查网络连接质量
2. 增加 `max_tokens` 参数
3. 重新尝试请求

## 获取更多帮助

如果问题仍未解决：

1. **收集日志**
   - 浏览器控制台输出（F12）
   - 服务器应用日志
   - API 响应内容

2. **检查文档**
   - 查看 `AI_THINKING_SUPPORT.md`
   - 查看 `netmind_proxy.py` 的源代码注释

3. **联系管理员**
   - 提供完整的错误信息
   - 提供使用的模型名称
   - 提供 API 密钥的有效期信息

## 实时日志输出

### 启用详细日志

在 `netmind_proxy.py` 中，您将看到这样的日志：

```
NetMind API call with model: deepseek-ai/DeepSeek-R1, payload keys: ['model', 'messages', 'stream']
Chunk 1: {"id":"chatcmpl-...","choices":[{"delta":{"reasoning_content":"Let me think..."}...}]}
```

这表明：
- ✓ API 调用正在进行
- ✓ 从 NetMind 接收到数据
- ✓ 数据包含 reasoning_content

## 测试 Python 脚本

运行测试脚本来验证实现：

```bash
python test_reasoning_support.py
```

应该看到：
- ✓ PASS: api_response
- ✓ PASS: stream_parsing

## 下一步

1. 如果看到了思考过程，尝试不同的问题来体验推理功能
2. 给管理员反馈使用体验
3. 探索其他支持推理的模型

---

**最后更新**: 2024-11-26
**相关文件**: 
- `project/netmind_proxy.py` - 后端处理
- `project/api.py` - API 端点
- `project/templates/space_netmind_chat.html` - 前端显示
