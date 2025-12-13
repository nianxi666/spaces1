#!/usr/bin/env python3
"""
IndexTTS WebSocket 远程推理客户端
支持自动重连，与 WebSocket Spaces 系统集成
"""
import json
import os
import sys
import time
import threading
import base64
import warnings
from datetime import datetime

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# 设置缓存目录
os.environ['HF_HUB_CACHE'] = '/gemini/code/checkpoints/hf_cache'
os.environ['TRANSFORMERS_CACHE'] = '/gemini/code/checkpoints/hf_cache'
os.environ['HF_HOME'] = '/gemini/code/checkpoints/hf_cache'
os.environ['WETEXT_CACHE'] = '/gemini/code/checkpoints/wetext_cache'

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, "indextts"))

import socketio

# ============== 配置 ==============
DEFAULT_SERVER_URL = "http://localhost:5001"
DEFAULT_SPACE_NAME = "IndexTTS"

# WebSocket 重连配置
RECONNECT_DELAY_INITIAL = 1  # 初始重连延迟(秒)
RECONNECT_DELAY_MAX = 60     # 最大重连延迟(秒)
RECONNECT_DELAY_MULTIPLIER = 2  # 延迟增长倍数

# ============== 日志工具 ==============
def log(level, message):
    timestamp = datetime.now().strftime('%H:%M:%S')
    prefix = {
        'INFO': '✓',
        'WARNING': '⚠',
        'ERROR': '✗',
        'DEBUG': '→'
    }.get(level, '•')
    print(f"[{timestamp}] {level}: {prefix} {message}")

# ============== IndexTTS 模型加载 ==============
class IndexTTSModel:
    """IndexTTS 模型封装"""
    
    def __init__(self, model_dir, use_fp16=False, use_deepspeed=False, use_cuda_kernel=False, verbose=False):
        self.model_dir = model_dir
        self.use_fp16 = use_fp16
        self.use_deepspeed = use_deepspeed
        self.use_cuda_kernel = use_cuda_kernel
        self.verbose = verbose
        self.tts = None
        self.mutex = threading.Lock()
        
    def load(self):
        """加载模型"""
        log('INFO', f"正在加载 IndexTTS 模型: {self.model_dir}")
        
        # 检查模型文件
        required_files = [
            "bpe.model",
            "gpt.pth",
            "config.yaml",
            "s2mel.pth",
            "wav2vec2bert_stats.pt"
        ]
        
        for file in required_files:
            file_path = os.path.join(self.model_dir, file)
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"模型文件不存在: {file_path}")
        
        from indextts.infer_v2 import IndexTTS2
        
        self.tts = IndexTTS2(
            model_dir=self.model_dir,
            cfg_path=os.path.join(self.model_dir, "config.yaml"),
            use_fp16=self.use_fp16,
            use_deepspeed=self.use_deepspeed,
            use_cuda_kernel=self.use_cuda_kernel,
        )
        
        log('INFO', f"模型加载完成 (版本: {self.tts.model_version or '1.0'})")
        
    def infer(self, text, prompt_audio_path, emo_control_method=0, emo_ref_path=None, 
              emo_weight=0.8, emo_text=None, emo_vector=None, max_text_tokens_per_segment=120,
              **kwargs):
        """执行推理"""
        with self.mutex:
            output_path = os.path.join("outputs", f"ws_{int(time.time())}.wav")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 处理情感控制
            if emo_control_method == 0:  # 与音色参考音频相同
                emo_ref_path = None
                emo_weight = 1.0
            
            vec = None
            if emo_control_method == 2 and emo_vector:  # 使用情感向量
                vec = emo_vector
            
            use_emo_text = (emo_control_method == 3)
            
            # 默认生成参数
            gen_kwargs = {
                "do_sample": kwargs.get("do_sample", True),
                "top_p": kwargs.get("top_p", 0.8),
                "top_k": kwargs.get("top_k", 30),
                "temperature": kwargs.get("temperature", 0.8),
                "length_penalty": kwargs.get("length_penalty", 0.0),
                "num_beams": kwargs.get("num_beams", 3),
                "repetition_penalty": kwargs.get("repetition_penalty", 10.0),
                "max_mel_tokens": kwargs.get("max_mel_tokens", 1500),
            }
            
            output = self.tts.infer(
                spk_audio_prompt=prompt_audio_path,
                text=text,
                output_path=output_path,
                emo_audio_prompt=emo_ref_path,
                emo_alpha=emo_weight,
                emo_vector=vec,
                use_emo_text=use_emo_text,
                emo_text=emo_text,
                use_random=kwargs.get("emo_random", False),
                verbose=self.verbose,
                max_text_tokens_per_segment=int(max_text_tokens_per_segment),
                **gen_kwargs
            )
            
            return output


