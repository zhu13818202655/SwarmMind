"""Subtask scheduling helpers."""

from swarmmind.models.task import SubTask, TaskStatus


class Scheduler:
    """Resolve the next executable subtasks from a task graph."""

    def get_ready_subtasks(self, subtasks: list[SubTask]) -> list[SubTask]:
        """Return subtasks whose dependencies are already satisfied.

        The first round uses a simple in-memory check over the provided task graph.
        """
        subtask_map = {subtask.id: subtask for subtask in subtasks}
        ready: list[SubTask] = []
        for subtask in subtasks:
            if subtask.status != TaskStatus.PENDING:
                continue
            if all(subtask_map[dependency].status == TaskStatus.SUCCEEDED for dependency in subtask.dependencies if dependency in subtask_map):
                ready.append(subtask)
        return ready
