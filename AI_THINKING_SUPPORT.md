# AI 思考功能支持指南

本文档说明如何使用和配置 AI 思考/推理功能（Reasoning Support）。

## 什么是 AI 思考功能？

AI 思考功能允许模型在生成最终答案前展示其思考/推理过程。这对复杂问题的解决特别有用。

## 支持的模型

只有特定的模型支持 `reasoning_content` 字段：

- **DeepSeek-R1** 系列 - 专为推理设计
- **其他支持推理的模型** - 取决于 NetMind API 的支持

## 技术实现

### 后端流程

1. **请求阶段**（`netmind_proxy.py`）
   - 通过 OpenAI 兼容 API 发送请求到 NetMind
   - 模型返回包含 `reasoning_content` 的响应

2. **响应处理**
   - **同步响应**：在 `_handle_sync()` 中提取 `reasoning_content` 并添加到响应
   - **流式响应**：在 `_sanitize_chunk_payload()` 中提取 `reasoning_content` 并添加到 delta

3. **API 端点**（`api.py`）
   - `/api/v1/chat/completions` 端点接收请求
   - 对于同步响应，显式提取并添加 `reasoning_content` 到 JSON 响应
   - 对于流式响应，通过 SSE 数据流传输 `reasoning_content`

### 前端流程

1. **接收处理**（`space_netmind_chat.html`）
   - 监听流式响应中的 `delta.reasoning_content` 字段
   - 在 `delta.content` 出现前累积推理内容

2. **显示逻辑**
   - 如果模型先发送 `reasoning_content`，显示"（模型正在思考...）"
   - 当 `content` 出现时，替换为最终答案
   - 如果只有 `reasoning_content` 没有 `content`，则显示完整的思考过程

## 使用示例

### 调用支持推理的模型

```bash
curl https://your-domain.com/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "deepseek-ai/DeepSeek-R1",
    "messages": [
      {"role": "user", "content": "请解释为什么1+1=2"}
    ],
    "stream": true,
    "max_tokens": 8192
  }'
```

### Python 调用示例

```python
from openai import OpenAI

client = OpenAI(
    api_key="YOUR_API_KEY",
    base_url="https://your-domain.com/api/v1"
)

response = client.chat.completions.create(
    model="deepseek-ai/DeepSeek-R1",
    messages=[
        {"role": "user", "content": "请解释为什么1+1=2"}
    ],
    stream=True,
    max_tokens=8192
)

for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end='', flush=True)
    elif chunk.choices[0].delta.reasoning_content:
        print(f"[Thinking: {chunk.choices[0].delta.reasoning_content}]", end='', flush=True)
```

## 故障排查

### 看不到思考内容

1. **确认模型支持推理**
   - 检查您使用的模型是否支持 `reasoning_content`
   - DeepSeek-R1 明确支持此功能

2. **检查 NetMind API 配置**
   - 确认管理员面板中配置的 API 密钥有效
   - 确认 base_url 正确

3. **查看浏览器控制台**
   - 打开浏览器开发者工具（F12）
   - 查看 Network 标签中的响应是否包含 `reasoning_content`

4. **服务器日志**
   - 查看应用日志输出
   - 关键词："NetMind API call with model"、"Chunk"

### 推理内容显示不完整

- 这可能是流式传输延迟
- 检查网络连接
- 增加 `max_tokens` 参数

## 配置建议

在管理员面板中配置以下内容：

1. **NetMind 设置**
   - API 密钥（有效且未过期）
   - Base URL（通常为 `https://api.netmind.ai/inference-api/openai/v1`）

2. **模型别名**（可选）
   - 为用户隐藏长模型名称
   - 例如：`R1` → `deepseek-ai/DeepSeek-R1`

## 开发调试

### 启用详细日志

在 `netmind_proxy.py` 中的日志会显示：
- API 调用的模型信息
- 流式响应的前几个块内容

### 测试思考功能

使用测试脚本：
```bash
python test_netmind_stream.py \
  --api-key YOUR_API_KEY \
  --base-url http://localhost:5001/api/v1 \
  --model "deepseek-ai/DeepSeek-R1" \
  --prompt "为什么天空是蓝色的？"
```

## 性能注意事项

- **推理时间**：含有推理过程的响应通常需要更长时间
- **Token 消耗**：`reasoning_content` 的 token 会计入总 token 用量
- **流式传输**：推理通常先发送，然后是最终答案

## 安全考虑

- 推理内容会完整发送给客户端
- 不要在系统提示中包含敏感信息
- 定期检查 API 密钥安全性
