import time
import random
import threading
import json
from openai import OpenAI, APIError, AuthenticationError, RateLimitError

DEFAULT_NETMIND_BASE_URL = 'https://api.netmind.ai/inference-api/openai/v1'

class NetMindClient:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(NetMindClient, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # State could be managed here if needed, but we mostly rely on DB passed in context
        pass

    def _get_settings(self, db):
        return db.get('netmind_settings', {})

    def _get_valid_keys(self, db):
        settings = self._get_settings(db)
        return [k for k in settings.get('keys', []) if k.strip()]

    def _get_next_key(self, db, exclude_key=None):
        keys = self._get_valid_keys(db)
        if not keys:
            return None

        if exclude_key and exclude_key in keys and len(keys) > 1:
            # Simple rotation: just pick a random one that is not the excluded one
            # For true round-robin, we would need persistent state
            candidates = [k for k in keys if k != exclude_key]
            return random.choice(candidates)

        return random.choice(keys)

    def _normalize_base_url(self, raw_url):
        """
        NetMind expects an OpenAI-compatible /openai/v1 endpoint.
        Admins sometimes save a shorter base URL (e.g. https://inference-api.netmind.ai/v1)
        which returns 404. This helper makes sure we always hit the canonical path.
        """
        if not raw_url:
            return DEFAULT_NETMIND_BASE_URL

        base_url = raw_url.strip()
        if not base_url:
            return DEFAULT_NETMIND_BASE_URL

        base_url = base_url.rstrip('/')

        # Known invalid public host -> fall back to canonical endpoint
        if base_url.startswith('https://inference-api.netmind.ai'):
            return DEFAULT_NETMIND_BASE_URL

        if '/openai/' not in base_url:
            if base_url.endswith('/inference-api'):
                base_url = f'{base_url}/openai/v1'
            else:
                base_url = f'{base_url}/openai/v1'
        elif not base_url.endswith('/v1'):
            base_url = f'{base_url}/v1'

        return base_url

    def _resolve_model_name(self, db, requested_model):
        """
        Allows admins to expose friendly model names to users when enabled.
        """
        if not requested_model:
            return requested_model

        settings = self._get_settings(db)
        if not settings or not settings.get('enable_alias_mapping'):
            return requested_model

        lookup = {}

        alias_config = settings.get('model_aliases') or {}
        for alias, target in alias_config.items():
            if not isinstance(alias, str) or not isinstance(target, str):
                continue
            alias_key = alias.strip().lower()
            upstream_value = target.strip()
            if alias_key and upstream_value:
                lookup[alias_key] = upstream_value

        for space in (db.get('spaces') or {}).values():
            if space.get('card_type') != 'netmind':
                continue
            alias = space.get('netmind_model')
            upstream = space.get('netmind_upstream_model') or alias
            if not isinstance(alias, str) or not isinstance(upstream, str):
                continue
            alias_key = alias.strip().lower()
            upstream_value = upstream.strip()
            if alias_key and upstream_value:
                lookup[alias_key] = upstream_value

        resolved = lookup.get(requested_model.strip().lower())
        return resolved or requested_model

    def chat_completion(self, db, messages, model, stream=False, max_tokens=None, extra_params=None):
        settings = self._get_settings(db)
        base_url = self._normalize_base_url(settings.get('base_url'))
        fallback_base_url = None
        if base_url != DEFAULT_NETMIND_BASE_URL:
            fallback_base_url = DEFAULT_NETMIND_BASE_URL

        ad_suffix = settings.get('ad_suffix', '')
        ad_enabled = settings.get('ad_enabled', False)
        public_model_name = model
        upstream_model_name = self._resolve_model_name(db, model)

        key = self._get_next_key(db)
        if not key:
            raise Exception("No NetMind API keys configured.")

        # Max retries based on the number of keys available
        max_retries = len(self._get_valid_keys(db))
        attempts = 0
        last_error = None

        current_base_url = base_url

        while attempts < max_retries:
            try:
                client = OpenAI(
                    api_key=key,
                    base_url=current_base_url
                )

                request_options = extra_params.copy() if extra_params else None

                if stream:
                    return self._handle_stream(
                        client,
                        messages,
                        upstream_model_name,
                        public_model_name,
                        ad_suffix,
                        ad_enabled,
                        max_tokens=max_tokens,
                        extra_params=request_options
                    )
                else:
                    return self._handle_sync(
                        client,
                        messages,
                        upstream_model_name,
                        public_model_name,
                        ad_suffix,
                        ad_enabled,
                        max_tokens=max_tokens,
                        extra_params=request_options
                    )

            except (AuthenticationError, RateLimitError) as e:
                print(f"NetMind API Error (Key: {key[:4]}...): {e}")
                last_error = e
                attempts += 1
                key = self._get_next_key(db, exclude_key=key)
                if not key:
                     break # Should not happen if max_retries is correct
                time.sleep(0.5) # Brief pause before retry
            except APIError as e:
                if e.status_code == 404 and fallback_base_url:
                    print(f"NetMind Base URL {current_base_url} returned 404. Falling back to {fallback_base_url}.")
                    current_base_url = fallback_base_url
                    fallback_base_url = None
                    continue
                print(f"NetMind API Error: {e}")
                raise e
            except Exception as e:
                 # Other errors (e.g. validation, network) might not be solved by rotating keys
                 print(f"NetMind Unexpected Error: {e}")
                 raise e

        raise last_error or Exception("All NetMind keys failed.")

    def _handle_sync(self, client, messages, upstream_model, public_model, ad_suffix, ad_enabled, max_tokens=None, extra_params=None):
        payload = {
            'model': upstream_model,
            'messages': messages,
            'stream': False
        }
        if isinstance(max_tokens, int) and max_tokens > 0:
            payload['max_tokens'] = max_tokens
        if extra_params:
            payload.update(extra_params)

        print(f"[DEBUG] Making API call with model: {upstream_model}")
        response = client.chat.completions.create(**payload)
        
        # Debug: Print response structure
        if response.choices:
            msg = response.choices[0].message
            print(f"[DEBUG] Response message type: {type(msg)}")
            print(f"[DEBUG] Message attributes: {dir(msg)}")
            if hasattr(msg, 'reasoning_content'):
                print(f"[DEBUG] ✓ Has reasoning_content: {msg.reasoning_content[:100] if msg.reasoning_content else 'None'}")
            else:
                print(f"[DEBUG] ✗ No reasoning_content attribute")
            
            # Check model_dump output
            try:
                dumped = msg.model_dump()
                print(f"[DEBUG] model_dump keys: {dumped.keys()}")
                if 'reasoning_content' in dumped:
                    print(f"[DEBUG] ✓ reasoning_content in model_dump: {dumped['reasoning_content'][:100]}")
            except Exception as e:
                print(f"[DEBUG] model_dump error: {e}")

        # Inject Ad (only to content, not reasoning)
        if ad_enabled and ad_suffix and response.choices:
            content = response.choices[0].message.content or ""
            response.choices[0].message.content = content + ad_suffix

        try:
            response.model = public_model
        except Exception:
            pass
        try:
            response.id = self._generate_public_id()
        except Exception:
            pass

        # Store reasoning_content for later serialization
        # This is needed for DeepSeek-R1 and other models with thinking support
        if response.choices:
            for choice in response.choices:
                if hasattr(choice, 'message') and choice.message:
                    message = choice.message
                    # Try to get reasoning_content from the message
                    # It may be an attribute or in __dict__
                    reasoning = None
                    if hasattr(message, 'reasoning_content'):
                        reasoning = message.reasoning_content
                    elif hasattr(message, '__dict__') and 'reasoning_content' in message.__dict__:
                        reasoning = message.__dict__.get('reasoning_content')
                    
                    # If found, ensure it's set as an attribute for model_dump
                    if reasoning:
                        try:
                            message.reasoning_content = reasoning
                        except (AttributeError, TypeError):
                            # If can't set, try to store in __dict__
                            if hasattr(message, '__dict__'):
                                message.__dict__['reasoning_content'] = reasoning

        return response

    def _handle_stream(self, client, messages, upstream_model, public_model, ad_suffix, ad_enabled, max_tokens=None, extra_params=None):
        payload = {
            'model': upstream_model,
            'messages': messages,
            'stream': True
        }
        if isinstance(max_tokens, int) and max_tokens > 0:
            payload['max_tokens'] = max_tokens
        if extra_params:
            payload.update(extra_params)
        
        # Note: Some models like DeepSeek-R1 automatically include reasoning_content
        # if the model supports it. No special parameter needed for most APIs.
        # If using a provider that requires explicit reasoning parameter, add it here.

        response = client.chat.completions.create(**payload)

        # We yield raw strings formatted as SSE data for the client
        # OpenAI client yields chunks, we need to wrap them

        chunk_id_base = self._generate_public_id()
        chunk_counter = 0

        for chunk in response:
            chunk_payload = self._sanitize_chunk_payload(chunk, public_model, chunk_id_base, chunk_counter)
            chunk_counter += 1
            
            # Debug: Log first few chunks
            if chunk_counter <= 3 or 'reasoning_content' in str(chunk_payload):
                print(f"[DEBUG] Chunk {chunk_counter}: {json.dumps(chunk_payload, ensure_ascii=False)[:200]}")
            
            yield f"data: {json.dumps(chunk_payload, ensure_ascii=False)}\n\n"

        # Inject Ad as a separate chunk before DONE
        if ad_enabled and ad_suffix:
            # Construct a fake chunk for the ad
            ad_chunk = {
                "id": self._generate_public_id(),
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": public_model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "content": ad_suffix
                        },
                        "finish_reason": None
                    }
                ]
            }
            yield f"data: {json.dumps(ad_chunk, ensure_ascii=False)}\n\n"

        yield "data: [DONE]\n\n"

    def _generate_public_id(self, prefix='chatcmpl'):
        return f"{prefix}-pumpkin-{int(time.time() * 1000)}-{random.randint(1000, 9999)}"

    def _sanitize_chunk_payload(self, chunk, public_model, chunk_id_base, chunk_index):
        chunk_dict = chunk.model_dump()
        chunk_dict['model'] = public_model
        chunk_id = str(chunk_dict.get('id') or '')
        if not chunk_id or 'netmind' in chunk_id.lower():
            chunk_dict['id'] = f"{chunk_id_base}-{chunk_index}"
        
        # Ensure reasoning_content is preserved in delta if present
        # This is needed for DeepSeek-R1 and other models with thinking support
        if 'choices' in chunk_dict and chunk_dict['choices']:
            for choice_idx, choice in enumerate(chunk_dict['choices']):
                if 'delta' in choice:
                    delta = choice['delta']
                    # Ensure delta is a dict
                    if not isinstance(delta, dict):
                        delta = {}
                        choice['delta'] = delta
                    
                    # Debug: Check what's in the original delta
                    if chunk_index <= 3:
                        print(f"[DEBUG] Original delta attributes: {dir(choice.get('delta', {}))}")
                    
                    # Check if original chunk has reasoning_content in the delta
                    if hasattr(chunk, 'choices') and chunk.choices and len(chunk.choices) > choice_idx:
                        original_choice = chunk.choices[choice_idx]
                        if hasattr(original_choice, 'delta') and original_choice.delta:
                            original_delta = original_choice.delta
                            
                            # Debug
                            if chunk_index <= 3:
                                print(f"[DEBUG] original_delta type: {type(original_delta)}")
                                print(f"[DEBUG] original_delta attributes: {[a for a in dir(original_delta) if not a.startswith('_')]}")
                            
                            # Try multiple methods to extract reasoning_content
                            reasoning = None
                            
                            # Method 1: Direct attribute
                            if hasattr(original_delta, 'reasoning_content'):
                                reasoning = original_delta.reasoning_content
                                if chunk_index <= 3 and reasoning:
                                    print(f"[DEBUG] Method 1 found reasoning_content: {reasoning[:50]}")
                            
                            # Method 2: Via __dict__
                            if not reasoning and hasattr(original_delta, '__dict__'):
                                reasoning = original_delta.__dict__.get('reasoning_content')
                                if chunk_index <= 3 and reasoning:
                                    print(f"[DEBUG] Method 2 found reasoning_content: {reasoning[:50]}")
                            
                            # Method 3: Via model_dump
                            if not reasoning and hasattr(original_delta, 'model_dump'):
                                try:
                                    delta_dict = original_delta.model_dump(exclude_none=False)
                                    reasoning = delta_dict.get('reasoning_content')
                                    if chunk_index <= 3 and reasoning:
                                        print(f"[DEBUG] Method 3 found reasoning_content: {reasoning[:50]}")
                                except Exception as e:
                                    if chunk_index <= 3:
                                        print(f"[DEBUG] Method 3 error: {e}")
                            
                            # Add to delta if found
                            if reasoning:
                                delta['reasoning_content'] = reasoning
        
        return chunk_dict
