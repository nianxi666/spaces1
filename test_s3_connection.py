#!/usr/bin/env python3
"""
Test script to verify S3/Tebi connection and configuration.
"""

import sys
import json
import os
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_s3_config():
    """Test that s3_config.json exists and is valid."""
    config_file = project_root / 's3_config.json'
    
    print("=" * 60)
    print("S3 Configuration Test")
    print("=" * 60)
    
    if not config_file.exists():
        print(f"❌ Config file not found: {config_file}")
        return False
    
    print(f"✓ Config file found: {config_file}")
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Failed to read config: {e}")
        return False
    
    print("✓ Config is valid JSON")
    
    required_keys = [
        'S3_ENDPOINT_URL',
        'S3_ACCESS_KEY_ID',
        'S3_SECRET_ACCESS_KEY',
        'S3_BUCKET_NAME'
    ]
    
    all_present = True
    for key in required_keys:
        if key not in config:
            print(f"❌ Missing key: {key}")
            all_present = False
        else:
            value = config[key]
            if value.startswith('YOUR_'):
                print(f"❌ {key} is still a placeholder: {value}")
                all_present = False
            else:
                masked_value = value[:4] + '...' + value[-4:] if len(value) > 8 else '***'
                print(f"✓ {key}: {masked_value}")
    
    if not all_present:
        return False
    
    print("\n" + "=" * 60)
    print("Testing S3 Connection...")
    print("=" * 60)
    
    try:
        import boto3
        from botocore.exceptions import NoCredentialsError, ClientError
        
        endpoint_url = config.get('S3_ENDPOINT_URL')
        access_key = config.get('S3_ACCESS_KEY_ID')
        secret_key = config.get('S3_SECRET_ACCESS_KEY')
        bucket_name = config.get('S3_BUCKET_NAME')
        
        s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name='auto'
        )
        
        print(f"✓ S3 client created successfully")
        
        # Try to list buckets
        try:
            response = s3_client.list_buckets()
            buckets = [b['Name'] for b in response.get('Buckets', [])]
            print(f"✓ Successfully listed buckets: {buckets}")
            
            if bucket_name in buckets:
                print(f"✓ Target bucket '{bucket_name}' is accessible")
                
                # Try to list objects in bucket
                try:
                    objects = s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=5)
                    count = objects.get('KeyCount', 0)
                    print(f"✓ Bucket contains {count} objects (showing first 5)")
                    if 'Contents' in objects:
                        for obj in objects['Contents'][:3]:
                            print(f"  - {obj['Key']}")
                except ClientError as e:
                    print(f"⚠ Could not list objects: {e}")
            else:
                print(f"❌ Bucket '{bucket_name}' not found in available buckets")
                return False
        
        except NoCredentialsError:
            print(f"❌ Authentication failed - check credentials")
            return False
        except ClientError as e:
            print(f"❌ AWS error: {e}")
            return False
        
        print("\n" + "=" * 60)
        print("✅ All tests passed! S3 is properly configured.")
        print("=" * 60)
        return True
        
    except ImportError:
        print("❌ boto3 not installed. Run: pip install boto3")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_s3_config()
    sys.exit(0 if success else 1)
