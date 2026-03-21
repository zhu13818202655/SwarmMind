"""Run and task state aggregation helpers."""

from __future__ import annotations

import uuid

from swarmmind.events import EventBus
from swarmmind.models.event import DomainEvent
from swarmmind.models.run import RunPhase, RunStatus
from swarmmind.models.task import TaskStatus
from swarmmind.repositories import ArtifactRepository, RunRepository, SubTaskRepository, TaskRepository


class RunStateService:
    """Aggregate subtask outcomes into run and task terminal states."""

    def __init__(
        self,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        subtask_repository: SubTaskRepository,
        artifact_repository: ArtifactRepository,
        event_bus: EventBus,
    ):
        self._task_repository = task_repository
        self._run_repository = run_repository
        self._subtask_repository = subtask_repository
        self._artifact_repository = artifact_repository
        self._event_bus = event_bus

    async def reconcile(self, run_id: str) -> None:
        """Recompute run and task status after subtask changes."""
        run = await self._run_repository.get(run_id)
        if run is None:
            return

        task = await self._task_repository.get(run.task_id)
        if task is None:
            return

        subtasks = await self._subtask_repository.list_for_run(run.id)
        artifacts = await self._artifact_repository.list_for_run(run.id)

        previous = (run.status, run.phase, task.status, task.error)

        failed = [subtask for subtask in subtasks if subtask.status == TaskStatus.FAILED]
        succeeded = [subtask for subtask in subtasks if subtask.status == TaskStatus.SUCCEEDED]
        pending = [
            subtask
            for subtask in subtasks
            if subtask.status not in {TaskStatus.SUCCEEDED, TaskStatus.FAILED}
        ]

        if failed:
            first_failed = failed[0]
            run.set_phase(RunPhase.REVIEWING)
            if run.status != RunStatus.FAILED:
                run.fail(first_failed.error or f"Subtask failed: {first_failed.name}")

            if task.status != TaskStatus.FAILED:
                task.fail(first_failed.error or f"Subtask failed: {first_failed.name}")
                task.result = {
                    "run_id": run.id,
                    "succeeded_subtasks": len(succeeded),
                    "failed_subtasks": [subtask.name for subtask in failed],
                    "artifact_count": len(artifacts),
                }
        elif subtasks and not pending:
            run.set_phase(RunPhase.DELIVERING)
            if run.status != RunStatus.SUCCEEDED:
                run.succeed()

            if task.status != TaskStatus.SUCCEEDED:
                task.succeed(
                    {
                        "run_id": run.id,
                        "subtask_count": len(subtasks),
                        "artifact_count": len(artifacts),
                        "completed_subtasks": [subtask.name for subtask in succeeded],
                    }
                )
        else:
            if task.status == TaskStatus.PLANNING:
                task.start()
            if run.status == RunStatus.PENDING:
                run.start()
            if run.phase != RunPhase.EXECUTING:
                run.set_phase(RunPhase.EXECUTING)

        await self._run_repository.save(run)
        await self._task_repository.save(task)

        current = (run.status, run.phase, task.status, task.error)
        if current == previous:
            return

        await self._event_bus.publish(
            DomainEvent(
                event_id=str(uuid.uuid4()),
                topic="run.updated",
                tenant_id=task.metadata.get("tenant_id", "local"),
                session_id=run.session_id,
                task_id=task.id,
                run_id=run.id,
                payload={
                    "status": run.status,
                    "phase": run.phase,
                    "task_status": task.status,
                    "artifact_count": len(artifacts),
                    "subtask_count": len(subtasks),
                },
            )
        )