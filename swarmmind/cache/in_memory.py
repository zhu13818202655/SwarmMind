"""In-memory cache store."""

from __future__ import annotations

import time
from typing import Any


class InMemoryCacheStore:
    """Simple process-local cache implementation."""

    def __init__(self) -> None:
        self._items: dict[str, tuple[Any, float | None]] = {}

    async def get(self, key: str) -> Any | None:
        item = self._items.get(key)
        if item is None:
            return None
        value, expires_at = item
        if expires_at is not None and expires_at <= time.monotonic():
            self._items.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        expires_at = None if ttl_seconds is None else time.monotonic() + ttl_seconds
        self._items[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        self._items.pop(key, None)