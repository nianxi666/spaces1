
import os
import sys
import json
import threading
import time
import argparse
import requests
from flask import Flask, request, jsonify

# --- IndexTTS Setup (Copied from user snippet) ---
# Ensure environment variables are set before imports
os.environ['HF_HUB_CACHE'] = './checkpoints/hf_cache'
os.environ['TRANSFORMERS_CACHE'] = './checkpoints/hf_cache'
os.environ['HF_HOME'] = './checkpoints/hf_cache'
os.environ['WETEXT_CACHE'] = './checkpoints/wetext_cache'

# Suppress warnings
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Ensure paths
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, "indextts"))

print("""================ IndexTTS Remote Worker =================""")

# Argument Parsing
parser = argparse.ArgumentParser(description="IndexTTS Remote Worker for PumpkinAI")
parser.add_argument("--port", type=int, default=7860, help="Port to run the API on")
parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to run the API on")
parser.add_argument("--model_dir", type=str, default="./pretrain/IndexTTS-2", help="Model checkpoints directory")
parser.add_argument("--fp16", action="store_true", default=False, help="Use FP16")
parser.add_argument("--deepspeed", action="store_true", default=False, help="Use DeepSpeed")
parser.add_argument("--cuda_kernel", action="store_true", default=False, help="Use CUDA kernel")
parser.add_argument("--verbose", action="store_true", default=False)

# Allow parsing from command line if running standalone
# If imported, args might need to be defaulted
try:
    cmd_args = parser.parse_args()
except:
    cmd_args = parser.parse_args([])

# Check Model Existence
if not os.path.exists(cmd_args.model_dir):
    print(f"Model directory {cmd_args.model_dir} does not exist. Please download the model first.")
    sys.exit(1)

# Import IndexTTS modules
try:
    from indextts.infer_v2 import IndexTTS2
    from tools.i18n.i18n import I18nAuto
except ImportError as e:
    print(f"Error importing IndexTTS modules: {e}")
    print("Please ensure this script is placed in the root of the IndexTTS repository.")
    sys.exit(1)

# Initialize Model
print("Initializing IndexTTS Model...")
i18n = I18nAuto(language="Auto")
tts = IndexTTS2(
    model_dir=cmd_args.model_dir,
    cfg_path=os.path.join(cmd_args.model_dir, "config.yaml"),
    use_fp16=cmd_args.fp16,
    use_deepspeed=cmd_args.deepspeed,
    use_cuda_kernel=cmd_args.cuda_kernel,
)
print("Model Initialized.")

# --- Flask Server ---
app = Flask(__name__)

