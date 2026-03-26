from __future__ import annotations

import pytest

from swarmmind.agents.profile import AgentProfileStore
from swarmmind.agents.agent_skill import resolve_agent_skill_dirs
from swarmmind.agents.config import AgentConfig, AgentScopeConfig
from swarmmind.agents.factory import AgentFactory
from swarmmind.models.run import Run
from swarmmind.models.task import SubTask, Task
from swarmmind.orchestration.planner import Planner, _PlanResult, _PlanSubtaskSpec


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
    assert subtask_map["analyze-requirement"].agent_profile_id == "planner-default"
    assert subtask_map["prepare-implementation"].agent_profile_id == "coder-default"
    assert subtask_map["review-result"].agent_profile_id == "reviewer-default"


@pytest.mark.asyncio
async def test_planner_prompt_includes_available_agent_profiles() -> None:
    planner = Planner(model_name="gpt-4o", model_api_key="dummy", agent_profile_store=AgentProfileStore())
    task = Task(id="task-3", goal="整理发布说明", metadata={"profile": "py-basic"})

    prompt = await planner._compose_planning_prompt(task)

    assert "Available Agent Profiles JSON" in prompt
    assert "coder-default" in prompt
    assert "agent-backed-default" in prompt


def test_build_subtasks_from_plan_resolves_role_compatible_agent_profile_ids() -> None:
    planner = Planner(agent_profile_store=AgentProfileStore())
    task = Task(id="task-4", goal="实现并评审", metadata={"profile": "py-basic", "agent_profile_id": "writer-default"})
    run = Run(id="run-4", task_id=task.id, session_id="session-4")
    plan_result = _PlanResult(
        subtasks=[
            _PlanSubtaskSpec(
                name="prepare-implementation",
                description="Implement the feature.",
                role="coder",
                agent_profile_id="writer-default",
                preferred_strategy="build_app",
                required_tool_groups=["project_read", "project_write", "sandbox_exec"],
            )
        ]
    )

    subtasks = planner._build_subtasks_from_plan(task, run, plan_result)

    assert len(subtasks) == 1
    assert subtasks[0].agent_profile_id == "coder-default"


def test_agent_factory_registers_native_agentscope_skills() -> None:
    factory = AgentFactory(
        AgentConfig(
            name="skill-agent",
            scope_config=AgentScopeConfig(model_name="gpt-4o"),
            skill_profiles=["task_planning", "build_app"],
        )
    )

    toolkit = factory.create_toolkit([])
    prompt = toolkit.get_agent_skill_prompt()

    assert resolve_agent_skill_dirs(["task_planning", "build_app"])
    assert "task_planning" in prompt
    assert "build_app" in prompt
