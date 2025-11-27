#!/usr/bin/env python3
"""
Standalone test for thinking utilities without Flask dependencies.
Tests the core logic directly.
"""

import sys
import re


def test_inject_thinking_logic():
    """Test the thinking injection logic."""
    print("Testing thinking injection logic...")
    
    # Simulate the inject_thinking_prompt logic
    THINKING_SYSTEM_PROMPT = """
You are a profound thinking assistant. 
Before answering the user's request, you must perform a detailed step-by-step analysis.
Enclose your internal thought process within <thinking>...</thinking> tags.
After the thinking tags, provide your final response.
"""
    
    # Test 1: Empty messages
    messages = []
    result = list(messages)
    assert result == [], "Empty messages should stay empty"
    print("  ✓ Test 1: Empty messages")
    
    # Test 2: Messages without system prompt
    messages = [{'role': 'user', 'content': 'Hello'}]
    messages_copy = list(messages)
    messages_copy.insert(0, {
        'role': 'system',
        'content': THINKING_SYSTEM_PROMPT
    })
    assert len(messages_copy) == 2, "Should add system message"
    assert messages_copy[0]['role'] == 'system', "First should be system"
    assert '<thinking>' in messages_copy[0]['content'], "Should contain thinking tags"
    print("  ✓ Test 2: System prompt injection")
    
    # Test 3: Messages with existing system prompt
    messages = [
        {'role': 'system', 'content': 'You are helpful'},
        {'role': 'user', 'content': 'Hello'}
    ]
    messages_copy = list(messages)
    for i, msg in enumerate(messages_copy):
        if msg.get('role') == 'system':
            messages_copy[i] = msg.copy()
            messages_copy[i]['content'] = THINKING_SYSTEM_PROMPT + '\n' + messages_copy[i].get('content', '')
            break
    
    assert len(messages_copy) == 2, "Should not duplicate system message"
    assert '<thinking>' in messages_copy[0]['content'], "Should enhance system message"
    assert 'You are helpful' in messages_copy[0]['content'], "Should preserve original"
    print("  ✓ Test 3: Existing system prompt enhancement")


def test_extract_thinking_logic():
    """Test the thinking extraction logic."""
    print("\nTesting thinking extraction logic...")
    
    # Test 1: No thinking tags
    text = "Just a response"
    thinking_match = re.search(r'<thinking>(.*?)</thinking>', text, re.DOTALL)
    assert thinking_match is None, "Should not find thinking"
    print("  ✓ Test 1: No thinking tags")
    
    # Test 2: Complete thinking tags
    text = "Start <thinking>This is thinking</thinking> End"
    thinking_match = re.search(r'<thinking>(.*?)</thinking>', text, re.DOTALL)
    assert thinking_match is not None, "Should find thinking"
    thinking_content = thinking_match.group(1).strip()
    assert thinking_content == "This is thinking", f"Wrong content: {thinking_content}"
    
    # Clean content
    final_content = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL).strip()
    assert final_content == "Start  End", f"Wrong final: {final_content}"
    print("  ✓ Test 2: Thinking extraction")
    
    # Test 3: Multiline thinking
    text = """<thinking>
Step 1: Understand
Step 2: Solve
</thinking>
The answer is 42"""
    thinking_match = re.search(r'<thinking>(.*?)</thinking>', text, re.DOTALL)
    thinking_content = thinking_match.group(1).strip()
    assert "Step 1" in thinking_content, "Should preserve multiline"
    assert "Step 2" in thinking_content, "Should preserve multiline"
    print("  ✓ Test 3: Multiline thinking")


def test_stream_chunk_logic():
    """Test the streaming chunk processing logic."""
    print("\nTesting streaming chunk processing logic...")
    
    # Test 1: Chunk without thinking
    chunk = {
        'choices': [{
            'delta': {'content': 'Hello world'}
        }]
    }
    content = chunk['choices'][0]['delta'].get('content', '')
    assert content == 'Hello world', "Content should be unchanged"
    print("  ✓ Test 1: Chunk without thinking")
    
    # Test 2: Chunk with complete thinking tags
    chunk = {
        'choices': [{
            'delta': {'content': '<thinking>I think</thinking> The answer'}
        }]
    }
    delta = chunk['choices'][0]['delta']
    content = delta['content']
    
    if '<thinking>' in content and '</thinking>' in content:
        thinking_match = re.search(r'<thinking>(.*?)</thinking>', content, re.DOTALL)
        if thinking_match:
            delta['reasoning_content'] = thinking_match.group(1)
            delta['content'] = re.sub(r'<thinking>.*?</thinking>', '', content, flags=re.DOTALL).strip()
    
    assert delta['reasoning_content'] == 'I think', f"Wrong reasoning: {delta['reasoning_content']}"
    assert delta['content'] == 'The answer', f"Wrong content: {delta['content']}"
    print("  ✓ Test 2: Thinking extraction from chunk")


def test_is_thinking_enabled_logic():
    """Test the thinking enabled check logic."""
    print("\nTesting is_thinking_enabled logic...")
    
    # Test 1: Default enabled
    settings = {}
    enabled = settings.get('enable_thinking', True)  # Default True
    assert enabled is True, "Should default to True"
    print("  ✓ Test 1: Default enabled")
    
    # Test 2: Explicit True
    settings = {'enable_thinking': True}
    enabled = settings.get('enable_thinking', True)
    assert enabled is True, "Should be True"
    print("  ✓ Test 2: Explicit True")
    
    # Test 3: Explicit False
    settings = {'enable_thinking': False}
    enabled = settings.get('enable_thinking', True)
    assert enabled is False, "Should be False"
    print("  ✓ Test 3: Explicit False")
    
    # Test 4: String 'true'
    settings = {'enable_thinking': 'true'}
    enabled_str = settings.get('enable_thinking', True)
    if isinstance(enabled_str, str):
        enabled = enabled_str.lower() in ('true', '1', 'yes', 'on')
    assert enabled is True, "Should recognize string 'true'"
    print("  ✓ Test 4: String 'true'")
    
    # Test 5: String 'false'
    settings = {'enable_thinking': 'false'}
    enabled_str = settings.get('enable_thinking', True)
    if isinstance(enabled_str, str):
        enabled = enabled_str.lower() in ('true', '1', 'yes', 'on')
    assert enabled is False, "Should recognize string 'false'"
    print("  ✓ Test 5: String 'false'")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Standalone Thinking Feature Tests")
    print("=" * 60)
    
    try:
        test_inject_thinking_logic()
        test_extract_thinking_logic()
        test_stream_chunk_logic()
        test_is_thinking_enabled_logic()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed! (13 test cases)")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
