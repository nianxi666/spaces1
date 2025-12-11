"""
S3 Connection Test Script for Tebi Cloud
Tests connection, upload, list, and download functionality
"""

import boto3
from botocore.exceptions import NoCredentialsError, ClientError
import json
import os
import tempfile
from datetime import datetime

# Load S3 configuration
with open('s3_config.json', 'r') as f:
    s3_config = json.load(f)

# Initialize S3 client
s3_client = boto3.client(
    's3',
    endpoint_url=s3_config['S3_ENDPOINT_URL'],
    aws_access_key_id=s3_config['S3_ACCESS_KEY_ID'],
    aws_secret_access_key=s3_config['S3_SECRET_ACCESS_KEY'],
    region_name='auto'
)

bucket_name = s3_config['S3_BUCKET_NAME']

print("=" * 60)
print("S3 Connection Test - Tebi Cloud")
print("=" * 60)
print(f"\nEndpoint: {s3_config['S3_ENDPOINT_URL']}")
print(f"Bucket: {bucket_name}")
print(f"Access Key: {s3_config['S3_ACCESS_KEY_ID'][:8]}...")
print("\n" + "=" * 60)

# Test 1: List existing objects
print("\n📋 Test 1: Listing existing objects in bucket...")
try:
    response = s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=10)
    if 'Contents' in response:
        print(f"✅ Success! Found {len(response['Contents'])} objects (showing first 10):")
        for item in response['Contents'][:10]:
            size_mb = item['Size'] / (1024 * 1024)
            print(f"   - {item['Key']} ({size_mb:.2f} MB)")
    else:
        print("✅ Success! Bucket is empty.")
except ClientError as e:
    print(f"❌ Failed: {e}")
    exit(1)

# Test 2: Upload a test file
print("\n📤 Test 2: Uploading a test file...")
try:
    # Create a temporary test file
    test_content = f"Test file created at {datetime.now().isoformat()}\n"
    test_content += "This is a test upload from the remote inference system.\n"
    test_content += "If you can read this, the S3 connection is working!\n"
    
    test_key = f"test/connection_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    s3_client.put_object(
        Bucket=bucket_name,
        Key=test_key,
        Body=test_content.encode('utf-8'),
        ContentType='text/plain'
    )
    
    print(f"✅ Success! Uploaded: {test_key}")
    
    # Generate public URL
    public_url = f"{s3_config['S3_ENDPOINT_URL']}/{bucket_name}/{test_key}"
    print(f"   Public URL: {public_url}")
    
except ClientError as e:
    print(f"❌ Failed: {e}")
    exit(1)

# Test 3: Download the file we just uploaded
print("\n📥 Test 3: Downloading the test file...")
try:
    response = s3_client.get_object(Bucket=bucket_name, Key=test_key)
    downloaded_content = response['Body'].read().decode('utf-8')
    
    print(f"✅ Success! Downloaded content:")
    print(f"   {downloaded_content.strip()}")
    
except ClientError as e:
    print(f"❌ Failed: {e}")
    exit(1)

# Test 4: Generate presigned URL
print("\n🔗 Test 4: Generating presigned upload URL...")
try:
    presigned_url = s3_client.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': bucket_name,
            'Key': f"test/presigned_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        },
        ExpiresIn=3600,
        HttpMethod='PUT'
    )
    
    print(f"✅ Success! Generated presigned URL (expires in 1 hour)")
    print(f"   URL length: {len(presigned_url)} characters")
    
except ClientError as e:
    print(f"❌ Failed: {e}")
    exit(1)

# Test 5: Get bucket size and object count
print("\n📊 Test 5: Getting bucket statistics...")
try:
    total_size = 0
    total_objects = 0
    
    paginator = s3_client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=bucket_name)
    
    for page in pages:
        if 'Contents' in page:
            for obj in page['Contents']:
                total_size += obj['Size']
                total_objects += 1
    
    size_mb = total_size / (1024 * 1024)
    size_gb = total_size / (1024 * 1024 * 1024)
    
    print(f"✅ Success! Bucket statistics:")
    print(f"   Total objects: {total_objects}")
    print(f"   Total size: {size_mb:.2f} MB ({size_gb:.3f} GB)")
    
except ClientError as e:
    print(f"❌ Failed: {e}")
    exit(1)

# Test 6: Test user-specific folder structure
print("\n📁 Test 6: Testing user folder structure...")
try:
    test_user = "testuser"
    test_user_file = f"{test_user}/test_image_{datetime.now().strftime('%Y%m%d%H%M')}.txt"
    
    s3_client.put_object(
        Bucket=bucket_name,
        Key=test_user_file,
        Body=b"This is a test user file",
        ContentType='text/plain'
    )
    
    print(f"✅ Success! Created user folder: {test_user}/")
    print(f"   File: {test_user_file}")
    
    # List files for this user
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=f"{test_user}/")
    if 'Contents' in response:
        print(f"   Found {len(response['Contents'])} file(s) for {test_user}")
    
except ClientError as e:
    print(f"❌ Failed: {e}")
    exit(1)

print("\n" + "=" * 60)
print("🎉 All tests passed successfully!")
print("=" * 60)
print("\n✅ S3 Configuration Summary:")
print(f"   Endpoint: {s3_config['S3_ENDPOINT_URL']}")
print(f"   Bucket: {bucket_name}")
print(f"   Region: auto")
print(f"   Total Objects: {total_objects}")
print(f"   Total Size: {size_gb:.3f} GB")
print("\n✅ Remote Inference System is ready to use this S3 bucket!")
print("=" * 60)
