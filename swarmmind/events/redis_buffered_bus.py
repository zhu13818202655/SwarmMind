"""Redis-backed event bus with local dispatch and stream buffering."""

from __future__ import annotations

import json
from collections import defaultdict

from redis import asyncio as redis_asyncio

from swarmmind.events.bus import EventHandler
from swarmmind.models.event import DomainEvent


class RedisBufferedEventBus:
    """Publish events to Redis while preserving in-process subscribers."""

    def __init__(self, url: str, stream_name: str = "swarmmind:events", channel_prefix: str = "swarmmind"):
        self._client = redis_asyncio.from_url(url, decode_responses=True)
        self._stream_name = stream_name
        self._channel_prefix = channel_prefix.rstrip(":")
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._events: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> None:
        payload = event.model_dump(mode="json")
        serialized = json.dumps(payload, ensure_ascii=False)
        self._events.append(event)

        await self._client.xadd(
            self._stream_name,
            {
                "topic": event.topic,
                "event": serialized,
            },
        )
        await self._client.publish(self._channel_name(event.topic), serialized)

        handlers = list(self._subscribers.get(event.topic, [])) + list(self._subscribers.get("*", []))
        for handler in handlers:
            await handler(event)

    async def subscribe(self, topic: str, handler: EventHandler) -> None:
        self._subscribers[topic].append(handler)

    def list_events(self) -> list[DomainEvent]:
        return list(self._events)

    def _channel_name(self, topic: str) -> str:
        return f"{self._channel_prefix}:{topic}"