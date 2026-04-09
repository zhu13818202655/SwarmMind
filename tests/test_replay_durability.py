from __future__ import annotations

import asyncio
import uuid

import httpx
import pytest

from swarmmind.api.server import create_app
from swarmmind.app.container import build_container
from swarmmind.config import SwarmMindConfig
from swarmmind.gateway import TaskSubmitRequest
from swarmmind.models.artifact import Artifact, ArtifactType
from swarmmind.models.event import DomainEvent
from swarmmind.models.replay import ReplayEntry, ReplayRoot
from swarmmind.models.run import RunStatus
from swarmmind.repositories import FileArtifactRepository, FileReplayRepository


async def _wait_for_terminal_run(container, run_id: str, identity, timeout: float = 10.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        run_detail = await container.query_service.get_run_detail(run_id, identity)
        if run_detail is not None and run_detail.run.status in {
            RunStatus.SUCCEEDED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        }:
            return run_detail
        await asyncio.sleep(0.05)
    raise TimeoutError(f"Run {run_id} did not reach terminal state within {timeout}s")


@pytest.mark.asyncio
async def test_file_backed_replay_and_artifacts_persist_across_container_restart(tmp_path) -> None:
    settings = SwarmMindConfig(
        sandbox={"provider": "local"},
        repositories={
            "artifact_backend": "file",
            "replay_backend": "file",
            "file_base_path": str(tmp_path),
        },
    )
    container = await build_container(settings)
    identity = await container.identity_resolver.resolve()

    submission = await container.gateway.submit_task(
        TaskSubmitRequest(goal="实现一个导出 Excel 功能并补测试", profile="py-basic"),
        identity=identity,
    )

    run_detail = await _wait_for_terminal_run(container, submission.run_id, identity)
    replay = await container.replay_repository.get_by_run(submission.run_id)
    implementation_subtask = next(subtask for subtask in run_detail.subtasks if subtask.name == "prepare-implementation")
    subtask_artifacts = await container.artifact_repository.list_for_subtask(submission.run_id, implementation_subtask.id)

    assert replay is not None
    assert subtask_artifacts
    event_types = [entry.event_type for entry in replay.entries]
    assert "run.terminal" in event_types
    assert "run.summary" in event_types
    assert "subtask.terminal" in event_types
    assert "subtask.summary" in event_types

    fresh_container = await build_container(settings)
    persisted_replay = await fresh_container.replay_repository.get_by_run(submission.run_id)
    persisted_artifacts = await fresh_container.artifact_repository.list_for_subtask(submission.run_id, implementation_subtask.id)

    assert persisted_replay is not None
    assert persisted_replay.entries
    assert persisted_artifacts


@pytest.mark.asyncio
async def test_subtask_replay_and_artifact_api_returns_filtered_results(tmp_path) -> None:
    run_id = "run-api-1"
    subtask_id = "subtask-api-1"
    other_subtask_id = "subtask-api-2"

    replay_repository = FileReplayRepository(tmp_path)
    artifact_repository = FileArtifactRepository(tmp_path)
    await replay_repository.create(
        ReplayRoot(
            id=str(uuid.uuid4()),
            task_id="task-api-1",
            run_id=run_id,
            entries=[
                ReplayEntry(event_type="subtask.started", payload={"subtask_id": subtask_id, "name": "prepare-implementation"}),
                ReplayEntry(event_type="tool.failed", payload={"subtask_id": subtask_id, "tool_name": "sandbox_exec", "error": "boom"}),
                ReplayEntry(event_type="subtask.summary", payload={"subtask_id": subtask_id, "status": "succeeded"}),
                ReplayEntry(event_type="subtask.summary", payload={"subtask_id": other_subtask_id, "status": "succeeded"}),
            ],
        )
    )
    await artifact_repository.create(
        Artifact(
            id=str(uuid.uuid4()),
            task_id="task-api-1",
            run_id=run_id,
            subtask_id=subtask_id,
            name="prepare-implementation-report.md",
            type=ArtifactType.REPORT,
            metadata={"content": "ok"},
        )
    )
    await artifact_repository.create(
        Artifact(
            id=str(uuid.uuid4()),
            task_id="task-api-1",
            run_id=run_id,
            subtask_id=other_subtask_id,
            name="other-report.md",
            type=ArtifactType.REPORT,
            metadata={"content": "other"},
        )
    )

    settings = SwarmMindConfig(
        sandbox={"provider": "local"},
        repositories={
            "artifact_backend": "file",
            "replay_backend": "file",
            "file_base_path": str(tmp_path),
        },
    )
    app = create_app(settings)
    app.state.container = await build_container(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        events_response = await client.get(f"/v1/runs/{run_id}/subtasks/{subtask_id}/events")
        assert events_response.status_code == 200
        events_payload = events_response.json()
        assert events_payload["run_id"] == run_id
        assert events_payload["subtask_id"] == subtask_id
        assert events_payload["events"]
        assert all(
            item["payload"].get("subtask_id") == subtask_id
            for item in events_payload["events"]
        )

        filtered_events_response = await client.get(
            f"/v1/runs/{run_id}/subtasks/{subtask_id}/events",
            params={"topic": "tool.failed", "tool_name": "sandbox_exec"},
        )
        assert filtered_events_response.status_code == 200
        filtered_events_payload = filtered_events_response.json()
        assert [item["event_type"] for item in filtered_events_payload["events"]] == ["tool.failed"]
        assert all(item["payload"].get("tool_name") == "sandbox_exec" for item in filtered_events_payload["events"])

        artifacts_response = await client.get(f"/v1/runs/{run_id}/subtasks/{subtask_id}/artifacts")
        assert artifacts_response.status_code == 200
        artifacts_payload = artifacts_response.json()
        assert artifacts_payload["run_id"] == run_id
        assert artifacts_payload["subtask_id"] == subtask_id
        assert artifacts_payload["artifacts"]
        assert all(
            item.get("subtask_id") == subtask_id
            for item in artifacts_payload["artifacts"]
        )


@pytest.mark.asyncio
async def test_audit_trace_events_persist_to_file_backed_artifacts(tmp_path) -> None:
    settings = SwarmMindConfig(
        repositories={
            "artifact_backend": "file",
            "replay_backend": "file",
            "file_base_path": str(tmp_path),
        },
    )
    container = await build_container(settings)

    await container.event_bus.publish(
        DomainEvent(
            event_id="event-llm-1",
            topic="llm.requested",
            tenant_id="tenant-test",
            session_id="session-test",
            task_id="task-audit-1",
            run_id="run-audit-1",
            subtask_id="subtask-audit-1",
            payload={
                "model_name": "gpt-4o",
                "messages": [{"role": "user", "content": "record this prompt"}],
            },
        )
    )
    await container.event_bus.publish(
        DomainEvent(
            event_id="event-tool-1",
            topic="tool.completed",
            tenant_id="tenant-test",
            session_id="session-test",
            task_id="task-audit-1",
            run_id="run-audit-1",
            subtask_id="subtask-audit-1",
            payload={
                "tool_name": "sandbox_exec",
                "command": "pytest -q",
                "result": {"exit_code": 0, "stdout": "ok"},
            },
        )
    )

    artifacts = await container.artifact_repository.list_for_run("run-audit-1")

    assert len(artifacts) == 2
    assert {artifact.metadata.get("topic") for artifact in artifacts} == {"llm.requested", "tool.completed"}
    llm_artifact = next(artifact for artifact in artifacts if artifact.metadata.get("topic") == "llm.requested")
    tool_artifact = next(artifact for artifact in artifacts if artifact.metadata.get("topic") == "tool.completed")
    assert llm_artifact.type == ArtifactType.TRANSCRIPT
    assert tool_artifact.type == ArtifactType.LOG
    assert llm_artifact.metadata["payload"]["messages"][0]["content"] == "record this prompt"
    assert tool_artifact.metadata["payload"]["result"]["stdout"] == "ok"