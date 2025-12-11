@api_bp.route('/relay-to-s3', methods=['POST'])
def relay_to_s3():
    """
    接收远程服务器上传的文件，立即转存到S3，然后删除本地临时文件。
    不占用VPS硬盘空间。
    
    用法：远程服务器调用此API，文件会被中转到S3，本地不保留。
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing or invalid Authorization header'}), 401
    
    api_key = auth_header[7:]
    if not api_key:
        return jsonify({'error': 'Missing API key'}), 401
    
    # 验证API key
    db = load_db()
    found_user = None
    for username, user_data in db['users'].items():
        if user_data.get('api_key') == api_key:
            found_user = username
            break
    
    if not found_user:
        return jsonify({'error': 'Invalid API key'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    temp_path = None
    try:
        # 1. 保存到临时文件
        suffix = os.path.splitext(file.filename)[1]
        fd, temp_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        file.save(temp_path)
        
        # 2. 立即上传到S3
        from .s3_utils import get_s3_client, get_s3_config, get_public_s3_url
        
        s3_client = get_s3_client()
        s3_config = get_s3_config()
        
        if not s3_client or not s3_config:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
            return jsonify({'error': 'S3 not configured'}), 500
        
        # 使用原始文件名存储到S3
        s3_key = file.filename
        bucket_name = s3_config.get('S3_BUCKET_NAME')
        
        # 上传到S3
        s3_client.upload_file(
            temp_path,
            bucket_name,
            s3_key,
            ExtraArgs={'ContentType': file.content_type or 'audio/wav'}
        )
        
        # 3. 生成公共URL
        public_url = get_public_s3_url(s3_key)
        
        # 4. 立即删除临时文件（不占用VPS硬盘）
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
            temp_path = None
        
        return jsonify({
            'success': True,
            'message': 'File relayed to S3 successfully',
            's3_key': s3_key,
            'public_url': public_url,
            'filename': file.filename
        }), 200
        
    except Exception as e:
        # 确保删除临时文件
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