# ============== WebSocket 客户端 ==============
class IndexTTSWebSocketClient:
    """IndexTTS WebSocket 客户端，支持自动重连"""
    
    def __init__(self, server_url, space_name, model):
        self.server_url = server_url
        self.space_name = space_name
        self.model = model
        
        self.sio = socketio.Client(
            reconnection=False,  # 我们手动处理重连
            logger=False,
            engineio_logger=False
        )
        
        self.connected = False
        self.registered = False
        self.should_run = True
        self.reconnect_delay = RECONNECT_DELAY_INITIAL
        
        self._setup_event_handlers()
        
    def _setup_event_handlers(self):
        """设置 Socket.IO 事件处理器"""
        
        @self.sio.on('connect')
        def on_connect():
            log('INFO', f"已连接到服务器: {self.server_url}")
            self.connected = True
            self.reconnect_delay = RECONNECT_DELAY_INITIAL  # 重置重连延迟
            
            # 注册 Space
            log('INFO', f"正在注册 Space: {self.space_name}")
            self.sio.emit('register', {'space_name': self.space_name})
        
        @self.sio.on('register_response')
        def on_register_response(data):
            if data.get('success'):
                self.registered = True
                log('INFO', f"注册成功! Connection ID: {data.get('connection_id', 'N/A')}")
                log('INFO', "📡 等待推理请求...")
            else:
                log('ERROR', f"注册失败: {data.get('message')}")
                self.registered = False
        
        @self.sio.on('inference_request')
        def on_inference_request(data):
            request_id = data.get('request_id')
            username = data.get('username', 'anonymous')
            payload = data.get('payload', {})
            
            log('INFO', f"收到推理请求 [{request_id[:8]}...] 来自用户: {username}")
            
            # 在新线程中处理请求以避免阻塞
            thread = threading.Thread(
                target=self._process_request,
                args=(request_id, username, payload)
            )
            thread.start()
        
        @self.sio.on('disconnect')
        def on_disconnect():
            self.connected = False
            self.registered = False
            log('WARNING', "与服务器断开连接")
    
    def _process_request(self, request_id, username, payload):
        """处理推理请求"""
        try:
            log('DEBUG', f"开始处理请求 [{request_id[:8]}...]")
            start_time = time.time()
            
            # 简化参数：只需要 prompt (文本) 和 audio (音频直链)
            text = payload.get('prompt', '')
            audio_url = payload.get('audio', '')
            
            if not text:
                raise ValueError("缺少参数: prompt")
            if not audio_url:
                raise ValueError("缺少参数: audio")
            
            log('DEBUG', f"文本: {text[:50]}..." if len(text) > 50 else f"文本: {text}")
            log('DEBUG', f"音频: {audio_url}")
            
            # 下载音色参考音频
            prompt_audio_path = self._download_audio(audio_url, f"prompt_{request_id[:8]}")
            
            # 执行推理（使用默认情感设置）
            output_path = self.model.infer(
                text=text,
                prompt_audio_path=prompt_audio_path
            )
            
            elapsed = time.time() - start_time
            log('INFO', f"推理完成 [{request_id[:8]}...] 耗时: {elapsed:.2f}s")
            
            # 读取并编码音频
            with open(output_path, 'rb') as f:
                audio_data = base64.b64encode(f.read()).decode('utf-8')
            
            # 发送成功结果
            self.sio.emit('inference_result', {
                'request_id': request_id,
                'status': 'completed',
                'result': {
                    'audio': audio_data,
                    'audio_format': 'wav',
                    'duration': elapsed
                }
            })
            
            log('INFO', f"结果已发送 [{request_id[:8]}...]")
            
        except Exception as e:
            log('ERROR', f"处理请求失败 [{request_id[:8]}...]: {e}")
            
            # 发送错误结果
            self.sio.emit('inference_result', {
                'request_id': request_id,
                'status': 'error',
                'result': {'error': str(e)}
            })
    
    def _download_audio(self, url_or_path, prefix):
        """下载或定位音频文件"""
        import urllib.request
        
        # 如果是本地路径
        if os.path.exists(url_or_path):
            return url_or_path
        
        # 如果是 URL，下载到临时文件
        temp_dir = os.path.join("outputs", "temp")
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"{prefix}.wav")
        
        urllib.request.urlretrieve(url_or_path, temp_path)
        return temp_path
    
    def connect(self):
        """连接到服务器（带自动重连）"""
        while self.should_run:
            try:
                log('INFO', f"正在连接到服务器: {self.server_url}")
                self.sio.connect(self.server_url, transports=['websocket', 'polling'])
                
                # 连接成功，等待直到断开
                self.sio.wait()
                
            except socketio.exceptions.ConnectionError as e:
                log('ERROR', f"连接失败: {e}")
            except Exception as e:
                log('ERROR', f"发生错误: {e}")
            
            if not self.should_run:
                break
            
            # 自动重连
            log('WARNING', f"将在 {self.reconnect_delay} 秒后重新连接...")
            time.sleep(self.reconnect_delay)
            
            # 增加重连延迟（指数退避）
            self.reconnect_delay = min(
                self.reconnect_delay * RECONNECT_DELAY_MULTIPLIER,
                RECONNECT_DELAY_MAX
            )
    
    def disconnect(self):
        """断开连接"""
        self.should_run = False
        if self.sio.connected:
            self.sio.disconnect()


