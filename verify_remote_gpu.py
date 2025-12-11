import requests
import json
import time

url = "http://direct.virtaicloud.com:21564/run/generate"
# Payload with 24 args matching the signature I gathered
payload = {
    "data": [
        0, # emo_control_method
        "examples/sample_prompt.wav", # prompt_audio (assuming this path exists inside container/workdir)
        "Testing S3 upload functionality.", # input_text_single
        None, # emo_upload
        1.0, # emo_weight
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, # vec1-8
        "", # emo_text
        False, # emo_random
        120, # max_text_tokens
        True, 0.8, 30, 0.8, 0.0, 3, 10.0, 1500 # advanced
    ]
}

print(f"Sending request to {url}...")
try:
    response = requests.post(url, json=payload, timeout=300)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    if response.status_code == 200:
        print("Success!")
    else:
        print("Failed.")
except Exception as e:
    print(f"Exception: {e}")
