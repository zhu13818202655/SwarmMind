"""Test fixtures for the FlyReport intent layer.

We mock at the **LM client boundary** rather than at the chat-model boundary so
tests stay focused on the parser's contract: given a JSON reply from the
``OpenAICompatibleLMClient``, the parser must produce a valid
``DraftFilterSpec`` (or raise :class:`FilterParseError`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pytest


@dataclass
class StubLMClient:
    """Minimal async-callable stand-in for :class:`OpenAICompatibleLMClient`.

    The stub records every call it receives in :attr:`calls` and returns a
    pre-canned reply string.  ``replies`` may contain either a string or a
    callable producing one.
    """

    replies: list[str | Callable[[str], str]] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def chat(
        self,
        *,
        system_prompt: str | None = None,
        user_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        self.calls.append(
            {"system_prompt": system_prompt, "user_prompt": user_prompt, **kwargs}
        )
        if not self.replies:
            raise AssertionError("StubLMClient received an unexpected call")
        reply = self.replies.pop(0)
        text = reply(user_prompt or "") if callable(reply) else reply
        return text


@pytest.fixture
def stub_lm_client_factory() -> Callable[..., StubLMClient]:
    def _factory(*replies: str | Callable[[str], str]) -> StubLMClient:
        return StubLMClient(replies=list(replies))

    return _factory
