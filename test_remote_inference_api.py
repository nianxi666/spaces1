"""
远程推理API实际测试
测试 http://direct.virtaicloud.com:21564 音频生成API
"""

import os
import time
import wave
import struct
import math
from gradio_client import Client, handle_file


# 配置
API_URL = "http://direct.virtaicloud.com:21564"
DUMMY_WAV = "test_audio_sample.wav"

def generate_dummy_wav(filename):
    """生成一个简单的 1 秒正弦波音频文件用于测试"""
    print(f"📝 生成测试音频文件: {filename}...")
    with wave.open(filename, 'w') as file:
        # 参数: (声道数, 采样宽度, 采样率, 帧数, 压缩类型, 压缩名称)
        file.setparams((1, 2, 44100, 44100, 'NONE', 'not compressed'))
        # 生成1秒的正弦波
        values = [struct.pack('h', int(math.sin(i/100.0)*32767)) for i in range(44100)]
        file.writeframes(b''.join(values))
    print(f"   ✅ 音频文件已生成 ({os.path.getsize(filename)} bytes)")

def test_remote_gpu_api():
    """测试远程GPU API"""
    
    print("=" * 70)
    print("远程推理API测试 - 音频生成")
    print("=" * 70)
    
    # 1. 生成测试文件
    if not os.path.exists(DUMMY_WAV):
        generate_dummy_wav(DUMMY_WAV)
    else:
        print(f"📝 使用现有测试音频: {DUMMY_WAV}")
    
    print(f"\n🌐 连接到远程GPU: {API_URL}")
    
    try:
        # 2. 初始化客户端
        print("🔧 初始化 Gradio Client...")
        client = Client(API_URL)
        print("   ✅ 成功连接到 Gradio API")
        
        # 3. 准备请求参数
        print("\n📋 准备推理参数...")
        prompt = "Same as the voice reference"
        text_to_synthesize = "Hello! This is a test message from your local terminal. Testing remote inference system."
        
        print(f"   Prompt: {prompt}")
        print(f"   Text: {text_to_synthesize[:50]}...")
        
        # 4. 发送推理请求
        print("\n🚀 发送推理请求...")
        print("   ⏳ 等待远程GPU处理...")
        
        start_time = time.time()
        
        result = client.predict(
            prompt,                                 # Prompt
            handle_file(DUMMY_WAV),                # Reference Audio (Original)
            text_to_synthesize,                     # Text to synthesize
            handle_file(DUMMY_WAV),                # Reference Audio (Target)
            0.8,                                    # Alpha/Beta param
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,  # Style/Timbre params
            "",                                     # Extra prompt
            False,                                  # Disable prompt
            120,                                    # Speed
            True,                                   # Enable some flag
            0.8, 30, 0.8, 0.0, 3, 10.0, 1500,      # Advanced params
            api_name="/generate"
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        print("\n" + "=" * 70)
        print("✅ 推理成功完成!")
        print("=" * 70)
        print(f"⏱️  耗时: {duration:.2f} 秒")
        print(f"📂 结果文件: {result}")
        
        # 检查结果文件
        if result and os.path.exists(result):
            file_size = os.path.getsize(result)
            file_size_mb = file_size / (1024 * 1024)
            print(f"📊 文件大小: {file_size_mb:.2f} MB ({file_size} bytes)")
            print(f"✅ 结果文件已保存到本地: {result}")
        else:
            print(f"⚠️  结果是URL或路径: {result}")
        
        print("\n" + "=" * 70)
        print("🎉 远程推理API测试成功!")
        print("=" * 70)
        
        return True, result
        
    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ API 请求失败!")
        print("=" * 70)
        print(f"错误详情: {e}")
        print("\n可能的原因:")
        print("1. 远程服务器已停止或正在启动")
        print("2. 网络防火墙阻止了端口 21564")
        print("3. 输入参数与API schema不匹配")
        print("4. API endpoint 已更改")
        
        return False, None
    
    finally:
        # 清理测试文件
        if os.path.exists(DUMMY_WAV):
            try:
                os.remove(DUMMY_WAV)
                print(f"\n🧹 已清理临时文件: {DUMMY_WAV}")
            except:
                pass

if __name__ == "__main__":
    success, result = test_remote_gpu_api()
    
    if success:
        print("\n✨ 测试总结:")
        print("   ✅ 远程API连接成功")
        print("   ✅ 音频生成请求成功")
        print("   ✅ 收到推理结果")
        print(f"   📄 结果: {result}")
        print("\n💡 您可以将此逻辑集成到 remote_inference.py 模块中!")
    else:
        print("\n❌ 测试失败，请检查:")
        print("   1. API地址是否正确")
        print("   2. 远程服务是否在运行")
        print("   3. 网络连接是否正常")
