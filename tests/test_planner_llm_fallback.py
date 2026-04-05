from __future__ import annotations

import pytest

from swarmmind.agents.agent_skill import resolve_agent_skill_dirs
from swarmmind.agents.config import AgentConfig, AgentScopeConfig
from swarmmind.agents.factory import AgentFactory
from swarmmind.agents.profile import AgentProfileStore
from swarmmind.models.capability import AgentRole, RuntimeKind, ToolGroup
from swarmmind.models.run import Run
from swarmmind.models.task import SubTask, Task
from swarmmind.orchestration.planner import (
    Planner,
    _ExecutionConfigurationSubtaskSpec,
    _PlanResult,
    _PlanSubtaskSpec,
)
from swarmmind.prompt_template.planner import PLANNER_ROLE_ENUM


@pytest.mark.asyncio
async def test_planner_uses_llm_subtasks_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    planner = Planner(model_name="gpt-4o", model_api_key="dummy")
    task = Task(id="task-1", goal="写一个python版本贪吃蛇", metadata={"profile": "py-basic"})
    run = Run(id="run-1", task_id=task.id, session_id="session-1")

    llm_subtask = SubTask(
        id="subtask-1",
        task_id=task.id,
        name="implement-snake",
        description="Implement game loop and controls.",
        metadata={"run_id": run.id, "plan_source": "llm"},
    )

    async def fake_plan_with_model(_task: Task, _run: Run) -> list[SubTask] | None:
        return [llm_subtask]

    monkeypatch.setattr(planner, "_plan_with_model", fake_plan_with_model)

    subtasks = await planner.plan(task, run)

    assert len(subtasks) == 1
    assert subtasks[0].name == "implement-snake"
    assert subtasks[0].metadata.get("plan_source") == "llm"


@pytest.mark.asyncio
async def test_planner_falls_back_to_rules_when_llm_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    planner = Planner(model_name="gpt-4o", model_api_key="dummy", agent_profile_store=AgentProfileStore())
    task = Task(id="task-2", goal="实现导出并验证", metadata={"profile": "py-basic"})
    run = Run(id="run-2", task_id=task.id, session_id="session-2")

    async def fake_plan_with_model(_task: Task, _run: Run) -> list[SubTask] | None:
        return None

    monkeypatch.setattr(planner, "_plan_with_model", fake_plan_with_model)

    subtasks = await planner.plan(task, run)

    assert any(subtask.name == "analyze-requirement" for subtask in subtasks)
    assert any(subtask.name == "prepare-implementation" for subtask in subtasks)
    assert any(subtask.name == "verify-result" for subtask in subtasks)
    assert any(subtask.name == "review-result" for subtask in subtasks)
    assert all(subtask.metadata.get("plan_source") == "rules" for subtask in subtasks)

    subtask_map = {subtask.name: subtask for subtask in subtasks}
    assert subtask_map["prepare-implementation"].dependencies == [subtask_map["analyze-requirement"].id]
    assert subtask_map["verify-result"].dependencies == [subtask_map["prepare-implementation"].id]
    assert subtask_map["review-result"].dependencies == [subtask_map["verify-result"].id]
    assert subtask_map["prepare-implementation"].execution_configuration is not None
    assert subtask_map["prepare-implementation"].execution_configuration.runtime_kind == RuntimeKind.SANDBOX
    assert ToolGroup.CODE_EXEC in subtask_map["prepare-implementation"].execution_configuration.tool_requirements


@pytest.mark.asyncio
async def test_planner_prompt_includes_available_agent_profiles() -> None:
    planner = Planner(model_name="gpt-4o", model_api_key="dummy", agent_profile_store=AgentProfileStore())
    task = Task(id="task-3", goal="整理发布说明", metadata={"profile": "py-basic"})

    prompt = await planner._compose_planning_prompt(task)

    assert "可用 Agent Profiles JSON" in prompt
    assert "coder-default" in prompt
    assert "verifier-default" in prompt
    assert PLANNER_ROLE_ENUM in prompt
    assert "expected_artifacts" in prompt
    assert "candidate_runtime_kinds" not in prompt
    assert "preferred_strategy" not in prompt
    assert "http" not in prompt


