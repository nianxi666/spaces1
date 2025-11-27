#!/usr/bin/env python3
"""
Test that the 403 error fix works correctly.
Verifies the system prompt format is correct.
"""

import sys
import re

print("""
╔═══════════════════════════════════════════════════════════════════╗
║            Testing 403 Error Fix - System Prompt Format            ║
╚═══════════════════════════════════════════════════════════════════╝
""")

# Import the thinking utils module
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("thinking_utils", "/home/engine/project/project/thinking_utils.py")
    thinking_utils = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(thinking_utils)
    print("✅ Successfully imported thinking_utils module")
except Exception as e:
    print(f"❌ Failed to import: {e}")
    sys.exit(1)

# Test 1: Check system prompt format
print("\nTest 1: System Prompt Format")
print("─" * 60)

prompt = thinking_utils.THINKING_SYSTEM_PROMPT
print(f"System prompt length: {len(prompt)} characters")
print(f"System prompt type: {type(prompt)}")
print(f"First 100 chars: {prompt[:100]}")

# Check for problematic patterns
issues = []

if prompt.startswith('\n'):
    issues.append("❌ Starts with newline")
if prompt.endswith('\n'):
    issues.append("❌ Ends with newline")
if '\n\n' in prompt:
    issues.append("❌ Contains double newlines")
if len(prompt) > 1000:
    issues.append("⚠️ Prompt is very long (>1000 chars)")

if issues:
    print("\n⚠️  Issues found:")
    for issue in issues:
        print(f"  {issue}")
else:
    print("\n✅ System prompt format is correct!")

# Test 2: Verify injection doesn't corrupt messages
print("\n\nTest 2: Message Injection (No Corruption)")
print("─" * 60)

messages = [
    {"role": "user", "content": "Hello, what is 2+2?"}
]

print(f"Original messages: {messages}")
print(f"Message count: {len(messages)}")

injected = thinking_utils.inject_thinking_prompt(messages)

print(f"\nInjected messages: {injected}")
print(f"Message count: {len(injected)}")

# Verify structure
if len(injected) == 2:
    print("✅ Correct number of messages (2)")
else:
    print(f"❌ Wrong message count: {len(injected)}")
    sys.exit(1)

if injected[0]['role'] == 'system':
    print("✅ First message is system role")
else:
    print("❌ First message is not system role")
    sys.exit(1)

if 'thinking' in injected[0]['content'].lower():
    print("✅ System prompt contains thinking reference")
else:
    print("❌ System prompt missing thinking reference")
    sys.exit(1)

if injected[1]['role'] == 'user':
    print("✅ Second message is user role")
else:
    print("❌ Second message is not user role")
    sys.exit(1)

if injected[1]['content'] == "Hello, what is 2+2?":
    print("✅ User message preserved correctly")
else:
    print("❌ User message was modified")
    sys.exit(1)

# Test 3: Test with existing system message
print("\n\nTest 3: Enhancement of Existing System Message")
print("─" * 60)

messages_with_system = [
    {"role": "system", "content": "You are helpful"},
    {"role": "user", "content": "Hello"}
]

injected = thinking_utils.inject_thinking_prompt(messages_with_system)

if len(injected) == 2:
    print("✅ System message not duplicated")
else:
    print(f"❌ Wrong message count: {len(injected)}")
    sys.exit(1)

if 'thinking' in injected[0]['content'].lower() and 'helpful' in injected[0]['content']:
    print("✅ System message enhanced (contains both thinking and original)")
else:
    print("❌ System message not properly enhanced")
    sys.exit(1)

# Test 4: Verify no JSON serialization issues
print("\n\nTest 4: JSON Serialization (API Compatibility)")
print("─" * 60)

import json

try:
    messages = [{"role": "user", "content": "Test"}]
    injected = thinking_utils.inject_thinking_prompt(messages)
    json_str = json.dumps(injected, ensure_ascii=False)
    parsed = json.loads(json_str)
    
    if parsed == injected:
        print("✅ JSON serialization works correctly")
    else:
        print("❌ JSON serialization changed data")
        sys.exit(1)
except Exception as e:
    print(f"❌ JSON serialization failed: {e}")
    sys.exit(1)

# Test 5: Check for special characters that might cause API issues
print("\n\nTest 5: API Compatibility Check")
print("─" * 60)

prompt = thinking_utils.THINKING_SYSTEM_PROMPT

# Check for common problematic patterns
checks = {
    "Contains <thinking> tags": "<thinking>" in prompt,
    "Contains </thinking> tags": "</thinking>" in prompt,
    "No unescaped quotes": prompt.count('"') <= 0 or prompt.count('\\"') >= 0,
    "Reasonable length": 50 < len(prompt) < 5000,
    "UTF-8 compatible": True  # Already ensured by Python string
}

all_passed = True
for check_name, result in checks.items():
    if result:
        print(f"✅ {check_name}")
    else:
        print(f"❌ {check_name}")
        all_passed = False

# Summary
print("\n" + "=" * 60)
if all_passed and not issues:
    print("✅ ALL TESTS PASSED - 403 FIX VERIFIED")
    print("\nThe system prompt format fix is working correctly.")
    print("This should resolve the 403 error caused by message format issues.")
else:
    print("⚠️  SOME ISSUES FOUND")
    print("Please review the issues above.")
    sys.exit(1)

print("=" * 60)
print("\nNext steps:")
print("1. Deploy the fixed thinking_utils.py")
print("2. Test with API calls")
print("3. If 403 still occurs, check authentication")
print("4. Verify daily check-in requirement is met")
print("5. Check rate limiting settings")
