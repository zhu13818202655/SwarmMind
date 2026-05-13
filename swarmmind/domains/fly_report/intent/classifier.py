"""Lightweight LLM-based intent classifier for FlyReport conversations.

Each user turn is first routed into one of three buckets so that the service
can decide whether to invoke the report pipeline, answer with chitchat, or
hand off to the (future) Text-to-SQL data-query path.

The classifier deliberately mirrors the simple style of
``simple_composer.llm_client``: a single OpenAI-compatible chat call with a
strict JSON ``response_format``. It is intentionally cheap and stateless.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from swarmmind.config.settings import get_settings
from swarmmind.domains.fly_report.lm.client import OpenAICompatibleLMClient
from swarmmind.domains.fly_report.lm.types import LMChatRequest, LMOutputFormat

logger = logging.getLogger(__name__)

IntentLabel = Literal["chitchat", "report", "data_query"]
_VALID_LABELS: set[str] = {"chitchat", "report", "data_query"}
_MAX_ATTEMPTS = 3

_SYSTEM_PROMPT = (
    "你是飞行报告平台的意图分类器。\n"
    "用户输入会被分到下列三类之一：\n"
    "1. chitchat —— 闲聊、问候、致谢、与平台无关的开放问题；\n"
    "2. report —— 用户希望生成、导出、修改飞行/算法/媒体相关的统计报告；\n"
    "3. data_query —— 用户希望就具体业务数据进行查询、检索、明细查找、"
    "聚合统计或对比（最终需要 Text-to-SQL 才能回答）。\n"
    "严格输出 JSON：{\"intent\": \"chitchat|report|data_query\", \"reason\": \"...\"}。"
    "不要输出任何额外文字、解释或代码块。"
)


class IntentClassifier:
    """Classify a user utterance into chitchat / report / data_query."""

    def __init__(
        self,
        *,
        client: OpenAICompatibleLMClient | None = None,
    ) -> None:
        if client is None:
            settings = get_settings()
            client = OpenAICompatibleLMClient(
                model_name=settings.agent.model.name,
                api_key=settings.agent.model.api_key,
                base_url=settings.agent.model.base_url,
                temperature=1.0,
                max_tokens=128,
                timeout_sec=20.0,
            )
        self._client = client

    async def classify(self, text: str) -> IntentLabel:
        """Return the predicted intent label.

        Retries up to ``_MAX_ATTEMPTS`` times when the LLM call raises or the
        response cannot be parsed into a valid label. Falls back to
        ``"report"`` after all attempts fail so that the existing report
        pipeline remains the safe default.
        """

        if not text or not text.strip():
            return "chitchat"

        request = LMChatRequest(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=f"用户输入：\n{text.strip()}",
            output_format=LMOutputFormat.JSON,
            temperature=1.0,
            max_tokens=512,
            response_format={"type": "json_object"},
        )

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = await self._client.chat_response(request)
            except Exception:
                logger.exception(
                    "fly_report.intent_classify_llm_failed",
                    extra={
                        "text_preview": text[:120],
                        "attempt": attempt,
                        "max_attempts": _MAX_ATTEMPTS,
                    },
                )
                continue

            label = self._parse_label(response.parsed)
            if label is not None:
                return label

            logger.warning(
                "fly_report.intent_classify_unparsable",
                extra={
                    "raw": response.text[:200] if response.text else "",
                    "attempt": attempt,
                    "max_attempts": _MAX_ATTEMPTS,
                },
            )

        return "report"

    @staticmethod
    def _parse_label(payload: Any) -> IntentLabel | None:
        if not isinstance(payload, dict):
            return None
        value = payload.get("intent")
        if not isinstance(value, str):
            return None
        normalized = value.strip().lower()
        if normalized in _VALID_LABELS:
            return normalized  # type: ignore[return-value]
        return None


__all__ = ["IntentClassifier", "IntentLabel"]
