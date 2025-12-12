import boto3
from botocore.exceptions import NoCredentialsError, ClientError
import json
import os
from flask import current_app

def get_s3_config():
    """Loads S3 configuration from the JSON file."""
    config_path = current_app.config.get('S3_CONFIG_FILE')
    if not config_path or not os.path.exists(config_path):
        return None
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return None

def get_s3_client():
    """
    Initializes and returns a boto3 S3 client using credentials
    from the s3_config.json file.
    """
    s3_config = get_s3_config()
    if not s3_config:
        return None

    endpoint_url = s3_config.get('S3_ENDPOINT_URL')
    access_key = s3_config.get('S3_ACCESS_KEY_ID')
    secret_key = s3_config.get('S3_SECRET_ACCESS_KEY')

    if not all([endpoint_url, access_key, secret_key]):
        return None

    try:
        from botocore.config import Config
        import urllib3
        
        # Disable SSL warnings (necessary when verify=False)
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Configure with SSL verification and retries
        # For Tebi Cloud, we disable SSL verification due to certificate issues
        config = Config(
            signature_version='s3v4',
            retries={
                'max_attempts': 3,
                'mode': 'standard'
            }
        )
        
        s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name='auto',  # Tebi uses 'auto' or 'global'
            config=config,
            verify=False  # Disabled for Tebi Cloud SSL certificate issues
        )
        return s3_client
    except Exception as e:
        print(f"Failed to create S3 client: {e}")
        return None

def generate_presigned_url(file_name, content_type=None, expiration=7200):
    """
    Generate a presigned URL to upload a file to an S3 bucket.

    :param file_name: string. The name of the file to be uploaded.
    :param content_type: string. The MIME type of the file being uploaded.
    :param expiration: Integer. Time in seconds for the presigned URL to remain valid.
    :return: Dictionary containing the presigned URL and the final object URL.
             Returns None if generation fails.
    """
    s3_client = get_s3_client()
    s3_config = get_s3_config()

    if not s3_client or not s3_config:
        print("S3 client or config not available.")
        return None

    bucket_name = s3_config.get('S3_BUCKET_NAME')
    endpoint_url = s3_config.get('S3_ENDPOINT_URL')
    if not bucket_name:
        print("S3 bucket name not configured.")
        return None

    try:
        params = {'Bucket': bucket_name, 'Key': file_name}
        if content_type:
            params['ContentType'] = content_type

        response = s3_client.generate_presigned_url(
            'put_object',
            Params=params,
            ExpiresIn=expiration,
            HttpMethod='PUT'
        )
        # Construct the final, permanent URL
        final_url = f"{endpoint_url}/{bucket_name}/{file_name}"

        return {'presigned_url': response, 'final_url': final_url}

    except ClientError as e:
        print(f"Failed to generate presigned URL: {e}")
        return None
    except NoCredentialsError:
        print("Credentials not available for S3.")
        return None

def upload_file_to_s3(file_path, object_name, content_type=None):
    """
    Upload a file directly to S3 from the server.
    
    :param file_path: Local path to the file to upload.
    :param object_name: S3 object name (key).
    :param content_type: Optional MIME type of the file.
    :return: True if successful, False otherwise.
    """
    s3_client = get_s3_client()
    s3_config = get_s3_config()

    if not s3_client or not s3_config:
        print("S3 client or config not available.")
        return False

    bucket_name = s3_config.get('S3_BUCKET_NAME')
    if not bucket_name:
        print("S3 bucket name not configured.")
        return False

    try:
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type
        
        # Determine content type from extension if not provided
        if not content_type:
            import mimetypes
            guessed_type, _ = mimetypes.guess_type(file_path)
            if guessed_type:
                extra_args['ContentType'] = guessed_type
        
        s3_client.upload_file(
            file_path,
            bucket_name,
            object_name,
            ExtraArgs=extra_args if extra_args else None
        )
        
        print(f"Successfully uploaded {file_path} to s3://{bucket_name}/{object_name}")
        return True

    except ClientError as e:
        print(f"Failed to upload file to S3: {e}")
        return False
    except NoCredentialsError:
        print("Credentials not available for S3.")
        return False
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return False

def delete_s3_object(object_key):
    """
    Delete an object from the S3 bucket.
    
    :param object_key: The key of the object to delete.
    :return: True if successful, False otherwise.
    """
    s3_client = get_s3_client()
    s3_config = get_s3_config()

    if not s3_client or not s3_config:
        print("S3 client or config not available.")
        return False

    bucket_name = s3_config.get('S3_BUCKET_NAME')
    if not bucket_name:
        print("S3 bucket name not configured.")
        return False

    try:
        s3_client.delete_object(Bucket=bucket_name, Key=object_key)
        print(f"Successfully deleted s3://{bucket_name}/{object_key}")
        return True
    except ClientError as e:
        print(f"Failed to delete object from S3: {e}")
        return False

