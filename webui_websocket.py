# -*- coding: utf-8 -*-
"""
更新后的 webui.py - 使用 WebSocket 上传到S3
将此文件替换远程服务器上的原webui.py

WebSocket 优势：
1. 实时双向通信
2. 连接保持，无需每次建立新连接
3. 支持大文件分块传输
4. 实时进度反馈
"""

import json
import os
import base64
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

# WebSocket 相关
try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    print("⚠️ websocket-client not installed. Run: pip install websocket-client")

import requests  # 备用 HTTP 方式

# ===== WebSocket 上传配置 =====
# 替换为您的实际值
WEBSOCKET_URL = "wss://your-website.com/ws/upload"  # WebSocket 端点
RELAY_API_URL = "https://your-website.com/api/relay-to-s3"  # HTTP 备用端点
API_KEY = "YOUR_API_KEY_HERE"  # 在您的网站个人资料页面获取

# 分块大小 (64KB)
CHUNK_SIZE = 64 * 1024

# 线程池执行器，用于异步上传
executor = ThreadPoolExecutor(max_workers=2)


class WebSocketUploader:
    """WebSocket 文件上传器"""
    
    def __init__(self, ws_url, api_key):
        self.ws_url = ws_url
        self.api_key = api_key
        self.ws = None
        self.connected = False
        self.upload_result = None
        self.upload_complete = threading.Event()
        
    def connect(self):
        """建立 WebSocket 连接"""
        if self.connected and self.ws:
            return True
            
        try:
            # 创建 WebSocket 连接，带认证头
            self.ws = websocket.create_connection(
                self.ws_url,
                header=[f"Authorization: Bearer {self.api_key}"],
                timeout=30
            )
            self.connected = True
            print(f"✅ WebSocket connected to {self.ws_url}")
            return True
        except Exception as e:
            print(f"❌ WebSocket connection failed: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """关闭 WebSocket 连接"""
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
            self.ws = None
            self.connected = False
    
    def upload_file(self, file_path, object_name=None):
        """
        通过 WebSocket 上传文件
        
        Args:
            file_path: 本地文件路径
            object_name: 在S3中的文件名
            
        Returns:
            str: S3公共URL，如果失败则返回None
        """
        if object_name is None:
            object_name = os.path.basename(file_path)
        
        # 确保连接
        if not self.connect():
            print("⚠️ WebSocket unavailable, falling back to HTTP")
            return None
        
        try:
            file_size = os.path.getsize(file_path)
            print(f"📤 Uploading {object_name} ({file_size} bytes) via WebSocket...")
            
            # 发送开始上传消息
            start_msg = {
                "action": "start_upload",
                "filename": object_name,
                "file_size": file_size,
                "content_type": self._get_content_type(file_path)
            }
            self.ws.send(json.dumps(start_msg))
            
            # 等待服务器确认
            response = json.loads(self.ws.recv())
            if response.get("status") != "ready":
                print(f"❌ Server not ready: {response.get('error', 'Unknown error')}")
                return None
            
            upload_id = response.get("upload_id")
            print(f"📋 Upload ID: {upload_id}")
            
            # 分块读取并发送文件
            chunk_index = 0
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    
                    # 将二进制数据编码为 base64
                    chunk_b64 = base64.b64encode(chunk).decode('utf-8')
                    
                    chunk_msg = {
                        "action": "upload_chunk",
                        "upload_id": upload_id,
                        "chunk_index": chunk_index,
                        "data": chunk_b64,
                        "is_last": len(chunk) < CHUNK_SIZE
                    }
                    self.ws.send(json.dumps(chunk_msg))
                    
                    # 等待确认
                    ack = json.loads(self.ws.recv())
                    if ack.get("status") != "ok":
                        print(f"❌ Chunk {chunk_index} failed: {ack.get('error')}")
                        return None
                    
                    chunk_index += 1
                    progress = min(100, int((chunk_index * CHUNK_SIZE / file_size) * 100))
                    print(f"   Progress: {progress}%", end='\r')
            
            print()  # 换行
            
            # 发送完成消息
            complete_msg = {
                "action": "complete_upload",
                "upload_id": upload_id
            }
            self.ws.send(json.dumps(complete_msg))
            
            # 等待最终结果
            result = json.loads(self.ws.recv())
            if result.get("status") == "success":
                public_url = result.get("public_url")
                print(f"✅ Upload successful: {public_url}")
                return public_url
            else:
                print(f"❌ Upload failed: {result.get('error', 'Unknown error')}")
                return None
                
        except Exception as e:
            print(f"❌ WebSocket upload error: {e}")
            self.disconnect()
            return None
    
    def _get_content_type(self, file_path):
        """根据文件扩展名获取 MIME 类型"""
        ext = os.path.splitext(file_path)[1].lower()
        content_types = {
            '.wav': 'audio/wav',
            '.mp3': 'audio/mpeg',
            '.ogg': 'audio/ogg',
            '.flac': 'audio/flac',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.mp4': 'video/mp4',
            '.webm': 'video/webm',
            '.glb': 'model/gltf-binary',
        }
        return content_types.get(ext, 'application/octet-stream')


# 全局 WebSocket 上传器实例
ws_uploader = None

def get_ws_uploader():
    """获取或创建 WebSocket 上传器"""
    global ws_uploader
    if ws_uploader is None:
        ws_uploader = WebSocketUploader(WEBSOCKET_URL, API_KEY)
    return ws_uploader


def upload_to_relay_server_http(file_path, object_name=None):
    """
    HTTP 备用上传方式
    当 WebSocket 不可用时使用
    """
    if object_name is None:
        object_name = os.path.basename(file_path)
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (object_name, f, 'audio/wav')}
            headers = {'Authorization': f'Bearer {API_KEY}'}
            
            print(f"📤 Uploading {object_name} via HTTP (fallback)...")
            response = requests.post(
                RELAY_API_URL,
                files=files,
                headers=headers,
                timeout=300
            )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                public_url = data.get('public_url')
                print(f"✅ Uploaded to S3: {public_url}")
                return public_url
            else:
                print(f"❌ Upload failed: {data.get('error', 'Unknown error')}")
                return None
        else:
            print(f"❌ HTTP Error {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ HTTP Upload Error: {e}")
        return None


def upload_to_relay_server(file_path, object_name=None):
    """
    上传文件到中转服务器 - 优先使用 WebSocket
    
    Args:
        file_path: 本地文件路径
        object_name: 在S3中的文件名
    
    Returns:
        str: S3公共URL，如果失败则返回None
    """
    if object_name is None:
        object_name = os.path.basename(file_path)
    
    # 优先尝试 WebSocket
    if WEBSOCKET_AVAILABLE:
        uploader = get_ws_uploader()
        result = uploader.upload_file(file_path, object_name)
        if result:
            return result
        print("⚠️ WebSocket upload failed, trying HTTP fallback...")
    
    # HTTP 备用
    return upload_to_relay_server_http(file_path, object_name)


def upload_async(file_path, object_name=None, callback=None):
    """
    异步上传文件（在后台线程中执行）
    
    Args:
        file_path: 本地文件路径
        object_name: 在S3中的文件名
        callback: 上传完成后的回调函数，接收 (success, url_or_error) 参数
    """
    def _upload():
        try:
            url = upload_to_relay_server(file_path, object_name)
            if callback:
                callback(url is not None, url)
        except Exception as e:
            if callback:
                callback(False, str(e))
    
    executor.submit(_upload)


# ===== 原 webui.py 代码开始 =====

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


print("""================ IndexTTS WebUI (WebSocket Edition) =================""")
import argparse
parser = argparse.ArgumentParser(
    description="IndexTTS WebUI",
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
cmd_args = parser.parse_args()

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
os.makedirs("outputs/tasks",exist_ok=True)
os.makedirs("prompts",exist_ok=True)

MAX_LENGTH_TO_USE_SPEED = 70
with open("/gemini/code/index-tts/examples/cases.jsonl", "r", encoding="utf-8") as f:
    example_cases = []
    for line in f:
        line = line.strip()
        if not line:
            continue
        example = json.loads(line)
        if example.get("emo_audio",None):
            emo_audio_path = os.path.join("examples",example["emo_audio"])
        else:
            emo_audio_path = None
        example_cases.append([os.path.join("examples", example.get("prompt_audio", "sample_prompt.wav")),
                              EMO_CHOICES[example.get("emo_mode",0)],
                              example.get("text"),
                             emo_audio_path,
                             example.get("emo_weight",1.0),
                             example.get("emo_text",""),
                             example.get("emo_vec_1",0),
                             example.get("emo_vec_2",0),
                             example.get("emo_vec_3",0),
                             example.get("emo_vec_4",0),
                             example.get("emo_vec_5",0),
                             example.get("emo_vec_6",0),
                             example.get("emo_vec_7",0),
                             example.get("emo_vec_8",0)]
                             )


def gen_single(emo_control_method,prompt, text,
               emo_ref_path, emo_weight,
               vec1, vec2, vec3, vec4, vec5, vec6, vec7, vec8,
               emo_text,emo_random,
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
    if emo_control_method == 0:  # emotion from speaker
        emo_ref_path = None  # remove external reference audio
        emo_weight = 1.0
    if emo_control_method == 1:  # emotion from reference audio
        # emo_weight = emo_weight
        pass
    if emo_control_method == 2:  # emotion from custom vectors
        vec = [vec1, vec2, vec3, vec4, vec5, vec6, vec7, vec8]
        if sum(vec) > 1.5:
            gr.Warning(i18n("情感向量之和不能超过1.5，请调整后重试。"))
            return
    else:
        # don't use the emotion vector inputs for the other modes
        vec = None

    if emo_text == "":
        # erase empty emotion descriptions; `infer()` will then automatically use the main prompt
        emo_text = None

    print(f"Emo control mode:{emo_control_method},weight:{emo_weight},vec:{vec}")
    output = tts.infer(spk_audio_prompt=prompt, text=text,
                        output_path=output_path,
                        emo_audio_prompt=emo_ref_path, emo_alpha=emo_weight,
                        emo_vector=vec,
                        use_emo_text=(emo_control_method==3), emo_text=emo_text,use_random=emo_random,
                        verbose=cmd_args.verbose,
                        max_text_tokens_per_segment=int(max_text_tokens_per_segment),
                        **kwargs)
    
    # ===== 修改：使用 WebSocket 上传 =====
    print(f"🎵 Inference complete, uploading result...")
    s3_url = upload_to_relay_server(output)
    if s3_url:
        print(f"✅ File uploaded to S3: {s3_url}")
    else:
        print(f"⚠️ S3 upload failed, file saved locally at: {output}")
    # ===== 修改结束 =====

    return gr.update(value=output, visible=True)

def update_prompt_audio():
    update_button = gr.update(interactive=True)
    return update_button

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
            os.makedirs("prompts",exist_ok=True)
            prompt_audio = gr.Audio(label=i18n("音色参考音频"),key="prompt_audio",
                                    sources=["upload","microphone"],type="filepath")
            prompt_list = os.listdir("prompts")
            default = ''
            if prompt_list:
                default = prompt_list[0]
            with gr.Column():
                input_text_single = gr.TextArea(label=i18n("文本"),key="input_text_single", placeholder=i18n("请输入目标文本"), info=f"{i18n('当前模型版本')}{tts.model_version or '1.0'}")
                gen_button = gr.Button(i18n("生成语音"), key="gen_button",interactive=True)
            output_audio = gr.Audio(label=i18n("生成结果"), visible=True,key="output_audio")
        with gr.Accordion(i18n("功能设置")):
            # 情感控制选项部分
            with gr.Row():
                emo_control_method = gr.Radio(
                    choices=EMO_CHOICES,
                    type="index",
                    value=EMO_CHOICES[0],label=i18n("情感控制方式"))
        # 情感参考音频部分
        with gr.Group(visible=False) as emotion_reference_group:
            with gr.Row():
                emo_upload = gr.Audio(label=i18n("上传情感参考音频"), type="filepath")

        # 情感随机采样
        with gr.Row(visible=False) as emotion_randomize_group:
            emo_random = gr.Checkbox(label=i18n("情感随机采样"), value=False)

        # 情感向量控制部分
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
                emo_text = gr.Textbox(label=i18n("情感描述文本"), placeholder=i18n("请输入情绪描述（或留空以自动使用目标文本作为情绪描述）"), value="", info=i18n("例如：高兴，愤怒，悲伤等"))

        with gr.Row(visible=False) as emo_weight_group:
            emo_weight = gr.Slider(label=i18n("情感权重"), minimum=0.0, maximum=1.6, value=0.8, step=0.01)

        with gr.Accordion(i18n("高级生成参数设置"), open=False):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown(f"**{i18n('GPT2 采样设置')}** _{i18n('参数会影响音频多样性和生成速度详见')} [Generation strategies](https://huggingface.co/docs/transformers/main/en/generation_strategies)._")
                    with gr.Row():
                        do_sample = gr.Checkbox(label="do_sample", value=True, info=i18n("是否进行采样"))
                        temperature = gr.Slider(label="temperature", minimum=0.1, maximum=2.0, value=0.8, step=0.1)
                    with gr.Row():
                        top_p = gr.Slider(label="top_p", minimum=0.0, maximum=1.0, value=0.8, step=0.01)
                        top_k = gr.Slider(label="top_k", minimum=0, maximum=100, value=30, step=1)
                        num_beams = gr.Slider(label="num_beams", value=3, minimum=1, maximum=10, step=1)
                    with gr.Row():
                        repetition_penalty = gr.Number(label="repetition_penalty", precision=None, value=10.0, minimum=0.1, maximum=20.0, step=0.1)
                        length_penalty = gr.Number(label="length_penalty", precision=None, value=0.0, minimum=-2.0, maximum=2.0, step=0.1)
                    max_mel_tokens = gr.Slider(label="max_mel_tokens", value=1500, minimum=50, maximum=tts.cfg.gpt.max_mel_tokens, step=10, info=i18n("生成Token最大数量，过小导致音频被截断"), key="max_mel_tokens")
                with gr.Column(scale=2):
                    gr.Markdown(f'**{i18n("分句设置")}** _{i18n("参数会影响音频质量和生成速度")}_')
                    with gr.Row():
                        initial_value = max(20, min(tts.cfg.gpt.max_text_tokens, cmd_args.gui_seg_tokens))
                        max_text_tokens_per_segment = gr.Slider(
                            label=i18n("分句最大Token数"), value=initial_value, minimum=20, maximum=tts.cfg.gpt.max_text_tokens, step=2, key="max_text_tokens_per_segment",
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
                        vec1,vec2,vec3,vec4,vec5,vec6,vec7,vec8]
            )

    def on_input_text_change(text, max_text_tokens_per_segment):
        if text and len(text) > 0:
            text_tokens_list = tts.tokenizer.tokenize(text)

            segments = tts.tokenizer.split_segments(text_tokens_list, max_text_tokens_per_segment=int(max_text_tokens_per_segment))
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
        if emo_control_method == 1:  # emotion reference audio
            return (gr.update(visible=True),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=True)
                    )
        elif emo_control_method == 2:  # emotion vectors
            return (gr.update(visible=False),
                    gr.update(visible=True),
                    gr.update(visible=True),
                    gr.update(visible=False),
                    gr.update(visible=True)
                    )
        elif emo_control_method == 3:  # emotion text description
            return (gr.update(visible=False),
                    gr.update(visible=True),
                    gr.update(visible=False),
                    gr.update(visible=True),
                    gr.update(visible=True)
                    )
        else:  # 0: same as speaker voice
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
                     inputs=[emo_control_method,prompt_audio, input_text_single, emo_upload, emo_weight,
                             vec1, vec2, vec3, vec4, vec5, vec6, vec7, vec8,
                             emo_text,emo_random,
                             max_text_tokens_per_segment,
                             *advanced_params,
                     ],
                     outputs=[output_audio],
                     api_name="generate")



if __name__ == "__main__":
    demo.queue(20)
    demo.launch(server_name=cmd_args.host, server_port=cmd_args.port)
