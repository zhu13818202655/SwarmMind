"""Cache store protocol."""

from __future__ import annotations

from typing import Any, Protocol


class CacheStore(Protocol):
    """Async cache abstraction."""

    async def get(self, key: str) -> Any | None:
        ...

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        ...

    async def delete(self, key: str) -> None:
        ...