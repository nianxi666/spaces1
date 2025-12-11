import os
import sys

try:
    with open('webui.py', 'r', encoding='utf-8') as f:
        code = f.read()
except UnicodeDecodeError:
    with open('webui.py', 'r', encoding='latin-1') as f:
        code = f.read()

imports = """
import os
try:
    import boto3
    from botocore.exceptions import NoCredentialsError
except ImportError:
    boto3 = None
    print("Boto3 not found")

S3_ENDPOINT_URL = "https://s3.tebi.io"
S3_ACCESS_KEY_ID = "YxWVUUhcFT6lGi9c"
S3_SECRET_ACCESS_KEY = "UkN7jF9L0P8XAqPcGOdjl3wi5SQ1d87st80fqC4A"
S3_BUCKET_NAME = "driver"

def upload_to_s3(file_path):
    if not boto3: return
    try:
        s3 = boto3.client('s3', endpoint_url=S3_ENDPOINT_URL, aws_access_key_id=S3_ACCESS_KEY_ID, aws_secret_access_key=S3_SECRET_ACCESS_KEY, region_name='auto')
        name = os.path.basename(file_path)
        s3.upload_file(file_path, S3_BUCKET_NAME, name)
        print(f"Uploaded {name}")
    except Exception as e:
        print(f"Upload fail: {e}")
"""

if "S3_ENDPOINT_URL" not in code:
    code = imports + "\n" + code

# Insert call in gen_single
if "upload_to_s3(output)" not in code:
    target = "return gr.update(value=output,visible=True)"
    replacement = "upload_to_s3(output)\n    return gr.update(value=output,visible=True)"
    code = code.replace(target, replacement)

# Insert api_name
if 'api_name="generate"' not in code and "api_name='generate'" not in code:
    target = "outputs=[output_audio])"
    replacement = "outputs=[output_audio], api_name='generate')"
    code = code.replace(target, replacement)

with open('webui.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("Patched webui.py")
