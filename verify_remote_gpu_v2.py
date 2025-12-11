import requests
import time

url = "http://direct.virtaicloud.com:21564/"

print(f"Checking root {url}...")
try:
    response = requests.get(url, timeout=10)
    print(f"Root Status: {response.status_code}")
except Exception as e:
    print(f"Root Error: {e}")

api_url = "http://direct.virtaicloud.com:21564/run/generate"
# Updated payload based on Gradio API
payload = {
    "data": [
        0, 
        "examples/sample_prompt.wav", 
        "Test text", 
        None, 
        1.0, 
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 
        "", 
        False, 
        120, 
        True, 0.8, 30, 0.8, 0.0, 3, 10.0, 1500
    ]
}

print(f"Sending POST to {api_url}...")
try:
    response = requests.post(api_url, json=payload, timeout=300)
    print(f"API Status: {response.status_code}")
    print(f"Response: {response.text[:200]}")
except Exception as e:
    print(f"API Error: {e}")

call_url = "http://direct.virtaicloud.com:21564/call/generate"
print(f"Sending POST to {call_url}...")
try:
    response = requests.post(call_url, json=payload, timeout=300)
    print(f"Call API Status: {response.status_code}")
    print(f"Call Response: {response.text[:200]}")
except Exception as e:
    print(f"Call API Error: {e}")

info_url = "http://direct.virtaicloud.com:21564/info"
print(f"Checking info {info_url}...")
try:
    response = requests.get(info_url, timeout=10)
    print(f"Info Status: {response.status_code}")
    print(f"Info Response: {response.text[:500]}")
except Exception as e:
    print(f"Info Error: {e}")
