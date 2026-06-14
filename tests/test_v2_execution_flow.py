from __future__ import annotations

import asyncio
import json
from typing import cast

import pytest

from swarmmind.agents import OmniAgentResult
from swarmmind.app.container import build_container
from swarmmind.config import SwarmMindConfig
from swarmmind.gateway import TaskSubmitRequest
from swarmmind.models.agent_profile import AgentProfile, SkillsMode
from swarmmind.models.artifact import Artifact
from swarmmind.models.artifact import ArtifactType
from swarmmind.models.capability import AgentRole, RuntimeKind, ToolGroup
from swarmmind.models.event import DomainEvent
from swarmmind.models.execution import ExecutionConfiguration, ExecutionProfile, ReviewDecisionType
from swarmmind.models.replay import ReplayRoot
from swarmmind.models.run import Run, RunStatus
from swarmmind.models.task import SubTask, SubTaskStatus, Task, TaskStatus
from swarmmind.sandbox import CommandRequest


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


def _install_real_command_plan_stub(monkeypatch: pytest.MonkeyPatch, container) -> None:
    original = container.execution_runner._run_omni_agent_prompt

    async def fake_run_omni_agent_prompt(**kwargs):
        if kwargs.get("step_kind") == "command.plan":
            subtask = kwargs["subtask"]
            command = (
                "python3 -c \"print('running subtask: "
                + subtask.name.replace("'", "")
                + "')\""
            )
            return OmniAgentResult(
                status="completed",
                content=json.dumps({"command": command, "cwd": "."}, ensure_ascii=False),
            )
        return await original(**kwargs)

    monkeypatch.setattr(container.execution_runner, "_run_omni_agent_prompt", fake_run_omni_agent_prompt)


@pytest.mark.asyncio
async def test_submit_task_executes_subtasks_and_collects_artifacts(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)
    _install_real_command_plan_stub(monkeypatch, container)
    identity = await container.identity_resolver.resolve()

    submission = await container.gateway.submit_task(
        TaskSubmitRequest(goal="实现一个导出 Excel 功能并补测试", profile="py-basic"),
        identity=identity,
    )

    run_detail = await _wait_for_terminal_run(container, submission.run_id, identity)
    task = await container.gateway.get_task(submission.task_id)
    replay = await container.replay_repository.get_by_run(submission.run_id)

    assert run_detail is not None
    assert task is not None
    assert replay is not None
    assert run_detail.run.status == RunStatus.SUCCEEDED
    assert task.status == TaskStatus.SUCCEEDED
    assert run_detail.artifacts
    assert all(subtask.status == SubTaskStatus.SUCCEEDED for subtask in run_detail.subtasks)

    review_subtask = next(subtask for subtask in run_detail.subtasks if subtask.name == "review-result")
    assert review_subtask.result is not None
    assert review_subtask.result.get("decision") == ReviewDecisionType.ACCEPT.value
    assert review_subtask.metadata.get("execution_label") == "review"
    assert "artifact_read" in review_subtask.metadata.get("selected_tools", [])

    implementation_subtask = next(subtask for subtask in run_detail.subtasks if subtask.name == "prepare-implementation")
    implementation_profile = ExecutionProfile.model_validate(implementation_subtask.metadata.get("execution_profile") or {})
    assert implementation_subtask.metadata.get("execution_label") == "build_app"
    assert implementation_subtask.metadata.get("resolved_runtime_kind") == RuntimeKind.SANDBOX.value
    assert implementation_subtask.metadata.get("runtime_resolution_reason")
    assert "sandbox_exec" in implementation_subtask.metadata.get("selected_tools", [])
    assert implementation_profile.agent_profile_id == "coder-default"
    assert implementation_profile.resolved_runtime_kind == RuntimeKind.SANDBOX
    assert implementation_profile.runtime_fallback_chain == [RuntimeKind.HOST_TOOLS]
    assert implementation_profile.skill_profiles == []
    assert ToolGroup.CODE_EXEC in implementation_profile.allowed_tool_groups

    event_types = [entry.event_type for entry in replay.entries]
    assert "subtask.started" in event_types
    assert "artifact.created" in event_types
    assert "run.updated" in event_types
    assert "execution.started" in event_types
    assert "tool.completed" in event_types


@pytest.mark.asyncio
async def test_failed_subtask_marks_run_and_task_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)
    _install_real_command_plan_stub(monkeypatch, container)
    identity = await container.identity_resolver.resolve()

    submission = await container.gateway.submit_task(
        TaskSubmitRequest(
            goal="实现一个导出 Excel 功能并补测试",
            profile="py-basic",
            constraints={"force_fail_subtask": "prepare-implementation"},
        ),
        identity=identity,
    )

    run_detail = await _wait_for_terminal_run(container, submission.run_id, identity)
    task = await container.gateway.get_task(submission.task_id)
    replay = await container.replay_repository.get_by_run(submission.run_id)

    assert run_detail is not None
    assert task is not None
    assert replay is not None
    assert run_detail.run.status == RunStatus.FAILED
    assert task.status == TaskStatus.FAILED
    assert any(subtask.status == SubTaskStatus.FAILED for subtask in run_detail.subtasks)
    assert any(entry.event_type == "subtask.failed" for entry in replay.entries)


