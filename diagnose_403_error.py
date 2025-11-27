#!/usr/bin/env python3
"""
Diagnostic script to identify 403 error causes.
"""

import sys
import json

print("""
╔═══════════════════════════════════════════════════════════════════╗
║               API 403 ERROR DIAGNOSTIC TOOL                       ║
╚═══════════════════════════════════════════════════════════════════╝

Possible Causes of 403 Error:
""")

causes = [
    {
        "number": 1,
        "cause": "Invalid or Expired API Key",
        "description": "The NetMind API key in settings is invalid or has expired",
        "solution": [
            "1. Check netmind_settings in database",
            "2. Verify API key is valid",
            "3. Generate new API key if needed",
            "4. Restart application"
        ]
    },
    {
        "number": 2,
        "cause": "User Token Expired",
        "description": "The user's authentication token has expired",
        "solution": [
            "1. User needs to re-login",
            "2. Get a new API token",
            "3. Try the request again"
        ]
    },
    {
        "number": 3,
        "cause": "Insufficient Permissions",
        "description": "User doesn't have permission to access the model or endpoint",
        "solution": [
            "1. Check user permissions in database",
            "2. Verify user has access to the model",
            "3. Check rate limiting settings",
            "4. Verify daily check-in requirement is met"
        ]
    },
    {
        "number": 4,
        "cause": "Model Not Available",
        "description": "The requested model is not available or not configured",
        "solution": [
            "1. Verify model exists in NetMind",
            "2. Check if model alias is correctly configured",
            "3. Try with a different model",
            "4. Check server logs for more details"
        ]
    },
    {
        "number": 5,
        "cause": "Rate Limit Exceeded",
        "description": "User has exceeded their rate limit",
        "solution": [
            "1. Check rate limit settings",
            "2. Wait before making another request",
            "3. Check user's recent request history",
            "4. Increase rate limit if needed"
        ]
    },
    {
        "number": 6,
        "cause": "Thinking Feature Issue",
        "description": "Problem with injected thinking system prompt",
        "solution": [
            "1. Check if thinking feature is enabled",
            "2. Verify system prompt injection works",
            "3. Test with thinking disabled",
            "4. Check message format"
        ]
    }
]

for item in causes:
    print(f"\n{item['number']}. {item['cause']}")
    print(f"   └─ {item['description']}")
    print(f"   └─ Solutions:")
    for sol in item['solution']:
        print(f"      └─ {sol}")

print("""

DEBUGGING STEPS:
═════════════════════════════════════════════════════════════════════

Step 1: Check the exact error message
   Look for the full error details in:
   - Server logs
   - Network response
   - Client console

Step 2: Check database configuration
   - Verify netmind_settings are correct
   - Check API keys are valid
   - Verify user has permissions

Step 3: Test basic connectivity
   - Try API with valid credentials
   - Test without thinking feature
   - Check network connectivity

Step 4: Check thinking feature integration
   - Verify inject_thinking_prompt() is working
   - Check system prompt format
   - Verify no errors in message injection

SPECIFIC TO THINKING FEATURE:
═════════════════════════════════════════════════════════════════════

If the 403 error started after implementing thinking feature:

1. ✓ Check that inject_thinking_prompt() doesn't corrupt messages
2. ✓ Verify thinking system prompt format is correct
3. ✓ Test with thinking disabled: 
   - Set db['netmind_settings']['enable_thinking'] = False
   - Try the request again
   - If it works, the issue is in thinking injection
4. ✓ Check message format after injection
5. ✓ Verify no extra fields are added to messages

QUICK TEST:
═════════════════════════════════════════════════════════════════════

Try this request with thinking DISABLED:

POST /api/v1/chat/completions
Authorization: Bearer <your_token>
Content-Type: application/json

{
  "model": "zai-org/GLM-4.6",
  "messages": [{"role": "user", "content": "Hello"}],
  "stream": false
}

If this works, the issue is likely in the thinking feature.
If this also returns 403, the issue is in authentication/permissions.

═════════════════════════════════════════════════════════════════════

NEXT STEPS:
═════════════════════════════════════════════════════════════════════

1. Identify which cause matches your error
2. Apply the suggested solutions
3. Test again
4. If still not working, collect these details:
   - Full error message
   - Request details (model, user, etc.)
   - Database configuration
   - Network response headers
5. Check server logs for more context
""")
