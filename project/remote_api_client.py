"""
Remote API Client for Gradio and generic HTTP APIs
Handles efficient multipart file upload without base64 encoding
"""

import requests
import os
import tempfile
from typing import Dict, Optional, Any, List


def call_remote_api(
    api_url: str,
    files_dict: Optional[Dict[str, str]] = None,
    params_dict: Optional[Dict[str, Any]] = None,
    timeout: int = 300
) -> Dict[str, Any]:
    """
    Call remote API with multipart file upload (no base64 encoding)
    
    Args:
        api_url: Full API endpoint URL
        files_dict: Dictionary of {field_name: file_path}
        params_dict: Dictionary of other parameters
        timeout: Request timeout in seconds
    
    Returns:
        Dict with 'success', 'data', 'error' keys
    """
    
    try:
        # Prepare multipart form data
        files = {}
        data = {}
        
        # Add files (binary stream, no encoding)
        if files_dict:
            for field_name, file_path in files_dict.items():
                if file_path and os.path.exists(file_path):
                    files[field_name] = open(file_path, 'rb')
        
        # Add other parameters
        if params_dict:
            data = params_dict
        
        # Send request
        response = requests.post(
            api_url,
            files=files if files else None,
            data=data if data else None,
            timeout=timeout
        )
        
        # Close all opened files
        for f in files.values():
            if hasattr(f, 'close'):
                f.close()
        
        response.raise_for_status()
        
        # Parse response
        result_data = response.json() if response.content else {}
        
        return {
            'success': True,
            'data': result_data,
            'status_code': response.status_code
        }
        
    except requests.exceptions.Timeout:
        return {
            'success': False,
            'error': f'Request timeout after {timeout} seconds'
        }
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'error': f'Request failed: {str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        }



def smart_call_remote_api(
    api_url: str,
    files_dict: Optional[Dict[str, str]] = None,
    params_dict: Optional[Dict[str, Any]] = None,
    timeout: int = 300
) -> Dict[str, Any]:
    """
    Call remote API with intelligent endpoint detection.
    Retries with /run/predict (Gradio 4+) and /api/predict (Gradio 3) if base URL fails.
    """
    
    # List of URLs to try
    urls_to_try = [api_url]
    
    # If URL is a base URL (no specific path), prioritize common Gradio paths
    clean_url = api_url.rstrip('/')
    if clean_url == api_url or api_url.endswith('/'):
        # Usually users paste the base URL e.g. http://host:21564/
        # We should try specific endpoints if the raw one fails
        urls_to_try.append(f"{clean_url}/run/predict") # Gradio 4.x
        urls_to_try.append(f"{clean_url}/api/predict") # Gradio 3.x
        
    last_result = {'success': False, 'error': 'Unknown error'}
    
    for try_url in urls_to_try:
        print(f"DEBUG: Trying Remote API: {try_url}")
        result = call_remote_api(try_url, files_dict, params_dict, timeout)
        
        if result['success']:
            return result
            
        # If failed with 404 or 405, continue to next candidate
        # If it's a connection error or 500, probably no point trying other paths on same host
        error_msg = result.get('error', '')
        status_code = result.get('status_code')
        
        if status_code in [404, 405] or '404' in error_msg or '405' in error_msg:
             print(f"DEBUG: {try_url} failed with {status_code}, trying next...")
             last_result = result
             continue
        else:
            # Fatal error (e.g. connection refused), stop trying
            return result
            
    return last_result



def call_gradio_api(
    api_url: str,
    data_params: List[Any],
    file_paths: Optional[List[str]] = None,
    timeout: int = 300
) -> Dict[str, Any]:
    """
    Call Gradio API with standard format
    
    Args:
        api_url: Gradio API URL (e.g., http://host:port/api/generate)
        data_params: List of parameters in order
        file_paths: List of file paths to upload
        timeout: Request timeout
    
    Returns:
        Dict with result
    """
    
    try:
        # Method 1: Try JSON format first (newer Gradio)
        payload = {
            "data": data_params,
            "fn_index": 0
        }
        
        response = requests.post(
            api_url,
            json=payload,
            timeout=timeout
        )
        
        response.raise_for_status()
        result = response.json()
        
        return {
            'success': True,
            'data': result.get('data', result)
        }
        
    except Exception as e:
        # Fallback: try multipart if JSON fails
        return call_remote_api(
            api_url=api_url,
            params_dict={'data': str(data_params)},
            timeout=timeout
        )


def download_result_file(
    result_url: str,
    save_path: Optional[str] = None
) -> Optional[str]:
    """
    Download result file from remote API
    
    Args:
        result_url: URL of the result file
        save_path: Where to save (None = temp file)
    
    Returns:
        Path to downloaded file, or None if failed
    """
    
    try:
        response = requests.get(result_url, stream=True, timeout=60)
        response.raise_for_status()
        
        if not save_path:
            # Create temp file
            suffix = os.path.splitext(result_url)[1] or '.bin'
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                save_path = tmp.name
        
        # Download file
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return save_path
        
    except Exception as e:
        print(f"Failed to download result: {e}")
        return None
