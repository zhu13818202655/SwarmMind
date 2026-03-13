"""First-round coordinator implementation."""

from __future__ import annotations

from swarmmind.models.execution import ExecutionProfile
from swarmmind.models.run import Run
from swarmmind.models.task import SubTask, Task


class Coordinator:
    """Attach execution metadata to ready subtasks."""

    async def assign(self, task: Task, run: Run, subtasks: list[SubTask]) -> list[SubTask]:
        """Assign an execution profile to each ready subtask."""
        assigned: list[SubTask] = []
        for subtask in subtasks:
            profile = ExecutionProfile(
                role=subtask.role,
                preferred_skill=subtask.preferred_skill,
                required_tool_groups=subtask.required_tool_groups,
                sandbox_profile=subtask.sandbox_profile or task.metadata.get("profile"),
            )
            subtask.metadata["execution_profile"] = profile.model_dump(mode="json")
            subtask.metadata["assigned_run_id"] = run.id
            assigned.append(subtask)
        return assigned
