"""IntentParser: LLM-backed natural language → :class:`DraftFilterSpec`."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from swarmmind.domains.fly_report.errors import FilterParseError
from swarmmind.domains.fly_report.lm.client import OpenAICompatibleLMClient
from swarmmind.domains.fly_report.schemas import ChatTurn, DraftFilterSpec, FilterSpec
from swarmmind.prompt_template.fly_report.intent_parse import (
    INTENT_PARSE_SYSTEM_PROMPT,
    INTENT_PARSE_USER_PROMPT,
)
from swarmmind.prompt_template.renderer import render_prompt

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


class IntentParser:
    """Wraps an :class:`OpenAICompatibleLMClient` and produces
    :class:`DraftFilterSpec`.

    Parameters
    ----------
    client:
        A lightweight LM client (e.g. built by
        :func:`swarmmind.domains.fly_report.lm.client.build_intent_lm_client`).
    """

    def __init__(self, client: OpenAICompatibleLMClient) -> None:
        self._client = client

    async def parse(
        self,
        user_text: str,
        *,
        preference: dict[str, Any] | None = None,
        now: datetime | None = None,
        dept_names: list[str] | None = None,
        existing_filter: FilterSpec | None = None,
        recent_turns: list[ChatTurn] | None = None,
    ) -> DraftFilterSpec:
        """Parse a single user utterance into a :class:`DraftFilterSpec`.

        The method composes a structured user prompt and sends it to the LM
        client with the intent-parse system prompt.

        Parameters
        ----------
        user_text:
            Raw user utterance.
        preference:
            Optional user preference dict (reserved for future use).
        now:
            Current time in Asia/Shanghai; used to resolve relative periods.
        dept_names:
            Available department names for fuzzy matching.
        existing_filter:
            Previously parsed :class:`FilterSpec` in multi-turn scenarios.
        recent_turns:
            Recent conversation turns for multi-turn context.

        Notes
        -----
        - Ambiguous input is **not** an error: ``missing`` / ``conflicts`` may
          be populated and the state machine decides whether to clarify.
        - :class:`FilterParseError` is only raised when the LLM reply is not
          valid JSON or does not satisfy the schema.
        """

        if not user_text or not user_text.strip():
            raise FilterParseError("empty user text")

        prompt = self._compose_parse_prompt(
            user_text=user_text,
            now=now,
            dept_names=dept_names,
            preference=preference,
            existing_filter=existing_filter,
            recent_turns=recent_turns,
        )

        text = await self._client.chat(
            system_prompt=INTENT_PARSE_SYSTEM_PROMPT.template,
            user_prompt=prompt,
            response_format={"type": "json_object"},
        )

        payload = self._extract_json(text)

        try:
            return DraftFilterSpec.model_validate(payload)
        except ValidationError as exc:
            raise FilterParseError(
                "intent parser produced invalid DraftFilterSpec",
                details={"errors": exc.errors(), "raw": text[:1000]},
            ) from exc

    # ------------------------------------------------------------------
    # Prompt composition (mirrors Planner._compose_planning_prompt)
    # ------------------------------------------------------------------

    @staticmethod
    def _compose_parse_prompt(
        *,
        user_text: str,
        now: datetime | None = None,
        dept_names: list[str] | None = None,
        preference: dict[str, Any] | None = None,
        existing_filter: FilterSpec | None = None,
        recent_turns: list[ChatTurn] | None = None,
    ) -> str:
        """Render the user prompt template with structured context."""

        existing_filter_data: dict[str, Any] | None = None
        if existing_filter is not None:
            existing_filter_data = existing_filter.model_dump(mode="json")

        recent_turns_data: list[dict[str, Any]] = []
        if recent_turns:
            recent_turns_data = [
                {"role": t.role, "text": t.text} for t in recent_turns
            ]

        return render_prompt(
            INTENT_PARSE_USER_PROMPT,
            {
                "user_text": user_text,
                "now_iso": now.isoformat() if now else "",
                "dept_names_json": json.dumps(
                    dept_names or [], ensure_ascii=False
                ),
                "preference_json": json.dumps(
                    preference or {}, ensure_ascii=False
                ),
                "existing_filter_json": json.dumps(
                    existing_filter_data or {}, ensure_ascii=False
                ),
                "recent_turns_json": json.dumps(
                    recent_turns_data, ensure_ascii=False
                ),
            },
        )

    # ------------------------------------------------------------------
    # Response extraction helpers
    # ------------------------------------------------------------------

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
