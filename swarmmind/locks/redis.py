"""Redis-backed lock manager."""

from __future__ import annotations

import uuid
from typing import Any

from redis import asyncio as redis_asyncio


class RedisLockManager:
    """Lock manager using Redis SET NX EX semantics."""

    _RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""

    _EXTEND_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('expire', KEYS[1], ARGV[2])
end
return 0
"""

    def __init__(self, url: str, prefix: str = "swarmmind:lock") -> None:
        self._client = redis_asyncio.from_url(url, decode_responses=True)
        self._prefix = prefix

    async def acquire(self, key: str, ttl_seconds: int) -> str | None:
        token = str(uuid.uuid4())
        acquired = await self._client.set(self._build_key(key), token, ex=ttl_seconds, nx=True)
        return token if acquired else None

    async def release(self, key: str, token: str) -> bool:
        released = await self._execute_lua(self._RELEASE_SCRIPT, self._build_key(key), token)
        return bool(released)

    async def extend(self, key: str, token: str, ttl_seconds: int) -> bool:
        extended = await self._execute_lua(
            self._EXTEND_SCRIPT,
            self._build_key(key),
            token,
            ttl_seconds,
        )
        return bool(extended)

    def _build_key(self, key: str) -> str:
        return f"{self._prefix}:{key}"

    async def _execute_lua(self, script: str, key: str, *args: Any) -> Any:
        return await self._client.execute_command("EVAL", script, 1, key, *args)