"""
Remote Inference Module
Handles remote GPU inference through Gradio client with curl fallback.
Supports queuing, audio uploads, prompt management, and provides admin templates.
"""

import os
import json
import time
import wave
import struct
import math
import subprocess
import tempfile
from flask import current_app
from .database import load_db, save_db


def generate_curl_command(api_url, params, files=None):
    """
    Generate a curl command for remote API requests without exposing API URL in logs.
    Returns a tuple of (command_list, sanitized_display_command)
    """
    # Build curl command
    cmd = ['curl', '-X', 'POST', api_url]
    cmd.extend(['-H', 'Content-Type: multipart/form-data'])
    
    # Add files
    if files:
        for field_name, file_path in files.items():
            cmd.extend(['-F', f'{field_name}=@{file_path}'])
    
    # Add data params
    for key, value in params.items():
        cmd.extend(['-F', f'{key}={value}'])
    
    # Create sanitized version for display (hide actual API URL)
    sanitized_cmd = ' '.join(cmd).replace(api_url, '<HIDDEN_API_URL>')
    
    return cmd, sanitized_cmd


def execute_remote_inference(config_id, params, uploaded_files=None):
    """
    Execute remote inference using the configuration.
    
    Args:
        config_id: Remote inference configuration ID
        params: Dictionary of parameters for the API
        uploaded_files: Dictionary of {field_name: file_path} for file uploads
    
    Returns:
        Dict with status, result, and logs
    """
    db = load_db()
    
    # Find configuration
    config = None
    for user_data in db.get('users', {}).values():
        for c in user_data.get('remote_inference_configs', []):
            if c.get('id') == config_id:
                config = c
                break
        if config:
            break
    
    if not config:
        return {
            'status': 'error',
            'error': 'Configuration not found',
            'logs': 'Remote inference configuration does not exist'
        }
    
    api_url = config.get('api_url')
    if not api_url:
        return {
            'status': 'error',
            'error': 'API URL not configured',
            'logs': 'Remote inference API URL is missing'
        }
    
    try:
        # Generate curl command
        cmd, sanitized_cmd = generate_curl_command(api_url, params, uploaded_files)
        
        # Execute
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=config.get('timeout', 300)
        )
        
        if result.returncode == 0:
            # Parse response
            try:
                response = json.loads(result.stdout)
                return {
                    'status': 'completed',
                    'result': response,
                    'logs': f'Command: {sanitized_cmd}\n\nResponse received successfully'
                }
            except json.JSONDecodeError:
                return {
                    'status': 'completed',
                    'result': result.stdout,
                    'logs': f'Command: {sanitized_cmd}\n\nRaw response:\n{result.stdout}'
                }
        else:
            return {
                'status': 'error',
                'error': result.stderr,
                'logs': f'Command: {sanitized_cmd}\n\nError:\n{result.stderr}'
            }
            
    except subprocess.TimeoutExpired:
        return {
            'status': 'error',
            'error': 'Request timeout',
            'logs': f'Request exceeded timeout of {config.get("timeout", 300)} seconds'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'logs': f'Execution error: {str(e)}'
        }


