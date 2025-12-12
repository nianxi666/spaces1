"""
IndexTTS WebUI with WebSocket Remote Inference Support

This version adds WebSocket connectivity to allow the TTS service
to be accessed remotely via the website's WebSocket system.
"""
import json
import os
import base64
import tempfile

os.environ['HF_HUB_CACHE'] = '/gemini/code/checkpoints/hf_cache'
os.environ['TRANSFORMERS_CACHE'] = '/gemini/code/checkpoints/hf_cache'
os.environ['HF_HOME'] = '/gemini/code/checkpoints/hf_cache'
os.environ['WETEXT_CACHE'] = '/gemini/code/checkpoints/wetext_cache'

import sys
import threading
import time

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

import pandas as pd

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, "indextts"))

print("""================ IndexTTS WebUI =================""")
import argparse
parser = argparse.ArgumentParser(
    description="IndexTTS WebUI with WebSocket Support",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)
parser.add_argument("--verbose", action="store_true", default=False, help="Enable verbose mode")
parser.add_argument("--port", type=int, default=7860, help="Port to run the web UI on")
parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to run the web UI on")
parser.add_argument("--model_dir", type=str, default="/gemini/pretrain/IndexTTS-2", help="Model checkpoints directory")
parser.add_argument("--fp16", action="store_true", default=False, help="Use FP16 for inference if available")
parser.add_argument("--deepspeed", action="store_true", default=False, help="Use DeepSpeed to accelerate if available")
parser.add_argument("--cuda_kernel", action="store_true", default=False, help="Use CUDA kernel for inference if available")
parser.add_argument("--gui_seg_tokens", type=int, default=120, help="GUI: Max tokens per generation segment")

# WebSocket 相关参数
parser.add_argument("--ws_host", type=str, default=None, help="WebSocket server host (e.g., http://localhost:5001)")
parser.add_argument("--ws_space", type=str, default=None, help="WebSocket space name to connect to")
parser.add_argument("--ws_only", action="store_true", default=False, help="Only run WebSocket mode, no Gradio UI")

cmd_args = parser.parse_args()

# Model validation
if not os.path.exists(cmd_args.model_dir):
    print(f"Model directory {cmd_args.model_dir} does not exist. Please download the model first.")
    sys.exit(1)

for file in [
    "bpe.model",
    "gpt.pth",
    "config.yaml",
    "s2mel.pth",
    "wav2vec2bert_stats.pt"
]:
    file_path = os.path.join(cmd_args.model_dir, file)
    if not os.path.exists(file_path):
        print(f"Required file {file_path} does not exist. Please download it.")
        sys.exit(1)

import gradio as gr
from indextts.infer_v2 import IndexTTS2
from tools.i18n.i18n import I18nAuto

i18n = I18nAuto(language="Auto")
MODE = 'local'
tts = IndexTTS2(model_dir=cmd_args.model_dir,
                cfg_path=os.path.join(cmd_args.model_dir, "config.yaml"),
                use_fp16=cmd_args.fp16,
                use_deepspeed=cmd_args.deepspeed,
                use_cuda_kernel=cmd_args.cuda_kernel,
                )

# 支持的语言列表
LANGUAGES = {
    "中文": "zh_CN",
    "English": "en_US"
}
EMO_CHOICES = [i18n("与音色参考音频相同"),
                i18n("使用情感参考音频"),
                i18n("使用情感向量控制"),
                i18n("使用情感描述文本控制")]
os.makedirs("outputs/tasks", exist_ok=True)
os.makedirs("prompts", exist_ok=True)

MAX_LENGTH_TO_USE_SPEED = 70