@pytest.mark.asyncio
async def test_review_rework_generates_repair_chain_and_run_recovers(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)
    _install_real_command_plan_stub(monkeypatch, container)
    identity = await container.identity_resolver.resolve()

    submission = await container.gateway.submit_task(
        TaskSubmitRequest(
            goal="实现一个导出 Excel 功能并补测试",
            profile="py-basic",
            constraints={
                "force_review_decisions": {"review-result": "rework"},
                "max_repair_attempts": 1,
            },
        ),
        identity=identity,
    )

    run_detail = await _wait_for_terminal_run(container, submission.run_id, identity)
    replay = await container.replay_repository.get_by_run(submission.run_id)

    assert run_detail is not None
    assert replay is not None
    assert run_detail.run.status == RunStatus.SUCCEEDED
    assert any(subtask.name.startswith("repair-prepare-implementation") for subtask in run_detail.subtasks)
    assert any(subtask.name.startswith("verify-repair-prepare-implementation") for subtask in run_detail.subtasks)
    assert any(subtask.name.startswith("review-repair-prepare-implementation") for subtask in run_detail.subtasks)
    assert any(entry.event_type == "subtask.rework_requested" for entry in replay.entries)


@pytest.mark.asyncio
async def test_failed_subtask_can_trigger_failure_repair_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)
    _install_real_command_plan_stub(monkeypatch, container)
    identity = await container.identity_resolver.resolve()

    submission = await container.gateway.submit_task(
        TaskSubmitRequest(
            goal="实现一个导出 Excel 功能并补测试",
            profile="py-basic",
            constraints={
                "force_fail_subtask": "prepare-implementation",
                "enable_failure_repair": True,
                "max_repair_attempts": 1,
            },
        ),
        identity=identity,
    )

    run_detail = await _wait_for_terminal_run(container, submission.run_id, identity)
    replay = await container.replay_repository.get_by_run(submission.run_id)

    assert run_detail is not None
    assert replay is not None
    assert run_detail.run.status == RunStatus.SUCCEEDED
    assert any(subtask.name.startswith("repair-prepare-implementation-failure-attempt-1") for subtask in run_detail.subtasks)
    assert any(entry.event_type == "subtask.repair_requested" for entry in replay.entries)


@pytest.mark.asyncio
async def test_host_tools_runtime_uses_omni_agent_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)
    identity = await container.identity_resolver.resolve()
    captured: list[dict[str, object]] = []

    async def fake_run(request, *, publisher=None):
        payload = {
            "step_kind": request.step_kind,
            "tool_names": [getattr(tool, "__name__", repr(tool)) for tool in request.tool_functions],
            "skill_profiles": list(request.skill_profiles),
        }
        captured.append(payload)
        if publisher is not None:
            await publisher("agent.step.fallback", {**payload, "reason": "test_fallback"})
        return OmniAgentResult(status="fallback", reason="test_fallback", tool_names=payload["tool_names"])

    monkeypatch.setattr(container.execution_runner._omni_agent, "run", fake_run)

    task = Task(
        id="task-host-tools-1",
        goal="整理月度金价研究并输出摘要",
        metadata={
            "tenant_id": identity.tenant_id,
            "principal_id": identity.principal_id,
            "profile": "py-basic",
        },
    )
    run = Run(id="run-host-tools-1", task_id=task.id, session_id="session-host-tools-1")
    execution_configuration = ExecutionConfiguration(
        runtime_kind=RuntimeKind.HOST_TOOLS,
        tool_requirements=[ToolGroup.WORKSPACE, ToolGroup.ARTIFACT],
        skill_profiles=["pptx"],
    )
    execution_profile = ExecutionProfile(
        role=AgentRole.WRITER,
        execution_configuration=execution_configuration,
        required_tool_groups=[ToolGroup.WORKSPACE, ToolGroup.ARTIFACT],
        resolved_runtime_kind=RuntimeKind.HOST_TOOLS,
        runtime_resolution_reason="Test forces host_tools runtime for OmniAgent coverage.",
        runtime_fallback_chain=[RuntimeKind.SANDBOX],
        skill_profiles=["pptx"],
    )
    subtask = SubTask(
        id="subtask-host-tools-1",
        task_id=task.id,
        name="draft-investment-summary",
        description="Draft the final investment summary for the user.",
        role=AgentRole.WRITER,
        execution_configuration=execution_configuration,
        acceptance_criteria=["A concise Markdown summary is produced."],
        metadata={"run_id": run.id, "plan_source": "test"},
    )
    subtask.assign(execution_profile.model_dump(mode="json"), run.id)
    run.attach_subtasks([subtask.id])

    await container.task_repository.create(task)
    await container.run_repository.create(run)
    await container.subtask_repository.save(subtask)
    await container.replay_repository.create(ReplayRoot(id="replay-host-tools-1", task_id=task.id, run_id=run.id))

    await container.event_bus.publish(
        DomainEvent(
            event_id="event-host-tools-1",
            topic="subtask.assigned",
            tenant_id=identity.tenant_id,
            session_id=run.session_id,
            task_id=task.id,
            run_id=run.id,
            subtask_id=subtask.id,
            payload={"name": subtask.name, "role": subtask.role.value},
        )
    )

    assigned_subtask = await container.subtask_repository.get(subtask.id)
    stored_run = await container.run_repository.get(run.id)
    replay = await container.replay_repository.get_by_run(run.id)

    assert assigned_subtask is not None
    assert stored_run is not None
    assert replay is not None
    assert stored_run.status == RunStatus.SUCCEEDED
    assert assigned_subtask.status == SubTaskStatus.SUCCEEDED
    assert assigned_subtask.metadata.get("resolved_runtime_kind") == RuntimeKind.HOST_TOOLS.value
    assert assigned_subtask.result is not None
    assert assigned_subtask.result.get("execution_backend") == "omni_agent"
    assert any(item.get("step_kind") == "content.render" and item.get("tool_names") for item in captured)


