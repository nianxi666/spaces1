#!/usr/bin/env python3
"""
Quick manual test for the PumpkinAI NetMind proxy.

Example:
    python spaces/test_netmind_stream.py \\
        --api-key 12345678-aaaa-bbbb-cccc-1234567890ab \\
        --base-url http://127.0.0.1:5001/api/v1 \\
        --prompt "请解释 1+2 等于几？"
"""

import argparse
import sys
from typing import Optional
from openai import OpenAI


def extract_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return value


def main():
    parser = argparse.ArgumentParser(description="Pumpkin NetMind stream tester")
    parser.add_argument("--api-key", required=True, help="Pumpkin 用户 token")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:5001/api/v1",
        help="Pumpkin API 根路径（默认指向本地服务）"
    )
    parser.add_argument(
        "--model",
        default="zai-org/GLM-4.6",
        help="NetMind 模型 ID"
    )
    parser.add_argument(
        "--prompt",
        default="请用中文回答：1+2等于多少？",
        help="发送给模型的用户消息"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=512,
        help="最大输出 token 数"
    )
    args = parser.parse_args()

    client = OpenAI(
        api_key=args.api_key,
        base_url=args.base_url.rstrip("/")
    )

    print(f"[info] streaming completion via {args.base_url} ...", file=sys.stderr)
    stream = client.chat.completions.create(
        model=args.model,
        messages=[{"role": "user", "content": args.prompt}],
        stream=True,
        max_tokens=args.max_tokens
    )

    has_content = False
    reasoning_buffer = []

    try:
        for chunk in stream:
            choice = chunk.choices[0]
            delta = choice.delta
            text = extract_text(delta.content)
            reasoning = extract_text(getattr(delta, "reasoning_content", None))

            if text:
                has_content = True
                reasoning_buffer.clear()
                sys.stdout.write(text)
                sys.stdout.flush()
            elif reasoning:
                # 只在模型尚未输出 content 时暂存推理内容
                reasoning_buffer.append(reasoning)
    except KeyboardInterrupt:
        print("\n[warn] aborted by user", file=sys.stderr)
        return

    if not has_content and reasoning_buffer:
        print("\n[reasoning fallback]\n" + "".join(reasoning_buffer))
    else:
        print("\n[done]")


if __name__ == "__main__":
    main()
