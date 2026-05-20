"""LLM service subclasses used by the FlyReport Text-to-SQL agent.

Vanna's stock :class:`OpenAILlmService` does not surface ``extra_body`` on
``chat.completions.create`` and never re-sends the previous assistant's
``reasoning_content`` on the next turn. With DeepSeek's hybrid-reasoning
models that default to thinking mode (e.g. ``deepseek-v4-pro``,
``deepseek-reasoner``) the second turn fails with::

    openai.BadRequestError: Error code: 400 - The `reasoning_content` in the
    thinking mode must be passed back to the API.

We work around this by force-disabling thinking on every request. This is the
same trick used in ``scripts/test_deepseek.py`` — pass the three flags that
DeepSeek / vLLM / SGLang / LiteLLM all recognise so the upstream model never
emits ``reasoning_content`` in the first place.
"""

from __future__ import annotations

from typing import Any, Dict

from vanna.core.llm import LlmRequest
from vanna.integrations.openai import OpenAILlmService


# All three keys are needed for max compatibility across DeepSeek's official
# endpoint and the various OpenAI-compatible gateways (vLLM/SGLang/LiteLLM).
_DISABLE_THINKING_EXTRA_BODY: Dict[str, Any] = {
    "chat_template_kwargs": {"thinking": False},
    "enable_thinking": False,
    "thinking": {"type": "disabled"},
}


class NoThinkingOpenAILlmService(OpenAILlmService):
    """OpenAI-compatible LLM service that disables hybrid thinking mode.

    Use this for any provider whose default behaviour returns
    ``reasoning_content`` but whose multi-turn protocol requires the caller
    to echo that field back (DeepSeek V3.1+/V4 Pro/Reasoner today).
    """

    def _build_payload(self, request: LlmRequest) -> Dict[str, Any]:
        payload = super()._build_payload(request)
        existing = payload.get("extra_body") or {}
        merged = {**_DISABLE_THINKING_EXTRA_BODY, **existing}
        payload["extra_body"] = merged
        return payload


__all__ = ["NoThinkingOpenAILlmService"]
