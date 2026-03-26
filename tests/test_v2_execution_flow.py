from __future__ import annotations

import asyncio

import pytest

from swarmmind.models.agent_profile import AgentProfile, HandoffPolicy, SkillsMode
from swarmmind.models.capability import AgentRole, ToolGroup
from swarmmind.app.container import build_container
from swarmmind.config import SwarmMindConfig
from swarmmind.gateway import TaskSubmitRequest
from swarmmind.models.execution import ExecutionProfile
from swarmmind.models.run import RunStatus
from swarmmind.models.execution import ReviewDecisionType
from swarmmind.models.task import SubTaskStatus, TaskStatus


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
    assert "sandbox_exec" in implementation_subtask.metadata.get("selected_tools", [])
    assert implementation_profile.agent_profile_id == "coder-default"
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
    assert any(entry.event_type == "strategy.completed" for entry in replay.entries)


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