def get_admin_template_code(config_type='audio_generation'):
    """
    Get template code for admins to integrate into their webui.py or app.py.
    This is a universal template that works across different webui implementations.
    
    Args:
        config_type: Type of configuration ('audio_generation', 'custom', etc.)
    
    Returns:
        String containing the template code
    """
    
    if config_type == 'audio_generation':
        return '''
# ===== Remote Inference Integration Template =====
# Copy this code into your webui.py or app.py
# This template is universal and works with any Gradio webui

import os
import json
from gradio_client import Client, handle_file

# Configuration - Update these values
REMOTE_API_URL = "http://direct.virtaicloud.com:21564"  # Your remote API endpoint
API_NAME = "/generate"  # API endpoint name

def process_remote_inference(
    prompt="Same as the voice reference",
    reference_audio_orig=None,  # File path or handle_file() object
    text_to_synthesize="",
    reference_audio_target=None,  # File path or handle_file() object  
    alpha_beta=0.8,
    style_params=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    extra_prompt="",
    disable_prompt=False,
    speed=120,
    enable_flag=True,
    advanced_params=(0.8, 30, 0.8, 0.0, 3, 10.0, 1500)
):
    """
    Process remote inference request.
    
    Args:
        prompt: Text prompt for generation
        reference_audio_orig: Original reference audio file
        text_to_synthesize: Text content to synthesize
        reference_audio_target: Target reference audio file
        (... other parameters ...)
    
    Returns:
        Result from remote API (typically a file path or URL)
    """
    try:
        # Initialize Gradio client
        client = Client(REMOTE_API_URL)
        
        # Handle file uploads
        if reference_audio_orig and isinstance(reference_audio_orig, str):
            reference_audio_orig = handle_file(reference_audio_orig)
        
        if reference_audio_target and isinstance(reference_audio_target, str):
            reference_audio_target = handle_file(reference_audio_target)
        
        # Unpack style and advanced parameters
        (s1, s2, s3, s4, s5, s6, s7, s8) = style_params
        (a1, a2, a3, a4, a5, a6, a7) = advanced_params
        
        # Send prediction request
        result = client.predict(
            prompt,
            reference_audio_orig,
            text_to_synthesize,
            reference_audio_target,
            alpha_beta,
            s1, s2, s3, s4, s5, s6, s7, s8,
            extra_prompt,
            disable_prompt,
            speed,
            enable_flag,
            a1, a2, a3, a4, a5, a6, a7,
            api_name=API_NAME
        )
        
        return {
            'status': 'success',
            'result': result,
            'message': 'Inference completed successfully'
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'message': f'Inference failed: {str(e)}'
        }


# Example usage in your Gradio interface:
# 
# def your_gradio_function(audio_file, text):
#     result = process_remote_inference(
#         reference_audio_orig=audio_file,
#         text_to_synthesize=text,
#         reference_audio_target=audio_file
#     )
#     
#     if result['status'] == 'success':
#         return result['result']
#     else:
#         raise Exception(result['error'])
#
# # In your Gradio blocks:
# with gr.Blocks() as demo:
#     audio_input = gr.Audio(type="filepath", label="Reference Audio")
#     text_input = gr.Textbox(label="Text to Synthesize")
#     output = gr.Audio(label="Generated Audio")
#     btn = gr.Button("Generate")
#     btn.click(your_gradio_function, [audio_input, text_input], output)

# ===== End of Template =====
'''
    
    elif config_type == 'custom':
        return '''
# ===== Generic Remote Inference Template =====
# Copy this code into your webui.py or app.py

import os
import json
from gradio_client import Client, handle_file

# Configuration
REMOTE_API_URL = "YOUR_API_URL_HERE"
API_NAME = "/your_endpoint"

def process_remote_inference(**kwargs):
    """
    Generic remote inference processor.
    Update parameters according to your API requirements.
    """
    try:
        client = Client(REMOTE_API_URL)
        
        # Handle file uploads
        for key, value in kwargs.items():
            if isinstance(value, str) and os.path.isfile(value):
                kwargs[key] = handle_file(value)
        
        # Send request
        result = client.predict(**kwargs, api_name=API_NAME)
        
        return {
            'status': 'success',
            'result': result
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }

# ===== End of Template =====
'''
    
    return ''


def create_default_remote_config():
    """
    Create default remote inference configuration for audio generation.
    """
    return {
        'type': 'audio_generation',
        'api_url': 'http://direct.virtaicloud.com:21564',
        'api_endpoint': '/generate',
        'timeout': 300,
        'supports_queue': True,
        'supports_prompt': True,
        'supports_audio_upload': True,
        'parameters': [
            {'name': 'prompt', 'type': 'text', 'default': 'Same as the voice reference'},
            {'name': 'reference_audio_orig', 'type': 'audio', 'required': True},
            {'name': 'text_to_synthesize', 'type': 'text', 'required': True},
            {'name': 'reference_audio_target', 'type': 'audio', 'required': True},
            {'name': 'alpha_beta', 'type': 'float', 'default': 0.8},
            {'name': 'speed', 'type': 'int', 'default': 120}
        ]
    }
