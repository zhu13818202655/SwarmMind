"""Run and task state aggregation helpers."""

from __future__ import annotations

import uuid

from swarmmind.events import EventBus
from swarmmind.models.event import DomainEvent
from swarmmind.models.execution import ReviewDecisionType
from swarmmind.models.run import RunPhase, RunStatus
from swarmmind.models.task import SubTaskStatus, TaskStatus
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

        covered_failure_ids = {
            str(subtask.metadata.get("repair_source_subtask_id"))
            for subtask in subtasks
            if subtask.metadata.get("repair_source_subtask_id")
        }
        failed = [
            subtask
            for subtask in subtasks
            if subtask.status == SubTaskStatus.FAILED and subtask.id not in covered_failure_ids
        ]
        succeeded = [subtask for subtask in subtasks if subtask.status == SubTaskStatus.SUCCEEDED]
        pending = [
            subtask
            for subtask in subtasks
            if subtask.status not in {SubTaskStatus.SUCCEEDED, SubTaskStatus.FAILED, SubTaskStatus.CANCELLED}
        ]
        unresolved_rework = [
            subtask
            for subtask in succeeded
            if str((subtask.result or {}).get("decision") or "").lower() == ReviewDecisionType.REWORK.value
            and not subtask.metadata.get("rework_generated")
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
        elif unresolved_rework and not pending:
            first_rework = unresolved_rework[0]
            run.set_phase(RunPhase.REVIEWING)
            if run.status != RunStatus.FAILED:
                run.fail(f"Review requested rework but no repair chain was created: {first_rework.name}")

            if task.status != TaskStatus.FAILED:
                task.fail(f"Review requested rework but repair budget was exhausted: {first_rework.name}")
                task.result = {
                    "run_id": run.id,
                    "succeeded_subtasks": len(succeeded),
                    "pending_subtasks": [subtask.name for subtask in pending],
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

        if run.status in {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED}:
            terminal_payload = {
                "status": run.status,
                "phase": run.phase,
                "task_status": task.status,
                "artifact_count": len(artifacts),
                "subtask_count": len(subtasks),
                "error": run.error,
            }
            await self._event_bus.publish(
                DomainEvent(
                    event_id=str(uuid.uuid4()),
                    topic="run.terminal",
                    tenant_id=task.metadata.get("tenant_id", "local"),
                    session_id=run.session_id,
                    task_id=task.id,
                    run_id=run.id,
                    payload=terminal_payload,
                )
            )
            await self._event_bus.publish(
                DomainEvent(
                    event_id=str(uuid.uuid4()),
                    topic="run.summary",
                    tenant_id=task.metadata.get("tenant_id", "local"),
                    session_id=run.session_id,
                    task_id=task.id,
                    run_id=run.id,
                    payload={
                        **terminal_payload,
                        "completed_subtasks": [subtask.name for subtask in succeeded],
                        "failed_subtasks": [subtask.name for subtask in failed],
                        "pending_subtasks": [subtask.name for subtask in pending],
                    },
                )
            )