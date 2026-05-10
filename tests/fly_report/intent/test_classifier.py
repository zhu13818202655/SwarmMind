"""Unit tests for :class:`IntentClassifier`.

We stub the LM client at the ``chat_response`` boundary so the tests stay
focused on the classifier's contract: turn the parsed JSON into one of
``chitchat / report / data_query``, and fall back to ``report`` whenever
the LLM call or its payload is unusable.
"""

from __future__ import annotations

from typing import Any

import pytest

from swarmmind.domains.fly_report.intent.classifier import IntentClassifier
from swarmmind.domains.fly_report.lm.types import (
    LMChatRequest,
    LMChatResponse,
    LMOutputFormat,
)


class _StubLMClient:
    def __init__(
        self,
        *,
        parsed: Any = None,
        text: str = "{}",
        raise_exc: Exception | None = None,
    ) -> None:
        self._parsed = parsed
        self._text = text
        self._raise = raise_exc
        self.requests: list[LMChatRequest] = []

    async def chat_response(self, request: LMChatRequest) -> LMChatResponse:
        self.requests.append(request)
        if self._raise is not None:
            raise self._raise
        return LMChatResponse(
            text=self._text,
            output_format=LMOutputFormat.JSON,
            parsed=self._parsed,
            raw=None,
            model_name="stub",
            usage=None,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "parsed, expected",
    [
        ({"intent": "chitchat", "reason": "greeting"}, "chitchat"),
        ({"intent": "report"}, "report"),
        ({"intent": "data_query"}, "data_query"),
        ({"intent": "REPORT"}, "report"),  # case-insensitive
        ({"intent": " data_query "}, "data_query"),  # whitespace tolerant
    ],
)
async def test_classify_returns_label(parsed: dict[str, Any], expected: str) -> None:
    classifier = IntentClassifier(client=_StubLMClient(parsed=parsed))
    assert await classifier.classify("帮我生成本周报告") == expected


@pytest.mark.asyncio
async def test_blank_text_short_circuits_to_chitchat() -> None:
    stub = _StubLMClient(parsed={"intent": "report"})
    classifier = IntentClassifier(client=stub)
    assert await classifier.classify("   ") == "chitchat"
    assert stub.requests == []  # LLM should not be called at all


@pytest.mark.asyncio
async def test_unknown_label_falls_back_to_report() -> None:
    classifier = IntentClassifier(
        client=_StubLMClient(parsed={"intent": "weather"}),
    )
    assert await classifier.classify("今天天气怎么样") == "report"


@pytest.mark.asyncio
async def test_non_dict_parsed_falls_back_to_report() -> None:
    classifier = IntentClassifier(client=_StubLMClient(parsed="not a dict"))
    assert await classifier.classify("随便聊聊") == "report"


@pytest.mark.asyncio
async def test_missing_intent_field_falls_back_to_report() -> None:
    classifier = IntentClassifier(client=_StubLMClient(parsed={"reason": "x"}))
    assert await classifier.classify("随便聊聊") == "report"


@pytest.mark.asyncio
async def test_llm_exception_falls_back_to_report() -> None:
    classifier = IntentClassifier(
        client=_StubLMClient(raise_exc=RuntimeError("boom")),
    )
    assert await classifier.classify("随便聊聊") == "report"


@pytest.mark.asyncio
async def test_request_uses_json_response_format() -> None:
    stub = _StubLMClient(parsed={"intent": "chitchat"})
    classifier = IntentClassifier(client=stub)
    await classifier.classify("你好")

    assert len(stub.requests) == 1
    req = stub.requests[0]
    assert req.response_format == {"type": "json_object"}
    assert req.output_format == LMOutputFormat.JSON
    assert req.user_prompt is not None and "你好" in req.user_prompt
