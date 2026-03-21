"""In-memory lock manager."""

from __future__ import annotations

import time
import uuid


class InMemoryLockManager:
    """Process-local lock manager for development and tests."""

    def __init__(self) -> None:
        self._locks: dict[str, tuple[str, float]] = {}

    async def acquire(self, key: str, ttl_seconds: int) -> str | None:
        self._cleanup_expired(key)
        if key in self._locks:
            return None
        token = str(uuid.uuid4())
        self._locks[key] = (token, time.monotonic() + ttl_seconds)
        return token

    async def release(self, key: str, token: str) -> bool:
        self._cleanup_expired(key)
        current = self._locks.get(key)
        if current is None or current[0] != token:
            return False
        self._locks.pop(key, None)
        return True

    async def extend(self, key: str, token: str, ttl_seconds: int) -> bool:
        self._cleanup_expired(key)
        current = self._locks.get(key)
        if current is None or current[0] != token:
            return False
        self._locks[key] = (token, time.monotonic() + ttl_seconds)
        return True

    def _cleanup_expired(self, key: str) -> None:
        current = self._locks.get(key)
        if current is not None and current[1] <= time.monotonic():
            self._locks.pop(key, None)