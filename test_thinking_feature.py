#!/usr/bin/env python3
"""
Test script for the thinking feature implementation.
Tests the core thinking utilities without requiring Flask or OpenAI.
"""

import sys
import json


def test_inject_thinking_prompt():
    """Test the inject_thinking_prompt function."""
    from project.thinking_utils import inject_thinking_prompt
    
    # Test 1: Empty messages list
    result = inject_thinking_prompt([])
    assert result == [], "Empty messages should remain empty"
    print("✓ Test 1 passed: Empty messages list handled")
    
    # Test 2: Messages without system prompt
    messages = [{'role': 'user', 'content': 'Hello'}]
    result = inject_thinking_prompt(messages)
    assert len(result) == 2, "Should add system message"
    assert result[0]['role'] == 'system', "First message should be system"
    assert '<thinking>' in result[0]['content'], "System message should mention thinking"
    print("✓ Test 2 passed: Thinking prompt injected for messages without system")
    
    # Test 3: Messages with existing system prompt
    messages = [
        {'role': 'system', 'content': 'You are helpful'},
        {'role': 'user', 'content': 'Hello'}
    ]
    result = inject_thinking_prompt(messages)
    assert len(result) == 2, "Should not add duplicate system message"
    assert result[0]['role'] == 'system', "First message should still be system"
    assert '<thinking>' in result[0]['content'], "System message should be enhanced"
    assert 'You are helpful' in result[0]['content'], "Original system message should be preserved"
    print("✓ Test 3 passed: Existing system prompt enhanced")


def test_extract_thinking_and_content():
    """Test the extract_thinking_and_content function."""
    from project.thinking_utils import extract_thinking_and_content
    
    # Test 1: No thinking tags
    thinking, content = extract_thinking_and_content("Just a response")
    assert thinking == "", "No thinking found"
    assert content == "Just a response", "Content should be unchanged"
    print("✓ Test 4 passed: Response without thinking tags handled")
    
    # Test 2: Complete thinking tags
    text = "Start <thinking>This is thinking</thinking> End"
    thinking, content = extract_thinking_and_content(text)
    assert thinking == "This is thinking", f"Thinking not extracted: {thinking}"
    assert content == "Start  End", f"Content not cleaned: {content}"
    print("✓ Test 5 passed: Thinking extracted from response")
    
    # Test 3: Multiline thinking
    text = "<thinking>\nStep 1\nStep 2\n</thinking>\nFinal answer"
    thinking, content = extract_thinking_and_content(text)
    assert "Step 1" in thinking and "Step 2" in thinking, "Multiline thinking not extracted"
    assert thinking.startswith("Step 1"), "Thinking should be trimmed"
    assert content == "Final answer", "Content should be trimmed"
    print("✓ Test 6 passed: Multiline thinking handled")


def test_process_streaming_chunk():
    """Test the process_streaming_chunk function."""
    from project.thinking_utils import process_streaming_chunk
    
    # Test 1: Chunk without thinking
    chunk = {
        'choices': [{
            'delta': {'content': 'Hello world'}
        }]
    }
    result = process_streaming_chunk(chunk)
    assert result['choices'][0]['delta']['content'] == 'Hello world', "Content should be unchanged"
    assert 'reasoning_content' not in result['choices'][0]['delta'], "No reasoning_content should be added"
    print("✓ Test 7 passed: Chunk without thinking unchanged")
    
    # Test 2: Chunk with complete thinking tags
    chunk = {
        'choices': [{
            'delta': {'content': '<thinking>I think</thinking> The answer'}
        }]
    }
    result = process_streaming_chunk(chunk)
    assert result['choices'][0]['delta']['reasoning_content'] == 'I think', "Reasoning should be extracted"
    assert result['choices'][0]['delta']['content'] == 'The answer', "Content should be cleaned"
    print("✓ Test 8 passed: Thinking extracted from chunk")


def test_is_thinking_enabled():
    """Test the is_thinking_enabled function."""
    from project.netmind_config import is_thinking_enabled, DEFAULT_ENABLE_THINKING
    
    # Test 1: Default enabled
    enabled = is_thinking_enabled()
    assert enabled == DEFAULT_ENABLE_THINKING, f"Should use default: {DEFAULT_ENABLE_THINKING}"
    print("✓ Test 9 passed: Default thinking setting works")
    
    # Test 2: Explicit True
    settings = {'enable_thinking': True}
    enabled = is_thinking_enabled(settings)
    assert enabled is True, "Should be enabled"
    print("✓ Test 10 passed: Explicit True setting works")
    
    # Test 3: Explicit False
    settings = {'enable_thinking': False}
    enabled = is_thinking_enabled(settings)
    assert enabled is False, "Should be disabled"
    print("✓ Test 11 passed: Explicit False setting works")
    
    # Test 4: String 'true'
    settings = {'enable_thinking': 'true'}
    enabled = is_thinking_enabled(settings)
    assert enabled is True, "Should recognize string 'true'"
    print("✓ Test 12 passed: String 'true' setting works")
    
    # Test 5: String 'false'
    settings = {'enable_thinking': 'false'}
    enabled = is_thinking_enabled(settings)
    assert enabled is False, "Should recognize string 'false'"
    print("✓ Test 13 passed: String 'false' setting works")


def main():
    """Run all tests."""
    print("Testing thinking feature implementation...\n")
    
    try:
        test_inject_thinking_prompt()
        print()
        test_extract_thinking_and_content()
        print()
        test_process_streaming_chunk()
        print()
        test_is_thinking_enabled()
        print()
        print("✅ All tests passed!")
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
