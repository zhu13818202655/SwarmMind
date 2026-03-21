"""Gateway dispatch helpers."""

from __future__ import annotations

import asyncio
import logging

from swarmmind.events.bus import EventBus
from swarmmind.models.event import DomainEvent


logger = logging.getLogger(__name__)


class GatewayDispatcher:
    """Dispatch gateway events onto the event bus."""

    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._background_tasks: set[asyncio.Task[None]] = set()

    async def dispatch(self, event: DomainEvent) -> None:
        """Publish an event to the bus."""
        await self._event_bus.publish(event)

    def dispatch_background(self, event: DomainEvent) -> None:
        """Publish an event in the background without blocking the caller."""
        task = asyncio.create_task(self._event_bus.publish(event))
        self._background_tasks.add(task)
        task.add_done_callback(self._on_background_done)

    def _on_background_done(self, task: asyncio.Task[None]) -> None:
        self._background_tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.exception("Background event dispatch failed", exc_info=exc)