# ============== 主程序 ==============
def main():
    import argparse
    
    print("""
==================================================
    IndexTTS WebSocket 远程推理客户端
    支持与 WebSocket Spaces 系统集成
==================================================
""")
    
    parser = argparse.ArgumentParser(
        description="IndexTTS WebSocket Client",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--server", type=str, default=DEFAULT_SERVER_URL, 
                        help="WebSocket 服务器地址")
    parser.add_argument("--space", type=str, default=DEFAULT_SPACE_NAME,
                        help="Space 名称 (必须与服务器上创建的 Space 名称一致)")
    parser.add_argument("--model_dir", type=str, default="/gemini/pretrain/IndexTTS-2",
                        help="模型目录")
    parser.add_argument("--fp16", action="store_true", default=False,
                        help="使用 FP16 推理")
    parser.add_argument("--deepspeed", action="store_true", default=False,
                        help="使用 DeepSpeed 加速")
    parser.add_argument("--cuda_kernel", action="store_true", default=False,
                        help="使用 CUDA 内核")
    parser.add_argument("--verbose", action="store_true", default=False,
                        help="详细输出")
    
    args = parser.parse_args()
    
    # 检查模型目录
    if not os.path.exists(args.model_dir):
        log('ERROR', f"模型目录不存在: {args.model_dir}")
        sys.exit(1)
    
    # 加载模型
    model = IndexTTSModel(
        model_dir=args.model_dir,
        use_fp16=args.fp16,
        use_deepspeed=args.deepspeed,
        use_cuda_kernel=args.cuda_kernel,
        verbose=args.verbose
    )
    
    try:
        model.load()
    except Exception as e:
        log('ERROR', f"模型加载失败: {e}")
        sys.exit(1)
    
    # 创建 WebSocket 客户端
    client = IndexTTSWebSocketClient(
        server_url=args.server,
        space_name=args.space,
        model=model
    )
    
    # 连接（自动重连循环）
    try:
        log('INFO', "按 Ctrl+C 停止")
        client.connect()
    except KeyboardInterrupt:
        log('INFO', "正在停止...")
        client.disconnect()
    
    log('INFO', "程序已退出")


if __name__ == "__main__":
    main()
