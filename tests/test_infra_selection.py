from __future__ import annotations

import pytest

from swarmmind.app.container import (
    _build_cache_store,
    _build_event_bus,
    _build_lock_manager,
    _build_long_term_memory,
    _build_repositories,
    _build_sandbox_provider,
    build_container,
)
from swarmmind.cache import InMemoryCacheStore, RedisCacheStore
from swarmmind.config import SwarmMindConfig
from swarmmind.events import InMemoryEventBus, RedisBufferedEventBus
from swarmmind.locks import InMemoryLockManager, RedisLockManager
from swarmmind.memory import InMemoryLongTermMemory
from swarmmind.repositories import PostgresTaskRepository
from swarmmind.repositories import FileArtifactRepository, FileReplayRepository
from swarmmind.sandbox.local_adapter import LocalSandboxAdapter
from swarmmind.sandbox.opensandbox_adapter import OpenSandboxAdapter
from swarmmind.sandbox.profiles import DEFAULT_PROFILES


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


def test_build_sandbox_provider_uses_opensandbox_without_api_key() -> None:
    settings = SwarmMindConfig(sandbox={"provider": "opensandbox", "api_key": None, "base_url": "http://localhost:45698"})

    provider = _build_sandbox_provider(settings)

    assert isinstance(provider, OpenSandboxAdapter)


def test_build_sandbox_provider_defaults_to_local_for_local_provider() -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})

    provider = _build_sandbox_provider(settings)

    assert isinstance(provider, LocalSandboxAdapter)


def test_default_aio_profile_uses_latest_agent_infra_image() -> None:
    profile = DEFAULT_PROFILES["aio"]

    assert profile.image == "ghcr.io/agent-infra/sandbox:latest"
    assert profile.entrypoint == ["/opt/gem/run.sh"]


def test_opensandbox_adapter_sanitizes_metadata_for_label_compatibility() -> None:
    metadata = {
        "skill_name": "pptx",
        "script_path": "scripts/add_slide.py",
        "task id": "  a490552e-0fbc-4b02-8a8e-8ea8203751ec  ",
    }

    sanitized = OpenSandboxAdapter._sanitize_metadata(metadata)

    assert sanitized == {
        "skill_name": "pptx",
        "script_path": "scripts-add_slide.py",
        "task-id": "a490552e-0fbc-4b02-8a8e-8ea8203751ec",
    }


@pytest.mark.asyncio
async def test_opensandbox_adapter_create_error_includes_root_cause(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = OpenSandboxAdapter(
        api_key="test-key",
        base_url="http://localhost:45698",
        create_retry_count=2,
        create_retry_backoff_seconds=0.0,
    )

    async def fail_create(profile, metadata):
        del profile, metadata
        raise ValueError("missing auth header")

    monkeypatch.setattr(adapter, "_create_sandbox", fail_create)

    with pytest.raises(RuntimeError) as exc_info:
        await adapter.create("aio")

    message = str(exc_info.value)
    assert "Failed to create sandbox after retries" in message
    assert "profile=aio" in message
    assert "cause=ValueError: missing auth header" in message