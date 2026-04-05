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
    task = Task(id="task-2", goal="调研最近一个月金价走势", metadata={"profile": "research-net"})
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
