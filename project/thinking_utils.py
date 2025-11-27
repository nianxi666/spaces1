"""
Utility module for enabling and managing internal thinking in model responses.
Supports adding thinking prompts, parsing thinking tags, and extracting reasoning content.
"""

import re
import json

THINKING_SYSTEM_PROMPT = "You are a profound thinking assistant. Before answering the user's request, you must perform a detailed step-by-step analysis. Enclose your internal thought process within <thinking>...</thinking> tags. After the thinking tags, provide your final response."

def has_system_message(messages):
    """Check if messages already contain a system message."""
    if not messages:
        return False
    return any(msg.get('role') == 'system' for msg in messages)

def inject_thinking_prompt(messages):
    """
    Inject the thinking system prompt into messages if not already present.
    
    Args:
        messages: List of message dicts with 'role' and 'content' keys
        
    Returns:
        Modified messages list with thinking prompt added
    """
    if not messages:
        return messages
    
    # Create a shallow copy to avoid mutating the original list
    messages = list(messages)
    
    # Check if a system message already exists
    if has_system_message(messages):
        # If a system message exists, prepend our thinking instruction to it
        for i, msg in enumerate(messages):
            if msg.get('role') == 'system':
                # Create a copy of the message to avoid mutating the original
                messages[i] = msg.copy()
                # Enhance the existing system message with thinking instruction
                current_content = messages[i].get('content', '')
                messages[i]['content'] = THINKING_SYSTEM_PROMPT + '\n' + current_content
                break
    else:
        # If no system message exists, insert one at the beginning
        messages.insert(0, {
            'role': 'system',
            'content': THINKING_SYSTEM_PROMPT
        })
    
    return messages

def extract_thinking_and_content(text):
    """
    Extract thinking content and final response from text with <thinking> tags.
    
    Args:
        text: Response text that may contain <thinking>...</thinking> tags
        
    Returns:
        Tuple of (thinking_content, final_content)
    """
    thinking_match = re.search(r'<thinking>(.*?)</thinking>', text, re.DOTALL)
    
    if thinking_match:
        thinking_content = thinking_match.group(1).strip()
        # Remove thinking tags to get final answer
        final_content = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL).strip()
        return thinking_content, final_content
    
    return '', text

def parse_thinking_chunk(chunk_dict):
    """
    Parse a streaming chunk to extract reasoning_content if available.
    
    Args:
        chunk_dict: Dictionary representing a chunk
        
    Returns:
        Modified chunk dict with reasoning_content extracted if thinking tags are found
    """
    if not chunk_dict:
        return chunk_dict
    
    # Check if chunk has content that might contain thinking tags
    choices = chunk_dict.get('choices', [])
    if not choices:
        return chunk_dict
    
    choice = choices[0]
    delta = choice.get('delta', {})
    content = delta.get('content', '')
    
    if content and '<thinking>' in content:
        # Extract thinking from content
        thinking_match = re.search(r'<thinking>(.*?)</thinking>', content, re.DOTALL)
        if thinking_match:
            # Set reasoning_content from thinking tags
            if 'reasoning_content' not in delta:
                delta['reasoning_content'] = thinking_match.group(1)
    
    return chunk_dict

def process_streaming_chunk(chunk_dict):
    """
    Process a chunk from streaming response.
    Handles thinking tag extraction for streaming chunks.
    
    Args:
        chunk_dict: Dictionary representing a streaming chunk
        
    Returns:
        The chunk dict potentially modified with reasoning_content
    """
    if not chunk_dict or 'choices' not in chunk_dict:
        return chunk_dict
    
    choices = chunk_dict.get('choices', [])
    if not choices:
        return chunk_dict
    
    choice = choices[0]
    delta = choice.get('delta', {})
    
    # If we have content, check for thinking tags
    if 'content' in delta and delta['content']:
        content = delta['content']
        if '<thinking>' in content and '</' not in content:
            # Partial thinking tag - set as reasoning_content
            delta['reasoning_content'] = content
            # Clear content so it's not shown as regular output
            delta['content'] = ''
        elif '<thinking>' in content and '</thinking>' in content:
            # Complete thinking block in one chunk
            thinking_match = re.search(r'<thinking>(.*?)</thinking>', content, re.DOTALL)
            if thinking_match:
                delta['reasoning_content'] = thinking_match.group(1)
                # Remove thinking tags from content
                delta['content'] = re.sub(r'<thinking>.*?</thinking>', '', content, flags=re.DOTALL).strip()
    
    return chunk_dict

def enhance_response_with_thinking(response):
    """
    Enhance a complete response with thinking information.
    Extracts thinking from content and optionally moves it to a separate field.
    
    Args:
        response: OpenAI ChatCompletion response object
        
    Returns:
        Enhanced response object
    """
    if not response or not response.choices:
        return response
    
    choice = response.choices[0]
    message = choice.message
    content = message.content
    
    if content and '<thinking>' in content:
        thinking_content, final_content = extract_thinking_and_content(content)
        
        # Update the message content to remove thinking tags
        message.content = final_content
        
        # Store thinking in a custom field if it exists
        if thinking_content and not hasattr(message, 'reasoning_content'):
            message.reasoning_content = thinking_content
    
    return response