def test_build_subtasks_from_plan_applies_default_execution_configuration() -> None:
    planner = Planner(agent_profile_store=AgentProfileStore())
    task = Task(id="task-4", goal="实现并评审", metadata={"profile": "py-basic"})
    run = Run(id="run-4", task_id=task.id, session_id="session-4")
    plan_result = _PlanResult(
        subtasks=[
            _PlanSubtaskSpec(
                name="prepare-implementation",
                description="Implement the feature.",
                role="coder",
                acceptance_criteria=["Implementation is complete."],
                expected_artifacts=["code_changes"],
            )
        ]
    )

    normalized = planner._validate_and_normalize_plan(task, plan_result)
    merged = planner._merge_execution_configurations(task, normalized, [])
    subtasks = planner._build_subtasks_from_plan(task, run, merged)

    assert len(subtasks) == 1
    subtask = subtasks[0]
    assert subtask.role == AgentRole.CODER
    assert subtask.execution_configuration is not None
    assert subtask.execution_configuration.runtime_kind == RuntimeKind.SANDBOX
    assert ToolGroup.CODE_EXEC in subtask.execution_configuration.tool_requirements


def test_build_subtasks_from_plan_records_validation_warnings_for_missing_expected_artifacts() -> None:
    planner = Planner(agent_profile_store=AgentProfileStore())
    task = Task(id="task-5", goal="实现功能", metadata={"profile": "py-basic"})
    run = Run(id="run-5", task_id=task.id, session_id="session-5")
    plan_result = _PlanResult(
        subtasks=[
            _PlanSubtaskSpec(
                name="prepare-implementation",
                description="Implement the feature.",
                role="executor",
                acceptance_criteria=["Implementation is complete."],
                expected_artifacts=[],
            )
        ]
    )

    normalized = planner._validate_and_normalize_plan(task, plan_result)
    merged = planner._merge_execution_configurations(task, normalized, [])
    [subtask] = planner._build_subtasks_from_plan(task, run, merged)

    assert subtask.role == AgentRole.CODER
    assert subtask.expected_artifacts == ["deliverable"]
    warnings = subtask.metadata.get("planner_validation_warnings") or []
    assert any("expected_artifacts" in warning for warning in warnings)
    assert any("Normalized invalid planner role 'executor'" in warning for warning in warnings)


def test_merge_execution_configurations_prefers_llm_execution_output() -> None:
    planner = Planner(agent_profile_store=AgentProfileStore())
    task = Task(id="task-6", goal="整理发布说明", metadata={"profile": "py-basic"})
    plan_result = _PlanResult(
        subtasks=[
            _PlanSubtaskSpec(
                name="draft-release-summary",
                description="Draft the summary.",
                role="writer",
                acceptance_criteria=["Summary is complete."],
                expected_artifacts=["report"],
            )
        ]
    )

    normalized = planner._validate_and_normalize_plan(task, plan_result)
    merged = planner._merge_execution_configurations(
        task,
        normalized,
        [
            _ExecutionConfigurationSubtaskSpec(
                name="draft-release-summary",
                runtime_kind="host_tools",
                tool_requirements=["workspace", "artifact"],
                skill_profiles=["write_report"],
            )
        ],
    )

    assert len(merged) == 1
    execution_configuration = merged[0].execution_configuration
    assert execution_configuration is not None
    assert execution_configuration.runtime_kind == RuntimeKind.HOST_TOOLS
    assert execution_configuration.tool_requirements == [ToolGroup.WORKSPACE, ToolGroup.ARTIFACT]
    assert execution_configuration.skill_profiles == ["write_report"]


def test_agent_factory_registers_native_agentscope_skills() -> None:
    factory = AgentFactory(
        AgentConfig(
            name="skill-agent",
            scope_config=AgentScopeConfig(model_name="gpt-4o"),
            skill_profiles=["task_planning", "build_app"],
        )
    )

    toolkit = factory.create_toolkit([])
    assert toolkit is not None
    assert resolve_agent_skill_dirs(["build_app"]) == []
