from flask import (
    Blueprint, render_template, request, redirect, url_for, session, flash,
    Response, stream_with_context
)
import requests
from .s3_utils import list_files_for_user, get_public_s3_url
from .modal_drive_utils import (
    get_modal_drive_credentials,
    build_user_full_path,
    get_drive_username
)

results_bp = Blueprint('results', __name__, url_prefix='/results')

IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm', 'm4v', 'mpg', 'mpeg'}

def is_image(filename):
    """Check if a filename has an image extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in IMAGE_EXTENSIONS

def is_video(filename):
    """Check if a filename has a video extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in VIDEO_EXTENSIONS

@results_bp.before_request
def check_login():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

@results_bp.route('/my_results')
def my_results():
    username = session['username']
    s3_files = list_files_for_user(username)

    if s3_files is None:
        flash('无法从S3获取文件列表，请检查S3配置是否正确。', 'error')
        s3_files = []
    else:
        for file in s3_files:
            file['is_image'] = is_image(file['filename'])
            file['is_video'] = is_video(file['filename'])
            if file['is_image'] or file['is_video']:
                file['preview_url'] = get_public_s3_url(file['key'])
            else:
                file['preview_url'] = None


    return render_template('my_results.html', files=s3_files)


@results_bp.route('/modal_drive')
def modal_drive():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    base_url, token = get_modal_drive_credentials()
    drive_enabled = bool(base_url and token)
    return render_template(
        'modal_drive.html',
        drive_enabled=drive_enabled,
        modal_drive_url=base_url,
        drive_root=get_drive_username()
    )


@results_bp.route('/modal_drive/download')
def modal_drive_download():
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    path = request.args.get('path')
    if not path:
        flash('缺少文件路径', 'error')
        return redirect(url_for('results.modal_drive'))

    base_url, token = get_modal_drive_credentials()
    if not base_url or not token:
        flash('无限容量网盘尚未配置。', 'error')
        return redirect(url_for('results.modal_drive'))

    try:
        remote_path = build_user_full_path(path)
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('results.modal_drive'))

    try:
        response = requests.get(
            f"{base_url}/download",
            params={'path': remote_path},
            headers={'Authorization': f"Bearer {token}"},
            stream=True,
            timeout=120
        )
    except requests.RequestException as exc:
        flash(f"下载失败: {exc}", 'error')
        return redirect(url_for('results.modal_drive'))

    if response.status_code != 200:
        try:
            error_payload = response.json()
            error_message = error_payload.get('detail') or error_payload
        except ValueError:
            error_message = response.text or '下载失败'
        flash(f"下载失败: {error_message}", 'error')
        return redirect(url_for('results.modal_drive'))

    filename = path.split('/')[-1] or 'file'
    flask_response = Response(
        stream_with_context(response.iter_content(chunk_size=8192)),
        content_type=response.headers.get('Content-Type', 'application/octet-stream')
    )
    flask_response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return flask_response

@results_bp.route('/download/<path:object_key>')
def download_s3_file(object_key):
    """
    Generates a public URL for an S3 object and redirects to it.
    """
    username = session.get('username')
    # Security check: Ensure the user is trying to access their own files.
    if not object_key.startswith(f"{username}/"):
        flash('无权访问此文件。', 'error')
        return redirect(url_for('results.my_results'))

    url = get_public_s3_url(object_key)

    if url:
        return redirect(url)
    else:
        flash('无法生成下载链接。', 'error')
        return redirect(url_for('results.my_results'))
