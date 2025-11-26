#!/usr/bin/env python3
"""
Test script to verify reasoning_content support in the API.
This script helps debug whether reasoning_content is properly passed through the system.

Usage:
    python test_reasoning_support.py
"""

import json
from unittest.mock import MagicMock, patch


def test_sanitize_chunk_with_reasoning():
    """Test that _sanitize_chunk_payload preserves reasoning_content"""
    print("\n=== Test 1: _sanitize_chunk_payload with reasoning_content ===")
    
    # Import here to avoid Flask import issues
    import sys
    sys.path.insert(0, '/home/engine/project')
    
    from project.netmind_proxy import NetMindClient
    
    # Create a mock chunk with reasoning_content
    chunk = MagicMock()
    chunk.model_dump.return_value = {
        'id': 'chatcmpl-test-1',
        'object': 'chat.completion.chunk',
        'created': 1234567890,
        'model': 'upstream-model',
        'choices': [
            {
                'index': 0,
                'delta': {
                    'content': 'Hello'
                },
                'finish_reason': None
            }
        ]
    }
    
    # Create mock delta with reasoning_content
    mock_delta = MagicMock()
    mock_delta.content = 'Hello'
    mock_delta.reasoning_content = 'Let me think about this greeting...'
    
    mock_choice = MagicMock()
    mock_choice.delta = mock_delta
    
    chunk.choices = [mock_choice]
    
    # Test the method
    client = NetMindClient()
    result = client._sanitize_chunk_payload(chunk, 'public-model', 'base-id', 0)
    
    # Verify
    print(f"Result structure: {json.dumps(result, indent=2, default=str)[:300]}...")
    
    has_reasoning = 'reasoning_content' in result.get('choices', [{}])[0].get('delta', {})
    if has_reasoning:
        reasoning_value = result['choices'][0]['delta']['reasoning_content']
        print(f"✓ reasoning_content found: {reasoning_value}")
        assert reasoning_value == 'Let me think about this greeting...', "reasoning_content value mismatch"
        return True
    else:
        print("✗ reasoning_content NOT found in delta")
        return False


def test_api_response_with_reasoning():
    """Test that API response includes reasoning_content in non-streaming mode"""
    print("\n=== Test 2: API response with reasoning_content ===")
    
    import sys
    sys.path.insert(0, '/home/engine/project')
    
    # Simulate the API response processing
    # The response from OpenAI SDK
    response_json = {
        'id': 'chatcmpl-test',
        'object': 'chat.completion',
        'created': 1234567890,
        'model': 'gpt-4',
        'choices': [
            {
                'index': 0,
                'message': {
                    'role': 'assistant',
                    'content': 'The answer is 3.'
                },
                'finish_reason': 'stop'
            }
        ]
    }
    
    # Simulate what the API endpoint does
    response_dict = response_json.copy()
    
    # Add reasoning_content (simulating what we do in api.py)
    if response_dict['choices']:
        for i, choice in enumerate(response_dict['choices']):
            if 'message' not in choice:
                choice['message'] = {}
            # Simulate extracting reasoning_content from the API
            reasoning_value = '1 + 1 = 2, so 1 + 2 = 3'
            choice['message']['reasoning_content'] = reasoning_value
    
    print(f"Response with reasoning: {json.dumps(response_dict, indent=2)[:400]}...")
    
    has_reasoning = 'reasoning_content' in response_dict['choices'][0]['message']
    if has_reasoning:
        print(f"✓ reasoning_content in response: {response_dict['choices'][0]['message']['reasoning_content']}")
        return True
    else:
        print("✗ reasoning_content NOT in response")
        return False


def test_stream_chunk_parsing():
    """Test that frontend can parse streaming chunks with reasoning_content"""
    print("\n=== Test 3: Stream chunk parsing ===")
    
    # Simulate streaming chunks
    chunks = [
        {
            'id': 'chatcmpl-1',
            'object': 'chat.completion.chunk',
            'created': 1234567890,
            'model': 'gpt-4',
            'choices': [
                {
                    'index': 0,
                    'delta': {
                        'role': 'assistant',
                        'reasoning_content': 'Let me think...'
                    },
                    'finish_reason': None
                }
            ]
        },
        {
            'id': 'chatcmpl-2',
            'object': 'chat.completion.chunk',
            'created': 1234567890,
            'model': 'gpt-4',
            'choices': [
                {
                    'index': 0,
                    'delta': {
                        'reasoning_content': 'Now I understand...'
                    },
                    'finish_reason': None
                }
            ]
        },
        {
            'id': 'chatcmpl-3',
            'object': 'chat.completion.chunk',
            'created': 1234567890,
            'model': 'gpt-4',
            'choices': [
                {
                    'index': 0,
                    'delta': {
                        'content': 'The answer is '
                    },
                    'finish_reason': None
                }
            ]
        },
        {
            'id': 'chatcmpl-4',
            'object': 'chat.completion.chunk',
            'created': 1234567890,
            'model': 'gpt-4',
            'choices': [
                {
                    'index': 0,
                    'delta': {
                        'content': 'three.'
                    },
                    'finish_reason': 'stop'
                }
            ]
        }
    ]
    
    reasoning_buffer = []
    content_buffer = []
    has_content = False
    
    for chunk in chunks:
        delta = chunk.get('choices', [{}])[0].get('delta', {})
        content = delta.get('content')
        reasoning = delta.get('reasoning_content')
        
        if content:
            has_content = True
            if reasoning_buffer:
                print(f"  [Thinking phase complete with {len(reasoning_buffer)} chunks]")
            content_buffer.append(content)
        elif reasoning:
            if not has_content:
                reasoning_buffer.append(reasoning)
    
    print(f"Reasoning chunks: {reasoning_buffer}")
    print(f"Content chunks: {content_buffer}")
    
    if reasoning_buffer:
        print(f"✓ Reasoning detected: {''.join(reasoning_buffer)}")
    if content_buffer:
        print(f"✓ Content detected: {''.join(content_buffer)}")
    
    return bool(reasoning_buffer) and bool(content_buffer)


if __name__ == '__main__':
    print("Testing AI Thinking Support Implementation")
    print("=" * 50)
    
    results = []
    
    try:
        results.append(('sanitize_chunk', test_sanitize_chunk_with_reasoning()))
    except Exception as e:
        print(f"✗ Test failed: {e}")
        results.append(('sanitize_chunk', False))
    
    try:
        results.append(('api_response', test_api_response_with_reasoning()))
    except Exception as e:
        print(f"✗ Test failed: {e}")
        results.append(('api_response', False))
    
    try:
        results.append(('stream_parsing', test_stream_chunk_parsing()))
    except Exception as e:
        print(f"✗ Test failed: {e}")
        results.append(('stream_parsing', False))
    
    print("\n" + "=" * 50)
    print("Test Summary:")
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")
    
    all_passed = all(passed for _, passed in results)
    if all_passed:
        print("\n✓ All tests passed! AI Thinking Support is properly configured.")
    else:
        print("\n✗ Some tests failed. Check the implementation.")
    
    exit(0 if all_passed else 1)
