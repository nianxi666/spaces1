# WebSocket Spaces Testing Guide

This guide walks you through testing the WebSocket spaces functionality with the mock app.

## Quick Start

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt
pip install python-socketio python-engineio  # For mock_app.py
```

### Step 1: Start the Website

```bash
# Terminal 1 - Start the Flask app
python run.py
# App should be running on http://localhost:5001
```

### Step 2: Create a WebSocket Space

```bash
# Terminal 2 - Create test space
python test_websockets.py --setup-space --host http://localhost:5001
```

Output should show:
```
Creating test WebSocket space...
Host: http://localhost:5001
Admin User: admin

✓ Space created: TestSpace_1704067200

Now run the mock app with:
  python mock_app.py --host http://localhost:5001 --spaces "TestSpace_1704067200"
```

### Step 3: Start the Mock App

```bash
# Terminal 3 - Start mock inference app
python mock_app.py --host http://localhost:5001 --spaces "TestSpace_1704067200" --verbose
```

You should see output like:
```
======================================================================
  Mock WebSocket Inference App
======================================================================
  Host: http://localhost:5001
  Space: TestSpace_1704067200
  Verbose: True
======================================================================

[2024-01-08 12:00:00] [INFO] Initializing connection to http://localhost:5001
[2024-01-08 12:00:00] [INFO] Space name: TestSpace_1704067200
[2024-01-08 12:00:00] [INFO] Connecting to http://localhost:5001...
[2024-01-08 12:00:00] [✓] Socket.IO connection established
[2024-01-08 12:00:00] [INFO] Sent registration for space: TestSpace_1704067200
[2024-01-08 12:00:00] [✓] Registration successful!
[2024-01-08 12:00:00] [INFO] Connection ID: abc123def456
[2024-01-08 12:00:00] [INFO] Space ID: xyz789...
[2024-01-08 12:00:00] [INFO] Successfully connected to space "TestSpace_1704067200"
[2024-01-08 12:00:00] [INFO] Request processor started
```

### Step 4: Test via Web Interface

1. Open browser to `http://localhost:5001`
2. Login with your credentials
3. Find and open the TestSpace you created
4. You should see:
   - Status: "✓ 已连接" (Connected)
   - Queue size: 0 (showing queue size when connected)
5. Submit a test prompt in the form
6. Watch the mock app process the request
7. See the result appear on the web page

## Detailed Testing Scenarios

### Scenario 1: Single Request

1. **Setup**: Mock app connected and running
2. **Action**: Submit prompt "Generate a poem about cats"
3. **Expected**:
   - Mock app shows "[REQUEST] New inference request received"
   - Processing shows progress: "Progress: 25%", "Progress: 50%", etc.
   - Result appears within 2 minutes
   - Web page shows the generated text

**Success Criteria**:
- Request reaches mock app ✓
- Result returns to website ✓
- User sees complete result ✓

### Scenario 2: Multiple Concurrent Requests

1. **Setup**: Mock app connected
2. **Action**: Submit 3 requests rapidly from different browser tabs
3. **Expected**:
   - All 3 requests queue up
   - Mock app processes them sequentially
   - Each completes and returns results

**Success Criteria**:
- All requests received ✓
- Processing happens in order ✓
- All users get their results ✓
- No requests lost ✓

### Scenario 3: Request with Files

1. **Setup**: Space configured with audio/video enabled
2. **Action**: Submit request with audio file
3. **Expected**:
   - File data included in request payload
   - Mock app receives and logs file info
   - Result includes file processing details

**Success Criteria**:
- Files transmitted ✓
- Mock app receives them ✓
- Results indicate file processing ✓

### Scenario 4: Disconnection Recovery

1. **Setup**: Mock app connected and processing
2. **Action**: Stop mock app (Ctrl+C)
3. **Expected**:
   - Web page shows "✗ 未连接"
   - New requests fail with "remote app not connected"
   - Form becomes disabled

