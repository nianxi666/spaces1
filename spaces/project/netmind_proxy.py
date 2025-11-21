import time
import random
import threading
from openai import OpenAI, APIError, AuthenticationError, RateLimitError
from flask import current_app

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

    def chat_completion(self, db, messages, model, stream=False):
        settings = self._get_settings(db)
        base_url = settings.get('base_url', 'https://inference-api.netmind.ai/v1')
        ad_suffix = settings.get('ad_suffix', '')

        key = self._get_next_key(db)
        if not key:
            raise Exception("No NetMind API keys configured.")

        # Max retries based on the number of keys available
        max_retries = len(self._get_valid_keys(db))
        attempts = 0
        last_error = None

        while attempts < max_retries:
            try:
                client = OpenAI(
                    api_key=key,
                    base_url=base_url
                )

                if stream:
                    return self._handle_stream(client, messages, model, ad_suffix)
                else:
                    return self._handle_sync(client, messages, model, ad_suffix)

            except (AuthenticationError, RateLimitError) as e:
                print(f"NetMind API Error (Key: {key[:4]}...): {e}")
                last_error = e
                attempts += 1
                key = self._get_next_key(db, exclude_key=key)
                if not key:
                     break # Should not happen if max_retries is correct
                time.sleep(0.5) # Brief pause before retry
            except Exception as e:
                 # Other errors (e.g. validation, network) might not be solved by rotating keys
                 print(f"NetMind Unexpected Error: {e}")
                 raise e

        raise last_error or Exception("All NetMind keys failed.")

    def _handle_sync(self, client, messages, model, ad_suffix):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=False
        )

        # Inject Ad
        if ad_suffix and response.choices:
            content = response.choices[0].message.content or ""
            response.choices[0].message.content = content + ad_suffix

        return response

    def _handle_stream(self, client, messages, model, ad_suffix):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True
        )

        # We yield raw strings formatted as SSE data for the client
        # OpenAI client yields chunks, we need to wrap them

        for chunk in response:
            # Directly yield the chunk logic?
            # The client expects the object.
            # If we return a generator, Flask will stream it.
            # But we need to intercept [DONE] to inject ad.

            content = chunk.choices[0].delta.content
            if content:
                 yield f"data: {chunk.model_dump_json()}\n\n"
            else:
                 # Keep alive or empty chunks
                 yield f"data: {chunk.model_dump_json()}\n\n"

        # Inject Ad as a separate chunk before DONE
        if ad_suffix:
            import json
            import time

            # Construct a fake chunk for the ad
            ad_chunk = {
                "id": "ad-" + str(int(time.time())),
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
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
            yield f"data: {json.dumps(ad_chunk)}\n\n"

        yield "data: [DONE]\n\n"