# Load example cases
example_cases = []
if os.path.exists("examples/cases.jsonl"):
    with open("examples/cases.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            example = json.loads(line)
            if example.get("emo_audio", None):
                emo_audio_path = os.path.join("examples", example["emo_audio"])
            else:
                emo_audio_path = None
            example_cases.append([os.path.join("examples", example.get("prompt_audio", "sample_prompt.wav")),
                                  EMO_CHOICES[example.get("emo_mode", 0)],
                                  example.get("text"),
                                  emo_audio_path,
                                  example.get("emo_weight", 1.0),
                                  example.get("emo_text", ""),
                                  example.get("emo_vec_1", 0),
                                  example.get("emo_vec_2", 0),
                                  example.get("emo_vec_3", 0),
                                  example.get("emo_vec_4", 0),
                                  example.get("emo_vec_5", 0),
                                  example.get("emo_vec_6", 0),
                                  example.get("emo_vec_7", 0),
                                  example.get("emo_vec_8", 0)]
                                  )


# ============================================================
# WebSocket Client for Remote Inference
# ============================================================

class WebSocketInferenceClient:
    """WebSocket client for remote inference via website."""
    
    def __init__(self, host, space_name):
        self.host = host
        self.space_name = space_name
        self.sio = None
        self.connected = False
        self.registered = False
        self.running = True
        
    def start(self):
        """Start WebSocket connection in a separate thread."""
        try:
            import socketio
        except ImportError:
            print("[WebSocket] Error: python-socketio not installed")
            print("[WebSocket] Run: pip install python-socketio[client]")
            return False
        
        self.sio = socketio.Client(
            reconnection=True,
            reconnection_attempts=0,  # Infinite retries
            reconnection_delay=3,
            reconnection_delay_max=30
        )
        
        self._setup_handlers()
        
        try:
            print(f"[WebSocket] Connecting to {self.host}...")
            self.sio.connect(self.host, transports=['websocket', 'polling'])
            return True
        except Exception as e:
            print(f"[WebSocket] Connection failed: {e}")
            return False
    
    def _setup_handlers(self):
        @self.sio.event
        def connect():
            self.connected = True
            print(f"[WebSocket] ✓ Connected to server")
            print(f"[WebSocket] Registering for space: {self.space_name}")
            self.sio.emit('register_remote', {'space_name': self.space_name})
        
        @self.sio.event
        def disconnect():
            self.connected = False
            self.registered = False
            print(f"[WebSocket] Disconnected from server")
        
        @self.sio.on('register_result')
        def on_register_result(data):
            if data.get('success'):
                self.registered = True
                print(f"[WebSocket] ✓ Successfully registered for space: {self.space_name}")
                print(f"[WebSocket] Ready to receive inference requests...")
            else:
                print(f"[WebSocket] ✗ Registration failed: {data.get('error')}")
        
        @self.sio.on('inference_request')
        def on_inference_request(data):
            """Handle incoming inference request."""
            request_id = data.get('request_id')
            user = data.get('user')
            request_data = data.get('data', {})
            
            print(f"\n[WebSocket] ═══════════════════════════════════════")
            print(f"[WebSocket] 收到推理请求!")
            print(f"[WebSocket] Request ID: {request_id}")
            print(f"[WebSocket] User: {user}")
            
            # Process in a thread to avoid blocking WebSocket
            thread = threading.Thread(
                target=self._process_request,
                args=(request_id, user, request_data)
            )
            thread.daemon = True
            thread.start()
    
    def _process_request(self, request_id, user, request_data):
        """Process TTS inference request."""
        try:
            prompt = request_data.get('prompt', '')
            prompt_audio_base64 = request_data.get('audio')  # Base64 encoded audio
            
            print(f"[WebSocket] Processing TTS request...")
            print(f"[WebSocket] Text: {prompt[:100]}...")
            
            # Handle prompt audio (reference voice)
            prompt_audio_path = None
            if prompt_audio_base64:
                # Decode base64 audio and save to temp file
                try:
                    # Remove data URL prefix if present
                    if ',' in prompt_audio_base64:
                        prompt_audio_base64 = prompt_audio_base64.split(',')[1]
                    
                    audio_data = base64.b64decode(prompt_audio_base64)
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                        f.write(audio_data)
                        prompt_audio_path = f.name
                    print(f"[WebSocket] Received reference audio: {len(audio_data)} bytes")
                except Exception as e:
                    print(f"[WebSocket] Failed to decode audio: {e}")
            
            # Use default prompt audio if none provided
            if not prompt_audio_path:
                default_prompt = "examples/sample_prompt.wav"
                if os.path.exists(default_prompt):
                    prompt_audio_path = default_prompt
                    print(f"[WebSocket] Using default prompt audio")
                else:
                    # Try to find any prompt audio
                    prompts_dir = "prompts"
                    if os.path.exists(prompts_dir):
                        files = [f for f in os.listdir(prompts_dir) if f.endswith('.wav')]
                        if files:
                            prompt_audio_path = os.path.join(prompts_dir, files[0])
                            print(f"[WebSocket] Using prompt: {prompt_audio_path}")
            
            if not prompt_audio_path or not os.path.exists(prompt_audio_path):
                raise ValueError("No reference audio available for TTS")
            
            if not prompt or not prompt.strip():
                raise ValueError("No text provided for TTS")
            
            # Generate output path
            output_path = os.path.join("outputs", f"ws_{request_id[:8]}_{int(time.time())}.wav")
            
            # Run TTS inference
            print(f"[WebSocket] Running TTS inference...")
            start_time = time.time()
            
            output = tts.infer(
                spk_audio_prompt=prompt_audio_path,
                text=prompt,
                output_path=output_path,
                verbose=cmd_args.verbose,
                max_text_tokens_per_segment=120
            )
            
            elapsed = time.time() - start_time
            print(f"[WebSocket] ✓ TTS completed in {elapsed:.2f}s")
            
            # Read generated audio and encode to base64
            if output and os.path.exists(output):
                with open(output, 'rb') as f:
                    audio_bytes = f.read()
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                
                result = {
                    'type': 'audio',
                    'audio_base64': audio_base64,
                    'audio_format': 'wav',
                    'duration_seconds': elapsed,
                    'text_length': len(prompt),
                    'message': f'TTS 生成成功！处理时间: {elapsed:.2f}秒'
                }
                
                self.sio.emit('inference_result', {
                    'request_id': request_id,
                    'success': True,
                    'result': result
                })
                
                print(f"[WebSocket] ✓ Result sent! Audio size: {len(audio_bytes)} bytes")
            else:
                raise ValueError("TTS output file not generated")
            
        except Exception as e:
            error_msg = str(e)
            print(f"[WebSocket] ✗ Error: {error_msg}")
            
            self.sio.emit('inference_result', {
                'request_id': request_id,
                'success': False,
                'error': error_msg
            })
        
        finally:
            # Cleanup temp files
            if prompt_audio_path and prompt_audio_path.startswith(tempfile.gettempdir()):
                try:
                    os.remove(prompt_audio_path)
                except:
                    pass
        
        print(f"[WebSocket] ═══════════════════════════════════════\n")
    
    def wait(self):
        """Wait for WebSocket events."""
        if self.sio:
            self.sio.wait()
    
    def stop(self):
        """Stop the WebSocket client."""
        self.running = False
        if self.sio and self.sio.connected:
            self.sio.disconnect()


# ============================================================
# Original Gradio Functions
# ============================================================

def gen_single(emo_control_method, prompt, text,
               emo_ref_path, emo_weight,
               vec1, vec2, vec3, vec4, vec5, vec6, vec7, vec8,
               emo_text, emo_random,
               max_text_tokens_per_segment=120,
               *args, progress=gr.Progress()):
    output_path = None
    if not output_path:
        output_path = os.path.join("outputs", f"spk_{int(time.time())}.wav")
    # set gradio progress
    tts.gr_progress = progress
    do_sample, top_p, top_k, temperature, \
        length_penalty, num_beams, repetition_penalty, max_mel_tokens = args
    kwargs = {
        "do_sample": bool(do_sample),
        "top_p": float(top_p),
        "top_k": int(top_k) if int(top_k) > 0 else None,
        "temperature": float(temperature),
        "length_penalty": float(length_penalty),
        "num_beams": num_beams,
        "repetition_penalty": float(repetition_penalty),
        "max_mel_tokens": int(max_mel_tokens),
    }
    if type(emo_control_method) is not int:
        emo_control_method = emo_control_method.value
    if emo_control_method == 0:
        emo_ref_path = None
        emo_weight = 1.0
    if emo_control_method == 1:
        pass
    if emo_control_method == 2:
        vec = [vec1, vec2, vec3, vec4, vec5, vec6, vec7, vec8]
        if sum(vec) > 1.5:
            gr.Warning(i18n("情感向量之和不能超过1.5，请调整后重试。"))
            return
    else:
        vec = None

    if emo_text == "":
        emo_text = None

    print(f"Emo control mode:{emo_control_method},weight:{emo_weight},vec:{vec}")
    output = tts.infer(spk_audio_prompt=prompt, text=text,
                       output_path=output_path,
                       emo_audio_prompt=emo_ref_path, emo_alpha=emo_weight,
                       emo_vector=vec,
                       use_emo_text=(emo_control_method == 3), emo_text=emo_text, use_random=emo_random,
                       verbose=cmd_args.verbose,
                       max_text_tokens_per_segment=int(max_text_tokens_per_segment),
                       **kwargs)
    return gr.update(value=output, visible=True)


def update_prompt_audio():
    update_button = gr.update(interactive=True)
    return update_button


# ============================================================
# Main Entry Point
# ============================================================

def create_gradio_ui():
    """Create and return the Gradio UI."""
    with gr.Blocks(title="IndexTTS Demo") as demo:
        mutex = threading.Lock()
        gr.HTML('''
        <h2><center>IndexTTS2: A Breakthrough in Emotionally Expressive and Duration-Controlled Auto-Regressive Zero-Shot Text-to-Speech</h2>
    <p align="center">
    <a href='https://arxiv.org/abs/2506.21619'><img src='https://img.shields.io/badge/ArXiv-2506.21619-red'></a>
    </p>
        ''')

        with gr.Tab(i18n("音频生成")):
            with gr.Row():
                os.makedirs("prompts", exist_ok=True)
                prompt_audio = gr.Audio(label=i18n("音色参考音频"), key="prompt_audio",
                                        sources=["upload", "microphone"], type="filepath")
                prompt_list = os.listdir("prompts")
                default = ''
                if prompt_list:
                    default = prompt_list[0]
                with gr.Column():
                    input_text_single = gr.TextArea(label=i18n("文本"), key="input_text_single",
                                                    placeholder=i18n("请输入目标文本"),
                                                    info=f"{i18n('当前模型版本')}{tts.model_version or '1.0'}")
                    gen_button = gr.Button(i18n("生成语音"), key="gen_button", interactive=True)
                output_audio = gr.Audio(label=i18n("生成结果"), visible=True, key="output_audio")
            with gr.Accordion(i18n("功能设置")):
                with gr.Row():
                    emo_control_method = gr.Radio(
                        choices=EMO_CHOICES,
                        type="index",
                        value=EMO_CHOICES[0], label=i18n("情感控制方式"))

            with gr.Group(visible=False) as emotion_reference_group:
                with gr.Row():
                    emo_upload = gr.Audio(label=i18n("上传情感参考音频"), type="filepath")

            with gr.Row(visible=False) as emotion_randomize_group:
                emo_random = gr.Checkbox(label=i18n("情感随机采样"), value=False)

            with gr.Group(visible=False) as emotion_vector_group:
                with gr.Row():
                    with gr.Column():
                        vec1 = gr.Slider(label=i18n("喜"), minimum=0.0, maximum=1.4, value=0.0, step=0.05)
                        vec2 = gr.Slider(label=i18n("怒"), minimum=0.0, maximum=1.4, value=0.0, step=0.05)
                        vec3 = gr.Slider(label=i18n("哀"), minimum=0.0, maximum=1.4, value=0.0, step=0.05)
                        vec4 = gr.Slider(label=i18n("惧"), minimum=0.0, maximum=1.4, value=0.0, step=0.05)
                    with gr.Column():
                        vec5 = gr.Slider(label=i18n("厌恶"), minimum=0.0, maximum=1.4, value=0.0, step=0.05)
                        vec6 = gr.Slider(label=i18n("低落"), minimum=0.0, maximum=1.4, value=0.0, step=0.05)
                        vec7 = gr.Slider(label=i18n("惊喜"), minimum=0.0, maximum=1.4, value=0.0, step=0.05)
                        vec8 = gr.Slider(label=i18n("平静"), minimum=0.0, maximum=1.4, value=0.0, step=0.05)

            with gr.Group(visible=False) as emo_text_group:
                with gr.Row():
                    emo_text = gr.Textbox(label=i18n("情感描述文本"),
                                          placeholder=i18n("请输入情绪描述（或留空以自动使用目标文本作为情绪描述）"),
                                          value="", info=i18n("例如：高兴，愤怒，悲伤等"))

            with gr.Row(visible=False) as emo_weight_group:
                emo_weight = gr.Slider(label=i18n("情感权重"), minimum=0.0, maximum=1.6, value=0.8, step=0.01)

            with gr.Accordion(i18n("高级生成参数设置"), open=False):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown(
                            f"**{i18n('GPT2 采样设置')}** _{i18n('参数会影响音频多样性和生成速度详见')} [Generation strategies](https://huggingface.co/docs/transformers/main/en/generation_strategies)._")
                        with gr.Row():
                            do_sample = gr.Checkbox(label="do_sample", value=True, info=i18n("是否进行采样"))
                            temperature = gr.Slider(label="temperature", minimum=0.1, maximum=2.0, value=0.8, step=0.1)
                        with gr.Row():
                            top_p = gr.Slider(label="top_p", minimum=0.0, maximum=1.0, value=0.8, step=0.01)
                            top_k = gr.Slider(label="top_k", minimum=0, maximum=100, value=30, step=1)
                            num_beams = gr.Slider(label="num_beams", value=3, minimum=1, maximum=10, step=1)
                        with gr.Row():
                            repetition_penalty = gr.Number(label="repetition_penalty", precision=None, value=10.0,
                                                           minimum=0.1, maximum=20.0, step=0.1)
                            length_penalty = gr.Number(label="length_penalty", precision=None, value=0.0, minimum=-2.0,
                                                       maximum=2.0, step=0.1)
                        max_mel_tokens = gr.Slider(label="max_mel_tokens", value=1500, minimum=50,
                                                   maximum=tts.cfg.gpt.max_mel_tokens, step=10,
                                                   info=i18n("生成Token最大数量，过小导致音频被截断"),
                                                   key="max_mel_tokens")
                    with gr.Column(scale=2):
                        gr.Markdown(f'**{i18n("分句设置")}** _{i18n("参数会影响音频质量和生成速度")}_')
                        with gr.Row():
                            initial_value = max(20, min(tts.cfg.gpt.max_text_tokens, cmd_args.gui_seg_tokens))
                            max_text_tokens_per_segment = gr.Slider(
                                label=i18n("分句最大Token数"), value=initial_value, minimum=20,
                                maximum=tts.cfg.gpt.max_text_tokens, step=2, key="max_text_tokens_per_segment",
                                info=i18n("建议80~200之间，值越大，分句越长；值越小，分句越碎；过小过大都可能导致音频质量不高"),
                            )
                        with gr.Accordion(i18n("预览分句结果"), open=True) as segments_settings:
                            segments_preview = gr.Dataframe(
                                headers=[i18n("序号"), i18n("分句内容"), i18n("Token数")],
                                key="segments_preview",
                                wrap=True,
                            )
                advanced_params = [
                    do_sample, top_p, top_k, temperature,
                    length_penalty, num_beams, repetition_penalty, max_mel_tokens,
                ]

            if len(example_cases) > 0:
                gr.Examples(
                    examples=example_cases,
                    examples_per_page=20,
                    inputs=[prompt_audio,
                            emo_control_method,
                            input_text_single,
                            emo_upload,
                            emo_weight,
                            emo_text,
                            vec1, vec2, vec3, vec4, vec5, vec6, vec7, vec8]
                )

        def on_input_text_change(text, max_text_tokens_per_segment):
            if text and len(text) > 0:
                text_tokens_list = tts.tokenizer.tokenize(text)
                segments = tts.tokenizer.split_segments(text_tokens_list,
                                                        max_text_tokens_per_segment=int(max_text_tokens_per_segment))
                data = []
                for i, s in enumerate(segments):
                    segment_str = ''.join(s)
                    tokens_count = len(s)
                    data.append([i, segment_str, tokens_count])
                return {
                    segments_preview: gr.update(value=data, visible=True, type="array"),
                }
            else:
                df = pd.DataFrame([], columns=[i18n("序号"), i18n("分句内容"), i18n("Token数")])
                return {
                    segments_preview: gr.update(value=df),
                }

        def on_method_select(emo_control_method):
            if emo_control_method == 1:
                return (gr.update(visible=True),
                        gr.update(visible=False),
                        gr.update(visible=False),
                        gr.update(visible=False),
                        gr.update(visible=True)
                        )
            elif emo_control_method == 2:
                return (gr.update(visible=False),
                        gr.update(visible=True),
                        gr.update(visible=True),
                        gr.update(visible=False),
                        gr.update(visible=True)
                        )
            elif emo_control_method == 3:
                return (gr.update(visible=False),
                        gr.update(visible=True),
                        gr.update(visible=False),
                        gr.update(visible=True),
                        gr.update(visible=True)
                        )
            else:
                return (gr.update(visible=False),
                        gr.update(visible=False),
                        gr.update(visible=False),
                        gr.update(visible=False),
                        gr.update(visible=False)
                        )

        emo_control_method.select(on_method_select,
                                  inputs=[emo_control_method],
                                  outputs=[emotion_reference_group,
                                           emotion_randomize_group,
                                           emotion_vector_group,
                                           emo_text_group,
                                           emo_weight_group]
                                  )

        input_text_single.change(
            on_input_text_change,
            inputs=[input_text_single, max_text_tokens_per_segment],
            outputs=[segments_preview]
        )
        max_text_tokens_per_segment.change(
            on_input_text_change,
            inputs=[input_text_single, max_text_tokens_per_segment],
            outputs=[segments_preview]
        )
        prompt_audio.upload(update_prompt_audio,
                            inputs=[],
                            outputs=[gen_button])

        gen_button.click(gen_single,
                         inputs=[emo_control_method, prompt_audio, input_text_single, emo_upload, emo_weight,
                                 vec1, vec2, vec3, vec4, vec5, vec6, vec7, vec8,
                                 emo_text, emo_random,
                                 max_text_tokens_per_segment,
                                 *advanced_params,
                                 ],
                         outputs=[output_audio])

    return demo


if __name__ == "__main__":
    ws_client = None
    
    # Check if WebSocket mode is requested
    if cmd_args.ws_host and cmd_args.ws_space:
        print("\n" + "="*60)
        print("  IndexTTS WebSocket Mode")
        print("="*60)
        print(f"  Server: {cmd_args.ws_host}")
        print(f"  Space:  {cmd_args.ws_space}")
        print("="*60 + "\n")
        
        ws_client = WebSocketInferenceClient(cmd_args.ws_host, cmd_args.ws_space)
        
        if ws_client.start():
            # Give time for registration
            time.sleep(2)
            
            if cmd_args.ws_only:
                # WebSocket only mode - no Gradio
                print("[WebSocket] Running in WebSocket-only mode")
                print("[WebSocket] Press Ctrl+C to stop")
                try:
                    ws_client.wait()
                except KeyboardInterrupt:
                    print("\n[WebSocket] Shutting down...")
                    ws_client.stop()
                sys.exit(0)
        else:
            print("[WebSocket] Failed to connect, falling back to Gradio-only mode")
    
    # Run Gradio UI
    demo = create_gradio_ui()
    
    # Start WebSocket in background if connected
    if ws_client and ws_client.connected:
        print("[WebSocket] Running alongside Gradio UI")
        ws_thread = threading.Thread(target=ws_client.wait, daemon=True)
        ws_thread.start()
    
    demo.queue(20)
    demo.launch(server_name=cmd_args.host, server_port=cmd_args.port)