@pytest.mark.asyncio
async def test_execution_prompt_includes_declared_skill_scripts() -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)

    task = Task(
        id="task-skill-prompt-1",
        goal="生成黄金投资建议PPT",
        metadata={"tenant_id": "local", "principal_id": "tester"},
    )
    execution_profile = ExecutionProfile(
        role=AgentRole.WRITER,
        required_tool_groups=[ToolGroup.CODE_EXEC, ToolGroup.ARTIFACT],
        resolved_runtime_kind=RuntimeKind.SANDBOX,
        skill_profiles=["pptx"],
    )
    subtask = SubTask(
        id="subtask-skill-prompt-1",
        task_id=task.id,
        name="draft-gold-investment-ppt",
        description="基于研究结果生成可直接打开的 PPT。",
        role=AgentRole.WRITER,
        acceptance_criteria=["输出为可直接打开的 .pptx 文件。"],
        expected_artifacts=["presentation"],
        metadata={"execution_profile": execution_profile.model_dump(mode="json")},
    )

    prompt = await container.execution_runner._compose_subtask_prompt(task, subtask)

    assert '当前选中的 skill profiles：["pptx"]' in prompt
    assert 'scripts/create_presentation.py' in prompt
    assert '技能入口信息：' in prompt
    assert 'read_skill_reference(skill_name)' in prompt
    assert '真实文件产物要求：' in prompt
    assert '必须设置 `allow_sandbox_exec=true`' in prompt


@pytest.mark.asyncio
async def test_materialized_skill_sandbox_subtask_uses_omni_agent_path(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)

    calls: dict[str, object] = {}

    async def fake_execute_omni_agent_subtask(*, task, run, subtask, event, runtime_kind):
        del task, run, subtask, event
        calls["runtime_kind"] = runtime_kind

    async def fake_execute_sandbox_subtask(task, run, subtask, event):
        del task, run, subtask, event
        calls["sandbox_called"] = True

    monkeypatch.setattr(container.execution_runner, "_execute_omni_agent_subtask", fake_execute_omni_agent_subtask)
    monkeypatch.setattr(container.execution_runner, "_execute_sandbox_subtask", fake_execute_sandbox_subtask)

    task = Task(
        id="task-materialized-route-1",
        goal="生成黄金投资建议 PPT",
        metadata={"tenant_id": "local", "principal_id": "tester"},
    )
    run = Run(id="run-materialized-route-1", task_id=task.id, session_id="session-materialized-route-1")
    execution_configuration = ExecutionConfiguration(
        runtime_kind=RuntimeKind.SANDBOX,
        tool_requirements=[ToolGroup.CODE_EXEC, ToolGroup.ARTIFACT],
        skill_profiles=["pptx"],
    )
    execution_profile = ExecutionProfile(
        role=AgentRole.WRITER,
        execution_configuration=execution_configuration,
        required_tool_groups=[ToolGroup.CODE_EXEC, ToolGroup.ARTIFACT],
        resolved_runtime_kind=RuntimeKind.SANDBOX,
        runtime_resolution_reason="Test skill route.",
        skill_profiles=["pptx"],
        allowed_tool_groups=[ToolGroup.CODE_EXEC, ToolGroup.ARTIFACT],
    )
    subtask = SubTask(
        id="subtask-materialized-route-1",
        task_id=task.id,
        name="draft-gold-investment-ppt",
        description="基于研究结果生成可直接打开的 PPT。",
        role=AgentRole.WRITER,
        acceptance_criteria=["输出为可直接打开的 .pptx 文件。"],
        expected_artifacts=["outputs/demo.pptx"],
        execution_configuration=execution_configuration,
        metadata={"run_id": run.id, "plan_source": "test"},
    )
    subtask.assign(execution_profile.model_dump(mode="json"), run.id)

    await container.execution_runner._execute_subtask(
        task,
        run,
        subtask,
        DomainEvent(
            event_id="event-materialized-route-1",
            topic="subtask.assigned",
            tenant_id="local",
            session_id=run.session_id,
            task_id=task.id,
            run_id=run.id,
            subtask_id=subtask.id,
            payload={},
        ),
    )

    assert calls.get("runtime_kind") == RuntimeKind.SANDBOX
    assert "sandbox_called" not in calls


