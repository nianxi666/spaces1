import base64
import os

try:
    # Read as bytes to handle potential encoding issues or just read as text with utf-16
    with open('webui.b64', 'r', encoding='utf-16') as f:
        content = f.read().strip()
    
    # It might contain the SSH banner or password prompt garbage at start/end if not clean
    # But usually > captures stdout. 
    # However, ssh might have outputted CR/LF
    
    # clean up non-base64 chars if any?
    # actually, let's just try to decode.
    decoded = base64.b64decode(content)
    with open('temp_webui.py', 'wb') as f:
        f.write(decoded)
    print("Success")
except Exception as e:
    print(f"Error: {e}")
