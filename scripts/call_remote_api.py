
import argparse
import os
import shutil
from gradio_client import Client, handle_file
from project.database import load_db
from project import create_app

def run_remote_inference(prompt, output_path, config_name=None, direct_url=None):
    api_url = None

    if direct_url:
        print(f"Using direct URL: {direct_url}")
        api_url = direct_url
    elif config_name:
        print(f"Looking up config: {config_name}...")
        app = create_app()
        with app.app_context():
            db = load_db()
            target_config = None
            for u, d in db.get('users', {}).items():
                for c in d.get('cerebrium_configs', []):
                    if c.get('name') == config_name:
                        target_config = c
                        break
                if target_config:
                    break

            if target_config:
                api_url = target_config['api_url']
            else:
                print(f"Error: GPU configuration '{config_name}' not found.")
                exit(1)
    else:
        # Backward compatibility default
        print("No config specified, defaulting to 'Remote Gemini' lookup...")
        app = create_app()
        with app.app_context():
            db = load_db()
            for u, d in db.get('users', {}).items():
                for c in d.get('cerebrium_configs', []):
                    if c.get('name') == 'Remote Gemini':
                        api_url = c['api_url']
                        break
                if api_url: break

    if not api_url:
        print("Error: Could not determine API URL.")
        exit(1)

    print(f"Connecting to {api_url}...")

    try:
        client = Client(api_url)

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

        print(f"Raw result: {result}")

        if isinstance(result, dict) and 'value' in result:
            src_path = result['value']
        elif isinstance(result, str):
            src_path = result
        elif isinstance(result, tuple):
            src_path = result[1]
        else:
            print("Unknown result format.")
            exit(1)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        shutil.copy(src_path, output_path)
        print(f"Saved output to {output_path}")

    except Exception as e:
        print(f"Inference failed: {e}")
        exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True, help="Text prompt")
    parser.add_argument("--output", default="output/output.wav", help="Output file path")
    parser.add_argument("--config-name", help="Name of the Custom GPU config to use")
    parser.add_argument("--url", help="Direct API URL (overrides config-name)")

    args = parser.parse_args()
    run_remote_inference(args.prompt, args.output, args.config_name, args.url)
