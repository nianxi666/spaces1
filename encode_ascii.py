import base64

with open('modified_webui.py', 'rb') as f:
    content = f.read()

b64 = base64.b64encode(content).decode('ascii')

with open('webui_upload.b64', 'w', encoding='ascii') as f:
    f.write(b64)
print("Encoded ascii.")
