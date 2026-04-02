from __future__ import annotations

import pytest

from swarmmind.app.container import (
    _build_cache_store,
    _build_event_bus,
    _build_lock_manager,
    _build_long_term_memory,
    _build_repositories,
    build_container,
)
from swarmmind.cache import InMemoryCacheStore, RedisCacheStore
from swarmmind.config import SwarmMindConfig
from swarmmind.events import InMemoryEventBus, RedisBufferedEventBus
from swarmmind.locks import InMemoryLockManager, RedisLockManager
from swarmmind.memory import InMemoryLongTermMemory
from swarmmind.repositories import PostgresTaskRepository
from swarmmind.repositories import FileArtifactRepository, FileReplayRepository


@pytest.mark.asyncio
async def test_build_repositories_uses_postgres_when_enabled_without_init() -> None:
    settings = SwarmMindConfig(
        postgres={
            "enabled": True,
            "dsn": "postgresql://swarmmind:swarmmind@127.0.0.1:5432/swarmmind",
            "auto_init_schema": False,
        }
    )

    repositories = await _build_repositories(settings)

    assert isinstance(repositories[0], PostgresTaskRepository)


@pytest.mark.asyncio
async def test_build_repositories_can_use_file_backed_replay_and_artifacts(tmp_path) -> None:
    settings = SwarmMindConfig(
        repositories={
            "artifact_backend": "file",
            "replay_backend": "file",
            "file_base_path": str(tmp_path),
        }
    )

    repositories = await _build_repositories(settings)

    assert isinstance(repositories[4], FileArtifactRepository)
    assert isinstance(repositories[5], FileReplayRepository)


def test_infra_builders_switch_to_redis_types_when_enabled() -> None:
    settings = SwarmMindConfig(redis={"enabled": True, "url": "redis://127.0.0.1:6379/0"})

    assert isinstance(_build_event_bus(settings), RedisBufferedEventBus)
    assert isinstance(_build_cache_store(settings), RedisCacheStore)
    assert isinstance(_build_lock_manager(settings), RedisLockManager)


def test_infra_builders_default_to_in_memory_types() -> None:
    settings = SwarmMindConfig()

    assert isinstance(_build_event_bus(settings), InMemoryEventBus)
    assert isinstance(_build_cache_store(settings), InMemoryCacheStore)
    assert isinstance(_build_lock_manager(settings), InMemoryLockManager)


def test_long_term_memory_defaults_to_in_memory() -> None:
    settings = SwarmMindConfig(vector_store={"provider": "memory", "enabled": False})

    assert isinstance(_build_long_term_memory(settings), InMemoryLongTermMemory)


@pytest.mark.asyncio
async def test_container_exposes_protocol_backed_infra_fields() -> None:
    settings = SwarmMindConfig(
        sandbox={"provider": "local"},
        redis={"enabled": False},
        postgres={"enabled": False},
        vector_store={"provider": "memory", "enabled": False},
    )

    container = await build_container(settings)

    assert isinstance(container.event_bus, InMemoryEventBus)
    assert isinstance(container.cache_store, InMemoryCacheStore)
    assert isinstance(container.lock_manager, InMemoryLockManager)
    assert isinstance(container.long_term_memory, InMemoryLongTermMemory)