"""In-memory event bus implementation."""

from __future__ import annotations

from collections import defaultdict

from swarmmind.events.bus import EventHandler
from swarmmind.models.event import DomainEvent


class InMemoryEventBus:
    """A simple in-process event bus for the first rewrite round."""

    def __init__(self):
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._events: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> None:
        """Publish an event to all matching subscribers."""
        self._events.append(event)
        handlers = list(self._subscribers.get(event.topic, [])) + list(self._subscribers.get("*", []))
        for handler in handlers:
            await handler(event)

    async def subscribe(self, topic: str, handler: EventHandler) -> None:
        """Register a handler for a topic."""
        self._subscribers[topic].append(handler)

    def list_events(self) -> list[DomainEvent]:
        """Return the published event history."""
        return list(self._events)
