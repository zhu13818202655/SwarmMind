"""Task orchestrator for the first rewrite round."""

from __future__ import annotations

import uuid

from swarmmind.events.bus import EventBus
from swarmmind.models.event import DomainEvent
from swarmmind.models.run import RunPhase
from swarmmind.models.task import TaskStatus
from swarmmind.orchestration.coordinator import Coordinator
from swarmmind.orchestration.planner import Planner
from swarmmind.orchestration.scheduler import Scheduler
from swarmmind.repositories import RunRepository, SubTaskRepository, TaskRepository


class TaskOrchestrator:
    """Event-driven task orchestrator skeleton."""

    def __init__(
        self,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        subtask_repository: SubTaskRepository,
        event_bus: EventBus,
        planner: Planner,
        coordinator: Coordinator,
        scheduler: Scheduler,
    ):
        self._task_repository = task_repository
        self._run_repository = run_repository
        self._subtask_repository = subtask_repository
        self._event_bus = event_bus
        self._planner = planner
        self._coordinator = coordinator
        self._scheduler = scheduler

    async def handle_task_created(self, event: DomainEvent) -> None:
        """Build the initial task graph and assign ready subtasks."""
        task = await self._task_repository.get(event.task_id or "")
        run = await self._run_repository.get(event.run_id or "")
        if task is None or run is None:
            return

        task.status = TaskStatus.PLANNING
        await self._task_repository.save(task)

        run.start()
        run.set_phase(RunPhase.PLANNING)
        await self._run_repository.save(run)

        subtasks = await self._planner.plan(task, run)
        await self._subtask_repository.create_many(subtasks)

        run.attach_subtasks([subtask.id for subtask in subtasks])
        run.set_phase(RunPhase.COORDINATING)
        await self._run_repository.save(run)

        await self._event_bus.publish(
            DomainEvent(
                event_id=str(uuid.uuid4()),
                topic="task.planning.completed",
                tenant_id=event.tenant_id,
                session_id=event.session_id,
                task_id=task.id,
                run_id=run.id,
                payload={"subtask_count": len(subtasks)},
            )
        )

        ready_subtasks = self._scheduler.get_ready_subtasks(subtasks)
        assigned_subtasks = await self._coordinator.assign(task, run, ready_subtasks)

        task.start()
        await self._task_repository.save(task)

        run.set_phase(RunPhase.EXECUTING)
        await self._run_repository.save(run)

        for subtask in assigned_subtasks:
            await self._subtask_repository.save(subtask)
            await self._event_bus.publish(
                DomainEvent(
                    event_id=str(uuid.uuid4()),
                    topic="subtask.assigned",
                    tenant_id=event.tenant_id,
                    session_id=event.session_id,
                    task_id=task.id,
                    run_id=run.id,
                    subtask_id=subtask.id,
                    payload={
                        "name": subtask.name,
                        "role": subtask.role,
                        "preferred_skill": subtask.preferred_skill,
                    },
                )
            )

