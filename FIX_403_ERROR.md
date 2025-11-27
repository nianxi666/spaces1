# 🔧 Fixing 403 Error in Model Internal Thinking Feature

## Issue
Getting `[Error: API Error: 403]` when calling the chat completions API.

## Root Causes & Solutions

### 1. **System Prompt Format Issue** ✅ FIXED
**Problem:** The THINKING_SYSTEM_PROMPT had extra whitespace/newlines that could corrupt the message format.

**Fix Applied:** 
- Changed from multi-line string to single-line string
- Removed unnecessary newlines and whitespace
- Improved compatibility with OpenAI API format

```python
# Before (problematic):
THINKING_SYSTEM_PROMPT = """
You are a profound thinking assistant. 
Before answering...
"""

# After (fixed):
THINKING_SYSTEM_PROMPT = "You are a profound thinking assistant. Before answering the user's request, you must perform a detailed step-by-step analysis. Enclose your internal thought process within <thinking>...</thinking> tags. After the thinking tags, provide your final response."
```

### 2. **Authentication Issues**

If you're still getting 403 after the fix above, check:

#### A. API Key Validation
```python
# Check in admin panel or database:
db['netmind_settings']['keys']  # Should have valid API keys
```

**Action:**
1. Go to Admin Panel → Settings → NetMind Settings
2. Verify at least one API key is configured
3. Test the API key in NetMind API directly
4. If invalid, generate a new one and update

#### B. User Token Validation
```python
# Check user authentication:
db['users']['username']['api_key']  # Should exist
```

**Action:**
1. User must login to generate API key
2. Check if API key is still valid
3. Regenerate if needed in user profile

#### C. Daily Check-in Requirement
```python
# The code checks:
if user_data.get('last_check_in_date') != today_str:
    # 403 error: Need to check in
    return jsonify({'error': '您需要完成今日签到才能继续使用API'}), 403
```

**Action:**
1. User must visit profile page and click "签到" (Check-in) button
2. This must be done daily to use the API
3. Check-in resets the limit

### 3. **Rate Limiting**

```python
# Rate limit check:
allowed, retry_after = _check_netmind_rate_limit(username, max_requests, window_seconds)
if not allowed:
    return 429 (Rate Limited)  # Not 403, but similar issue
```

**Action:**
1. Check rate limit configuration in Admin Panel
2. Default: 30 requests per 60 seconds
3. Increase limits in Settings if needed
4. Wait before retrying if limit exceeded

### 4. **Thinking Feature-Specific Issues**

If 403 started after enabling thinking:

#### A. Test Without Thinking
```python
# Temporarily disable thinking feature:
db['netmind_settings']['enable_thinking'] = False

# Try the request again
# If it works, the problem is in thinking injection
```

#### B. Check Message Injection
```python
# The messages should look like:
[
  {"role": "system", "content": "You are a profound thinking assistant..."},
  {"role": "user", "content": "Hello"}
]

# NOT like:
[
  {"role": "system", "content": "\nYou are...\n"},  # ❌ Extra newlines
  {"role": "user", "content": "Hello"}
]
```

#### C. Verify Thinking Configuration
```python
# Check in database:
db['netmind_settings']['enable_thinking']  # Should be True or False

# Check is_thinking_enabled() works:
from project.netmind_config import is_thinking_enabled
is_thinking_enabled(db['netmind_settings'])  # Should return bool
```

## Debugging Checklist

- [ ] System prompt format is correct (no extra whitespace)
- [ ] API key is valid and active
- [ ] User token is valid and not expired
- [ ] User has completed daily check-in
- [ ] User is not rate-limited
- [ ] Thinking feature is enabled in settings
- [ ] Messages are properly formatted after injection
- [ ] Network connectivity to NetMind API is working
- [ ] Correct model name is being used
- [ ] User has permission to access the model

## Quick Fix Steps

1. **Apply the system prompt fix** (already done in code):
   ```bash
   # Verify the fix is applied:
   grep -n "THINKING_SYSTEM_PROMPT" project/thinking_utils.py
   # Should show single-line string, not multi-line
   ```

2. **Test with thinking disabled**:
   ```python
   db = load_db()
   db['netmind_settings']['enable_thinking'] = False
   save_db(db)
   # Try API call again
   ```

3. **Verify authentication**:
   - Login with user account
   - Go to Profile → API Settings
   - Click "Generate New Token" if needed
   - Copy new token
   - Use in API calls

4. **Check daily check-in**:
   - Visit user profile
   - Click "签到" (Check-in) button
   - Should show "您已签到" (Checked in)
   - Then try API again

5. **Check rate limiting**:
   - Admin Panel → Settings → NetMind Settings
   - Note: rate_limit_max_requests (default: 30)
   - Note: rate_limit_window_seconds (default: 60)
   - Wait if you've exceeded limit

## Verification

After applying fixes, test with:

```bash
curl -X POST http://localhost:5001/api/v1/chat/completions \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "zai-org/GLM-4.6",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": false
  }'
```

**Expected Response:** 
```json
{
  "choices": [{
    "message": {
      "content": "Response text...",
      "reasoning_content": "Thinking process..."
    }
  }]
}
```

**If still 403:**
1. Check server logs for details
2. Verify all authentication details
3. Test with thinking disabled
4. Contact NetMind API support if still failing

## Prevention

- ✅ Keep API keys safe and rotated
- ✅ Regenerate user tokens regularly
- ✅ Remind users to do daily check-in
- ✅ Monitor rate limit usage
- ✅ Keep thinking feature compatible
- ✅ Test API calls regularly

---

**Version:** 1.0  
**Fixed:** System prompt whitespace issue  
**Status:** Ready for testing  
