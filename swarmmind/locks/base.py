"""Lock manager protocol."""

from __future__ import annotations

from typing import Protocol


class LockManager(Protocol):
    """Async distributed lock abstraction."""

    async def acquire(self, key: str, ttl_seconds: int) -> str | None:
        ...

    async def release(self, key: str, token: str) -> bool:
        ...

    async def extend(self, key: str, token: str, ttl_seconds: int) -> bool:
        ...