@pytest.mark.asyncio
async def test_build_command_request_prefers_structured_command_response(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)

    async def fake_run_omni_agent_prompt(**kwargs):
        del kwargs
        return OmniAgentResult(status="completed", content='{"command":"python3 scripts/build.py","cwd":"workspace"}')

    monkeypatch.setattr(container.execution_runner, "_run_omni_agent_prompt", fake_run_omni_agent_prompt)

    task = Task(
        id="task-command-plan-1",
        goal="执行普通 sandbox 构建命令",
        metadata={"tenant_id": "local", "principal_id": "tester"},
    )
    execution_profile = ExecutionProfile(
        role=AgentRole.CODER,
        required_tool_groups=[ToolGroup.CODE_EXEC],
        resolved_runtime_kind=RuntimeKind.SANDBOX,
        allowed_tool_groups=[ToolGroup.CODE_EXEC],
    )
    subtask = SubTask(
        id="subtask-command-plan-1",
        task_id=task.id,
        name="run-build-command",
        description="运行构建命令。",
        role=AgentRole.CODER,
        acceptance_criteria=["命令执行完成。"],
        metadata={"execution_profile": execution_profile.model_dump(mode="json")},
    )

    request = await container.execution_runner._build_command_request(task, subtask)

    assert request.command == "python3 scripts/build.py"
    assert request.cwd == "workspace"


@pytest.mark.asyncio
async def test_build_command_request_requires_real_command(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)

    async def fake_run_omni_agent_prompt(**kwargs):
        del kwargs
        return OmniAgentResult(status="completed", content='{"cwd":"workspace"}')

    monkeypatch.setattr(container.execution_runner, "_run_omni_agent_prompt", fake_run_omni_agent_prompt)

    task = Task(
        id="task-command-plan-missing-1",
        goal="执行普通 sandbox 构建命令",
        metadata={"tenant_id": "local", "principal_id": "tester"},
    )
    execution_profile = ExecutionProfile(
        role=AgentRole.CODER,
        required_tool_groups=[ToolGroup.CODE_EXEC],
        resolved_runtime_kind=RuntimeKind.SANDBOX,
        allowed_tool_groups=[ToolGroup.CODE_EXEC],
    )
    subtask = SubTask(
        id="subtask-command-plan-missing-1",
        task_id=task.id,
        name="run-build-command-without-command",
        description="运行构建命令。",
        role=AgentRole.CODER,
        acceptance_criteria=["命令执行完成。"],
        metadata={"execution_profile": execution_profile.model_dump(mode="json")},
    )

    with pytest.raises(RuntimeError, match="requires a real sandbox command"):
        await container.execution_runner._build_command_request(task, subtask)


@pytest.mark.asyncio
async def test_omni_agent_sandbox_subtask_accepts_materialized_file_artifact(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)

    task = Task(
        id="task-omni-materialized-1",
        goal="生成黄金投资建议 PPT",
        metadata={"tenant_id": "local", "principal_id": "tester"},
    )
    run = Run(id="run-omni-materialized-1", task_id=task.id, session_id="session-omni-materialized-1")
    execution_configuration = ExecutionConfiguration(
        runtime_kind=RuntimeKind.SANDBOX,
        tool_requirements=[ToolGroup.CODE_EXEC, ToolGroup.ARTIFACT],
        skill_profiles=["pptx"],
    )
    execution_profile = ExecutionProfile(
        role=AgentRole.WRITER,
        execution_configuration=execution_configuration,
        required_tool_groups=[ToolGroup.CODE_EXEC, ToolGroup.ARTIFACT],
        resolved_runtime_kind=RuntimeKind.SANDBOX,
        runtime_resolution_reason="Test materialized omni-agent path.",
        skill_profiles=["pptx"],
        allowed_tool_groups=[ToolGroup.CODE_EXEC, ToolGroup.ARTIFACT],
    )
    subtask = SubTask(
        id="subtask-omni-materialized-1",
        task_id=task.id,
        name="draft-gold-investment-ppt",
        description="生成一个可直接打开的 .pptx 文件。",
        role=AgentRole.WRITER,
        acceptance_criteria=["输出真实的 .pptx 文件。"],
        expected_artifacts=["outputs/demo.pptx"],
        execution_configuration=execution_configuration,
        metadata={"run_id": run.id, "plan_source": "test"},
    )
    subtask.assign(execution_profile.model_dump(mode="json"), run.id)

    await container.task_repository.create(task)
    await container.run_repository.create(run)
    await container.subtask_repository.save(subtask)

    async def fake_render_materialized_subtask_content_with_retry(task_arg, run_arg, subtask_arg, max_attempts=2):
        del task_arg, max_attempts
        await container.artifact_repository.create(
            Artifact(
                id="artifact-omni-materialized-1",
                task_id=task.id,
                run_id=run_arg.id,
                subtask_id=subtask_arg.id,
                name="demo.pptx",
                type=ArtifactType.FILE,
                storage_ref="/v1/runs/run-omni-materialized-1/artifacts/artifact-omni-materialized-1/content",
                content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ),
            payload=b"PK\x03\x04omni-pptx",
        )
        return OmniAgentResult(
            status="completed",
            content="已生成 PPT 文件。",
            used_tool_names=["run_skill_script"],
            tool_call_count=1,
            skill_execution_count=1,
        )

    monkeypatch.setattr(
        container.execution_runner,
        "_render_materialized_subtask_content_with_retry",
        fake_render_materialized_subtask_content_with_retry,
    )

    await container.execution_runner._execute_omni_agent_subtask(
        task=task,
        run=run,
        subtask=subtask,
        event=DomainEvent(
            event_id="event-omni-materialized-1",
            topic="subtask.assigned",
            tenant_id="local",
            session_id=run.session_id,
            task_id=task.id,
            run_id=run.id,
            subtask_id=subtask.id,
            payload={},
        ),
        runtime_kind=RuntimeKind.SANDBOX,
    )

    stored_subtask = await container.subtask_repository.get(subtask.id)

    assert stored_subtask is not None
    assert stored_subtask.status == SubTaskStatus.SUCCEEDED
    assert stored_subtask.result is not None
    assert stored_subtask.result.get("materialized_artifact_count") == 1


