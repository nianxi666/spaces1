import sys
import os

print(f"Python: {sys.executable}")
print(f"CWD: {os.getcwd()}")
try:
    import boto3
    print("Boto3: OK")
except ImportError:
    print("Boto3: FAIL")

model_dir = "/gemini/pretrain/IndexTTS-2"
if os.path.exists(model_dir):
    print(f"Files in {model_dir}: {os.listdir(model_dir)}")
else:
    print(f"Dir {model_dir} NOT FOUND")
