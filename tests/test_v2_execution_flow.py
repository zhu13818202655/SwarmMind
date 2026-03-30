from __future__ import annotations

import asyncio
from typing import cast

import pytest

from swarmmind.agents import OmniAgentResult
from swarmmind.models.agent_profile import AgentProfile, HandoffPolicy, SkillsMode
from swarmmind.models.capability import AgentRole, RuntimeKind, ToolGroup
from swarmmind.app.container import build_container
from swarmmind.config import SwarmMindConfig
from swarmmind.gateway import TaskSubmitRequest
from swarmmind.models.event import DomainEvent
from swarmmind.models.execution import ExecutionProfile
from swarmmind.models.replay import ReplayRoot
from swarmmind.models.run import Run, RunStatus
from swarmmind.models.execution import ReviewDecisionType
from swarmmind.models.task import SubTask, SubTaskStatus, Task, TaskStatus


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
async def test_submit_task_executes_subtasks_and_collects_artifacts() -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)
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
    assert review_subtask.metadata.get("resolved_strategy_name") == "review"
    assert "artifact_read" in review_subtask.metadata.get("selected_tools", [])
    implementation_subtask = next(subtask for subtask in run_detail.subtasks if subtask.name == "prepare-implementation")
    implementation_profile = ExecutionProfile.model_validate(implementation_subtask.metadata.get("execution_profile") or {})
    assert implementation_subtask.metadata.get("resolved_strategy_name") == "build_app"
    assert implementation_subtask.metadata.get("resolved_runtime_kind") == RuntimeKind.SANDBOX.value
    assert implementation_subtask.metadata.get("runtime_resolution_reason")
    assert "sandbox_exec" in implementation_subtask.metadata.get("selected_tools", [])
    assert implementation_profile.agent_profile_id == "coder-default"
    assert implementation_profile.resolved_runtime_kind == RuntimeKind.SANDBOX
    assert implementation_profile.runtime_fallback_chain == [RuntimeKind.SANDBOX, RuntimeKind.HOST_TOOLS]
    assert implementation_profile.preferred_skill_profiles == ["build_app"]
    assert implementation_profile.skill_profiles == ["build_app"]
    assert ToolGroup.SANDBOX_EXEC in implementation_profile.allowed_tool_groups


    event_types = [entry.event_type for entry in replay.entries]
    assert "subtask.started" in event_types
    assert "artifact.created" in event_types
    assert "run.updated" in event_types
    assert "strategy.started" in event_types
    assert "tool.completed" in event_types


@pytest.mark.asyncio
async def test_failed_subtask_marks_run_and_task_failed() -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)
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
async def test_review_rework_generates_repair_chain_and_run_recovers() -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)
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
async def test_failed_subtask_can_trigger_failure_repair_chain() -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)
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
async def test_agent_backed_strategy_completes_with_reserved_profile() -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)
    identity = await container.identity_resolver.resolve()

    submission = await container.gateway.submit_task(
        TaskSubmitRequest(
            goal="整理一份版本发布说明",
            preferred_strategy="agent_backed",
            profile="py-basic",
        ),
        identity=identity,
    )

    run_detail = await _wait_for_terminal_run(container, submission.run_id, identity)
    replay = await container.replay_repository.get_by_run(submission.run_id)

    assert run_detail is not None
    assert replay is not None
    assert run_detail.run.status == RunStatus.SUCCEEDED

    implementation_subtask = next(subtask for subtask in run_detail.subtasks if subtask.name == "prepare-implementation")
    execution_profile = ExecutionProfile.model_validate(implementation_subtask.metadata.get("execution_profile") or {})
    assert implementation_subtask.metadata.get("resolved_strategy_name") == "agent_backed"
    assert execution_profile.agent_profile_id == "agent-backed-default"
    assert implementation_subtask.result is not None
    assert implementation_subtask.result.get("strategy_backend") == "agent_backed"
    assert implementation_subtask.result.get("execution_backend") == "omni_agent"
    assert any(entry.event_type == "strategy.completed" for entry in replay.entries)