@pytest.mark.asyncio
async def test_materialized_skill_subtask_retries_until_run_skill_script_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)

    task = Task(
        id="task-materialized-retry-1",
        goal="生成黄金投资建议 PPT",
        metadata={"tenant_id": "local", "principal_id": "tester"},
    )
    run = Run(id="run-materialized-retry-1", task_id=task.id, session_id="session-materialized-retry-1")
    execution_configuration = ExecutionConfiguration(
        runtime_kind=RuntimeKind.SANDBOX,
        tool_requirements=[ToolGroup.CODE_EXEC, ToolGroup.ARTIFACT],
        skill_profiles=["pptx"],
    )
    execution_profile = ExecutionProfile(
        role=AgentRole.WRITER,
        execution_configuration=execution_configuration,
        required_tool_groups=[ToolGroup.CODE_EXEC, ToolGroup.ARTIFACT],
        resolved_runtime_kind=RuntimeKind.SANDBOX,
        runtime_resolution_reason="Test materialized retry path.",
        skill_profiles=["pptx"],
        allowed_tool_groups=[ToolGroup.CODE_EXEC, ToolGroup.ARTIFACT],
    )
    subtask = SubTask(
        id="subtask-materialized-retry-1",
        task_id=task.id,
        name="draft-gold-investment-ppt",
        description="生成一个可直接打开的 .pptx 文件。",
        role=AgentRole.WRITER,
        acceptance_criteria=["输出真实的 .pptx 文件。"],
        expected_artifacts=["outputs/demo.pptx"],
        execution_configuration=execution_configuration,
        metadata={"run_id": run.id, "plan_source": "test"},
    )
    subtask.assign(execution_profile.model_dump(mode="json"), run.id)

    attempts: list[str] = []

    async def fake_run_omni_agent_prompt(**kwargs):
        attempts.append(str(kwargs.get("step_kind")))
        if len(attempts) == 1:
            return OmniAgentResult(status="completed", content="第一次只是口头总结", used_tool_names=[])
        return OmniAgentResult(
            status="completed",
            content="第二次执行了 skill",
            used_tool_names=["run_skill_script"],
            tool_call_count=1,
            skill_execution_count=1,
        )

    monkeypatch.setattr(container.execution_runner, "_run_omni_agent_prompt", fake_run_omni_agent_prompt)

    result = await container.execution_runner._render_materialized_subtask_content_with_retry(task, run, subtask)

    assert result.content == "第二次执行了 skill"
    assert result.used_tool_names == ["run_skill_script"]
    assert attempts == ["content.render.materialized.1", "content.render.materialized.2"]


@pytest.mark.asyncio
async def test_run_skill_script_defaults_to_sandbox_exec_for_materialized_output(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)

    captured: dict[str, object] = {}

    async def fake_run_tool(tool_name, **kwargs):
        captured["tool_name"] = tool_name
        captured["kwargs"] = kwargs
        return {"ok": True}

    monkeypatch.setattr(container.execution_runner, "_run_tool", fake_run_tool)

    task = Task(
        id="task-skill-default-1",
        goal="生成黄金投资建议PPT",
        metadata={"tenant_id": "local", "principal_id": "tester"},
    )
    run = Run(id="run-skill-default-1", task_id=task.id, session_id="session-skill-default-1")
    execution_profile = ExecutionProfile(
        role=AgentRole.WRITER,
        required_tool_groups=[ToolGroup.CODE_EXEC, ToolGroup.ARTIFACT],
        resolved_runtime_kind=RuntimeKind.SANDBOX,
        skill_profiles=["pptx"],
    )
    subtask = SubTask(
        id="subtask-skill-default-1",
        task_id=task.id,
        name="draft-gold-investment-ppt",
        description="基于研究结果生成可直接打开的 PPT。",
        role=AgentRole.WRITER,
        acceptance_criteria=["输出为可直接打开的 .pptx 文件。"],
        expected_artifacts=["presentation"],
        metadata={
            "selected_tools": ["run_skill_script"],
            "execution_profile": execution_profile.model_dump(mode="json"),
        },
    )

    tool_functions = container.execution_runner._build_agent_tool_functions(task, run, subtask)
    run_skill_script = next(tool for tool in tool_functions if tool.__name__ == "run_skill_script")

    await run_skill_script(
        skill="pptx",
        script="scripts/add_slide.py",
        script_args=["workspace/unpacked", "slideLayout2.xml"],
    )

    assert captured["tool_name"] == "run_skill_script"
    assert captured["kwargs"]["skill_name"] == "pptx"
    assert captured["kwargs"]["script_path"] == "scripts/add_slide.py"
    assert captured["kwargs"]["script_args"] == ["workspace/unpacked", "slideLayout2.xml"]
    assert captured["kwargs"]["allow_sandbox_exec"] is True


