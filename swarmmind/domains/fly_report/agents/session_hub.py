"""Per-session AgentScope ``MsgHub`` container for FlyReport.

One hub per ``(tenant_id, session_id)`` keeps cross-session contexts strictly
isolated.  Use it as an async context manager:

>>> async with FlyReportSessionHub(session_id, model_config) as hub:
...     reply = await hub.intent(msg)
"""

from __future__ import annotations

from typing import Any

from agentscope.message import Msg
from agentscope.pipeline import MsgHub

from swarmmind.config.schema import ModelConfig
from swarmmind.domains.fly_report.agents.factory import (
    build_clarifier_agent,
    build_followup_router_agent,
    build_intent_agent,
)


class FlyReportSessionHub:
    """Holds the per-session ``MsgHub`` plus its participating agents."""

    def __init__(
        self,
        session_id: str,
        model_config: ModelConfig,
        *,
        event_publisher: Any = None,
    ) -> None:
        self.session_id = session_id
        self.intent = build_intent_agent(model_config, event_publisher=event_publisher)
        self.clarifier = build_clarifier_agent(model_config, event_publisher=event_publisher)
        self.followup = build_followup_router_agent(
            model_config, event_publisher=event_publisher
        )
        self._hub: MsgHub | None = None

    async def __aenter__(self) -> "FlyReportSessionHub":
        self._hub = MsgHub(
            participants=[self.intent, self.clarifier, self.followup],
            announcement=Msg(
                "system",
                f"FlyReport session {self.session_id} started.",
                role="system",
            ),
        )
        await self._hub.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._hub is None:
            return
        try:
            await self._hub.__aexit__(exc_type, exc, tb)
        finally:
            self._hub = None


__all__ = ["FlyReportSessionHub"]
