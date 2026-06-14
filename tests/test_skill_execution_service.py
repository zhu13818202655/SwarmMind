from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from swarmmind.defaults import DEFAULT_SKILL_PIP_INDEX_URL
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
    payload = await artifact_repository.read_content(artifacts[0])

    assert result.exit_code == 0
    assert result.artifacts == {"outputs/result.txt": "hello artifact"}
    assert len(artifacts) == 1
    assert artifacts[0].name == "demo_skill:outputs/result.txt"
    assert artifacts[0].metadata["content"] == "hello artifact"
    assert artifacts[0].storage_ref == f"/v1/runs/{run_id}/artifacts/{artifacts[0].id}/content"
    assert payload == b"hello artifact"
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


@pytest.mark.asyncio
async def test_skill_tool_accepts_legacy_skill_script_aliases(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path, "alias_skill")
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

    result = await tool.run_skill_script(
        skill="alias_skill",
        script="scripts/run.py",
        allow_sandbox_exec=True,
        args={"artifact_paths": ["outputs/out.txt"]},
    )

    assert result["exit_code"] == 0
    assert result["artifacts"] == {"outputs/out.txt": "ok"}


@pytest.mark.asyncio
async def test_skill_tool_accepts_nested_aliases_inside_args(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path, "nested_alias_skill")
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

    result = await tool.run_skill_script(
        allow_sandbox_exec=True,
        args={
            "input": {
                "skill": "nested_alias_skill",
                "script": "scripts/run.py",
                "artifact_paths": ["outputs/out.txt"],
            }
        },
    )

    assert result["exit_code"] == 0
    assert result["artifacts"] == {"outputs/out.txt": "ok"}


@pytest.mark.asyncio
async def test_skill_tool_forwards_script_args(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path, "argv_tool_skill")
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "run.py").write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "Path('outputs').mkdir(exist_ok=True)\n"
        "Path('outputs/out.txt').write_text('|'.join(sys.argv[1:]), encoding='utf-8')\n",
        encoding="utf-8",
    )

    service = SkillExecutionService(
        executor=SkillScriptExecutor(SandboxManager(LocalSandboxAdapter())),
        skill_root=tmp_path,
    )
    tool = SkillTool(service)

    result = await tool.run_skill_script(
        skill_name="argv_tool_skill",
        script_path="scripts/run.py",
        allow_sandbox_exec=True,
        artifact_paths=["outputs/out.txt"],
        script_args=["first", "second value"],
    )

    assert result["exit_code"] == 0
    assert result["artifacts"] == {"outputs/out.txt": "first|second value"}


@pytest.mark.asyncio
async def test_skill_tool_accepts_script_args_via_legacy_args_dict(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path, "argv_alias_skill")
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "run.py").write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "Path('outputs').mkdir(exist_ok=True)\n"
        "Path('outputs/out.txt').write_text('|'.join(sys.argv[1:]), encoding='utf-8')\n",
        encoding="utf-8",
    )

    service = SkillExecutionService(
        executor=SkillScriptExecutor(SandboxManager(LocalSandboxAdapter())),
        skill_root=tmp_path,
    )
    tool = SkillTool(service)

    result = await tool.run_skill_script(
        skill="argv_alias_skill",
        script="scripts/run.py",
        allow_sandbox_exec=True,
        args={
            "artifact_paths": ["outputs/out.txt"],
            "script_args": ["first", "second value"],
        },
    )

    assert result["exit_code"] == 0
    assert result["artifacts"] == {"outputs/out.txt": "first|second value"}


@pytest.mark.asyncio
async def test_skill_execution_service_persists_binary_artifacts(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path, "binary_skill")
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "run.py").write_text(
        "from pathlib import Path\n"
        "Path('outputs').mkdir(exist_ok=True)\n"
        "Path('outputs/demo.pptx').write_bytes(b'PK\\x03\\x04demo-pptx')\n",
        encoding="utf-8",
    )

    artifact_repository = InMemoryArtifactRepository()
    service = SkillExecutionService(
        executor=SkillScriptExecutor(SandboxManager(LocalSandboxAdapter())),
        artifact_repository=artifact_repository,
        skill_root=tmp_path,
    )

    run_id = str(uuid.uuid4())
    result = await service.run_skill_script(
        skill_name="binary_skill",
        script_path="scripts/run.py",
        policy=SkillScriptExecutionPolicy(
            allow_sandbox_exec=True,
            artifact_paths=["outputs/demo.pptx"],
        ),
        context=SkillExecutionContext(
            task_id="task-1",
            run_id=run_id,
            subtask_id="subtask-1",
        ),
    )

    artifacts = await artifact_repository.list_for_run(run_id)
    payload = await artifact_repository.read_content(artifacts[0])

    assert result.exit_code == 0
    assert result.artifacts == {"outputs/demo.pptx": "[binary file: outputs/demo.pptx]"}
    assert len(artifacts) == 1
    assert artifacts[0].content_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    assert artifacts[0].metadata["file_name"] == "demo.pptx"
    assert payload == b"PK\x03\x04demo-pptx"


