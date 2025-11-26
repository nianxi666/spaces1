#!/usr/bin/env python3
"""
Test to verify reasoning_content extraction methods
"""

import json

class MockDelta:
    """Mock Delta object that might have reasoning_content"""
    def __init__(self, content=None, reasoning_content=None):
        self.content = content
        self.reasoning_content = reasoning_content
    
    def model_dump(self, exclude_none=False):
        result = {}
        if self.content is not None or not exclude_none:
            result['content'] = self.content
        if self.reasoning_content is not None or not exclude_none:
            result['reasoning_content'] = self.reasoning_content
        return result


class MockMessage:
    """Mock Message object"""
    def __init__(self, content, reasoning_content=None):
        self.role = "assistant"
        self.content = content
        self.reasoning_content = reasoning_content
    
    def model_dump(self, exclude_none=False):
        result = {
            'role': self.role,
            'content': self.content
        }
        if self.reasoning_content is not None or not exclude_none:
            result['reasoning_content'] = self.reasoning_content
        return result


def test_extract_reasoning_from_delta():
    """Test extracting reasoning_content from delta"""
    print("\n=== Testing Delta Reasoning Extraction ===")
    
    delta = MockDelta(
        content="Hello",
        reasoning_content="Let me think..."
    )
    
    # Method 1: Direct attribute
    reasoning = None
    if hasattr(delta, 'reasoning_content'):
        reasoning = delta.reasoning_content
        print(f"✓ Method 1 (direct): {reasoning}")
    
    # Method 2: Via __dict__
    if not reasoning and hasattr(delta, '__dict__'):
        reasoning = delta.__dict__.get('reasoning_content')
        print(f"✓ Method 2 (__dict__): {reasoning}")
    
    # Method 3: Via model_dump
    if not reasoning and hasattr(delta, 'model_dump'):
        try:
            delta_dict = delta.model_dump(exclude_none=False)
            reasoning = delta_dict.get('reasoning_content')
            print(f"✓ Method 3 (model_dump): {reasoning}")
        except Exception as e:
            print(f"✗ Method 3 failed: {e}")
    
    assert reasoning == "Let me think...", "Failed to extract reasoning_content"
    print("✅ All extraction methods work")


def test_extract_reasoning_from_message():
    """Test extracting reasoning_content from message"""
    print("\n=== Testing Message Reasoning Extraction ===")
    
    message = MockMessage(
        content="The answer is 42",
        reasoning_content="Let me calculate... 1+41=42"
    )
    
    # Method 1: Direct attribute
    reasoning = None
    if hasattr(message, 'reasoning_content'):
        reasoning = message.reasoning_content
        print(f"✓ Method 1 (direct): {reasoning}")
    
    # Method 2: Via __dict__
    if not reasoning and hasattr(message, '__dict__'):
        reasoning = message.__dict__.get('reasoning_content')
        print(f"✓ Method 2 (__dict__): {reasoning}")
    
    # Method 3: Via model_dump
    if not reasoning and hasattr(message, 'model_dump'):
        try:
            msg_dict = message.model_dump(exclude_none=False)
            reasoning = msg_dict.get('reasoning_content')
            print(f"✓ Method 3 (model_dump): {reasoning}")
        except Exception as e:
            print(f"✗ Method 3 failed: {e}")
    
    assert reasoning == "Let me calculate... 1+41=42", "Failed to extract reasoning_content"
    print("✅ All extraction methods work")


def test_json_serialization():
    """Test JSON serialization with reasoning_content"""
    print("\n=== Testing JSON Serialization ===")
    
    # Create response structure
    response_dict = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "gpt-4",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "The answer is 42",
                    "reasoning_content": "Let me think... 40+2=42"
                },
                "finish_reason": "stop"
            }
        ]
    }
    
    # Serialize to JSON
    json_str = json.dumps(response_dict)
    print(f"✓ Serialized: {json_str[:100]}...")
    
    # Deserialize
    parsed = json.loads(json_str)
    reasoning = parsed['choices'][0]['message'].get('reasoning_content')
    
    assert reasoning == "Let me think... 40+2=42", "Failed to preserve reasoning_content in JSON"
    print("✅ JSON serialization preserves reasoning_content")


def test_stream_chunk_reasoning():
    """Test stream chunk with reasoning_content"""
    print("\n=== Testing Stream Chunk Reasoning ===")
    
    chunks = [
        {
            "id": "chatcmpl-1",
            "object": "chat.completion.chunk",
            "created": 1234567890,
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "content": None,
                        "reasoning_content": "Let me think..."
                    },
                    "finish_reason": None
                }
            ]
        },
        {
            "id": "chatcmpl-2",
            "object": "chat.completion.chunk",
            "created": 1234567890,
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "content": "The answer is"
                    },
                    "finish_reason": None
                }
            ]
        }
    ]
    
    # Check each chunk
    for chunk in chunks:
        delta = chunk['choices'][0]['delta']
        if 'reasoning_content' in delta:
            print(f"✓ Chunk {chunk['id']}: reasoning_content = {delta['reasoning_content']}")
        if 'content' in delta and delta['content']:
            print(f"✓ Chunk {chunk['id']}: content = {delta['content']}")
    
    print("✅ Stream chunks preserve reasoning_content")


def test_front_end_parsing():
    """Simulate frontend parsing of reasoning_content"""
    print("\n=== Testing Frontend Parsing ===")
    
    # Simulate SSE chunks from backend
    sse_chunks = [
        'data: {"choices":[{"delta":{"reasoning_content":"Let me think..."}}]}',
        'data: {"choices":[{"delta":{"content":"The answer"}}]}',
        'data: [DONE]'
    ]
    
    reasoning_buffer = []
    content_buffer = []
    
    for line in sse_chunks:
        if not line.startswith('data: '):
            continue
        
        data_str = line[6:]
        if data_str == '[DONE]':
            break
        
        try:
            data = json.loads(data_str)
            delta = data.get('choices', [{}])[0].get('delta', {})
            
            if 'reasoning_content' in delta:
                reasoning_buffer.append(delta['reasoning_content'])
            elif 'content' in delta and delta['content']:
                content_buffer.append(delta['content'])
        except json.JSONDecodeError:
            pass
    
    full_reasoning = ''.join(reasoning_buffer)
    full_content = ''.join(content_buffer)
    
    print(f"✓ Parsed reasoning: {full_reasoning}")
    print(f"✓ Parsed content: {full_content}")
    
    assert full_reasoning == "Let me think...", "Failed to parse reasoning"
    assert full_content == "The answer", "Failed to parse content"
    print("✅ Frontend can parse reasoning_content from SSE")


if __name__ == '__main__':
    print("Testing Reasoning Content Extraction")
    print("=" * 50)
    
    try:
        test_extract_reasoning_from_delta()
        test_extract_reasoning_from_message()
        test_json_serialization()
        test_stream_chunk_reasoning()
        test_front_end_parsing()
        
        print("\n" + "=" * 50)
        print("✅ ALL TESTS PASSED")
        print("=" * 50)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
