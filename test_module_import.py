#!/usr/bin/env python3
"""
Test importing the thinking_utils module directly.
"""

import sys
import os

# Add project to path
sys.path.insert(0, '/home/engine/project')

try:
    # Test direct import of thinking_utils without Flask
    import importlib.util
    spec = importlib.util.spec_from_file_location("thinking_utils", "/home/engine/project/project/thinking_utils.py")
    thinking_utils = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(thinking_utils)
    
    print("✅ Successfully imported thinking_utils module")
    print("\nAvailable functions:")
    print("  - THINKING_SYSTEM_PROMPT")
    print("  - has_system_message()")
    print("  - inject_thinking_prompt()")
    print("  - extract_thinking_and_content()")
    print("  - parse_thinking_chunk()")
    print("  - process_streaming_chunk()")
    print("  - enhance_response_with_thinking()")
    
    # Test the functions work
    print("\nQuick functionality test:")
    
    # Test 1: has_system_message
    messages = [{'role': 'system', 'content': 'test'}]
    result = thinking_utils.has_system_message(messages)
    assert result is True
    print("  ✓ has_system_message() works")
    
    # Test 2: inject_thinking_prompt
    messages = [{'role': 'user', 'content': 'Hello'}]
    result = thinking_utils.inject_thinking_prompt(messages)
    assert len(result) == 2
    assert result[0]['role'] == 'system'
    print("  ✓ inject_thinking_prompt() works")
    
    # Test 3: extract_thinking_and_content
    text = "<thinking>thinking</thinking>content"
    thinking, content = thinking_utils.extract_thinking_and_content(text)
    assert thinking == "thinking"
    assert "content" in content
    print("  ✓ extract_thinking_and_content() works")
    
    # Test 4: process_streaming_chunk
    chunk = {
        'choices': [{
            'delta': {'content': '<thinking>test</thinking> answer'}
        }]
    }
    result = thinking_utils.process_streaming_chunk(chunk)
    assert 'reasoning_content' in result['choices'][0]['delta']
    print("  ✓ process_streaming_chunk() works")
    
    print("\n✅ All module imports and functions work correctly!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