@pytest.mark.asyncio
async def test_skill_execution_service_installs_required_python_packages(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path, "package_skill")
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: package_skill\n"
        "description: demo skill\n"
        "runtime_requirements:\n"
        "  python_packages:\n"
        "    - defusedxml\n"
        "---\n\n"
        "# Demo Skill\n",
        encoding="utf-8",
    )
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "run.py").write_text("print('ok')\n", encoding="utf-8")

    executor = SkillScriptExecutor(SandboxManager(LocalSandboxAdapter()))
    service = SkillExecutionService(executor=executor, skill_root=tmp_path)

    entry = service.get_skill_entry("package_skill")
    setup_command, script_command = executor._build_commands(
        entry.metadata.runtime_requirements,
        None,
        "scripts/run.py",
        {},
        [],
        [],
    )

    assert entry.metadata.runtime_requirements.python_packages == ["defusedxml"]
    assert setup_command == (
        "python3 -m pip install --disable-pip-version-check "
        f"-i {DEFAULT_SKILL_PIP_INDEX_URL} defusedxml"
    )
    assert script_command == "python3 scripts/run.py"


def test_skill_executor_uses_env_override_for_python_package_index(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path, "package_skill")
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: package_skill\n"
        "description: demo skill\n"
        "runtime_requirements:\n"
        "  python_packages:\n"
        "    - defusedxml\n"
        "---\n\n"
        "# Demo Skill\n",
        encoding="utf-8",
    )
    executor = SkillScriptExecutor(SandboxManager(LocalSandboxAdapter()))
    service = SkillExecutionService(executor=executor, skill_root=tmp_path)
    monkeypatch.setenv("SWARMMIND_SKILL_PIP_INDEX_URL", "https://mirror.example/simple")

    setup_command, script_command = executor._build_commands(
        service.get_skill_entry("package_skill").metadata.runtime_requirements,
        None,
        "scripts/run.py",
        {},
        [],
        [],
    )

    assert setup_command == (
        "python3 -m pip install --disable-pip-version-check "
        "-i https://mirror.example/simple defusedxml"
    )
    assert script_command == "python3 scripts/run.py"


@pytest.mark.asyncio
async def test_skill_execution_service_uses_script_input_from_script_specs(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path, "structured_skill")
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "run.py").write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "Path('outputs').mkdir(exist_ok=True)\n"
        "Path('outputs/out.txt').write_text('|'.join(sys.argv[1:]), encoding='utf-8')\n",
        encoding="utf-8",
    )
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: structured_skill\n"
        "description: structured input demo\n"
        "script_specs:\n"
        "  - path: scripts/run.py\n"
        "    runtime: python\n"
        "    argument_names:\n"
        "      - first\n"
        "      - second\n"
        "    artifacts:\n"
        "      - outputs/out.txt\n"
        "---\n\n"
        "# Structured\n",
        encoding="utf-8",
    )

    service = SkillExecutionService(
        executor=SkillScriptExecutor(SandboxManager(LocalSandboxAdapter())),
        skill_root=tmp_path,
    )

    result = await service.run_skill_script(
        skill_name="structured_skill",
        script_path="scripts/run.py",
        policy=SkillScriptExecutionPolicy(
            allow_sandbox_exec=True,
            script_input={"first": "hello", "second": "world"},
        ),
    )

    assert result.exit_code == 0
    assert result.applied_defaults["script_args"] == ["hello", "world"]
    assert result.resolved_artifact_paths == ["outputs/out.txt"]
    assert result.artifacts == {"outputs/out.txt": "hello|world"}


@pytest.mark.asyncio
async def test_skill_execution_service_expands_artifact_templates_from_script_input(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path, "templated_artifact_skill")
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "run.py").write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "output_path = Path(sys.argv[1])\n"
        "output_path.parent.mkdir(parents=True, exist_ok=True)\n"
        "output_path.write_text('artifact ready', encoding='utf-8')\n",
        encoding="utf-8",
    )
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: templated_artifact_skill\n"
        "description: templated artifact demo\n"
        "script_specs:\n"
        "  - path: scripts/run.py\n"
        "    runtime: python\n"
        "    argument_names:\n"
        "      - output_file\n"
        "    artifacts:\n"
        "      - '{output_file}'\n"
        "---\n\n"
        "# Templated\n",
        encoding="utf-8",
    )

    service = SkillExecutionService(
        executor=SkillScriptExecutor(SandboxManager(LocalSandboxAdapter())),
        skill_root=tmp_path,
    )

    result = await service.run_skill_script(
        skill_name="templated_artifact_skill",
        script_path="scripts/run.py",
        policy=SkillScriptExecutionPolicy(
            allow_sandbox_exec=True,
            script_input={"output_file": "outputs/result.txt"},
        ),
    )

    assert result.exit_code == 0
    assert result.resolved_artifact_paths == ["outputs/result.txt"]
    assert result.artifacts == {"outputs/result.txt": "artifact ready"}


@pytest.mark.asyncio
async def test_skill_execution_service_reports_missing_script_input_keys(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path, "missing_input_skill")
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "run.py").write_text("print('ok')\n", encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: missing_input_skill\n"
        "description: structured input demo\n"
        "script_specs:\n"
        "  - path: scripts/run.py\n"
        "    argument_names:\n"
        "      - first\n"
        "      - second\n"
        "---\n\n"
        "# Structured\n",
        encoding="utf-8",
    )

    service = SkillExecutionService(
        executor=SkillScriptExecutor(SandboxManager(LocalSandboxAdapter())),
        skill_root=tmp_path,
    )

    with pytest.raises(ValueError, match="input_mismatch"):
        await service.run_skill_script(
            skill_name="missing_input_skill",
            script_path="scripts/run.py",
            policy=SkillScriptExecutionPolicy(
                allow_sandbox_exec=True,
                script_input={"first": "hello"},
            ),
        )