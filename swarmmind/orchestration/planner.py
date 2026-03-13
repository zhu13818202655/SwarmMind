"""First-round planner implementation."""

from __future__ import annotations

import uuid

from swarmmind.models.capability import AgentRole, ToolGroup
from swarmmind.models.run import Run
from swarmmind.models.task import SubTask, Task


class Planner:
    """Create a simple task graph from the submitted goal."""

    async def plan(self, task: Task, run: Run) -> list[SubTask]:
        """Return a deterministic first-round task graph."""
        goal = task.goal.lower()
        subtasks: list[SubTask] = []

        subtasks.append(
            SubTask(
                id=str(uuid.uuid4()),
                task_id=task.id,
                name="analyze-requirement",
                description="Analyze the goal and identify the implementation scope.",
                role=AgentRole.PLANNER,
                preferred_skill="task_planning",
                required_tool_groups=[ToolGroup.PROJECT_READ],
                acceptance_criteria=["The implementation scope is summarized clearly."],
                metadata={"run_id": run.id},
            )
        )

        build_tool_groups = [ToolGroup.PROJECT_READ, ToolGroup.PROJECT_WRITE, ToolGroup.SANDBOX_EXEC]
        if "test" in goal:
            build_tool_groups.append(ToolGroup.ARTIFACT_READ)

        subtasks.append(
            SubTask(
                id=str(uuid.uuid4()),
                task_id=task.id,
                name="prepare-implementation",
                description=f"Prepare the implementation steps for: {task.goal}",
                role=AgentRole.CODER,
                preferred_skill=task.metadata.get("preferred_skill") or "build_app",
                required_tool_groups=build_tool_groups,
                sandbox_profile=task.metadata.get("profile", "py-basic"),
                acceptance_criteria=["The execution plan references the right tool groups."],
                metadata={"run_id": run.id},
            )
        )

        if "test" in goal or "验证" in task.goal:
            subtasks.append(
                SubTask(
                    id=str(uuid.uuid4()),
                    task_id=task.id,
                    name="verify-result",
                    description="Verify the implementation using the declared acceptance criteria.",
                    role=AgentRole.TESTER,
                    preferred_skill="verification",
                    required_tool_groups=[ToolGroup.SANDBOX_EXEC, ToolGroup.ARTIFACT_READ],
                    sandbox_profile=task.metadata.get("profile", "py-basic"),
                    acceptance_criteria=["Verification evidence is attached to the run."],
                    metadata={"run_id": run.id},
                )
            )

        return subtasks
