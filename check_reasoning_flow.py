#!/usr/bin/env python3
"""
Complete flow checker - traces reasoning_content through the entire pipeline
"""

import json
import sys

def main():
    print("\n" + "="*80)
    print("AI 思考功能 - 完整流程检查")
    print("="*80)
    
    # Step 1: 检查 OpenAI SDK
    print("\n步骤 1: 检查 OpenAI SDK")
    print("-" * 80)
    
    try:
        from openai import OpenAI
        print("✓ OpenAI SDK 已安装")
        
        import openai
        print(f"✓ OpenAI 版本: {openai.__version__}")
            
    except ImportError:
        print("✗ OpenAI SDK 未安装")
        print("  运行: pip install openai")
        return False
    
    # Step 2: 检查 API 连接
    print("\n步骤 2: 检查 NetMind API 连接")
    print("-" * 80)
    
    api_key = input("输入 NetMind API Key (或 'skip' 跳过): ").strip()
    
    if api_key.lower() == 'skip' or not api_key:
        print("⚠ 跳过 API 连接检查")
        return True
    
    base_url = input("输入 Base URL (默认: https://api.netmind.ai/inference-api/openai/v1): ").strip()
    
    if not base_url:
        base_url = "https://api.netmind.ai/inference-api/openai/v1"
    
    try:
        print(f"连接到 {base_url}...")
        client = OpenAI(api_key=api_key, base_url=base_url)
        
        # Test simple call
        print("发送测试请求...")
        response = client.chat.completions.create(
            model="deepseek-ai/DeepSeek-R1",
            messages=[{"role": "user", "content": "1+1=?"}],
            stream=False,
            max_tokens=100
        )
        
        print("✓ API 连接成功")
        
        # Step 3: 检查响应结构
        print("\n步骤 3: 检查 API 响应结构")
        print("-" * 80)
        
        print(f"响应类型: {type(response)}")
        
        if response.choices:
            msg = response.choices[0].message
            print(f"消息类型: {type(msg)}")
            
            # List all attributes
            attrs = [a for a in dir(msg) if not a.startswith('_')]
            print(f"消息属性: {attrs}")
            
            # Check reasoning_content
            print("\n检查 reasoning_content:")
            
            # Method 1
            if hasattr(msg, 'reasoning_content'):
                rc = msg.reasoning_content
                print(f"✓ 方法1 (hasattr): 找到 = {rc is not None}")
                if rc:
                    print(f"  内容: {rc[:100]}")
            else:
                print(f"✗ 方法1 (hasattr): 未找到")
            
            # Method 2
            if hasattr(msg, '__dict__'):
                rc = msg.__dict__.get('reasoning_content')
                print(f"✓ 方法2 (__dict__): 找到 = {rc is not None}")
                if rc:
                    print(f"  内容: {rc[:100]}")
            else:
                print(f"✗ 方法2 (__dict__): 未找到")
            
            # Method 3
            if hasattr(msg, 'model_dump'):
                try:
                    dumped = msg.model_dump(exclude_none=False)
                    rc = dumped.get('reasoning_content')
                    print(f"✓ 方法3 (model_dump): 找到 = {rc is not None}")
                    if rc:
                        print(f"  内容: {rc[:100]}")
                    print(f"  model_dump 包含的字段: {list(dumped.keys())}")
                except Exception as e:
                    print(f"✗ 方法3 (model_dump): 错误 - {e}")
            
            # Step 4: 检查 JSON 序列化
            print("\n步骤 4: 检查 JSON 序列化")
            print("-" * 80)
            
            try:
                json_str = response.model_dump_json()
                json_obj = json.loads(json_str)
                
                msg_obj = json_obj.get('choices', [{}])[0].get('message', {})
                print(f"JSON 消息字段: {list(msg_obj.keys())}")
                
                if 'reasoning_content' in msg_obj:
                    print(f"✓ reasoning_content 在 JSON 中: {msg_obj['reasoning_content'][:100]}")
                else:
                    print(f"✗ reasoning_content 不在 JSON 中")
                    
            except Exception as e:
                print(f"✗ JSON 序列化错误: {e}")
        
        # Step 5: 检查流式响应
        print("\n步骤 5: 检查流式响应")
        print("-" * 80)
        
        print("发送流式请求...")
        stream = client.chat.completions.create(
            model="deepseek-ai/DeepSeek-R1",
            messages=[{"role": "user", "content": "2+2=?"}],
            stream=True,
            max_tokens=100
        )
        
        chunk_count = 0
        reasoning_found = False
        
        for chunk in stream:
            chunk_count += 1
            if chunk_count <= 5:
                print(f"\nChunk {chunk_count}:")
                
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    print(f"  Delta 类型: {type(delta)}")
                    
                    # Check for reasoning_content
                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        print(f"  ✓ 包含 reasoning_content: {delta.reasoning_content[:50]}")
                        reasoning_found = True
                    elif hasattr(delta, 'content') and delta.content:
                        print(f"  ✓ 包含 content: {delta.content[:50]}")
                    else:
                        attrs = [a for a in dir(delta) if not a.startswith('_')]
                        print(f"  △ Delta 属性: {attrs[:5]}")
        
        print(f"\n✓ 接收 {chunk_count} 个流式 chunk")
        if reasoning_found:
            print("✓ 流中找到 reasoning_content")
        else:
            print("✗ 流中未找到 reasoning_content")
        
    except Exception as e:
        print(f"✗ API 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Summary
    print("\n" + "="*80)
    print("诊断总结")
    print("="*80)
    
    print("""
根据上面的检查结果，确定问题所在:

❌ 如果看到 "✗ 未找到 reasoning_content"
   → API 没有返回推理内容
   → 问题在 API 配置或模型选择
   → 解决方案:
      1. 检查 API 密钥是否有效
      2. 确认 Base URL 正确
      3. 尝试其他支持推理的模型
      4. 联系 NetMind 支持

✓ 如果看到 "✓ 包含 reasoning_content"
   → API 返回了推理内容
   → 问题在应用后端或前端
   → 解决方案:
      1. 检查应用日志中的 [DEBUG] 输出
      2. 查看浏览器开发工具 Network 标签
      3. 清除浏览器缓存并重新加载
      4. 检查前端 JavaScript 控制台是否有错误
""")
    
    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
