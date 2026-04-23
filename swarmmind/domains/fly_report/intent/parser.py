"""IntentParser: LLM-backed natural language → :class:`DraftFilterSpec`."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from agentscope.agent import ReActAgent
from agentscope.message import Msg
from pydantic import ValidationError

from swarmmind.domains.fly_report.errors import FilterParseError
from swarmmind.domains.fly_report.schemas import DraftFilterSpec

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


class IntentParser:
    """Wraps an ``IntentParserAgent`` and produces :class:`DraftFilterSpec`.

    Parameters
    ----------
    agent:
        A ``ReActAgent`` built by
        :func:`swarmmind.domains.fly_report.agents.factory.build_intent_agent`
        (or any compatible agent that returns a JSON ``DraftFilterSpec`` in the
        text content of its reply).
    """

    def __init__(self, agent: ReActAgent) -> None:
        self._agent = agent

    async def parse(
        self,
        user_text: str,
        *,
        preference: dict[str, Any] | None = None,
        now: datetime | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> DraftFilterSpec:
        """Parse a single user utterance into a :class:`DraftFilterSpec`.

        Notes
        -----
        - Ambiguous input is **not** an error: ``missing`` / ``conflicts`` may
          be populated and the state machine decides whether to clarify.
        - :class:`FilterParseError` is only raised when the LLM reply is not
          valid JSON or does not satisfy the schema.
        """

        if not user_text or not user_text.strip():
            raise FilterParseError("empty user text")

        metadata: dict[str, Any] = {}
        if preference is not None:
            metadata["preference"] = preference
        if now is not None:
            metadata["当前时间"] = now.isoformat()
        if extra_metadata:
            metadata.update(extra_metadata)

        msg = Msg(
            name="user",
            role="user",
            content=user_text,
            metadata=metadata or None,
        )

        reply = await self._agent(msg)
        text = self._extract_text(reply)
        payload = self._extract_json(text)

        try:
            return DraftFilterSpec.model_validate(payload)
        except ValidationError as exc:
            raise FilterParseError(
                "intent parser produced invalid DraftFilterSpec",
                details={"errors": exc.errors(), "raw": text[:1000]},
            ) from exc

    @staticmethod
    def _extract_text(reply: Any) -> str:
        """Pull text out of a ReActAgent reply (Msg-like)."""

        getter = getattr(reply, "get_text_content", None)
        if callable(getter):
            value = getter()
            if value:
                return str(value)

        content = getattr(reply, "content", reply)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict):
                    text = block.get("text")
                    if isinstance(text, str):
                        parts.append(text)
                else:
                    text = getattr(block, "text", None)
                    if isinstance(text, str):
                        parts.append(text)
            if parts:
                return "".join(parts)
        return str(content)

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        """Best-effort JSON extraction.

        Handles three shapes:
        1. Raw JSON object,
        2. JSON wrapped in ```json ... ``` code fences,
        3. JSON embedded in surrounding prose (first ``{...}`` block).
        """

        if not text or not text.strip():
            raise FilterParseError("intent parser returned empty content")

        candidates: list[str] = [text.strip()]
        fence = _JSON_FENCE_RE.search(text)
        if fence:
            candidates.insert(0, fence.group(1))

        # Fallback: substring from first '{' to last '}'.
        first = text.find("{")
        last = text.rfind("}")
        if first != -1 and last > first:
            candidates.append(text[first : last + 1])

        last_error: Exception | None = None
        for candidate in candidates:
            try:
                value = json.loads(candidate)
            except json.JSONDecodeError as exc:
                last_error = exc
                continue
            if isinstance(value, dict):
                return value
            last_error = FilterParseError(
                "intent parser JSON is not an object",
                details={"raw": candidate[:500]},
            )

        raise FilterParseError(
            "intent parser produced non-JSON content",
            details={"raw": text[:1000], "error": str(last_error)},
        )


__all__ = ["IntentParser"]
