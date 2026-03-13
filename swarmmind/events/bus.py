"""Event bus protocol."""

from __future__ import annotations

from typing import Awaitable, Callable, Protocol

from swarmmind.models.event import DomainEvent

EventHandler = Callable[[DomainEvent], Awaitable[None]]


class EventBus(Protocol):
    """Minimal async event bus contract."""

    async def publish(self, event: DomainEvent) -> None:
        ...

    async def subscribe(self, topic: str, handler: EventHandler) -> None:
        ...