@pytest.mark.asyncio
async def test_run_skill_script_accepts_structured_script_input(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)

    captured: dict[str, object] = {}

    async def fake_run_tool(tool_name, **kwargs):
        captured["tool_name"] = tool_name
        captured["kwargs"] = kwargs
        return {"ok": True}

    monkeypatch.setattr(container.execution_runner, "_run_tool", fake_run_tool)

    task = Task(
        id="task-skill-structured-1",
        goal="生成黄金投资建议PPT",
        metadata={"tenant_id": "local", "principal_id": "tester"},
    )
    run = Run(id="run-skill-structured-1", task_id=task.id, session_id="session-skill-structured-1")
    execution_profile = ExecutionProfile(
        role=AgentRole.WRITER,
        required_tool_groups=[ToolGroup.CODE_EXEC, ToolGroup.ARTIFACT],
        resolved_runtime_kind=RuntimeKind.SANDBOX,
        skill_profiles=["pptx"],
    )
    subtask = SubTask(
        id="subtask-skill-structured-1",
        task_id=task.id,
        name="draft-gold-investment-ppt",
        description="基于研究结果生成可直接打开的 PPT。",
        role=AgentRole.WRITER,
        acceptance_criteria=["输出为可直接打开的 .pptx 文件。"],
        expected_artifacts=["presentation"],
        metadata={
            "selected_tools": ["run_skill_script"],
            "execution_profile": execution_profile.model_dump(mode="json"),
        },
    )

    tool_functions = container.execution_runner._build_agent_tool_functions(task, run, subtask)
    run_skill_script = next(tool for tool in tool_functions if tool.__name__ == "run_skill_script")

    await run_skill_script(
        skill="pptx",
        script="scripts/add_slide.py",
        script_input={"unpacked_dir": "/workspace/gold_unpacked", "source": "slideLayout2.xml"},
    )

    assert captured["tool_name"] == "run_skill_script"
    assert captured["kwargs"]["script_input"] == {
        "unpacked_dir": "/workspace/gold_unpacked",
        "source": "slideLayout2.xml",
    }


@pytest.mark.asyncio
async def test_host_tools_runtime_propagates_execution_profile_to_omni_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)
    identity = await container.identity_resolver.resolve()
    captured: list[dict[str, object]] = []

    async def fake_run(request, *, publisher=None):
        captured.append(
            {
                "step_kind": request.step_kind,
                "resolved_runtime_kind": (
                    request.execution_profile.resolved_runtime_kind.value
                    if request.execution_profile is not None and request.execution_profile.resolved_runtime_kind is not None
                    else None
                ),
                "allowed_skill_scripts": (
                    list(request.execution_profile.allowed_skill_scripts)
                    if request.execution_profile is not None
                    else []
                ),
            }
        )
        return OmniAgentResult(status="fallback", reason="test_fallback")

    monkeypatch.setattr(container.execution_runner._omni_agent, "run", fake_run)

    task = Task(
        id="task-host-tools-profile-1",
        goal="整理月度金价研究并输出摘要",
        metadata={
            "tenant_id": identity.tenant_id,
            "principal_id": identity.principal_id,
            "profile": "py-basic",
        },
    )
    run = Run(id="run-host-tools-profile-1", task_id=task.id, session_id="session-host-tools-profile-1")
    execution_configuration = ExecutionConfiguration(
        runtime_kind=RuntimeKind.HOST_TOOLS,
        tool_requirements=[ToolGroup.WORKSPACE, ToolGroup.ARTIFACT],
        skill_profiles=["pptx"],
    )
    execution_profile = ExecutionProfile(
        role=AgentRole.WRITER,
        execution_configuration=execution_configuration,
        required_tool_groups=[ToolGroup.WORKSPACE, ToolGroup.ARTIFACT],
        resolved_runtime_kind=RuntimeKind.HOST_TOOLS,
        runtime_resolution_reason="Test request propagation.",
        runtime_fallback_chain=[RuntimeKind.SANDBOX],
        skill_profiles=["pptx"],
        allowed_skill_scripts=["pptx:scripts/render.py"],
    )
    subtask = SubTask(
        id="subtask-host-tools-profile-1",
        task_id=task.id,
        name="generate-summary-propagation",
        description="Generate the final investment summary.",
        role=AgentRole.WRITER,
        execution_configuration=execution_configuration,
        acceptance_criteria=["A concise Markdown summary is produced."],
        metadata={"run_id": run.id, "plan_source": "test"},
    )
    subtask.assign(execution_profile.model_dump(mode="json"), run.id)
    run.attach_subtasks([subtask.id])

    await container.task_repository.create(task)
    await container.run_repository.create(run)
    await container.subtask_repository.save(subtask)
    await container.replay_repository.create(ReplayRoot(id="replay-host-tools-profile-1", task_id=task.id, run_id=run.id))

    await container.event_bus.publish(
        DomainEvent(
            event_id="event-host-tools-profile-1",
            topic="subtask.assigned",
            tenant_id=identity.tenant_id,
            session_id=run.session_id,
            task_id=task.id,
            run_id=run.id,
            subtask_id=subtask.id,
            payload={"name": subtask.name, "role": subtask.role.value},
        )
    )

    assert any(item.get("step_kind") == "content.render" for item in captured)
    assert any(item.get("resolved_runtime_kind") == RuntimeKind.HOST_TOOLS.value for item in captured)
    assert any(item.get("allowed_skill_scripts") == ["pptx:scripts/render.py"] for item in captured)