def download_file(url, save_path):
    """Helper to download a file from a URL."""
    try:
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(save_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return True
    except Exception as e:
        print(f"Error downloading file from {url}: {e}")
        return False

@app.route('/api/run', methods=['POST'])
def run_inference():
    """
    Endpoint called by PumpkinAI VPS.
    Payload:
    {
        "task_id": "...",
        "username": "...",
        "prompt": "Text to speak",
        "params": {
            "speaker_audio_url": "...",
            "emo_control_method": 0, # 0, 1, 2, 3
            "emo_weight": 1.0,
            "emo_text": "",
            "vec1": 0.0, ... "vec8": 0.0,
            "max_text_tokens_per_segment": 120
        },
        "presigned_url": "...",
        "s3_object_name": "..."
    }
    """
    try:
        data = request.json
        print(f"Received task {data.get('task_id')} for user {data.get('username')}")

        # 1. Parse Parameters
        text = data.get('prompt', '')
        params = data.get('params', {})
        presigned_url = data.get('presigned_url')

        if not text:
            return jsonify({"status": "failed", "error": "No text provided"}), 400

        # Create temporary directory for processing
        temp_dir = os.path.join("temp", data.get('task_id', str(time.time())))
        os.makedirs(temp_dir, exist_ok=True)

        # 2. Handle Speaker/Prompt Audio
        # 'prompt_audio' in IndexTTS refers to the reference speaker audio
        speaker_audio_url = params.get('speaker_audio_url')
        prompt_audio_path = None

        if speaker_audio_url:
            prompt_audio_path = os.path.join(temp_dir, "speaker_ref.wav")
            if not download_file(speaker_audio_url, prompt_audio_path):
                return jsonify({"status": "failed", "error": "Failed to download speaker audio"}), 500
        else:
            # Fallback to a default sample if none provided (or handle error)
            # For now, let's assume a default exists or we use the first one found
            default_prompt_dir = "prompts"
            if os.path.exists(default_prompt_dir) and os.listdir(default_prompt_dir):
                prompt_audio_path = os.path.join(default_prompt_dir, os.listdir(default_prompt_dir)[0])
            else:
                # If absolute fallback is needed
                prompt_audio_path = os.path.join("examples", "sample_prompt.wav")

        if not os.path.exists(prompt_audio_path):
             return jsonify({"status": "failed", "error": "No speaker reference audio available"}), 400

        # 3. Handle Emotion Parameters
        emo_control_method = int(params.get('emo_control_method', 0))
        emo_weight = float(params.get('emo_weight', 1.0))
        emo_text = params.get('emo_text', '')

        # Emo Vectors
        vecs = [
            float(params.get(f'vec{i}', 0.0)) for i in range(1, 9)
        ]

        max_tokens = int(params.get('max_text_tokens_per_segment', 120))

        # 4. Run Inference (Logic from gen_single)
        # Adapt gen_single logic here

        output_path = os.path.join(temp_dir, "output.wav")

        emo_ref_path = prompt_audio_path # Default to speaker audio
        # If method 1 (Reference Audio), user might upload a DIFFERENT file for emotion?
        # The provided UI has 'emo_upload'.
        emo_upload_url = params.get('emo_upload_url')
        if emo_control_method == 1 and emo_upload_url:
             emo_ref_path = os.path.join(temp_dir, "emo_ref.wav")
             download_file(emo_upload_url, emo_ref_path)

        # Prepare vector argument
        vec_arg = None
        if emo_control_method == 2:
            vec_arg = vecs
            if sum(vec_arg) > 1.5:
                print("Warning: Vector sum > 1.5")

        if emo_control_method == 0:
            emo_ref_path = None
            emo_weight = 1.0

        kwargs = {
            "do_sample": True,
            "top_p": 0.8,
            "top_k": 30,
            "temperature": 0.8,
            "length_penalty": 0.0,
            "num_beams": 3,
            "repetition_penalty": 10.0,
            "max_mel_tokens": 1500
        }

        print(f"Running inference: Text='{text[:20]}...', EmoMode={emo_control_method}")

        # Use tts.infer
        # Note: tts.infer might not be thread-safe if it uses global state, but Flask is threaded.
        # IndexTTS seems to use a lock in the demo, we should probably lock here too if needed.
        # But this script is likely single-worker per process or we rely on torch.

        output_result = tts.infer(
            spk_audio_prompt=prompt_audio_path,
            text=text,
            output_path=output_path,
            emo_audio_prompt=emo_ref_path,
            emo_alpha=emo_weight,
            emo_vector=vec_arg,
            use_emo_text=(emo_control_method == 3),
            emo_text=emo_text if emo_text else None,
            use_random=False,
            verbose=cmd_args.verbose,
            max_text_tokens_per_segment=max_tokens,
            **kwargs
        )

        # 5. Upload Result
        if os.path.exists(output_path) and presigned_url:
            print(f"Uploading result to {presigned_url.split('?')[0]}...")
            with open(output_path, 'rb') as f:
                upload_resp = requests.put(presigned_url, data=f)
                if upload_resp.status_code == 200:
                    print("Upload successful.")
                else:
                    print(f"Upload failed: {upload_resp.status_code} {upload_resp.text}")
                    return jsonify({"status": "failed", "error": "S3 Upload failed"}), 500
        elif not os.path.exists(output_path):
             return jsonify({"status": "failed", "error": "Inference did not produce output file"}), 500

        return jsonify({
            "status": "success",
            "logs": "Inference completed successfully."
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "failed", "error": str(e)}), 500

if __name__ == "__main__":
    print(f"Starting Worker API on {cmd_args.host}:{cmd_args.port}")
    app.run(host=cmd_args.host, port=cmd_args.port)
