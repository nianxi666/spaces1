
import argparse
import os
import shutil
from gradio_client import Client, handle_file
from project.database import load_db
from project import create_app

def run_remote_inference(prompt, output_path):
    print(f"Connecting to Remote Gemini...")

    # Get URL from DB
    app = create_app()
    with app.app_context():
        db = load_db()
        # Find config again just to be dynamic
        target_config = None
        for u, d in db.get('users', {}).items():
            for c in d.get('cerebrium_configs', []):
                if c.get('name') == 'Remote Gemini':
                    target_config = c
                    break

        if not target_config:
            print("Error: Remote Gemini config not found.")
            return

        api_url = target_config['api_url']

    try:
        client = Client(api_url)

        # We need a dummy wav if the model requires it
        dummy_wav = "dummy_prompt.wav"
        if not os.path.exists(dummy_wav):
            import wave, struct, math
            with wave.open(dummy_wav, 'w') as file:
                file.setparams((1, 2, 44100, 44100, 'NONE', 'not compressed'))
                values = [struct.pack('h', int(math.sin(i/100.0)*32767)) for i in range(44100)]
                file.writeframes(b''.join(values))

        print(f"Sending prompt: {prompt}")
        result = client.predict(
            "Same as the voice reference",
            handle_file(dummy_wav),
            prompt,
            handle_file(dummy_wav),
            0.8,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            "",
            False,
            120,
            True, 0.8, 30, 0.8, 0.0, 3, 10.0, 1500,
            api_name="/generate"
        )

        # Result is a dict or path. Gradio client usually returns path to tmp file.
        # {'visible': True, 'value': '/tmp/...wav', ...} or just path string
        print(f"Raw result: {result}")

        if isinstance(result, dict) and 'value' in result:
            src_path = result['value']
        elif isinstance(result, str):
            src_path = result
        elif isinstance(result, tuple):
            src_path = result[1] # Sometimes it returns (json, path)
        else:
            print("Unknown result format.")
            return

        # Move to output path
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        shutil.copy(src_path, output_path)
        print(f"Saved output to {output_path}")

    except Exception as e:
        print(f"Inference failed: {e}")
        # Create a dummy failure file so pipeline doesn't hang? No, let it fail.
        exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True, help="Text prompt")
    # tasks.py might not pass output filename as arg easily unless we put it in base_command
    # But tasks.py expects the file to be at `predicted_filename`.
    # We will hardcode output path or accept it.
    parser.add_argument("--output", default="output/output.wav", help="Output file path")

    args = parser.parse_args()
    run_remote_inference(args.prompt, args.output)
