"""Task orchestrator for managing task execution."""

from typing import Any
from swarmmind.models.task import Task, SubTask, TaskStatus
from swarmmind.gateway.gateway import Gateway
from swarmmind.agents.factory import AgentFactory
from swarmmind.sandbox.manager import SandboxManager
from swarmmind.memory.transcript import Transcript


class TaskOrchestrator:
    """Orchestrator for managing task execution."""

    def __init__(
        self,
        gateway: Gateway,
        agent_factory: AgentFactory,
        sandbox_manager: SandboxManager,
    ):
        self._gateway = gateway
        self._agent_factory = agent_factory
        self._sandbox_manager = sandbox_manager

    async def execute_task(self, task: Task) -> dict[str, Any]:
        """Execute a task."""
        # Create session
        session = self._gateway.create_session(task.id)
        transcript: Transcript = session["transcript"]

        try:
            # Mark as running
            task.start()
            await self._gateway.update_task(task)
            transcript.add_event("task_started", {"goal": task.goal})

            # Decompose task into subtasks
            decomposer = TaskDecomposer()
            subtasks = await decomposer.decompose(task.goal)
            session["subtasks"] = subtasks

            # Execute subtasks
            results = []
            for subtask in subtasks:
                result = await self._execute_subtask(subtask, transcript)
                results.append(result)

            # Complete task
            task.succeed({"results": results, "task_id": task.id})
            await self._gateway.update_task(task)
            transcript.add_event("task_completed", {"results_count": len(results)})

            return task.result

        except Exception as e:
            task.fail(str(e))
            await self._gateway.update_task(task)
            transcript.add_error(str(e))
            raise

    async def _execute_subtask(self, subtask: SubTask, transcript: Transcript) -> dict[str, Any]:
        """Execute a subtask."""
        subtask.status = TaskStatus.RUNNING
        transcript.add_event("subtask_started", {"subtask": subtask.name})

        try:
            # Create sandbox if needed
            if subtask.sandbox_profile:
                handle = await self._sandbox_manager.create(subtask.sandbox_profile)
                subtask.agent_id = handle.sandbox_id

            # Execute (simplified - just mark as done)
            result = {"subtask_id": subtask.id, "status": "completed"}
            subtask.complete(result)

            transcript.add_event("subtask_completed", {"subtask": subtask.name})
            return result

        except Exception as e:
            subtask.fail(str(e))
            transcript.add_error(f"subtask_{subtask.id}: {str(e)}")
            raise


class TaskDecomposer:
    """Decompose a task into subtasks."""

    async def decompose(self, goal: str) -> list[SubTask]:
        """Decompose a goal into subtasks."""
        # Simplified implementation
        # In production, this would use LLM to decompose

        import uuid

        # Single subtask for now
        return [
            SubTask(
                id=str(uuid.uuid4()),
                task_id="",
                name="main",
                description=goal,
                sandbox_profile="py-basic",
            )
        ]