@pytest.mark.asyncio
async def test_execution_policy_denies_tools_outside_profile_allowlist() -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)
    container.agent_profile_store.save(
        AgentProfile(
            id="restricted-coder",
            name="Restricted Coder",
            role=AgentRole.CODER,
            description="Profile that intentionally blocks sandbox execution.",
            skill_mode=SkillsMode.INCLUSIVE,
            skill_profiles=[],
            default_tool_groups=[ToolGroup.WORKSPACE],
            recommended_runtime_kinds=[RuntimeKind.HOST_TOOLS],
            allowed_tool_groups=[ToolGroup.WORKSPACE],
        )
    )
    identity = await container.identity_resolver.resolve()

    submission = await container.gateway.submit_task(
        TaskSubmitRequest(
            goal="实现一个导出 Excel 功能",
            profile="py-basic",
            agent_profile_id="restricted-coder",
        ),
        identity=identity,
    )

    run_detail = await _wait_for_terminal_run(container, submission.run_id, identity)
    replay = await container.replay_repository.get_by_run(submission.run_id)

    assert run_detail is not None
    assert replay is not None
    assert run_detail.run.status == RunStatus.FAILED
    assert any(entry.event_type == "policy.denied" for entry in replay.entries)
    implementation_subtask = next(subtask for subtask in run_detail.subtasks if subtask.name == "prepare-implementation")
    assert implementation_subtask.status == SubTaskStatus.FAILED
    assert "sandbox_exec" not in implementation_subtask.metadata.get("selected_tools", [])


@pytest.mark.asyncio
async def test_sandbox_runtime_persists_binary_file_artifacts(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)
    identity = await container.identity_resolver.resolve()

    async def fake_build_command_request(task, subtask):
        del task, subtask
        command = (
            "python3 -c \"from pathlib import Path; "
            "Path('outputs').mkdir(parents=True, exist_ok=True); "
            "Path('outputs/demo.pptx').write_bytes(b'PK\\x03\\x04sandbox-pptx'); "
            "print('WROTE_ARTIFACT_FILE=outputs/demo.pptx')\""
        )
        return CommandRequest(command=command, cwd=".")

    monkeypatch.setattr(container.execution_runner, "_build_command_request", fake_build_command_request)

    task = Task(
        id="task-sandbox-file-1",
        goal="生成一个可下载的黄金投资建议 PPT",
        metadata={
            "tenant_id": identity.tenant_id,
            "principal_id": identity.principal_id,
            "profile": "aio",
        },
    )
    run = Run(id="run-sandbox-file-1", task_id=task.id, session_id="session-sandbox-file-1")
    execution_configuration = ExecutionConfiguration(
        runtime_kind=RuntimeKind.SANDBOX,
        tool_requirements=[ToolGroup.FILE_SYSTEM, ToolGroup.CODE_EXEC, ToolGroup.ARTIFACT],
    )
    execution_profile = ExecutionProfile(
        role=AgentRole.WRITER,
        execution_configuration=execution_configuration,
        required_tool_groups=[ToolGroup.FILE_SYSTEM, ToolGroup.CODE_EXEC, ToolGroup.ARTIFACT],
        resolved_runtime_kind=RuntimeKind.SANDBOX,
        runtime_resolution_reason="Test forces sandbox runtime for file export coverage.",
        runtime_fallback_chain=[RuntimeKind.HOST_TOOLS],
        sandbox_profile="aio",
    )
    subtask = SubTask(
        id="subtask-sandbox-file-1",
        task_id=task.id,
        name="draft-gold-investment-ppt",
        description="生成一个可直接打开的 .pptx 文件。",
        role=AgentRole.WRITER,
        acceptance_criteria=["输出真实的 .pptx 文件。"],
        expected_artifacts=["outputs/demo.pptx"],
        execution_configuration=execution_configuration,
        metadata={"run_id": run.id, "plan_source": "test"},
    )
    subtask.assign(execution_profile.model_dump(mode="json"), run.id)
    run.attach_subtasks([subtask.id])

    await container.task_repository.create(task)
    await container.run_repository.create(run)
    await container.subtask_repository.save(subtask)
    await container.replay_repository.create(ReplayRoot(id="replay-sandbox-file-1", task_id=task.id, run_id=run.id))

    await container.event_bus.publish(
        DomainEvent(
            event_id="event-sandbox-file-1",
            topic="subtask.assigned",
            tenant_id=identity.tenant_id,
            session_id=run.session_id,
            task_id=task.id,
            run_id=run.id,
            subtask_id=subtask.id,
            payload={"name": subtask.name, "role": subtask.role.value},
        )
    )

    stored_run = await container.run_repository.get(run.id)
    stored_subtask = await container.subtask_repository.get(subtask.id)
    artifacts = await container.artifact_repository.list_for_run(run.id)
    file_artifact = next(artifact for artifact in artifacts if artifact.type == ArtifactType.FILE)
    payload = await container.artifact_repository.read_content(file_artifact)

    assert stored_run is not None
    assert stored_subtask is not None
    assert stored_run.status == RunStatus.SUCCEEDED
    assert stored_subtask.status == SubTaskStatus.SUCCEEDED
    assert stored_subtask.result is not None
    assert stored_subtask.result.get("materialized_artifact_count") == 1
    assert file_artifact.name == "demo.pptx"
    assert file_artifact.content_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    assert file_artifact.storage_ref == f"/v1/runs/{run.id}/artifacts/{file_artifact.id}/content"
    assert payload == b"PK\x03\x04sandbox-pptx"


