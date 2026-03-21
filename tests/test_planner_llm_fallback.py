from __future__ import annotations

import pytest

from swarmmind.models.run import Run
from swarmmind.models.task import SubTask, Task
from swarmmind.orchestration.planner import Planner


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
    planner = Planner(model_name="gpt-4o", model_api_key="dummy")
    task = Task(id="task-2", goal="实现导出并验证", metadata={"profile": "py-basic"})
    run = Run(id="run-2", task_id=task.id, session_id="session-2")

    async def fake_plan_with_model(_task: Task, _run: Run) -> list[SubTask] | None:
        return None

    monkeypatch.setattr(planner, "_plan_with_model", fake_plan_with_model)

    subtasks = await planner.plan(task, run)

    assert any(subtask.name == "analyze-requirement" for subtask in subtasks)
    assert any(subtask.name == "prepare-implementation" for subtask in subtasks)
    assert any(subtask.name == "verify-result" for subtask in subtasks)
    assert all(subtask.metadata.get("plan_source") == "rules" for subtask in subtasks)
