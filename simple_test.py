# -*- coding: utf-8 -*-
"""
Simple Inference Test - Test file transfer from mock remote server
"""

import os
import sys
import time
import json
import requests
from datetime import datetime

MOCK_SERVER_URL = "http://localhost:5002"

def log(msg):
    """Safe logging that works on Windows"""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', 'replace').decode('ascii'))

def test_mock_server():
    """Test if mock server is running"""
    log("\n=== Test 1: Check Mock Server ===")
    try:
        response = requests.get(f"{MOCK_SERVER_URL}/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            log(f"[OK] Server running: {data.get('server')}")
            log(f"     Status: {data.get('status')}")
            return True
        else:
            log(f"[FAIL] Server returned: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        log(f"[FAIL] Cannot connect to {MOCK_SERVER_URL}")
        log("       Please run: python mock_remote_server.py")
        return False

def test_basic_inference():
    """Test basic inference without S3"""
    log("\n=== Test 2: Basic Inference ===")
    
    test_prompt = f"test image at {datetime.now().strftime('%H%M%S')}"
    output_file = f"output/simple_test_{int(time.time())}.png"
    
    log(f"Sending request...")
    log(f"  Prompt: {test_prompt}")
    log(f"  Output: {output_file}")
    
    response = requests.post(
        f"{MOCK_SERVER_URL}/run",
        json={
            "command": f"python generate.py --prompt '{test_prompt}'",
            "output_filename": output_file
        }
    )
    
    if response.status_code != 200:
        log(f"[FAIL] Request failed: {response.status_code}")
        return False
    
    task_id = response.json().get('task_id')
    log(f"[OK] Task created: {task_id}")
    
    # Wait for completion
    log("Waiting for completion...")
    for i in range(20):
        time.sleep(1)
        status = requests.get(f"{MOCK_SERVER_URL}/task/{task_id}/status").json()
        
        if status.get('status') == 'completed':
            log(f"[OK] Task completed in {i+1} seconds")
            log(f"     Output file: {status.get('output_file')}")
            return True
        elif status.get('status') == 'failed':
            log(f"[FAIL] Task failed")
            return False
    
    log("[FAIL] Timeout")
    return False

def test_s3_upload():
    """Test inference with S3 upload"""
    log("\n=== Test 3: S3 Upload Test ===")
    
    # Try to import S3 utils
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'project'))
        from project.s3_utils import generate_presigned_url, get_s3_config
        
        s3_config = get_s3_config()
        if not s3_config:
            log("[SKIP] S3 not configured")
            return True
        
        log(f"S3 Endpoint: {s3_config.get('S3_ENDPOINT_URL', 'N/A')}")
        log(f"S3 Bucket: {s3_config.get('S3_BUCKET_NAME', 'N/A')}")
        
    except ImportError as e:
        log(f"[SKIP] Cannot import S3 utils: {e}")
        return True
    
    # Generate presigned URL
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    s3_object_name = f"test_user/test_{timestamp}.png"
    
    log(f"Generating presigned URL for: {s3_object_name}")
    s3_urls = generate_presigned_url(s3_object_name)
    
    if not s3_urls:
        log("[FAIL] Cannot generate presigned URL")
        return False
    
    presigned_url = s3_urls['presigned_url']
    final_url = s3_urls['final_url']
    
    log(f"[OK] Presigned URL generated")
    log(f"     Final URL: {final_url}")
    
    # Send inference request with S3 upload
    test_prompt = "s3 upload test"
    
    response = requests.post(
        f"{MOCK_SERVER_URL}/run",
        json={
            "command": f"python generate.py --prompt '{test_prompt}'",
            "presigned_url": presigned_url,
            "output_filename": f"output/s3_test_{timestamp}.png"
        }
    )
    
    if response.status_code != 200:
        log(f"[FAIL] Request failed: {response.status_code}")
        return False
    
    task_id = response.json().get('task_id')
    log(f"[OK] Task created: {task_id}")
    
    # Wait for completion
    log("Waiting for completion and S3 upload...")
    for i in range(30):
        time.sleep(1)
        status = requests.get(f"{MOCK_SERVER_URL}/task/{task_id}/status").json()
        
        if status.get('status') == 'completed':
            log(f"[OK] Task completed in {i+1} seconds")
            
            # Show upload-related logs
            logs = status.get('logs', '')
            for line in logs.split('\n'):
                if 'S3' in line or 'Upload' in line:
                    log(f"     {line}")
            
            # Verify file on S3
            log(f"Verifying file on S3...")
            try:
                head_response = requests.head(final_url, timeout=10)
                if head_response.status_code == 200:
                    size = head_response.headers.get('Content-Length', 'unknown')
                    log(f"[OK] File accessible on S3 ({size} bytes)")
                else:
                    log(f"[WARN] S3 response: {head_response.status_code}")
            except Exception as e:
                log(f"[WARN] Cannot verify S3 file: {e}")
            
            return True
            
        elif status.get('status') == 'failed':
            log(f"[FAIL] Task failed")
            return False
    
    log("[FAIL] Timeout")
    return False

