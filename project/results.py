from flask import (
    Blueprint, render_template, request, redirect, url_for, session, flash,
    Response, stream_with_context
)
import requests
from .s3_utils import list_files_for_user, get_public_s3_url

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


@results_bp.route('/modal_drive')
def modal_drive():
    """Modal Drive page - infinite capacity cloud storage"""
    return render_template('modal_drive.html')


@results_bp.route('/modal_drive_download')
def modal_drive_download():
    """Placeholder for modal drive download - actual logic in API"""
    flash('请使用网盘界面下载文件。', 'info')
    return redirect(url_for('results.modal_drive'))

