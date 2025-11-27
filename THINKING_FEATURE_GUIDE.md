# Model Internal Thinking Feature Guide

## Overview

This guide explains the internal thinking/reasoning feature for all models. When enabled, models are instructed to enclose their internal thought process within `<thinking>...</thinking>` tags before providing their final response.

## How It Works

### 1. Automatic System Prompt Injection

When a user sends a message to any model through the API, the system automatically prepends a thinking system prompt:

```
You are a profound thinking assistant. 
Before answering the user's request, you must perform a detailed step-by-step analysis.
Enclose your internal thought process within <thinking>...</thinking> tags.
After the thinking tags, provide your final response.
```

### 2. Response Processing

The system automatically:
- **For sync responses**: Extracts the thinking content from `<thinking>...</thinking>` tags and stores it separately
- **For streaming responses**: Detects thinking tags in chunks and exposes them as `reasoning_content`
- **Content cleaning**: Removes thinking tags from the final response shown to users

### 3. Configuration

The thinking feature is enabled by default. To disable it, administrators can set `enable_thinking: false` in the netmind_settings configuration:

```python
db['netmind_settings']['enable_thinking'] = False
```

## API Response Examples

### Sync Response (Non-streaming)

**Request:**
```bash
curl -X POST http://localhost:5001/api/v1/chat/completions \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/gemini-3-pro-preview",
    "messages": [{"role": "user", "content": "What is 2+2?"}],
    "stream": false
  }'
```

**Response:**
The response will contain:
- `message.content`: The final answer (thinking tags removed)
- `message.reasoning_content`: (if available) The extracted thinking process

### Streaming Response

**Request:**
```bash
curl -X POST http://localhost:5001/api/v1/chat/completions \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/gemini-3-pro-preview",
    "messages": [{"role": "user", "content": "What is 2+2?"}],
    "stream": true
  }'
```

**Response Stream:**
Chunks will include:
- `delta.reasoning_content`: When the model is thinking (extracted from thinking tags)
- `delta.content`: The final response content

## Example Model Response

Model output:
```
<thinking>
The user is asking what 2+2 equals.
This is a basic arithmetic question.
2 + 2 = 4
I should provide a clear, confident answer.
</thinking>

2 + 2 equals 4.
```

After processing:
- **reasoning_content**: "The user is asking what 2+2 equals.\nThis is a basic arithmetic question.\n2 + 2 = 4\nI should provide a clear, confident answer."
- **content**: "2 + 2 equals 4."

## Files Modified

### project/thinking_utils.py (New)
Contains utility functions for:
- Injecting thinking prompts into message lists
- Extracting thinking from responses
- Processing streaming chunks

### project/netmind_proxy.py
- Imports thinking utilities
- Calls `inject_thinking_prompt()` before sending messages to models
- Calls `enhance_response_with_thinking()` for sync responses
- Calls `process_streaming_chunk()` for streaming responses

### project/netmind_config.py
- Added `DEFAULT_ENABLE_THINKING` configuration
- Added `is_thinking_enabled()` function to check feature status

## Key Functions

### `inject_thinking_prompt(messages)`
Adds the thinking system prompt to the beginning of a message list.

**Parameters:**
- `messages`: List of message dicts with 'role' and 'content' keys

**Returns:**
- Modified messages list with thinking prompt added

### `extract_thinking_and_content(text)`
Separates thinking tags from response content.

**Parameters:**
- `text`: Raw response text that may contain `<thinking>...</thinking>` tags

**Returns:**
- Tuple of (thinking_content, final_content)

### `enhance_response_with_thinking(response)`
Processes a complete response to extract and separate thinking.

**Parameters:**
- `response`: OpenAI ChatCompletion response object

**Returns:**
- Enhanced response with thinking extracted

### `process_streaming_chunk(chunk_dict)`
Handles thinking extraction from streaming chunks.

**Parameters:**
- `chunk_dict`: Dictionary representing a streaming chunk

**Returns:**
- Modified chunk dict with reasoning_content extracted if applicable

## Testing

To test the thinking feature:

```bash
# Start the server
python run.py

# Make a request with a complex question
curl -X POST http://localhost:5001/api/v1/chat/completions \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "zai-org/GLM-4.6",
    "messages": [{"role": "user", "content": "Explain quantum computing in simple terms"}],
    "stream": true,
    "max_tokens": 1024
  }'
```

## Disabling the Feature

To disable internal thinking for all models:

1. Access the admin panel
2. Go to NetMind Settings
3. Set `enable_thinking` to `false`

Or programmatically:
```python
from project.database import load_db, save_db

db = load_db()
db['netmind_settings']['enable_thinking'] = False
save_db(db)
```

## Backward Compatibility

The thinking feature is fully backward compatible:
- Existing API clients work without modification
- Thinking is extracted automatically and doesn't interfere with normal responses
- Feature can be toggled on/off without breaking anything
- Clients can ignore `reasoning_content` if they don't need it

## Performance Considerations

- Enabling thinking may increase response times as models spend tokens on internal reasoning
- The feature respects the `max_tokens` parameter - thinking content counts toward the token limit
- Streaming responses are processed efficiently in real-time

## Future Enhancements

Possible improvements:
- Make thinking prompt customizable per-request
- Add per-user thinking preference
- Support for different thinking depth levels
- Analytics on thinking content patterns
- Export thinking logs for debugging/analysis