4. **Restart** mock app
5. **Expected**:
   - Web page shows "✓ 已连接"
   - Form becomes enabled
   - New requests work

**Success Criteria**:
- Disconnection detected quickly ✓
- Status updated correctly ✓
- Reconnection works ✓

### Scenario 5: Duplicate Space Names

1. **Setup**: Two WebSocket spaces with same name
2. **Action**: Run `mock_app.py --spaces "DuplicateName"`
3. **Expected**:
   - Connection fails
   - Mock app shows error: "Multiple spaces with name found"
   - Connection closes
   - Mock app exits

**Success Criteria**:
- Duplicate detected ✓
- Connection prevented ✓
- Clear error message ✓

## Running Automated Tests

### Test Suite 1: Basic Functionality

```bash
# Terminal 2 - Run basic tests
python test_websockets.py --host http://localhost:5001 --verbose
```

Tests included:
- User authentication (login/registration)
- WebSocket space creation
- Space details retrieval
- Connection status checking
- Request rejection when disconnected

### Test Suite 2: Load Testing

```bash
# Create script to send multiple concurrent requests
python -c "
import requests
import concurrent.futures
import time

host = 'http://localhost:5001'
space_id = 'YOUR_SPACE_ID'

def send_request(i):
    with requests.Session() as s:
        s.post(f'{host}/login', data={'username': 'testuser', 'password': 'testpass123'})
        r = s.post(f'{host}/websockets/submit/{space_id}', data={'prompt': f'Request {i}'})
        return r.json()

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    results = list(executor.map(send_request, range(10)))
    print(f'Sent {len(results)} requests')
    print(f'Successful: {sum(1 for r in results if r.get(\"success\"))}')
"
```

## Monitoring and Debugging

### Check Website Logs

```bash
# View Flask application logs
tail -f error.log

# Or check console output for development mode
# (Will show in the Terminal 1 where you ran python run.py)
```

### Check Mock App Logs

```bash
# Already visible in Terminal 3
# Or run with --verbose for extra detail:
python mock_app.py --host http://localhost:5001 --spaces "TestSpace" --verbose
```

### Database State

```bash
# Check space configuration in database
python -c "
from project.database import load_db
db = load_db()
for space_id, space in db['spaces'].items():
    if space.get('card_type') == 'websockets':
        print(f'Space: {space[\"name\"]} (ID: {space_id})')
        print(f'  Config: {space.get(\"websockets_config\")}')
"
```

### Active Connections

```bash
# Check active WebSocket connections
python -c "
from project.websocket_manager import ws_manager
print(f'Connected spaces: {ws_manager.get_connected_spaces()}')
for space_id in ws_manager.get_connected_spaces():
    queue = ws_manager.get_queue_size(space_id)
    print(f'  {space_id}: {queue} requests in queue')
"
```

## Troubleshooting

### Mock App Won't Connect

**Problem**: `ERROR Connection failed: Connection refused`

**Solutions**:
1. Check website is running: `curl http://localhost:5001` should return HTML
2. Check host URL is correct: `python mock_app.py --host http://localhost:5001`
3. Check space name matches exactly (case-sensitive)
4. Check for firewall blocking WebSocket connections

**Debug**:
```bash
# Test connection with curl
curl http://localhost:5001/admin/  # Should return admin panel

# Test with verbose logging
python mock_app.py --host http://localhost:5001 --spaces "TestSpace" --verbose
```

### Requests Don't Reach Mock App

**Problem**: Submit request but mock app doesn't receive it

**Solutions**:
1. Check mock app shows "Registration successful"
2. Check website shows "✓ 已连接" for the space
3. Check request was actually submitted (look at browser console)

**Debug**:
```bash
# Check WebSocket connections in database
python -c "
from project.websocket_manager import ws_manager
print('Connected:', ws_manager.get_connected_spaces())
"

# Run with verbose to see incoming messages
python mock_app.py --host http://localhost:5001 --spaces "TestSpace" --verbose
```

