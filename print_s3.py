import json
with open('s3_config.json') as f:
    data = json.load(f)
    print(f"URL={data.get('S3_ENDPOINT_URL')}")
    print(f"ACCESS={data.get('S3_ACCESS_KEY_ID')}")
    print(f"SECRET={data.get('S3_SECRET_ACCESS_KEY')}")
    print(f"BUCKET={data.get('S3_BUCKET_NAME')}")