@pytest.mark.asyncio
async def test_sandbox_runtime_requires_materialized_file_artifact(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)
    identity = await container.identity_resolver.resolve()

    async def fake_build_command_request(task, subtask):
        del task, subtask
        return CommandRequest(
            command="python3 -c \"print('no exported file produced')\"",
            cwd=".",
        )

    monkeypatch.setattr(container.execution_runner, "_build_command_request", fake_build_command_request)

    task = Task(
        id="task-sandbox-file-missing-1",
        goal="生成一个可下载的黄金投资建议 PPT",
        metadata={
            "tenant_id": identity.tenant_id,
            "principal_id": identity.principal_id,
            "profile": "aio",
        },
    )
    run = Run(id="run-sandbox-file-missing-1", task_id=task.id, session_id="session-sandbox-file-missing-1")
    execution_configuration = ExecutionConfiguration(
        runtime_kind=RuntimeKind.SANDBOX,
        tool_requirements=[ToolGroup.FILE_SYSTEM, ToolGroup.CODE_EXEC, ToolGroup.ARTIFACT],
    )
    execution_profile = ExecutionProfile(
        role=AgentRole.WRITER,
        execution_configuration=execution_configuration,
        required_tool_groups=[ToolGroup.FILE_SYSTEM, ToolGroup.CODE_EXEC, ToolGroup.ARTIFACT],
        resolved_runtime_kind=RuntimeKind.SANDBOX,
        runtime_resolution_reason="Test forces sandbox runtime for missing file coverage.",
        runtime_fallback_chain=[RuntimeKind.HOST_TOOLS],
        sandbox_profile="aio",
    )
    subtask = SubTask(
        id="subtask-sandbox-file-missing-1",
        task_id=task.id,
        name="draft-gold-investment-ppt-missing-file",
        description="生成一个可直接打开的 .pptx 文件。",
        role=AgentRole.WRITER,
        acceptance_criteria=["输出真实的 .pptx 文件。"],
        expected_artifacts=["outputs/demo.pptx"],
        execution_configuration=execution_configuration,
        metadata={"run_id": run.id, "plan_source": "test"},
    )
    subtask.assign(execution_profile.model_dump(mode="json"), run.id)
    run.attach_subtasks([subtask.id])

    await container.task_repository.create(task)
    await container.run_repository.create(run)
    await container.subtask_repository.save(subtask)
    await container.replay_repository.create(ReplayRoot(id="replay-sandbox-file-missing-1", task_id=task.id, run_id=run.id))

    await container.event_bus.publish(
        DomainEvent(
            event_id="event-sandbox-file-missing-1",
            topic="subtask.assigned",
            tenant_id=identity.tenant_id,
            session_id=run.session_id,
            task_id=task.id,
            run_id=run.id,
            subtask_id=subtask.id,
            payload={"name": subtask.name, "role": subtask.role.value},
        )
    )

    run_detail = await _wait_for_terminal_run(container, run.id, identity)
    stored_subtask = await container.subtask_repository.get(subtask.id)

    assert run_detail.run.status == RunStatus.FAILED
    assert stored_subtask is not None
    assert stored_subtask.status == SubTaskStatus.FAILED
    assert stored_subtask.result is not None
    assert stored_subtask.result.get("materialized_artifact_count") == 0
    assert "materialized file artifact" in (stored_subtask.error or "")


@pytest.mark.asyncio
async def test_run_state_service_fails_run_when_verification_result_is_false() -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)

    task = Task(
        id="task-verification-failed-1",
        goal="验证失败时不能把 run 汇总成成功",
        metadata={"tenant_id": "local", "principal_id": "tester"},
    )
    run = Run(id="run-verification-failed-1", task_id=task.id, session_id="session-verification-failed-1")
    subtask = SubTask(
        id="subtask-verification-failed-1",
        task_id=task.id,
        name="verify-gold-ppt",
        description="检查 PPT 是否真的生成。",
        role=AgentRole.TESTER,
        acceptance_criteria=["必须存在真实产物文件。"],
        result={
            "passed": False,
            "verification_passed": False,
            "summary": "未生成真实 PPT 文件。",
        },
        status=SubTaskStatus.SUCCEEDED,
        metadata={"run_id": run.id},
    )
    run.attach_subtasks([subtask.id])

    await container.task_repository.create(task)
    await container.run_repository.create(run)
    await container.subtask_repository.save(subtask)

    await container.run_state_service.reconcile(run.id)

    stored_run = await container.run_repository.get(run.id)
    stored_task = await container.task_repository.get(task.id)

    assert stored_run is not None
    assert stored_task is not None
    assert stored_run.status == RunStatus.FAILED
    assert stored_task.status == TaskStatus.FAILED
    assert stored_task.error == "Subtask failed: verify-gold-ppt"
