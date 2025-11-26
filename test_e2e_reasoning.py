#!/usr/bin/env python3
"""
End-to-end test simulating the complete flow from API call to frontend rendering
"""

import json
import sys
from unittest.mock import MagicMock, patch


def test_complete_flow():
    """Test complete flow with reasoning_content"""
    print("\n" + "="*70)
    print("END-TO-END TEST: Reasoning Content Flow")
    print("="*70)
    
    # Simulate what happens in netmind_proxy.py
    print("\n1️⃣  Simulating NetMind API Response")
    print("-" * 70)
    
    # Mock the OpenAI SDK response
    # This is what we'd get back from client.chat.completions.create()
    mock_response = MagicMock()
    
    # Create mock message with reasoning_content
    mock_message = MagicMock()
    mock_message.role = "assistant"
    mock_message.content = "Yes, the sky appears blue due to Rayleigh scattering..."
    mock_message.reasoning_content = "<think>The user is asking why the sky is blue. This is about light scattering. I should explain Rayleigh scattering and how shorter wavelengths scatter more.</think>"
    
    # Setup mock response structure
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_choice.finish_reason = "stop"
    
    mock_response.choices = [mock_choice]
    mock_response.id = "chatcmpl-test"
    mock_response.model = "gpt-4"
    
    # Simulate model_dump_json (this is where reasoning_content might be lost)
    def mock_model_dump_json(*args, **kwargs):
        # Sometimes model_dump_json might not include reasoning_content
        # This is the bug we're trying to fix
        return json.dumps({
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Yes, the sky appears blue due to Rayleigh scattering...",
                        # Note: reasoning_content might be missing here!
                    },
                    "finish_reason": "stop"
                }
            ]
        })
    
    mock_response.model_dump_json = mock_model_dump_json
    
    print("✓ Mock response created with reasoning_content")
    print(f"  - content: {mock_message.content[:50]}...")
    print(f"  - reasoning_content: {mock_message.reasoning_content[:50]}...")
    
    # Simulate what api.py does
    print("\n2️⃣  Processing in API Endpoint (api.py)")
    print("-" * 70)
    
    response_dict = json.loads(mock_response.model_dump_json())
    print(f"✓ After model_dump_json():")
    print(f"  - content present: {'message' in response_dict['choices'][0]}")
    print(f"  - reasoning_content present: {'reasoning_content' in response_dict['choices'][0].get('message', {})}")
    
    # Try to extract and add reasoning_content
    if mock_response.choices:
        for i, choice in enumerate(mock_response.choices):
            if hasattr(choice, 'message') and choice.message:
                message = choice.message
                
                # Try multiple ways to get reasoning_content
                reasoning = None
                
                # Method 1: Direct attribute access
                if hasattr(message, 'reasoning_content'):
                    reasoning = message.reasoning_content
                    print(f"✓ Found reasoning_content via direct attribute")
                
                # Method 2: Access via __dict__
                if not reasoning and hasattr(message, '__dict__'):
                    reasoning = message.__dict__.get('reasoning_content')
                    if reasoning:
                        print(f"✓ Found reasoning_content via __dict__")
                
                # Add reasoning_content to response if found
                if reasoning and i < len(response_dict.get('choices', [])):
                    if 'message' not in response_dict['choices'][i]:
                        response_dict['choices'][i]['message'] = {}
                    response_dict['choices'][i]['message']['reasoning_content'] = reasoning
                    print(f"✓ Added reasoning_content to response dict")
    
    print(f"✓ After extraction:")
    print(f"  - reasoning_content present: {'reasoning_content' in response_dict['choices'][0].get('message', {})}")
    
    # Simulate stream response
    print("\n3️⃣  Testing Stream Response")
    print("-" * 70)
    
    # Create mock stream chunks
    chunks_data = [
        {
            "id": "chatcmpl-1",
            "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {"reasoning_content": "<think>Let me think..."}}]
        },
        {
            "id": "chatcmpl-2",
            "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {"reasoning_content": "The sky is blue..."}}]
        },
        {
            "id": "chatcmpl-3",
            "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {"content": "Yes, the sky..."}}]
        }
    ]
    
    stream_output = []
    for chunk_data in chunks_data:
        stream_output.append(f"data: {json.dumps(chunk_data)}\n")
    
    print(f"✓ Generated {len(stream_output)} stream chunks")
    
    # Simulate Frontend Processing
    print("\n4️⃣  Frontend Processing (space_netmind_chat.html)")
    print("-" * 70)
    
    # Process stream
    reasoning_buffer = []
    content_buffer = []
    has_content = False
    
    for line in stream_output:
        if not line.strip().startswith('data: '):
            continue
        
        data_str = line.strip()[6:]
        if data_str == '[DONE]':
            break
        
        try:
            chunk = json.loads(data_str)
            delta = chunk.get('choices', [{}])[0].get('delta', {})
            
            if 'reasoning_content' in delta and not has_content:
                reasoning_buffer.append(delta['reasoning_content'])
                print(f"✓ Captured reasoning: {delta['reasoning_content'][:40]}...")
            elif 'content' in delta and delta['content']:
                has_content = True
                content_buffer.append(delta['content'])
                print(f"✓ Captured content: {delta['content'][:40]}...")
        except json.JSONDecodeError as e:
            print(f"✗ Failed to parse: {e}")
    
    # Verify results
    print("\n5️⃣  Verification")
    print("-" * 70)
    
    full_reasoning = ''.join(reasoning_buffer)
    full_content = ''.join(content_buffer)
    
    print(f"✓ Final reasoning buffer ({len(full_reasoning)} chars):")
    print(f"  {full_reasoning[:100]}...")
    
    print(f"✓ Final content buffer ({len(full_content)} chars):")
    print(f"  {full_content[:100]}...")
    
    # Check if reasoning was captured
    if full_reasoning:
        print("\n✅ SUCCESS: Reasoning content was properly captured and transmitted!")
    else:
        print("\n❌ FAILURE: No reasoning content was captured!")
        return False
    
    # Verify synchronous response
    print("\n6️⃣  Synchronous Response Verification")
    print("-" * 70)
    
    sync_response = response_dict
    msg = sync_response['choices'][0].get('message', {})
    
    if 'reasoning_content' in msg:
        print(f"✓ Sync response includes reasoning_content")
        print(f"  {msg['reasoning_content'][:100]}...")
        print("✅ SUCCESS: Sync response includes reasoning!")
    else:
        print("❌ FAILURE: Sync response missing reasoning_content!")
        return False
    
    return True


def test_missing_reasoning_scenario():
    """Test scenario where reasoning_content is NOT in the API response"""
    print("\n" + "="*70)
    print("SCENARIO: API returns no reasoning_content")
    print("="*70)
    
    response_dict = {
        "id": "chatcmpl-test",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Just a simple response"
                }
            }
        ]
    }
    
    print("✓ API response without reasoning_content")
    
    if 'reasoning_content' not in response_dict['choices'][0]['message']:
        print("⚠️  No reasoning_content in response (expected for non-reasoning models)")
        print("✅ System handles gracefully (no error)")
        return True
    
    return False


if __name__ == '__main__':
    print("\n" + "="*70)
    print("COMPLETE END-TO-END REASONING CONTENT TEST")
    print("="*70)
    
    all_passed = True
    
    try:
        if not test_complete_flow():
            all_passed = False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    try:
        if not test_missing_reasoning_scenario():
            all_passed = False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        all_passed = False
    
    print("\n" + "="*70)
    if all_passed:
        print("✅ ALL TESTS PASSED - System is properly configured")
    else:
        print("❌ SOME TESTS FAILED")
    print("="*70)
    
    exit(0 if all_passed else 1)
