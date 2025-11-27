# Model Internal Thinking - Usage Examples

## Overview

With the thinking feature enabled, models now provide reasoning content alongside their responses. This guide shows practical examples of how to use this feature.

## Example 1: Simple Thinking Request (Sync)

### Python Code
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:5001/api",
    api_key="YOUR_USER_TOKEN"
)

response = client.chat.completions.create(
    model="zai-org/GLM-4.6",
    messages=[
        {
            "role": "user",
            "content": "What's the capital of France?"
        }
    ],
    stream=False
)

# Print the response
print("Answer:", response.choices[0].message.content)

# Check if reasoning is available
if hasattr(response.choices[0].message, 'reasoning_content'):
    print("Thinking process:", response.choices[0].message.reasoning_content)
```

### Expected Output
```
Answer: The capital of France is Paris.
Thinking process: The user is asking about the capital of France. This is a straightforward geography question. The capital city of France is Paris, which is located in northern France on the Seine River. It's been the capital for many centuries.
```

## Example 2: Streaming Response with Thinking

### Python Code
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:5001/api",
    api_key="YOUR_USER_TOKEN"
)

stream = client.chat.completions.create(
    model="zai-org/GLM-4.6",
    messages=[
        {
            "role": "user",
            "content": "Explain photosynthesis in simple terms"
        }
    ],
    stream=True,
    max_tokens=500
)

print("=== Model Reasoning ===")
has_content = False
reasoning_buffer = []

for chunk in stream:
    choice = chunk.choices[0]
    delta = choice.delta
    
    # Check for regular content
    if hasattr(delta, 'content') and delta.content:
        has_content = True
        reasoning_buffer.clear()  # Clear reasoning once content starts
        print(delta.content, end='', flush=True)
    
    # Check for reasoning content
    elif hasattr(delta, 'reasoning_content') and delta.reasoning_content:
        reasoning_buffer.append(delta.reasoning_content)

# Print buffered reasoning if no content was provided
if not has_content and reasoning_buffer:
    print("\n=== Thinking Process ===")
    print("".join(reasoning_buffer))
else:
    print("\n=== Done ===")
```

### Expected Output
```
=== Model Reasoning ===
Photosynthesis is the process by which plants convert light energy into chemical energy...
=== Done ===
```

## Example 3: Complex Question with Visible Reasoning

### Python Code
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:5001/api",
    api_key="YOUR_USER_TOKEN"
)

response = client.chat.completions.create(
    model="zai-org/GLM-4.6",
    messages=[
        {
            "role": "user",
            "content": "If a train travels 60 km/h and another train travels 80 km/h, starting from the same point at the same time, how far apart will they be after 2 hours?"
        }
    ],
    stream=False
)

print("=== Question ===")
print("If a train travels 60 km/h and another train travels 80 km/h, starting from the same point at the same time, how far apart will they be after 2 hours?")

print("\n=== Model's Thinking Process ===")
if hasattr(response.choices[0].message, 'reasoning_content'):
    print(response.choices[0].message.reasoning_content)

print("\n=== Final Answer ===")
print(response.choices[0].message.content)
```

### Expected Output
```
=== Question ===
If a train travels 60 km/h and another train travels 80 km/h, starting from the same point at the same time, how far apart will they be after 2 hours?

=== Model's Thinking Process ===
The user is asking about the distance between two trains moving at different speeds.

Train 1: 60 km/h
Train 2: 80 km/h
Time: 2 hours

Distance = speed × time

Train 1 distance: 60 km/h × 2 h = 120 km
Train 2 distance: 80 km/h × 2 h = 160 km

Distance between them: 160 km - 120 km = 40 km

=== Final Answer ===
After 2 hours, the two trains will be 40 km apart. Train 1 will have traveled 120 km (60 km/h × 2 hours), while Train 2 will have traveled 160 km (80 km/h × 2 hours), resulting in a separation of 40 km.
```

## Example 4: Using Thinking in a Web Application

### JavaScript (Frontend)
```javascript
async function askModelWithThinking(question) {
    const response = await fetch('http://localhost:5001/api/v1/chat/completions', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${userToken}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            model: 'zai-org/GLM-4.6',
            messages: [{ role: 'user', content: question }],
            stream: false
        })
    });

    const data = await response.json();
    const message = data.choices[0].message;
    
    return {
        answer: message.content,
        reasoning: message.reasoning_content || null
    };
}

// Usage
const result = await askModelWithThinking('What is quantum entanglement?');
console.log('Answer:', result.answer);
if (result.reasoning) {
    console.log('Model Thinking:', result.reasoning);
}
```

## Example 5: Streaming with Real-time Thinking Display

### JavaScript (Frontend)
```javascript
async function streamModelWithThinking(question) {
    const response = await fetch('http://localhost:5001/api/v1/chat/completions', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${userToken}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            model: 'zai-org/GLM-4.6',
            messages: [{ role: 'user', content: question }],
            stream: true
        })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    
    let answerDiv = document.getElementById('answer');
    let thinkingDiv = document.getElementById('thinking');
    let hasContent = false;

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value);
        const lines = text.split('\n');

        for (const line of lines) {
            if (line.startsWith('data: ') && line !== 'data: [DONE]') {
                const chunk = JSON.parse(line.slice(6));
                const delta = chunk.choices[0].delta;

                if (delta.content) {
                    hasContent = true;
                    thinkingDiv.style.display = 'none';
                    answerDiv.textContent += delta.content;
                } else if (delta.reasoning_content) {
                    answerDiv.style.display = 'none';
                    thinkingDiv.textContent += delta.reasoning_content;
                }
            }
        }
    }
}
```

## Configuration

### Enabling/Disabling Thinking

To disable thinking globally via admin panel or API:

```python
from project.database import load_db, save_db

db = load_db()
db['netmind_settings']['enable_thinking'] = False
save_db(db)
```

### Default Setting

By default, thinking is enabled. To change the default:

```python
# In project/netmind_config.py
DEFAULT_ENABLE_THINKING = False  # Change to disable by default
```

## Benefits

1. **Better Understanding**: See the model's reasoning process
2. **Transparency**: Understand how the model arrived at its answer
3. **Debugging**: Identify errors in the model's thinking
4. **Educational**: Learn how models approach problems
5. **Verification**: Check the correctness of intermediate steps

## Limitations

- Thinking tokens count toward the `max_tokens` limit
- Some models may not support thinking effectively
- Longer responses due to additional reasoning content
- May increase latency slightly

## Tips for Best Results

1. **Use for Complex Problems**: Thinking is most valuable for multi-step reasoning
2. **Set Adequate max_tokens**: Ensure max_tokens is high enough for both thinking and response
3. **Specific Questions**: Ask clear, specific questions to get detailed thinking
4. **Review Reasoning**: Always review the reasoning to ensure it's correct
5. **Combine with Context**: Provide context for complex topics

## Troubleshooting

### No Reasoning Content Returned
- Ensure `enable_thinking` is set to `true` in netmind_settings
- Some models may not support thinking - try a different model
- Check that `max_tokens` is sufficient

### Reasoning Seems Irrelevant
- The model might not understand the question clearly
- Try rephrasing or providing more context
- Some models are better at reasoning than others

### Too Many Tokens Used
- Reduce the thinking depth by asking for more concise thinking
- Increase `max_tokens` if you need more comprehensive thinking
- Consider disabling thinking if token usage is critical