@pytest.mark.asyncio
async def test_agent_backed_strategy_emits_unified_agent_step_events(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)
    identity = await container.identity_resolver.resolve()
    captured: list[dict[str, object]] = []

    async def fake_run(request, *, publisher=None):
        payload = {
            "step_kind": request.step_kind,
            "tool_names": [getattr(tool, "__name__", repr(tool)) for tool in request.tool_functions],
            "agent_profile_id": request.agent_profile.id if request.agent_profile is not None else None,
        }
        captured.append(payload)
        if publisher is not None:
            await publisher("agent.step.fallback", {**payload, "reason": "test_fallback"})
        return OmniAgentResult(status="fallback", reason="test_fallback", tool_names=payload["tool_names"])

    monkeypatch.setattr(container.execution_runner._omni_agent, "run", fake_run)

    submission = await container.gateway.submit_task(
        TaskSubmitRequest(
            goal="整理一份版本发布说明",
            preferred_strategy="agent_backed",
            profile="py-basic",
        ),
        identity=identity,
    )

    run_detail = await _wait_for_terminal_run(container, submission.run_id, identity)
    replay = await container.replay_repository.get_by_run(submission.run_id)

    assert run_detail is not None
    assert replay is not None
    assert run_detail.run.status == RunStatus.SUCCEEDED
    assert any(item.get("step_kind") == "execution.agent_backed" for item in captured)
    assert "agent.step.fallback" in [entry.event_type for entry in replay.entries]


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
        goal="整理月度金价研究并输出 PPT",
        metadata={
            "tenant_id": identity.tenant_id,
            "principal_id": identity.principal_id,
            "profile": "py-basic",
        },
    )
    run = Run(id="run-host-tools-1", task_id=task.id, session_id="session-host-tools-1")
    execution_profile = ExecutionProfile(
        role=AgentRole.WRITER,
        preferred_strategy="presentation_delivery",
        required_tool_groups=[ToolGroup.PRESENTATION, ToolGroup.ARTIFACT_READ, ToolGroup.PROJECT_WRITE],
        candidate_runtime_kinds=[RuntimeKind.HOST_TOOLS, RuntimeKind.SANDBOX],
        resolved_runtime_kind=RuntimeKind.HOST_TOOLS,
        runtime_resolution_reason="Test forces host_tools runtime for OmniAgent coverage.",
        runtime_fallback_chain=[RuntimeKind.HOST_TOOLS, RuntimeKind.SANDBOX],
        preferred_skill_profiles=["pptx"],
        skill_profiles=["pptx"],
    )
    subtask = SubTask(
        id="subtask-host-tools-1",
        task_id=task.id,
        name="generate-pptx",
        description="Generate the final presentation deck.",
        role=AgentRole.WRITER,
        preferred_strategy="presentation_delivery",
        required_tool_groups=[ToolGroup.PRESENTATION, ToolGroup.ARTIFACT_READ, ToolGroup.PROJECT_WRITE],
        candidate_runtime_kinds=[RuntimeKind.HOST_TOOLS, RuntimeKind.SANDBOX],
        preferred_skill_profiles=["pptx"],
        acceptance_criteria=["A PPT delivery artifact is produced."],
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
    assert any(
        isinstance(item.get("skill_profiles"), list)
        and "pptx" in cast(list[str], item.get("skill_profiles"))
        for item in captured
    )
    assert "agent.step.fallback" in [entry.event_type for entry in replay.entries]


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
            skill_profiles=["build_app"],
            allowed_tool_groups=[ToolGroup.PROJECT_READ],
            default_strategy="build_app",
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
async def test_agent_backed_handoff_emits_started_and_completed_events() -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)
    container.agent_profile_store.save(
        AgentProfile(
            id="delegating-coder",
            name="Delegating Coder",
            role=AgentRole.CODER,
            description="Coder profile that may hand off research-heavy work.",
            skill_mode=SkillsMode.ALL,
            allowed_tool_groups=[ToolGroup.PROJECT_READ, ToolGroup.MEMORY_LOOKUP],
            default_strategy="agent_backed",
            handoff_policy=HandoffPolicy(
                allow_handoff=True,
                allowed_targets=["researcher-default"],
                max_depth=1,
            ),
        )
    )
    identity = await container.identity_resolver.resolve()

    submission = await container.gateway.submit_task(
        TaskSubmitRequest(
            goal="整理竞品调研摘要",
            preferred_strategy="agent_backed",
            agent_profile_id="delegating-coder",
            constraints={"handoff_requests": {"prepare-implementation": "researcher-default"}},
        ),
        identity=identity,
    )

    run_detail = await _wait_for_terminal_run(container, submission.run_id, identity)
    replay = await container.replay_repository.get_by_run(submission.run_id)

    assert run_detail is not None
    assert replay is not None
    assert run_detail.run.status == RunStatus.SUCCEEDED
    implementation_subtask = next(subtask for subtask in run_detail.subtasks if subtask.name == "prepare-implementation")
    assert implementation_subtask.result is not None
    handoff = implementation_subtask.result.get("handoff") or {}
    assert handoff.get("to_agent_profile_id") == "researcher-default"
    event_types = [entry.event_type for entry in replay.entries]
    assert "agent.handoff.started" in event_types
    assert "agent.handoff.completed" in event_types


