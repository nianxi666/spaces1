
import os
import time
import threading
from gradio_client import Client, handle_file
from project import create_app
from project.database import load_db

def user_task(user_id, api_url, prompt_path):
    print(f"[{user_id}] Connecting...")
    try:
        client = Client(api_url)
        print(f"[{user_id}] Connected. Requesting inference...")
        start = time.time()

        # We assume the server is already running and warm from previous tests
        # We use a short text to try to be quick, but long enough to overlap
        result = client.predict(
            "Same as the voice reference",
            handle_file(prompt_path),
            f"This is user {user_id} testing the queue system.",
            handle_file(prompt_path),
            0.8,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            "",
            False,
            120,
            True, 0.8, 30, 0.8, 0.0, 3, 10.0, 1500,
            api_name="/generate"
        )
        duration = time.time() - start
        print(f"[{user_id}] Finished in {duration:.2f}s. Result: {result}")
    except Exception as e:
        print(f"[{user_id}] Failed: {e}")

def test_concurrency():
    # Setup dummy file
    prompt_path = "sample.wav"
    if not os.path.exists(prompt_path):
        import wave, struct, math
        with wave.open(prompt_path, 'w') as file:
            file.setparams((1, 2, 44100, 44100, 'NONE', 'not compressed'))
            values = [struct.pack('h', int(math.sin(i/100.0)*32767)) for i in range(44100)]
            file.writeframes(b''.join(values))

    # Get URL
    app = create_app()
    with app.app_context():
        db = load_db()
        target_config = None
        for u, d in db.get('users', {}).items():
            for c in d.get('cerebrium_configs', []):
                if c.get('name') == 'Remote Gemini':
                    target_config = c
                    break

        if not target_config:
            print("Config not found.")
            return

        api_url = target_config['api_url']

    print(f"Target API: {api_url}")
    print("Starting 2 concurrent users...")

    t1 = threading.Thread(target=user_task, args=("User1", api_url, prompt_path))
    t2 = threading.Thread(target=user_task, args=("User2", api_url, prompt_path))

    # Start User 1
    t1.start()
    # Wait a small bit to ensure User 1 hits the queue first, then User 2 hits it while U1 is processing
    time.sleep(2)
    t2.start()

    t1.join()
    t2.join()
    print("Concurrency test finished.")

    if os.path.exists(prompt_path):
        os.remove(prompt_path)

if __name__ == "__main__":
    test_concurrency()
