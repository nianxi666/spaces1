
import os
import time
import argparse
from project import create_app
from project.database import load_db
from gradio_client import Client, handle_file

def test_remote_gpu_api(timeout=300):
    """
    Test script to verify connection to the configured 'Remote Gemini' GPU.
    This script sends a request to the remote API and waits for a response.
    """

    # Generate dummy wav if missing
    dummy_wav = "sample.wav"
    if not os.path.exists(dummy_wav):
        print("Generating dummy sample.wav...")
        import wave, struct, math
        with wave.open(dummy_wav, 'w') as file:
            file.setparams((1, 2, 44100, 44100, 'NONE', 'not compressed'))
            values = [struct.pack('h', int(math.sin(i/100.0)*32767)) for i in range(44100)]
            file.writeframes(b''.join(values))

    app = create_app()
    with app.app_context():
        # Retrieve config
        db = load_db()
        target_config = None
        for username, user_data in db.get('users', {}).items():
            configs = user_data.get('cerebrium_configs', [])
            for config in configs:
                if config.get('name') == 'Remote Gemini':
                    target_config = config
                    break
            if target_config:
                break

        if not target_config:
            print("Error: 'Remote Gemini' configuration not found in database.")
            return

        api_url = target_config.get('api_url')
        print(f"Connecting to remote GPU at: {api_url}")

        try:
            client = Client(api_url)
            print("Successfully connected to Gradio API.")

            print(f"Sending prediction request (timeout={timeout}s)...")

            start_time = time.time()
            # Using handle_file for compatibility with newer Gradio servers
            # Note: This call may block for a long time if the model is loading or processing.
            result = client.predict(
                "Same as the voice reference",
                handle_file(dummy_wav),
                "Hello, this is a test of the remote inference system.",
                handle_file(dummy_wav),
                0.8,
                0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                "",
                False,
                120,
                True, 0.8, 30, 0.8, 0.0, 3, 10.0, 1500,
                api_name="/generate"
            )
            end_time = time.time()

            print(f"Prediction successful in {end_time - start_time:.2f}s.")
            print(f"Result saved to: {result}")

        except Exception as e:
            print(f"API Request Failed: {e}")
            print("Note: Timeouts are common during the first request if the remote model is cold-starting.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test remote API.')
    parser.add_argument('--timeout', type=int, default=300, help='Request timeout in seconds')
    args = parser.parse_args()

    test_remote_gpu_api(timeout=args.timeout)

    # Cleanup
    if os.path.exists("sample.wav"):
        os.remove("sample.wav")