@pytest.mark.asyncio
async def test_agent_backed_handoff_denied_emits_denied_event_and_falls_back_local() -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)
    identity = await container.identity_resolver.resolve()

    submission = await container.gateway.submit_task(
        TaskSubmitRequest(
            goal="整理一份版本发布说明",
            preferred_strategy="agent_backed",
            constraints={"handoff_requests": {"prepare-implementation": "researcher-default"}},
        ),
        identity=identity,
    )

    run_detail = await _wait_for_terminal_run(container, submission.run_id, identity)
    replay = await container.replay_repository.get_by_run(submission.run_id)

    assert run_detail is not None
    assert replay is not None
    assert run_detail.run.status == RunStatus.SUCCEEDED
    event_types = [entry.event_type for entry in replay.entries]
    assert "agent.handoff.denied" in event_types
    assert "policy.denied" in event_types


@pytest.mark.asyncio
async def test_validation_subtasks_use_agent_results_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)
    identity = await container.identity_resolver.resolve()

    async def fake_structured_prompt(*, subtask, **kwargs):
        if subtask.role == AgentRole.TESTER:
            return """{
  \"passed\": true,
  \"summary\": \"LLM verification passed.\",
  \"criteria_results\": [
    {
      \"criterion\": \"Repair evidence is attached and satisfies the review feedback.\",
      \"passed\": true,
      \"evidence\": \"verified from dependency and artifact summaries\"
    }
  ],
  \"evidence_subtask_ids\": [],
  \"artifact_ids\": []
}"""
        return """{
  \"decision\": \"accept\",
  \"summary\": \"LLM review accepted the result.\",
  \"rationale\": \"Verification result was accepted.\",
  \"follow_up_actions\": []
}"""

    monkeypatch.setattr(container.execution_runner, "_render_structured_prompt_with_model", fake_structured_prompt)

    submission = await container.gateway.submit_task(
        TaskSubmitRequest(goal="实现一个导出 Excel 功能并补测试", profile="py-basic"),
        identity=identity,
    )

    run_detail = await _wait_for_terminal_run(container, submission.run_id, identity)
    replay = await container.replay_repository.get_by_run(submission.run_id)

    assert run_detail is not None
    assert replay is not None
    assert run_detail.run.status == RunStatus.SUCCEEDED
    verify_subtask = next(subtask for subtask in run_detail.subtasks if subtask.name == "verify-result")
    review_subtask = next(subtask for subtask in run_detail.subtasks if subtask.name == "review-result")
    assert verify_subtask.result is not None
    assert verify_subtask.result.get("validation_backend") == "agent"
    assert review_subtask.result is not None
    assert review_subtask.result.get("validation_backend") == "agent"
    event_types = [entry.event_type for entry in replay.entries]
    assert "validation.agent.started" in event_types
    assert "validation.agent.completed" in event_types


@pytest.mark.asyncio
async def test_validation_subtasks_fall_back_to_rules_when_agent_output_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)
    identity = await container.identity_resolver.resolve()

    async def fake_structured_prompt(**kwargs):
        return None

    monkeypatch.setattr(container.execution_runner, "_render_structured_prompt_with_model", fake_structured_prompt)

    submission = await container.gateway.submit_task(
        TaskSubmitRequest(goal="实现一个导出 Excel 功能并补测试", profile="py-basic"),
        identity=identity,
    )

    run_detail = await _wait_for_terminal_run(container, submission.run_id, identity)
    replay = await container.replay_repository.get_by_run(submission.run_id)

    assert run_detail is not None
    assert replay is not None
    assert run_detail.run.status == RunStatus.SUCCEEDED
    verify_subtask = next(subtask for subtask in run_detail.subtasks if subtask.name == "verify-result")
    review_subtask = next(subtask for subtask in run_detail.subtasks if subtask.name == "review-result")
    assert verify_subtask.result is not None
    assert verify_subtask.result.get("validation_backend") == "rules_fallback"
    assert review_subtask.result is not None
    assert review_subtask.result.get("validation_backend") == "rules_fallback"
    event_types = [entry.event_type for entry in replay.entries]
    assert "validation.agent.fallback" in event_types