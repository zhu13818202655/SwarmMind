# scripts/test_deepseek_v4_pro_no_thinking.py
"""
调用 DeepSeek V4 Pro，并关闭思考(thinking)模式。

DeepSeek 的混合推理模型(V3.1/V3.2/V4 Pro 等)开启/关闭思考的标准做法是在
chat/completions 请求里通过 chat_template_kwargs.thinking=False 传递。
某些网关也接受顶层 enable_thinking=False，本脚本同时带上，最大化兼容性。
"""
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

# 加载与本脚本同目录下的 .env
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)

API_KEY  = os.getenv("DEEPSEEK_API_KEY")
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
MODEL    = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")


async def main() -> None:
    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)

    resp = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": "用一句话解释什么是 RAG。"},
        ],
        temperature=0.2,
        max_tokens=512,
        # 关键：关闭思考模式
        extra_body={
            "chat_template_kwargs": {"thinking": False},
            "enable_thinking": False,   # 兼容部分网关 (vLLM / SGLang / LiteLLM)
            "thinking": {"type": "disabled"},  # 兼容某些代理实现
        },
    )

    msg = resp.choices[0].message
    print("=== content ===")
    print(msg.content)

    # 如果上游仍然返回了 reasoning，打印出来便于核对是否真的关掉了
    reasoning = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None)
    if reasoning:
        print("\n[WARN] 仍然收到 reasoning，说明未生效：")
        print(reasoning)
    else:
        print("\n[OK] 未返回 reasoning，思考模式已关闭。")

    print("\n=== usage ===")
    print(resp.usage)


if __name__ == "__main__":
    asyncio.run(main())