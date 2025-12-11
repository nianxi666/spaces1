"""
Tebi Cloud S3 详细测试
根据官方文档: https://tebi.io
"""
import boto3
from botocore.exceptions import ClientError, BotoCoreError
import json

print("=" * 70)
print("Tebi Cloud S3 连接测试")
print("=" * 70)

# 配置信息
config = {
    "endpoint_url": "https://s3.tebi.io",
    "access_key": "YxWVUUhcFT6lGi9cF",
    "secret_key": "UkN7jF9L0P8XAqPcGOdjl3wi5SQ1d87st80fqC4A",
    "bucket_name": "driver"
}

print(f"\n📋 配置信息:")
print(f"   Endpoint: {config['endpoint_url']}")
print(f"   Bucket: {config['bucket_name']}")
print(f"   Access Key: {config['access_key'][:10]}...")
print()

# 创建S3客户端
print("🔧 创建 S3 客户端...")
try:
    s3 = boto3.client(
        's3',
        endpoint_url=config['endpoint_url'],
        aws_access_key_id=config['access_key'],
        aws_secret_access_key=config['secret_key']
    )
    print("   ✅ S3 客户端创建成功")
except Exception as e:
    print(f"   ❌ 失败: {e}")
    exit(1)

# 测试1: 列出所有buckets
print("\n📦 测试 1: 列出所有可用的 buckets...")
try:
    response = s3.list_buckets()
    buckets = response.get('Buckets', [])
    print(f"   ✅ 成功! 找到 {len(buckets)} 个bucket(s):")
    for bucket in buckets:
        print(f"      - {bucket['Name']} (创建于 {bucket['CreationDate']})")
    
    if config['bucket_name'] not in [b['Name'] for b in buckets]:
        print(f"\n   ⚠️  警告: bucket '{config['bucket_name']}' 不在列表中!")
        print(f"   请从上面的列表中选择正确的bucket名称")
    else:
        print(f"\n   ✅ bucket '{config['bucket_name']}' 已找到!")
        
except ClientError as e:
    error_code = e.response.get('Error', {}).get('Code')
    error_msg = e.response.get('Error', {}).get('Message')
    print(f"   ❌ 失败: {error_code}")
    print(f"   错误信息: {error_msg}")
    
    if error_code == 'InvalidAccessKeyId':
        print("\n   💡 提示: Access Key 可能不正确")
    elif error_code == 'SignatureDoesNotMatch':
        print("\n   💡 提示: Secret Key 可能不正确")
except Exception as e:
    print(f"   ❌ 未知错误: {e}")

# 测试2: 列出bucket中的对象
print(f"\n📄 测试 2: 列出 '{config['bucket_name']}' 中的对象...")
try:
    response = s3.list_objects_v2(Bucket=config['bucket_name'], MaxKeys=5)
    
    if 'Contents' in response:
        total = response.get('KeyCount', 0)
        print(f"   ✅ 成功! Bucket中有对象 (显示前5个):")
        
        for obj in response['Contents']:
            size_mb = obj['Size'] / (1024 * 1024)
            print(f"      - {obj['Key']} ({size_mb:.2f} MB)")
        
        # 获取总数
        print(f"\n   📊 总共显示: {total} 个对象")
        
    else:
        print("   ✅ 成功连接，但bucket为空")
        
except ClientError as e:
    error_code = e.response.get('Error', {}).get('Code')
    error_msg = e.response.get('Error', {}).get('Message')
    print(f"   ❌ 失败: {error_code}")
    print(f"   错误信息: {error_msg}")
    
    if error_code == 'NoSuchBucket':
        print(f"\n   💡 提示: Bucket '{config['bucket_name']}' 不存在")
        print(f"   请检查bucket名称是否正确，或在测试1中查看可用的bucket")
    elif error_code == 'AccessDenied':
        print(f"\n   💡 提示: 没有权限访问此bucket")
except Exception as e:
    print(f"   ❌ 未知错误: {e}")

# 测试3: 生成presigned URL
print(f"\n🔗 测试 3: 生成预签名上传URL...")
try:
    test_key = "test/tebi_connection_test.txt"
    presigned_url = s3.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': config['bucket_name'],
            'Key': test_key
        },
        ExpiresIn=3600
    )
    print(f"   ✅ 成功生成预签名URL!")
    print(f"   Key: {test_key}")
    print(f"   URL长度: {len(presigned_url)} 字符")
    print(f"   过期时间: 1小时")
    
except Exception as e:
    print(f"   ❌ 失败: {e}")

print("\n" + "=" * 70)
print("测试完成!")
print("=" * 70)
