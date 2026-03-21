"""Redis-backed cache store."""

from __future__ import annotations

import json
from typing import Any

from redis import asyncio as redis_asyncio


class RedisCacheStore:
    """Cache implementation backed by Redis."""

    def __init__(self, url: str, prefix: str = "swarmmind:cache") -> None:
        self._client = redis_asyncio.from_url(url, decode_responses=True)
        self._prefix = prefix

    async def get(self, key: str) -> Any | None:
        raw = await self._client.get(self._build_key(key))
        if raw is None:
            return None
        return json.loads(raw)

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        payload = json.dumps(value, ensure_ascii=False)
        await self._client.set(self._build_key(key), payload, ex=ttl_seconds)

    async def delete(self, key: str) -> None:
        await self._client.delete(self._build_key(key))

    def _build_key(self, key: str) -> str:
        return f"{self._prefix}:{key}"