def list_all_files():
    """
    Lists all files in the S3 bucket.

    :return: A list of file dictionaries, or None if an error occurs.
    """
    s3_client = get_s3_client()
    s3_config = get_s3_config()

    if not s3_client or not s3_config:
        print("S3 client or config not available.")
        return None

    bucket_name = s3_config.get('S3_BUCKET_NAME')
    endpoint_url = s3_config.get('S3_ENDPOINT_URL')
    if not bucket_name:
        print("S3 bucket name not configured.")
        return None

    try:
        # Use a paginator to handle buckets with many objects
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name)

        files = []
        for page in pages:
            if 'Contents' in page:
                for item in page['Contents']:
                    # Don't list "folders"
                    if item['Key'].endswith('/'):
                        continue

                    files.append({
                        'key': item['Key'],
                        'filename': os.path.basename(item['Key']),
                        'size': item['Size'],
                        'last_modified': item['LastModified'],
                        'url': f"{endpoint_url}/{bucket_name}/{item['Key']}"
                    })

        # Sort by last modified date, newest first
        files.sort(key=lambda x: x['last_modified'], reverse=True)

        return files

    except ClientError as e:
        print(f"Failed to list all objects: {e}")
        return None
    except NoCredentialsError:
        print("Credentials not available for S3.")
        return None

def rename_s3_object(old_key, new_key):
    """
    Renames an object in an S3 bucket by copying and deleting.

    :param old_key: The current key of the object.
    :param new_key: The new key for the object.
    :return: True if successful, False otherwise.
    """
    s3_client = get_s3_client()
    s3_config = get_s3_config()

    if not s3_client or not s3_config:
        print("S3 client or config not available for rename operation.")
        return False

    bucket_name = s3_config.get('S3_BUCKET_NAME')
    if not bucket_name:
        print("S3 bucket name not configured.")
        return False

    try:
        # Copy the object to the new key
        copy_source = {'Bucket': bucket_name, 'Key': old_key}
        s3_client.copy_object(Bucket=bucket_name, CopySource=copy_source, Key=new_key)

        # Delete the old object
        s3_client.delete_object(Bucket=bucket_name, Key=old_key)

        print(f"Successfully renamed {old_key} to {new_key}")
        return True
    except ClientError as e:
        print(f"Failed to rename object {old_key} to {new_key}: {e}")
        return False

def get_public_s3_url(object_key):
    """
    Constructs a direct public URL for an S3 object, assuming the bucket is public.

    :param object_key: The key of the object in S3.
    :return: The public URL as a string, or None if config is unavailable.
    """
    s3_config = get_s3_config()
    if not s3_config or not object_key:
        return None

    endpoint_url = s3_config.get('S3_ENDPOINT_URL')
    bucket_name = s3_config.get('S3_BUCKET_NAME')

    if not endpoint_url or not bucket_name:
        return None

    # Ensure no double slashes in the final URL
    if endpoint_url.endswith('/'):
        endpoint_url = endpoint_url.rstrip('/')

    return f"{endpoint_url}/{bucket_name}/{object_key}"

def list_files_for_user(username):
    """
    Lists all files for a given user from the S3 bucket.

    :param username: string. The user's name, used as a prefix.
    :return: A list of file dictionaries, or None if an error occurs.
    """
    s3_client = get_s3_client()
    s3_config = get_s3_config()

    if not s3_client or not s3_config:
        print("S3 client or config not available.")
        return None

    bucket_name = s3_config.get('S3_BUCKET_NAME')
    endpoint_url = s3_config.get('S3_ENDPOINT_URL')
    if not bucket_name:
        print("S3 bucket name not configured.")
        return None

    try:
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=f"{username}/"
        )

        files = []
        if 'Contents' in response:
            for item in response['Contents']:
                # Don't list the "folder" itself if it appears as an object
                if item['Key'].endswith('/'):
                    continue

                files.append({
                    'key': item['Key'],
                    'filename': os.path.basename(item['Key']),
                    'size': item['Size'],
                    'last_modified': item['LastModified'],
                    'url': f"{endpoint_url}/{bucket_name}/{item['Key']}"
                })

        # Sort by last modified date, newest first
        files.sort(key=lambda x: x['last_modified'], reverse=True)

        return files

    except ClientError as e:
        print(f"Failed to list objects for user {username}: {e}")
        return None
    except NoCredentialsError:
        print("Credentials not available for S3.")
        return None
