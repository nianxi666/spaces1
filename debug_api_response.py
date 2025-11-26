#!/usr/bin/env python3
"""
Debug script to inspect the actual API response structure from OpenAI SDK.
This helps understand where reasoning_content actually is.
"""

import json
import sys
from unittest.mock import MagicMock, patch

def inspect_response_object():
    """Inspect the structure of response objects from OpenAI SDK"""
    print("\n" + "="*60)
    print("Testing OpenAI SDK Response Structure")
    print("="*60)
    
    try:
        from openai.types.chat import ChatCompletion, ChatCompletionMessage
        from openai.types.chat.chat_completion_chunk import ChatCompletionChunk, Choice, ChoiceDelta
        
        print("\n✓ Successfully imported OpenAI types")
        
        # Check what attributes ChatCompletionMessage has
        print("\n--- ChatCompletionMessage attributes ---")
        msg = ChatCompletionMessage(role="assistant", content="test")
        print(f"Message object: {msg}")
        print(f"Message type: {type(msg)}")
        print(f"Message dict: {msg.model_dump()}")
        print(f"Has reasoning_content: {hasattr(msg, 'reasoning_content')}")
        
        # Try to add reasoning_content
        print("\n--- Attempting to add reasoning_content ---")
        try:
            msg.reasoning_content = "test reasoning"
            print(f"✓ Successfully added reasoning_content")
            print(f"reasoning_content value: {msg.reasoning_content}")
            print(f"model_dump with reasoning: {msg.model_dump()}")
        except Exception as e:
            print(f"✗ Failed to add reasoning_content: {e}")
        
        # Test with dict-based approach
        print("\n--- Testing dict-based approach ---")
        msg_dict = msg.model_dump()
        msg_dict['reasoning_content'] = "Added via dict"
        print(f"Dict with added reasoning_content: {msg_dict}")
        
    except ImportError as e:
        print(f"✗ Failed to import: {e}")
        print("OpenAI SDK might not be installed")
        return False
    
    return True


def test_stream_chunk_structure():
    """Test the structure of streaming chunks"""
    print("\n" + "="*60)
    print("Testing Stream Chunk Structure")
    print("="*60)
    
    try:
        from openai.types.chat.chat_completion_chunk import ChatCompletionChunk, Choice, ChoiceDelta
        
        print("\n--- Creating sample chunk with reasoning_content ---")
        
        # Create a mock delta with reasoning_content
        delta_data = {
            "content": None,
            "reasoning_content": "Let me think about this..."
        }
        
        print(f"Delta data: {delta_data}")
        
        # Try to create ChoiceDelta
        try:
            delta = ChoiceDelta(**delta_data)
            print(f"✓ Created ChoiceDelta: {delta}")
            print(f"Delta model_dump: {delta.model_dump()}")
            print(f"Has reasoning_content: {hasattr(delta, 'reasoning_content')}")
            if hasattr(delta, 'reasoning_content'):
                print(f"reasoning_content value: {delta.reasoning_content}")
        except Exception as e:
            print(f"✗ Failed to create ChoiceDelta: {e}")
            
    except ImportError as e:
        print(f"✗ Failed to import: {e}")
        return False
    
    return True


def mock_api_response_test():
    """Test with a mocked API response"""
    print("\n" + "="*60)
    print("Testing Mocked API Response")
    print("="*60)
    
    try:
        from openai.types.chat import ChatCompletion, ChatCompletionMessage, Choice
        
        # Create a mock response with reasoning_content
        mock_data = {
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
                        "reasoning_content": "Let me think... 1+1=2, so..."
                    },
                    "finish_reason": "stop"
                }
            ]
        }
        
        print(f"\nMock data: {json.dumps(mock_data, indent=2)}")
        
        try:
            response = ChatCompletion(**mock_data)
            print(f"\n✓ Created ChatCompletion object")
            print(f"Response: {response}")
            
            # Check the message
            msg = response.choices[0].message
            print(f"\n--- Message Analysis ---")
            print(f"Message type: {type(msg)}")
            print(f"Message: {msg}")
            print(f"Has reasoning_content: {hasattr(msg, 'reasoning_content')}")
            
            if hasattr(msg, 'reasoning_content'):
                print(f"reasoning_content: {msg.reasoning_content}")
            
            # Check model_dump
            print(f"\n--- model_dump Analysis ---")
            print(f"Message model_dump: {msg.model_dump()}")
            print(f"Full response model_dump_json: {response.model_dump_json()}")
            
        except Exception as e:
            print(f"✗ Failed to create response: {e}")
            import traceback
            traceback.print_exc()
            
    except ImportError as e:
        print(f"✗ Failed to import: {e}")
        return False
    
    return True


def test_raw_response_parsing():
    """Test parsing raw JSON responses"""
    print("\n" + "="*60)
    print("Testing Raw Response Parsing")
    print("="*60)
    
    # Simulate what NetMind API might return
    raw_json_response = {
        "id": "chatcmpl-8J7qK9L8mN2pQ3rS4tU5",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "deepseek-ai/DeepSeek-R1",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Based on my analysis, the answer is...",
                    "reasoning_content": "<think>Let me think through this problem step by step...</think>"
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 100,
            "total_tokens": 110
        }
    }
    
    print(f"\nRaw JSON response: {json.dumps(raw_json_response, indent=2)[:500]}...")
    
    # Parse it
    try:
        from openai.types.chat import ChatCompletion
        
        response = ChatCompletion(**raw_json_response)
        print(f"\n✓ Parsed as ChatCompletion")
        
        msg = response.choices[0].message
        print(f"Message has reasoning_content via getattr: {getattr(msg, 'reasoning_content', 'NOT FOUND')}")
        
        # Try model_dump
        msg_dict = msg.model_dump()
        print(f"Message model_dump includes reasoning_content: {'reasoning_content' in msg_dict}")
        print(f"Full model_dump: {msg_dict}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    print("OpenAI SDK Response Structure Debug Tool")
    print("========================================\n")
    
    all_passed = True
    
    # Run tests
    all_passed &= inspect_response_object()
    all_passed &= test_stream_chunk_structure()
    all_passed &= mock_api_response_test()
    test_raw_response_parsing()
    
    print("\n" + "="*60)
    if all_passed:
        print("✓ Debug tests completed")
    else:
        print("✗ Some debug tests failed")
    print("="*60)
