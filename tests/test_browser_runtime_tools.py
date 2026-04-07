from __future__ import annotations

import pytest

from swarmmind.app.container import build_container
from swarmmind.config import SwarmMindConfig
from swarmmind.models.capability import AgentRole, RuntimeKind, ToolGroup
from swarmmind.models.execution import ExecutionConfiguration, ExecutionProfile
from swarmmind.models.task import SubTask, Task


async def _build_runner():
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)
    return container.execution_runner


@pytest.mark.asyncio
async def test_select_tool_names_prefers_host_browser_tools_for_host_runtime() -> None:
    runner = await _build_runner()
    subtask = SubTask(
        id="subtask-host-browser",
        task_id="task-host-browser",
        name="collect-sources",
        description="Collect sources from the web.",
        role=AgentRole.RESEARCHER,
        metadata={
            "execution_profile": ExecutionProfile(
                role=AgentRole.RESEARCHER,
                execution_configuration=ExecutionConfiguration(
                    runtime_kind=RuntimeKind.HOST_TOOLS,
                    tool_requirements=[ToolGroup.WEB_SEARCH, ToolGroup.BROWSER, ToolGroup.WORKSPACE],
                ),
                required_tool_groups=[ToolGroup.WEB_SEARCH, ToolGroup.BROWSER, ToolGroup.WORKSPACE],
                resolved_runtime_kind=RuntimeKind.HOST_TOOLS,
                allowed_tool_groups=[ToolGroup.WEB_SEARCH, ToolGroup.BROWSER, ToolGroup.WORKSPACE, ToolGroup.CODE_EXEC],
            ).model_dump(mode="json")
        },
    )

    selected = runner._select_tool_names(subtask)

    assert "browser_get" in selected
    assert "browser_playwright" not in selected


@pytest.mark.asyncio
async def test_select_tool_names_exposes_playwright_for_sandbox_browser_runtime() -> None:
    runner = await _build_runner()
    subtask = SubTask(
        id="subtask-sandbox-browser",
        task_id="task-sandbox-browser",
        name="inspect-dynamic-page",
        description="Inspect a dynamic web page with browser automation.",
        role=AgentRole.RESEARCHER,
        metadata={
            "execution_profile": ExecutionProfile(
                role=AgentRole.RESEARCHER,
                execution_configuration=ExecutionConfiguration(
                    runtime_kind=RuntimeKind.SANDBOX,
                    tool_requirements=[ToolGroup.BROWSER, ToolGroup.WORKSPACE],
                    sandbox_profile="browser-playwright",
                ),
                required_tool_groups=[ToolGroup.BROWSER, ToolGroup.WORKSPACE],
                resolved_runtime_kind=RuntimeKind.SANDBOX,
                allowed_tool_groups=[ToolGroup.BROWSER, ToolGroup.WORKSPACE, ToolGroup.CODE_EXEC],
                sandbox_profile="browser-playwright",
            ).model_dump(mode="json")
        },
    )

    selected = runner._select_tool_names(subtask)

    assert "browser_playwright" in selected
    assert "browser_get" not in selected
    assert "sandbox_exec" not in selected


@pytest.mark.asyncio
async def test_execute_subtask_routes_sandbox_browser_runtime_to_inline_agent(monkeypatch) -> None:
    runner = await _build_runner()
    task = Task(id="task-browser-inline", goal="Inspect dynamic site", metadata={"profile": "browser-playwright"})
    subtask = SubTask(
        id="subtask-browser-inline",
        task_id=task.id,
        name="inspect-dynamic-page",
        description="Inspect a dynamic page with browser automation.",
        role=AgentRole.RESEARCHER,
        metadata={
            "execution_profile": ExecutionProfile(
                role=AgentRole.RESEARCHER,
                execution_configuration=ExecutionConfiguration(
                    runtime_kind=RuntimeKind.SANDBOX,
                    tool_requirements=[ToolGroup.BROWSER, ToolGroup.WORKSPACE],
                    sandbox_profile="browser-playwright",
                ),
                required_tool_groups=[ToolGroup.BROWSER, ToolGroup.WORKSPACE],
                resolved_runtime_kind=RuntimeKind.SANDBOX,
                allowed_tool_groups=[ToolGroup.BROWSER, ToolGroup.WORKSPACE, ToolGroup.CODE_EXEC],
                sandbox_profile="browser-playwright",
            ).model_dump(mode="json")
        },
    )
    calls: list[str] = []

    async def fake_validate(*args, **kwargs):
        return None

    async def fake_inline(*args, **kwargs):
        calls.append("inline")

    async def fake_sandbox(*args, **kwargs):
        calls.append("sandbox")

    monkeypatch.setattr(runner, "_validate_execution_policy", fake_validate)
    monkeypatch.setattr(runner, "_execute_inline_runtime_subtask", fake_inline)
    monkeypatch.setattr(runner, "_execute_sandbox_subtask", fake_sandbox)

    await runner._execute_subtask(task, None, subtask, None)

    assert calls == ["inline"]