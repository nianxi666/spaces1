"""
Tebi Cloud S3 上传测试 - SSL问题诊断和修复
"""

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, SSLError
import os
import tempfile

# Tebi Cloud 配置
config = {
    "endpoint_url": "https://s3.tebi.io",
    "access_key": "YxWVUUhcFT6lGi9cF",
    "secret_key": "UkN7jF9L0P8XAqPcGOdjl3wi5SQ1d87st80fqC4A",
    "bucket_name": "driver"
}

print("=" * 70)
print("Tebi Cloud S3 上传测试 - SSL问题诊断")
print("=" * 70)

# 创建测试文件
test_content = b"This is a test file for S3 upload with SSL fix."
test_filename = "test_ssl_upload.txt"

print(f"\n📝 创建测试文件: {test_filename}")
with open(test_filename, 'wb') as f:
    f.write(test_content)
print(f"   ✅ 文件创建成功 ({len(test_content)} bytes)")

# 测试方案 1: 使用标准SSL验证
print("\n🔐 测试方案 1: 标准SSL验证 (verify=True)")
try:
    boto_config = Config(
        signature_version='s3v4',
        retries={'max_attempts': 3, 'mode': 'standard'}
    )
    
    s3_client = boto3.client(
        's3',
        endpoint_url=config['endpoint_url'],
        aws_access_key_id=config['access_key'],
        aws_secret_access_key=config['secret_key'],
        config=boto_config,
        verify=True
    )
    
    s3_client.upload_file(
        test_filename,
        config['bucket_name'],
        f"test/{test_filename}"
    )
    
    print("   ✅ 成功! SSL验证正常工作")
    print(f"   文件已上传到: {config['endpoint_url']}/{config['bucket_name']}/test/{test_filename}")
    method_1_success = True
    
except SSLError as e:
    print(f"   ❌ SSL错误: {e}")
    print("   原因: SSL证书验证失败")
    method_1_success = False
    
except Exception as e:
    print(f"   ❌ 失败: {e}")
    method_1_success = False

# 测试方案 2: 禁用SSL验证 (仅用于开发/测试)
if not method_1_success:
    print("\n🔓 测试方案 2: 禁用SSL验证 (verify=False)")
    print("   ⚠️  警告: 这不推荐用于生产环境")
    
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        boto_config = Config(
            signature_version='s3v4',
            retries={'max_attempts': 3, 'mode': 'standard'}
        )
        
        s3_client = boto3.client(
            's3',
            endpoint_url=config['endpoint_url'],
            aws_access_key_id=config['access_key'],
            aws_secret_access_key=config['secret_key'],
            config=boto_config,
            verify=False  # 禁用SSL验证
        )
        
        s3_client.upload_file(
            test_filename,
            config['bucket_name'],
            f"test/{test_filename}_no_ssl"
        )
        
        print("   ✅ 成功! 禁用SSL验证后上传成功")
        print(f"   文件已上传到: {config['endpoint_url']}/{config['bucket_name']}/test/{test_filename}_no_ssl")
        method_2_success = True
        
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        method_2_success = False

# 测试方案 3: 使用 requests 直接上传 (适用于远程webui)
print("\n📤 测试方案 3: 使用 PUT 请求直接上传")
try:
    import requests
    
    # 生成预签名 URL
    boto_config = Config(signature_version='s3v4')
    s3_client = boto3.client(
        's3',
        endpoint_url=config['endpoint_url'],
        aws_access_key_id=config['access_key'],
        aws_secret_access_key=config['secret_key'],
        config=boto_config,
        verify=False  # 临时禁用
    )
    
    presigned_url = s3_client.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': config['bucket_name'],
            'Key': f'test/{test_filename}_presigned'
        },
        ExpiresIn=3600
    )
    
    # 使用 requests 上传
    with open(test_filename, 'rb') as f:
        response = requests.put(
            presigned_url,
            data=f,
            verify=False  # 禁用SSL验证
        )
    
    if response.status_code == 200:
        print("   ✅ 成功! 使用预签名URL上传成功")
        print(f"   HTTP状态码: {response.status_code}")
        method_3_success = True
    else:
        print(f"   ❌ 失败: HTTP {response.status_code}")
        method_3_success = False
        
except Exception as e:
    print(f"   ❌ 失败: {e}")
    method_3_success = False

# 清理
try:
    os.remove(test_filename)
    print(f"\n🧹 已清理测试文件: {test_filename}")
except:
    pass

# 总结和建议
print("\n" + "=" * 70)
print("📊 测试总结")
print("=" * 70)

if method_1_success:
    print("\n✅ 推荐方案: 使用标准SSL验证")
    print("   在 s3_utils.py 中保持 verify=True")
    
elif method_2_success or method_3_success:
    print("\n⚠️  SSL证书问题已确认")
    print("\n🔧 临时解决方案 (开发环境):")
    print("   1. 在 project/s3_utils.py 中将 verify=True 改为 verify=False")
    print("   2. 添加 urllib3.disable_warnings()")
    
    print("\n💡 建议的代码修改:")
    print("""
    # 在 s3_utils.py 的 get_s3_client() 函数中:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    s3_client = boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name='auto',
        config=config,
        verify=False  # 临时禁用SSL验证
    )
    """)
    
    print("\n🔐 生产环境解决方案:")
    print("   1. 联系 Tebi Cloud 支持更新SSL证书")
    print("   2. 或使用自定义CA证书包")
    print("   3. 或配置certifi证书")

else:
    print("\n❌ 所有测试方案均失败")
    print("   请检查:")
    print("   1. 网络连接")
    print("   2. Access Key 和 Secret Key")
    print("   3. Bucket 名称和权限")

print("\n" + "=" * 70)
