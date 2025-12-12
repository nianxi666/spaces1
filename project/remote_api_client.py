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
    finally:
        # Ensure all files are closed
        if files:
            for f in files.values():
                if hasattr(f, 'close'):
                    try:
                        f.close()
                    except:
                        pass


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
