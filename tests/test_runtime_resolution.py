from __future__ import annotations

import pytest

from swarmmind.agents.profile import AgentProfileStore
from swarmmind.models.capability import AgentRole, RuntimeKind, ToolGroup
from swarmmind.models.execution import ExecutionConfiguration, ExecutionProfile
from swarmmind.models.run import Run
from swarmmind.models.task import SubTask, Task
from swarmmind.orchestration.coordinator import Coordinator


@pytest.mark.asyncio
async def test_coordinator_uses_execution_configuration_for_writer_host_tools() -> None:
    coordinator = Coordinator(AgentProfileStore())
    task = Task(id="task-1", goal="整理月度金价研究并输出 PPT", metadata={"profile": "py-basic"})
    run = Run(id="run-1", task_id=task.id, session_id="session-1")
    subtask = SubTask(
        id="subtask-1",
        task_id=task.id,
        name="generate-pptx",
        description="Generate the final presentation deck.",
        role=AgentRole.WRITER,
        execution_configuration=ExecutionConfiguration(
            runtime_kind=RuntimeKind.HOST_TOOLS,
            tool_requirements=[ToolGroup.WORKSPACE, ToolGroup.ARTIFACT],
            skill_profiles=["pptx"],
        ),
    )

    [assigned_subtask] = await coordinator.assign(task, run, [subtask])
    profile = ExecutionProfile.model_validate(assigned_subtask.metadata["execution_profile"])

    assert profile.resolved_runtime_kind == RuntimeKind.HOST_TOOLS
    assert profile.runtime_fallback_chain == [RuntimeKind.SANDBOX, RuntimeKind.LLM_ONLY]
    assert profile.skill_profiles == ["pptx"]
    assert profile.sandbox_profile is None


@pytest.mark.asyncio
async def test_coordinator_prefers_host_tools_for_research_without_legacy_browser_runtime() -> None:
    coordinator = Coordinator(AgentProfileStore())
    task = Task(id="task-2", goal="调研最近一个月金价走势", metadata={"profile": "aio"})
    run = Run(id="run-2", task_id=task.id, session_id="session-2")
    subtask = SubTask(
        id="subtask-2",
        task_id=task.id,
        name="collect-price-data",
        description="Collect recent gold price sources.",
        role=AgentRole.RESEARCHER,
        execution_configuration=ExecutionConfiguration(
            tool_requirements=[ToolGroup.WEB_SEARCH, ToolGroup.BROWSER, ToolGroup.WORKSPACE],
        ),
    )

    [assigned_subtask] = await coordinator.assign(task, run, [subtask])
    profile = ExecutionProfile.model_validate(assigned_subtask.metadata["execution_profile"])

    assert profile.resolved_runtime_kind == RuntimeKind.HOST_TOOLS
    assert profile.runtime_fallback_chain == [RuntimeKind.SANDBOX, RuntimeKind.LLM_ONLY]
    assert profile.runtime_resolution_reason is not None
    assert "host_tools" in profile.runtime_resolution_reason


@pytest.mark.asyncio
async def test_coordinator_prefers_browser_playwright_for_dynamic_browser_tasks() -> None:
    coordinator = Coordinator(AgentProfileStore())
    task = Task(id="task-2b", goal="打开动态页面并截图", metadata={"profile": "aio"})
    run = Run(id="run-2b", task_id=task.id, session_id="session-2b")
    subtask = SubTask(
        id="subtask-2b",
        task_id=task.id,
        name="capture-dynamic-page",
        description="Open the dynamic page, click the login button, and capture a screenshot.",
        role=AgentRole.RESEARCHER,
        execution_configuration=ExecutionConfiguration(
            tool_requirements=[ToolGroup.BROWSER, ToolGroup.WORKSPACE],
        ),
    )

    [assigned_subtask] = await coordinator.assign(task, run, [subtask])
    profile = ExecutionProfile.model_validate(assigned_subtask.metadata["execution_profile"])

    assert profile.resolved_runtime_kind == RuntimeKind.SANDBOX
    assert profile.sandbox_profile == "aio"
    assert profile.runtime_resolution_reason is not None
    assert "dynamic browsing" in profile.runtime_resolution_reason


@pytest.mark.asyncio
async def test_coordinator_uses_planner_execution_candidate_runtime_priority() -> None:
    coordinator = Coordinator(AgentProfileStore())
    task = Task(id="task-3", goal="执行实现任务", metadata={"profile": "py-basic"})
    run = Run(id="run-3", task_id=task.id, session_id="session-3")
    subtask = SubTask(
        id="subtask-3",
        task_id=task.id,
        name="prepare-implementation",
        description="Implement feature with code execution.",
        role=AgentRole.CODER,
        execution_configuration=ExecutionConfiguration(
            tool_requirements=[ToolGroup.CODE_EXEC, ToolGroup.WORKSPACE],
            metadata={"planner_candidate_runtime_kinds": '["host_tools","sandbox"]'},
        ),
        metadata={
            "planner_execution_candidate": {
                "name": "prepare-implementation",
                "tool_groups": ["code_exec", "workspace"],
                "runtime_kinds": ["host_tools", "sandbox"],
                "skill_profiles": [],
            }
        },
    )

    [assigned_subtask] = await coordinator.assign(task, run, [subtask])
    profile = ExecutionProfile.model_validate(assigned_subtask.metadata["execution_profile"])

    assert profile.resolved_runtime_kind == RuntimeKind.HOST_TOOLS
    assert profile.runtime_fallback_chain[0] == RuntimeKind.SANDBOX
    assert assigned_subtask.metadata.get("resolved_execution_profile") is not None
    assert profile.skill_profiles == []