### Results Don't Return

**Problem**: Mock app processes request but result doesn't appear on website

**Solutions**:
1. Check mock app shows "[RESULT]" message
2. Check website poll is working (browser console)
3. Check request status endpoint: `curl http://localhost:5001/websockets/status?request_id=REQUEST_ID`

**Debug**:
```bash
# Check request status in database
python -c "
from project.websocket_manager import ws_manager
req = ws_manager.get_request_status('REQUEST_ID_HERE')
print(f'Status: {req}')
"
```

### Multiple Mock Apps Can't Connect Same Space

**Expected Behavior**: When you try to run two instances with the same space name, the second one will fail with duplicate error.

**Fix**: Create multiple WebSocket spaces with different names, then run:
```bash
# Terminal 3a
python mock_app.py --host http://localhost:5001 --spaces "Space1"

# Terminal 3b  
python mock_app.py --host http://localhost:5001 --spaces "Space2"
```

Each space can only have one connected instance.

## Performance Testing

### Measure Request Processing Time

The mock app includes processing time in results. Check the result JSON:
```json
{
  "result": {
    "processing_time_seconds": 2.45,
    "timestamp": "2024-01-08T12:00:00.000Z"
  }
}
```

### Queue Length

Watch mock app logs to see queue building up:
```
[REQUEST] New inference request received
  Queue size: 1
[REQUEST] New inference request received
  Queue size: 2
[REQUEST] New inference request received
  Queue size: 3
[INFO] Processing...
[RESULT] Result sent...
  Queue size: 2
```

### Concurrent Users

Use test script to simulate multiple users:
```bash
python test_websockets.py --host http://localhost:5001 --verbose
```

## Integration Testing

### Full End-to-End Test

```python
#!/usr/bin/env python3
import requests
import time
import subprocess
import threading

# 1. Setup
host = "http://localhost:5001"
space_name = f"E2ETest_{int(time.time())}"

# 2. Create space via admin
session = requests.Session()
session.post(f"{host}/login", data={'username': 'admin', 'password': 'admin123'})
r = session.post(f"{host}/admin/space/add", data={
    'name': space_name,
    'description': 'E2E Test',
    'card_type': 'websockets',
    'cover': 'default.png',
    'ws_enable_prompt': 'on'
})
assert r.status_code in [200, 302], f"Failed to create space: {r.status_code}"

# 3. Start mock app
def run_mock_app():
    subprocess.run([
        'python', 'mock_app.py',
        '--host', host,
        '--spaces', space_name
    ])

app_thread = threading.Thread(target=run_mock_app, daemon=True)
app_thread.start()
time.sleep(2)  # Wait for connection

# 4. Submit request
r = session.post(f"{host}/websockets/submit/{space_id}", data={'prompt': 'Test'})
assert r.json()['success'], f"Request failed: {r.json()}"
request_id = r.json()['request_id']

# 5. Poll for result
for i in range(60):  # 60 seconds timeout
    r = session.get(f"{host}/websockets/status?request_id={request_id}")
    data = r.json()
    if data['status'] == 'completed':
        print(f"✓ Test passed! Result: {data['result']}")
        break
    time.sleep(1)
else:
    print("✗ Test failed: Timeout waiting for result")
```

## Next Steps

After successful testing:

1. **Deploy Mock App**: Run on production servers
2. **Monitor Performance**: Check logs and response times
3. **Scale Testing**: Test with multiple concurrent users
4. **Error Handling**: Verify graceful degradation
5. **Documentation**: Update deployment docs with WebSocket setup

## Support

For issues:
1. Check WEBSOCKETS_GUIDE.md for architecture details
2. Review logs in both website and mock app
3. Test individual components separately
4. Use --verbose flag for detailed debugging

