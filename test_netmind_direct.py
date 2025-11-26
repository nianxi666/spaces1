#!/usr/bin/env python3
"""
Direct test of NetMind API to see what it actually returns
This helps identify if the issue is with API response or our code
"""

import json
import sys

def test_netmind_api():
    """Test NetMind API directly using OpenAI SDK"""
    print("\n" + "="*70)
    print("Testing NetMind API Directly")
    print("="*70)
    
    try:
        from openai import OpenAI
    except ImportError:
        print("❌ OpenAI SDK not installed")
        print("Install with: pip install openai")
        return False
    
    # Get configuration
    api_key = input("\n📝 Enter NetMind API Key: ").strip()
    base_url = input("📝 Enter NetMind Base URL (default: https://api.netmind.ai/inference-api/openai/v1): ").strip()
    
    if not base_url:
        base_url = "https://api.netmind.ai/inference-api/openai/v1"
    
    model = input("📝 Enter Model (default: deepseek-ai/DeepSeek-R1): ").strip()
    if not model:
        model = "deepseek-ai/DeepSeek-R1"
    
    if not api_key:
        print("❌ API key required")
        return False
    
    print(f"\n🔗 Connecting to:")
    print(f"  Base URL: {base_url}")
    print(f"  Model: {model}")
    
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        print("\n📤 Sending request...")
        
        # Test 1: Streaming
        print("\n" + "-"*70)
        print("TEST 1: Streaming Response")
        print("-"*70)
        
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Why is the sky blue? Be brief."}],
            stream=True,
            max_tokens=500
        )
        
        chunk_count = 0
        has_reasoning = False
        all_deltas = []
        
        for chunk in response:
            chunk_count += 1
            if chunk_count <= 5:
                print(f"\nChunk {chunk_count}:")
                
                # Check what's in the choice
                if hasattr(chunk, 'choices') and chunk.choices:
                    choice = chunk.choices[0]
                    print(f"  Choice attributes: {[a for a in dir(choice) if not a.startswith('_')][:10]}")
                    
                    if hasattr(choice, 'delta'):
                        delta = choice.delta
                        print(f"  Delta type: {type(delta)}")
                        print(f"  Delta attributes: {[a for a in dir(delta) if not a.startswith('_')]}")
                        
                        # Try to get content
                        if hasattr(delta, 'content'):
                            print(f"  Delta.content: {delta.content}")
                        
                        # Try to get reasoning_content
                        if hasattr(delta, 'reasoning_content'):
                            print(f"  ✓ Delta.reasoning_content: {delta.reasoning_content[:50] if delta.reasoning_content else 'None'}")
                            has_reasoning = True
                        else:
                            print(f"  ✗ No reasoning_content attribute")
                        
                        # Check __dict__
                        if hasattr(delta, '__dict__'):
                            print(f"  Delta.__dict__ keys: {delta.__dict__.keys()}")
                            if 'reasoning_content' in delta.__dict__:
                                print(f"  ✓ Found reasoning_content in __dict__")
                                has_reasoning = True
        
        print(f"\n✓ Received {chunk_count} chunks")
        print(f"  Reasoning found in stream: {'Yes' if has_reasoning else 'No'}")
        
        # Test 2: Non-streaming
        print("\n" + "-"*70)
        print("TEST 2: Non-Streaming Response")
        print("-"*70)
        
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Why is grass green? Be brief."}],
            stream=False,
            max_tokens=500
        )
        
        print(f"\nResponse type: {type(response)}")
        print(f"Response attributes: {[a for a in dir(response) if not a.startswith('_')][:10]}")
        
        if hasattr(response, 'choices') and response.choices:
            choice = response.choices[0]
            if hasattr(choice, 'message'):
                message = choice.message
                print(f"\nMessage type: {type(message)}")
                print(f"Message attributes: {[a for a in dir(message) if not a.startswith('_')]}")
                
                # Check content
                if hasattr(message, 'content'):
                    print(f"\n✓ message.content: {message.content[:100] if message.content else 'None'}")
                
                # Check reasoning_content
                if hasattr(message, 'reasoning_content'):
                    print(f"✓ message.reasoning_content: {message.reasoning_content[:100] if message.reasoning_content else 'None'}")
                else:
                    print(f"✗ No reasoning_content attribute")
                
                # Check __dict__
                if hasattr(message, '__dict__'):
                    print(f"\nmessage.__dict__ keys: {message.__dict__.keys()}")
                    if 'reasoning_content' in message.__dict__:
                        print(f"✓ Found reasoning_content in __dict__: {message.__dict__['reasoning_content'][:50]}")
                
                # Try model_dump
                if hasattr(message, 'model_dump'):
                    try:
                        dumped = message.model_dump()
                        print(f"\nmodel_dump() keys: {dumped.keys()}")
                        if 'reasoning_content' in dumped:
                            print(f"✓ Found reasoning_content in model_dump: {dumped['reasoning_content'][:50]}")
                    except Exception as e:
                        print(f"Error calling model_dump: {e}")
        
        # Test 3: JSON Response
        print("\n" + "-"*70)
        print("TEST 3: Full JSON Response")
        print("-"*70)
        
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "1+1=?"}],
            stream=False,
            max_tokens=100
        )
        
        # Convert to JSON and back
        response_json = response.model_dump_json()
        print(f"\nmodel_dump_json():")
        print(json.dumps(json.loads(response_json), indent=2)[:500] + "...")
        
        parsed = json.loads(response_json)
        if 'reasoning_content' in str(parsed):
            print("\n✓ reasoning_content found in JSON response")
        else:
            print("\n✗ reasoning_content NOT found in JSON response")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    print("\n" + "="*70)
    print("NetMind API Direct Test")
    print("="*70)
    print("\nThis script tests the NetMind API directly to see what it returns")
    print("and help identify why reasoning_content might not be appearing.")
    
    success = test_netmind_api()
    
    print("\n" + "="*70)
    if success:
        print("✅ Test completed - Check output above for reasoning_content presence")
    else:
        print("❌ Test failed")
    print("="*70)