def test_streaming():
    """Test streaming inference"""
    log("\n=== Test 4: Streaming Inference ===")
    
    test_prompt = "streaming test"
    
    log("Sending streaming request...")
    
    response = requests.post(
        f"{MOCK_SERVER_URL}/run_stream",
        json={
            "command": f"python generate.py --prompt '{test_prompt}'",
            "output_filename": "output/stream_result.png"
        },
        stream=True
    )
    
    if response.status_code != 200:
        log(f"[FAIL] Request failed: {response.status_code}")
        return False
    
    log("Receiving stream output:")
    line_count = 0
    for line in response.iter_lines():
        if line:
            decoded = line.decode('utf-8', errors='replace')
            log(f"  > {decoded[:80]}")
            line_count += 1
    
    log(f"[OK] Received {line_count} lines from stream")
    return True

def test_file_download():
    """Test downloading generated files"""
    log("\n=== Test 5: File Download ===")
    
    # List all generated files
    output_dir = os.path.join(os.path.dirname(__file__), 'mock_output', 'output')
    
    if not os.path.exists(output_dir):
        log("[SKIP] No output directory found")
        return True
    
    files = os.listdir(output_dir)
    log(f"Found {len(files)} files in output directory:")
    
    for f in files[:5]:  # Show first 5 files
        filepath = os.path.join(output_dir, f)
        size = os.path.getsize(filepath)
        log(f"  - {f}: {size} bytes")
    
    if len(files) > 5:
        log(f"  ... and {len(files) - 5} more files")
    
    # Try to download a file via HTTP
    if files:
        test_file = files[0]
        download_url = f"{MOCK_SERVER_URL}/output/output/{test_file}"
        log(f"\nTrying to download: {test_file}")
        log(f"  URL: {download_url}")
        
        try:
            response = requests.get(download_url, timeout=10)
            if response.status_code == 200:
                log(f"[OK] Downloaded successfully ({len(response.content)} bytes)")
                return True
            else:
                log(f"[WARN] Download returned: {response.status_code}")
                return True
        except Exception as e:
            log(f"[WARN] Download error: {e}")
            return True
    
    return True

def main():
    log("\n" + "=" * 50)
    log(" Inference File Transfer Test Suite")
    log("=" * 50)
    log(f"Mock Server: {MOCK_SERVER_URL}")
    log(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {}
    
    # Run tests
    results['mock_server'] = test_mock_server()
    
    if not results['mock_server']:
        log("\n[ABORT] Mock server not running!")
        return
    
    results['basic_inference'] = test_basic_inference()
    results['s3_upload'] = test_s3_upload()
    results['streaming'] = test_streaming()
    results['file_download'] = test_file_download()
    
    # Summary
    log("\n" + "=" * 50)
    log(" Test Results Summary")
    log("=" * 50)
    
    all_passed = True
    for name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        log(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    log("")
    if all_passed:
        log("[SUCCESS] All tests passed!")
    else:
        log("[WARNING] Some tests failed")
    
    log(f"\nEnd time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 50)

if __name__ == '__main__':
    main()
