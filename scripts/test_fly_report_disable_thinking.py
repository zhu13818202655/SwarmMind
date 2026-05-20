"""Smoke test for `ModelConfig.disable_thinking` across FlyReport LLM paths.

Validates that turning on `disable_thinking` correctly suppresses hybrid
reasoning ("thinking") for both LLM call paths used inside FlyReport:

1. ``AuditedOpenAIChatModel`` (AgentScope path) — used by intent / clarifier /
   followup agents via ``swarmmind/domains/fly_report/agents/factory.py``.
2. ``OpenAICompatibleLMClient`` (lightweight path) — used by chitchat /
   intent classifier / simple composer.

Run:

    # configure once in scripts/.env
    #   DEEPSEEK_API_KEY=...
    #   DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
    #   DEEPSEEK_MODEL=deepseek-v4-pro
    python scripts/test_fly_report_disable_thinking.py
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)

from swarmmind.config.schema import ModelConfig  # noqa: E402
from swarmmind.domains.fly_report.agents.factory import build_intent_agent  # noqa: E402
from swarmmind.domains.fly_report.lm.client import OpenAICompatibleLMClient  # noqa: E402
from swarmmind.domains.fly_report.lm.types import LMChatRequest  # noqa: E402

from agentscope.message import Msg  # noqa: E402


def _build_model_config(*, disable_thinking: bool) -> ModelConfig:
    return ModelConfig(
        provider="openai",
        name=os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro"),
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        temperature=0.2,
        max_tokens=256,
        disable_thinking=disable_thinking,
    )


def _has_reasoning(response: object) -> bool:
    """Best-effort: check if an OpenAI-style response carries reasoning."""
    for attr in ("reasoning_content", "reasoning", "thinking"):
        if getattr(response, attr, None):
            return True
    # AgentScope ChatResponse exposes .content list of content blocks
    content = getattr(response, "content", None)
    if isinstance(content, list):
        for block in content:
            block_type = getattr(block, "type", None) or (
                block.get("type") if isinstance(block, dict) else None
            )
            if block_type in {"thinking", "reasoning"}:
                return True
    return False


async def test_audited_model_path() -> None:
    print("\n[1/2] AgentScope path (AuditedOpenAIChatModel via build_intent_agent)")
    config = _build_model_config(disable_thinking=True)
    agent = build_intent_agent(config)
    msg = Msg(name="user", role="user", content="Reply with a tiny JSON: {\"ok\": true}")
    reply = await agent(msg)
    text = getattr(reply, "content", reply)
    print("  reply:", text)
    if _has_reasoning(reply):
        print("  [WARN] reasoning detected on AgentScope path — disable_thinking did NOT take effect")
    else:
        print("  [OK] no reasoning content detected")


async def test_lightweight_client_path() -> None:
    print("\n[2/2] Lightweight path (OpenAICompatibleLMClient.from_model_config)")
    config = _build_model_config(disable_thinking=True)
    client = OpenAICompatibleLMClient.from_model_config(config)
    response = await client.chat_response(
        LMChatRequest(
            system_prompt="You are concise.",
            user_prompt="用一句话解释 RAG。",
        )
    )
    print("  text:", response.text)
    print("  usage:", response.usage)
    # The lightweight client only surfaces .text; raw is dropped unless format=RAW.
    # If your gateway still echoes reasoning in `text`, you'll see it above.


async def main() -> None:
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise SystemExit("DEEPSEEK_API_KEY missing — please fill scripts/.env")
    await test_audited_model_path()
    await test_lightweight_client_path()


if __name__ == "__main__":
    asyncio.run(main())
