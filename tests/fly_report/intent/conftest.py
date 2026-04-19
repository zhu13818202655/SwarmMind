"""Test fixtures for the FlyReport intent layer.

We mock at the **agent boundary** rather than at the chat-model boundary so
tests stay focused on the parser's contract: given a JSON reply from the
``IntentParserAgent``, the parser must produce a valid ``DraftFilterSpec``
(or raise :class:`FilterParseError`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pytest
from agentscope.message import Msg


@dataclass
class StubAgent:
    """Minimal async-callable stand-in for ``IntentParserAgent``.

    The stub records every ``Msg`` it receives in :attr:`calls` and returns a
    pre-canned reply. ``replies`` may contain either a string (returned as the
    text content of an assistant ``Msg``) or a callable producing one.
    """

    replies: list[str | Callable[[Msg], str]] = field(default_factory=list)
    calls: list[Msg] = field(default_factory=list)

    async def __call__(self, msg: Msg, *args: Any, **kwargs: Any) -> Msg:
        self.calls.append(msg)
        if not self.replies:
            raise AssertionError("StubAgent received an unexpected call")
        reply = self.replies.pop(0)
        text = reply(msg) if callable(reply) else reply
        return Msg(name="fly_report.intent_parser", role="assistant", content=text)


@pytest.fixture
def stub_agent_factory() -> Callable[..., StubAgent]:
    def _factory(*replies: str | Callable[[Msg], str]) -> StubAgent:
        return StubAgent(replies=list(replies))

    return _factory
