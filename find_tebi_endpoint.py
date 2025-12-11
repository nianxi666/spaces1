"""
Quick S3 endpoint test for Tebi Cloud
"""
import boto3
from botocore.exceptions import ClientError

# Tebi Cloud endpoints to try
endpoints = [
    "https://s3.tebi.io",
    "https://tebi.io", 
    "https://s3.us-east-1.tebi.io",
    "https://s3.eu-central-1.tebi.io"
]

credentials = {
    "access_key": "YxWVUUhcFT6lGi9cF",
    "secret_key": "UkN7jF9L0P8XAqPcGOdjl3wi5SQ1d87st80fqC4A",
    "bucket": "driver"
}

print("Testing Tebi Cloud S3 endpoints...\n")

for endpoint in endpoints:
    print(f"Testing: {endpoint}")
    try:
        client = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=credentials['access_key'],
            aws_secret_access_key=credentials['secret_key']
        )
        
        # Try to list objects
        response = client.list_objects_v2(Bucket=credentials['bucket'], MaxKeys=1)
        print(f"  ✅ SUCCESS! This endpoint works!")
        print(f"  Bucket exists and is accessible\n")
        
        # Show bucket info
        if 'Contents' in response:
            print(f"  Sample object: {response['Contents'][0]['Key']}")
        break
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = str(e)
        print(f"  ❌ Failed: {error_code}")
        if "does not exist" in error_msg.lower():
            print(f"     Bucket not found at this endpoint")
        elif "signature" in error_msg.lower():
            print(f"     Authentication issue")
        else:
            print(f"     {error_msg[:100]}")
        print()
    except Exception as e:
        print(f"  ❌ Connection error: {str(e)[:100]}\n")
