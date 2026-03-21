from __future__ import annotations

import asyncio
import subprocess
import uuid

import pytest
from psycopg import AsyncConnection
from qdrant_client import QdrantClient
from redis import asyncio as redis_asyncio

from swarmmind.app.container import build_container
from swarmmind.config import SwarmMindConfig
from swarmmind.events import RedisBufferedEventBus
from swarmmind.gateway import TaskSubmitRequest
from swarmmind.locks import RedisLockManager
from swarmmind.memory import QdrantLongTermMemory
from swarmmind.models.run import RunStatus
from swarmmind.repositories import PostgresTaskRepository


def _discover_service_port(service: str, container_port: int) -> int:
    try:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                "deploy/docker-compose.yaml",
                "port",
                service,
                str(container_port),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        pytest.skip(f"Cannot discover Docker port mapping for {service}: {exc}")

    output = result.stdout.strip()
    if not output or ":" not in output:
        pytest.skip(f"No Docker port mapping found for {service}:{container_port}")

    return int(output.rsplit(":", 1)[1])


async def _ensure_postgres(dsn: str) -> None:
    for _ in range(20):
        try:
            connection = await AsyncConnection.connect(dsn)
        except Exception:
            await asyncio.sleep(1)
            continue
        await connection.close()
        return
    pytest.skip("PostgreSQL is unavailable for live integration test")


async def _ensure_redis(url: str) -> None:
    client = redis_asyncio.from_url(url, decode_responses=True)
    for _ in range(20):
        try:
            await client.ping()
        except Exception:
            await asyncio.sleep(1)
            continue
        await client.aclose()
        return
    await client.aclose()
    pytest.skip("Redis is unavailable for live integration test")


async def _ensure_qdrant(url: str) -> None:
    for _ in range(30):
        try:
            client = QdrantClient(url=url, check_compatibility=False)
            client.get_collections()
        except Exception:
            await asyncio.sleep(1)
            continue
        return
    pytest.skip("Qdrant is unavailable for live integration test")


async def _wait_for_terminal_run(container, run_id: str, identity, timeout: float = 20.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        run_detail = await container.query_service.get_run_detail(run_id, identity)
        if run_detail is not None and run_detail.run.status in {
            RunStatus.SUCCEEDED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        }:
            return run_detail
        await asyncio.sleep(0.1)
    pytest.fail(f"Run {run_id} did not reach terminal state within {timeout}s")


@pytest.mark.asyncio
async def test_live_postgres_redis_qdrant_stack_supports_task_flow() -> None:
    collection = f"swarmmind-test-{uuid.uuid4().hex[:12]}"
    postgres_port = _discover_service_port("postgres", 5432)
    redis_port = _discover_service_port("redis", 6379)
    qdrant_port = _discover_service_port("qdrant", 6333)
    settings = SwarmMindConfig(
        sandbox={"provider": "local"},
        postgres={
            "enabled": True,
            "dsn": f"postgresql://swarmmind:swarmmind@127.0.0.1:{postgres_port}/swarmmind",
            "auto_init_schema": True,
        },
        redis={
            "enabled": True,
            "url": f"redis://127.0.0.1:{redis_port}/0",
            "event_stream": "swarmmind:test:events",
            "channel_prefix": "swarmmind:test",
            "cache_prefix": "swarmmind:test:cache",
            "lock_prefix": "swarmmind:test:lock",
        },
        vector_store={
            "enabled": True,
            "provider": "qdrant",
            "qdrant_url": f"http://127.0.0.1:{qdrant_port}",
            "collection": collection,
            "embedding_dimension": 256,
        },
    )

    await _ensure_postgres(settings.postgres.dsn)
    await _ensure_redis(settings.redis.url)
    await _ensure_qdrant(settings.vector_store.qdrant_url)

    container = await build_container(settings)
    identity = await container.identity_resolver.resolve()

    assert isinstance(container.task_repository, PostgresTaskRepository)
    assert isinstance(container.event_bus, RedisBufferedEventBus)
    assert isinstance(container.lock_manager, RedisLockManager)
    assert isinstance(container.long_term_memory, QdrantLongTermMemory)

    submission = await container.gateway.submit_task(
        TaskSubmitRequest(goal="实现一个导出 Excel 功能并补测试", profile="py-basic"),
        identity=identity,
    )

    run_detail = await _wait_for_terminal_run(container, submission.run_id, identity)
    replay = await container.replay_repository.get_by_run(submission.run_id)
    persisted_task = await container.task_repository.get(submission.task_id)

    assert run_detail is not None
    assert replay is not None
    assert persisted_task is not None
    assert run_detail.artifacts
    assert replay.entries

    await container.cache_store.set("live-smoke", {"run_id": submission.run_id}, ttl_seconds=30)
    cached_value = await container.cache_store.get("live-smoke")
    assert cached_value == {"run_id": submission.run_id}

    lock_token = await container.lock_manager.acquire("live-smoke-lock", ttl_seconds=30)
    assert lock_token is not None
    assert await container.lock_manager.extend("live-smoke-lock", lock_token, ttl_seconds=30)
    assert await container.lock_manager.release("live-smoke-lock", lock_token)

    memory_id = await container.long_term_memory.store(
        "SwarmMind integrates PostgreSQL Redis and Qdrant in one execution flow",
        {"run_id": submission.run_id},
    )
    memories = await container.long_term_memory.retrieve("Redis Qdrant execution flow", top_k=5)
    assert any(memory.id == memory_id for memory in memories)

    fresh_container = await build_container(settings)
    fresh_identity = await fresh_container.identity_resolver.resolve()
    persisted_run_detail = await fresh_container.query_service.get_run_detail(submission.run_id, fresh_identity)

    assert persisted_run_detail is not None
    assert persisted_run_detail.run.id == submission.run_id
    assert persisted_run_detail.subtasks
    assert persisted_run_detail.artifacts

    await container.long_term_memory.clear()