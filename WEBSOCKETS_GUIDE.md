# WebSocket Spaces Guide

## Overview

WebSocket Spaces allow remote computers to connect to your website and handle inference requests without needing to expose public IP addresses or ports. This is useful for:

- Running inference on private networks
- Distributed inference across multiple machines
- No-port deployments
- Easy scaling

## How It Works

1. **Admin Setup**: Create a new "WebSocket Remote Connection" space in the admin panel
2. **Configuration**: Configure which features (prompt, audio, video, files) are enabled for this space
3. **Remote Connection**: Run `python example_websocket_app.py --host DOMAIN --spaces SPACE_NAME` on your remote computer
4. **User Interaction**: Users submit inference requests from the web interface
5. **Request Handling**: The remote app processes the request and returns results

## Setup Instructions

### Step 1: Create a WebSocket Space

1. Go to Admin Panel → Manage Spaces → Add Space
2. Select "WebSocket Remote Connection Type" as the card type
3. Fill in the space name and description
4. Configure which features are enabled:
   - **Enable Prompt Input**: Users can enter text prompts
   - **Enable Audio Upload**: Users can upload audio files
   - **Enable Video Upload**: Users can upload video files
   - **Enable File Upload**: Users can upload other file types
5. Click "Save Space"

### Step 2: Prepare Your Remote App

On your remote computer where you want to run inference:

1. Install required packages:
   ```bash
   pip install python-socketio python-engineio requests
   ```

2. Prepare your inference script:
   - The script should accept inference requests
   - It should return results in JSON format
   - See `example_websocket_app.py` for a complete template

### Step 3: Start the Remote Connection

Run the example app (or your modified version):

```bash
python example_websocket_app.py --host https://your-domain.com --spaces "MySpace"
```

Example output:
```
============================================================
WebSocket Inference App
============================================================
Host: https://your-domain.com
Space: MySpace
============================================================

[INFO] Initializing connection...
[INFO] Host: https://your-domain.com
[INFO] Space name: MySpace
[INFO] Connecting to https://your-domain.com...
[SUCCESS] Socket.IO connection established
[INFO] Sent registration for space: MySpace
[SUCCESS] Registration successful!
[INFO] Connection ID: abc123def456
[INFO] Space ID: xyz789
[INFO] Successfully connected to space "MySpace"
[INFO] Request processor started
```

The remote app is now ready to receive inference requests!

### Step 4: Users Submit Requests

1. Users visit the space page on the website
2. The page shows connection status (✓ Connected or ✗ Not Connected)
3. If connected, users can submit inference requests with:
   - Text prompts (if enabled)
   - Audio files (if enabled)
   - Video files (if enabled)
   - Other files (if enabled)
4. The request is sent to the remote app via WebSocket
5. The remote app processes and returns results
6. Results are displayed to the user

## Example Implementation

See `example_websocket_app.py` for a working example. Key components:

```python
from example_websocket_app import WebSocketApp

app = WebSocketApp(
    host="https://example.com",
    space_name="MySpace"
)
app.connect()
```

The example app will:
1. Connect to the website
2. Register with the specified space
3. Wait for inference requests
4. Process requests with simulated inference
5. Send results back to the website
6. Queue multiple requests for sequential processing

## API Protocol

### Remote App → Website

#### Registration
```json
{
  "type": "register",
  "space_name": "MySpace"
}
```

#### Inference Result
```json
{
  "type": "inference_result",
  "request_id": "uuid-here",
  "username": "user@example.com",
  "status": "completed",
  "result": {
    "text_output": "Generated result",
    "confidence": 0.95,
    "processing_time": 2.5
  }
}
```

#### Error Response
```json
{
  "type": "inference_error",
  "request_id": "uuid-here",
  "status": "failed",
  "error": "Error message"
}
```

### Website → Remote App

#### Inference Request
```json
{
  "type": "inference_request",
  "request_id": "uuid-here",
  "username": "user@example.com",
  "payload": {
    "prompt": "User's prompt",
    "timestamp": "2024-01-01T12:00:00.000Z"
  }
}
```

## Important Notes

### Unique Space Names
- Each space name must be unique
- If multiple spaces share the same name, the connection will fail
- Rename spaces to be descriptive and unique

### Connection Status
- The website shows if a remote app is connected
- Users can only submit requests if connected
- Connection is automatic when the remote app starts
- Disconnection is automatic when the remote app closes

### Request Queue
- Multiple users can submit requests simultaneously
- Requests are processed sequentially by the remote app
- The website shows queue length to users
- Requests timeout after 2 minutes if no response

### Security Considerations
- WebSocket connections are encrypted (WSS over HTTPS)
- Only authenticated users can submit requests
- Each request includes the username
- Implement authentication in your remote app if needed

## Troubleshooting

### Connection Failed
- Check that the website domain is correct and accessible
- Ensure the space name exactly matches (case-sensitive)
- Check for firewall/network issues preventing WebSocket connections
- Verify the space is configured as "WebSocket" type

### Requests Not Processing
- Check that the remote app is still connected
- Monitor the remote app console for errors
- Ensure your inference implementation is working
- Check that requests are being queued

### Requests Timing Out
- Increase processing speed in your inference code
- Check for network latency issues
- Ensure the remote app is not overloaded
- Consider load balancing across multiple instances

## Advanced Usage

### Multiple Instances

You can run multiple instances of the same space on different machines:

```bash
# Machine 1
python my_app.py --host https://example.com --spaces "MySpace"

# Machine 2
python my_app.py --host https://example.com --spaces "MySpace"
```

Note: Each instance must use a unique space name, or only one will connect successfully.

### Custom Inference Logic

Modify `example_websocket_app.py` to:
1. Load your actual ML models
2. Implement real inference instead of simulation
3. Handle specific input formats (audio, video, etc.)
4. Return structured results

Example:
```python
def simulate_inference(self, request_data):
    prompt = request_data.get("payload", {}).get("prompt", "")
    
    # Load your model
    model = load_model()
    
    # Run inference
    output = model.generate(prompt)
    
    return {
        "type": "inference_result",
        "request_id": request_data["request_id"],
        "status": "completed",
        "result": {
            "text_output": output,
            "processing_time": elapsed_time
        }
    }
```

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review example code
3. Check application logs
4. Contact support with connection details
