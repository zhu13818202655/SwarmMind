from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from swarmmind.events import InMemoryEventBus
from swarmmind.models.replay import ReplayRoot
from swarmmind.repositories import InMemoryArtifactRepository, InMemoryReplayRepository
from swarmmind.sandbox import LocalSandboxAdapter, ReplayRecorder, SandboxManager
from swarmmind.skill_system import (
    SkillExecutionContext,
    SkillExecutionService,
    SkillScriptExecutionPolicy,
    SkillScriptExecutor,
)
from swarmmind.tools.builtin import SkillTool


def _write_skill(root: Path, name: str) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        "description: demo skill\n"
        "---\n\n"
        "# Demo Skill\n",
        encoding="utf-8",
    )
    return skill_dir


@pytest.mark.asyncio
async def test_skill_execution_service_publishes_events_and_persists_artifacts(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path, "demo_skill")
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "run.sh").write_text(
        "printf 'hello artifact' > outputs/result.txt\n",
        encoding="utf-8",
    )

    event_bus = InMemoryEventBus()
    artifact_repository = InMemoryArtifactRepository()
    replay_repository = InMemoryReplayRepository()
    replay_recorder = ReplayRecorder(replay_repository)
    await event_bus.subscribe("*", replay_recorder.handle_event)

    run_id = str(uuid.uuid4())
    await replay_repository.create(
        ReplayRoot(
            id=str(uuid.uuid4()),
            task_id="task-1",
            run_id=run_id,
        )
    )

    service = SkillExecutionService(
        executor=SkillScriptExecutor(SandboxManager(LocalSandboxAdapter())),
        event_bus=event_bus,
        artifact_repository=artifact_repository,
        skill_root=tmp_path,
    )

    result = await service.run_skill_script(
        skill_name="demo_skill",
        script_path="scripts/run.sh",
        policy=SkillScriptExecutionPolicy(
            allow_sandbox_exec=True,
            artifact_paths=["outputs/result.txt"],
        ),
        context=SkillExecutionContext(
            tenant_id="tenant-1",
            session_id="session-1",
            task_id="task-1",
            run_id=run_id,
            subtask_id="subtask-1",
        ),
    )

    artifacts = await artifact_repository.list_for_run(run_id)
    replay = await replay_repository.get_by_run(run_id)
    events = [event.topic for event in event_bus.list_events()]

    assert result.exit_code == 0
    assert result.artifacts == {"outputs/result.txt": "hello artifact"}
    assert len(artifacts) == 1
    assert artifacts[0].name == "demo_skill:outputs/result.txt"
    assert artifacts[0].metadata["content"] == "hello artifact"
    assert replay is not None
    assert [entry.event_type for entry in replay.entries] == [
        "skill.script.started",
        "artifact.created",
        "skill.script.completed",
    ]
    assert replay.artifact_ids == [artifacts[0].id]
    assert events == ["skill.script.started", "artifact.created", "skill.script.completed"]


@pytest.mark.asyncio
async def test_skill_execution_service_marks_nonzero_exit_as_failed_event(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path, "failing_skill")
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "fail.sh").write_text("echo boom >&2\nexit 3\n", encoding="utf-8")

    event_bus = InMemoryEventBus()
    service = SkillExecutionService(
        executor=SkillScriptExecutor(SandboxManager(LocalSandboxAdapter())),
        event_bus=event_bus,
        skill_root=tmp_path,
    )

    result = await service.run_skill_script(
        skill_name="failing_skill",
        script_path="scripts/fail.sh",
        policy=SkillScriptExecutionPolicy(allow_sandbox_exec=True),
        context=SkillExecutionContext(run_id="run-1"),
    )

    assert result.exit_code == 3
    assert [event.topic for event in event_bus.list_events()] == [
        "skill.script.started",
        "skill.script.failed",
    ]


@pytest.mark.asyncio
async def test_skill_tool_wraps_service_calls(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path, "tool_skill")
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "run.py").write_text(
        "from pathlib import Path\nPath('outputs').mkdir(exist_ok=True)\nPath('outputs/out.txt').write_text('ok', encoding='utf-8')\n",
        encoding="utf-8",
    )

    service = SkillExecutionService(
        executor=SkillScriptExecutor(SandboxManager(LocalSandboxAdapter())),
        skill_root=tmp_path,
    )
    tool = SkillTool(service)

    assert await tool.list_skill_scripts("tool_skill") == ["scripts/run.py"]
    details = await tool.get_skill_details("tool_skill")
    result = await tool.run_skill_script(
        skill_name="tool_skill",
        script_path="scripts/run.py",
        allow_sandbox_exec=True,
        artifact_paths=["outputs/out.txt"],
    )

    assert details["name"] == "tool_skill"
    assert result["exit_code"] == 0
    assert result["artifacts"] == {"outputs/out.txt": "ok"}