"""Task state machine."""

from enum import Enum
from typing import Callable
from swarmmind.models.task import TaskStatus


class TaskStateMachine:
    """State machine for task status transitions."""

    # Valid transitions
    TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
        TaskStatus.PENDING: {TaskStatus.PLANNING, TaskStatus.RUNNING, TaskStatus.CANCELLED},
        TaskStatus.PLANNING: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
        TaskStatus.RUNNING: {TaskStatus.REVIEWING, TaskStatus.FAILED, TaskStatus.CANCELLED},
        TaskStatus.REVIEWING: {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.RUNNING},
        TaskStatus.SUCCEEDED: set(),
        TaskStatus.FAILED: {TaskStatus.PENDING},  # Allow retry
        TaskStatus.CANCELLED: {TaskStatus.PENDING},  # Allow restart
    }

    def __init__(self):
        self._handlers: dict[tuple[TaskStatus, TaskStatus], list[Callable]] = {}

    def can_transition(self, from_status: TaskStatus, to_status: TaskStatus) -> bool:
        """Check if transition is valid."""
        return to_status in self.TRANSITIONS.get(from_status, set())

    def register_handler(
        self,
        from_status: TaskStatus,
        to_status: TaskStatus,
        handler: Callable,
    ) -> None:
        """Register a handler for a transition."""
        key = (from_status, to_status)
        if key not in self._handlers:
            self._handlers[key] = []
        self._handlers[key].append(handler)

    async def transition(
        self,
        current_status: TaskStatus,
        new_status: TaskStatus,
    ) -> TaskStatus:
        """Perform transition with handlers."""
        if not self.can_transition(current_status, new_status):
            raise ValueError(f"Invalid transition: {current_status} -> {new_status}")

        # Run handlers
        key = (current_status, new_status)
        handlers = self._handlers.get(key, [])
        for handler in handlers:
            await handler()

        return new_status
