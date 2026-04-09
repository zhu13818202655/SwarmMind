"""Task orchestrator for the first rewrite round."""

from __future__ import annotations

import uuid

from swarmmind.events.bus import EventBus
from swarmmind.models.capability import AgentRole, RuntimeKind, ToolGroup
from swarmmind.models.event import DomainEvent
from swarmmind.models.execution import ExecutionConfiguration, ReviewDecisionType
from swarmmind.models.run import RunPhase
from swarmmind.models.task import SubTask, SubTaskStatus, TaskStatus
from swarmmind.utils import utc_now
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
        task = await self._task_repository.get(event.task_id or "")  # TODO 需要区分 task and run？
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

        await self._dispatch_ready_subtasks(task, run, event)

    async def handle_subtask_terminal(self, event: DomainEvent) -> None:
        """Continue scheduling when subtasks complete, and create rework chains if required."""
        if not event.task_id or not event.run_id or not event.subtask_id:
            return

        task = await self._task_repository.get(event.task_id)
        run = await self._run_repository.get(event.run_id)
        subtask = await self._subtask_repository.get(event.subtask_id)
        if task is None or run is None or subtask is None:
            return

        if event.topic == "subtask.completed":
            await self._maybe_generate_rework_chain(task, run, subtask, event)
        elif event.topic == "subtask.failed":
            await self._maybe_generate_failure_repair_chain(task, run, subtask, event)

        await self._dispatch_ready_subtasks(task, run, event)

    async def _dispatch_ready_subtasks(self, task, run, event: DomainEvent) -> None:
        subtasks = await self._subtask_repository.list_for_run(run.id)
        ready_subtasks = self._scheduler.get_ready_subtasks(subtasks)
        assigned_subtasks = await self._coordinator.assign(task, run, ready_subtasks)

        if not assigned_subtasks:
            return

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
                        "runtime_kind": (
                            subtask.execution_configuration.runtime_kind.value
                            if subtask.execution_configuration and subtask.execution_configuration.runtime_kind is not None
                            else None
                        ),
                    },
                )
            )

    async def _maybe_generate_rework_chain(self, task, run, subtask: SubTask, event: DomainEvent) -> None:
        if subtask.role != AgentRole.REVIEWER:
            return
        decision = str((subtask.result or {}).get("decision") or "").lower()
        if decision != ReviewDecisionType.REWORK.value:
            return

        current_attempt = int(subtask.metadata.get("repair_attempt") or 0)
        max_attempts = int(task.constraints.get("max_repair_attempts", 1))
        if current_attempt >= max_attempts:
            return

        all_subtasks = await self._subtask_repository.list_for_run(run.id)
        subtask_map = {item.id: item for item in all_subtasks}
        target = self._find_rework_target(subtask, subtask_map)
        if target is None:
            return

        attempt = current_attempt + 1
        repair_subtask = SubTask(
            id=str(uuid.uuid4()),
            task_id=task.id,
            name=f"repair-{target.name}-attempt-{attempt}",
            description=f"Repair issues identified during review for {target.name}.",
            role=target.role,
            acceptance_criteria=target.acceptance_criteria,
            expected_artifacts=list(target.expected_artifacts),
            execution_configuration=self._clone_execution_configuration(
                target.execution_configuration,
                task=task,
                role=target.role,
            ),
            dependencies=[subtask.id],
            metadata={
                "run_id": run.id,
                "plan_source": "rework",
                "repair_attempt": attempt,
                "rework_source_subtask_id": subtask.id,
                "repair_target_subtask_id": target.id,
            },
        )
        verify_subtask = SubTask(
            id=str(uuid.uuid4()),
            task_id=task.id,
            name=f"verify-repair-{target.name}-attempt-{attempt}",
            description=f"Verify the repair result for {target.name}.",
            role=AgentRole.TESTER,
            acceptance_criteria=["Repair evidence is attached and satisfies the review feedback."],
            expected_artifacts=["verification_report"],
            execution_configuration=ExecutionConfiguration(
                runtime_kind=RuntimeKind.HOST_TOOLS,
                tool_requirements=[ToolGroup.ARTIFACT, ToolGroup.MEMORY],
                skill_profiles=[],
            ),
            dependencies=[repair_subtask.id],
            metadata={
                "run_id": run.id,
                "plan_source": "rework",
                "repair_attempt": attempt,
                "rework_source_subtask_id": subtask.id,
                "repair_source_subtask_id": target.id,
            },
        )
        review_subtask = SubTask(
            id=str(uuid.uuid4()),
            task_id=task.id,
            name=f"review-repair-{target.name}-attempt-{attempt}",
            description=f"Review the repaired result for {target.name}.",
            role=AgentRole.REVIEWER,
            acceptance_criteria=["A final accept or escalate decision is recorded."],
            expected_artifacts=["review_decision"],
            execution_configuration=ExecutionConfiguration(
                runtime_kind=RuntimeKind.HOST_TOOLS,
                tool_requirements=[ToolGroup.ARTIFACT, ToolGroup.MEMORY],
                skill_profiles=[],
            ),
            dependencies=[verify_subtask.id],
            metadata={
                "run_id": run.id,
                "plan_source": "rework",
                "repair_attempt": attempt,
                "rework_source_subtask_id": subtask.id,
            },
        )

        subtask.metadata["rework_generated"] = True
        subtask.metadata["rework_generated_at"] = event.event_id
        await self._subtask_repository.save(subtask)
        await self._subtask_repository.create_many([repair_subtask, verify_subtask, review_subtask])

        run.attach_subtasks([*run.subtask_ids, repair_subtask.id, verify_subtask.id, review_subtask.id])
        await self._run_repository.save(run)

        await self._event_bus.publish(
            DomainEvent(
                event_id=str(uuid.uuid4()),
                topic="subtask.rework_requested",
                tenant_id=event.tenant_id,
                session_id=event.session_id,
                task_id=task.id,
                run_id=run.id,
                subtask_id=subtask.id,
                payload={
                    "repair_attempt": attempt,
                    "target_subtask_id": target.id,
                    "generated_subtask_ids": [repair_subtask.id, verify_subtask.id, review_subtask.id],
                },
            )
        )

    async def _maybe_generate_failure_repair_chain(self, task, run, subtask: SubTask, event: DomainEvent) -> None:
        if not task.constraints.get("enable_failure_repair"):
            return
        if subtask.role not in {
            AgentRole.CODER,
            AgentRole.WRITER,
            AgentRole.RESEARCHER,
            AgentRole.PLANNER,
        }:
            return
        if subtask.metadata.get("repair_generated"):
            return

        attempt = int(subtask.metadata.get("repair_attempt") or 0) + 1
        max_attempts = int(task.constraints.get("max_repair_attempts", 1))
        if attempt > max_attempts:
            return

        repair_subtask = SubTask(
            id=str(uuid.uuid4()),
            task_id=task.id,
            name=f"repair-{subtask.name}-failure-attempt-{attempt}",
            description=f"Retry and repair failed subtask {subtask.name} using failure evidence.",
            role=subtask.role,
            acceptance_criteria=subtask.acceptance_criteria,
            expected_artifacts=list(subtask.expected_artifacts),
            execution_configuration=self._clone_execution_configuration(
                subtask.execution_configuration,
                task=task,
                role=subtask.role,
            ),
            dependencies=list(subtask.dependencies),
            metadata={
                "run_id": run.id,
                "plan_source": "repair_failure",
                "repair_attempt": attempt,
                "repair_source_subtask_id": subtask.id,
                "failure_reason": subtask.error,
            },
        )
        verify_subtask = SubTask(
            id=str(uuid.uuid4()),
            task_id=task.id,
            name=f"verify-repair-{subtask.name}-failure-attempt-{attempt}",
            description=f"Verify the repaired execution result for failed subtask {subtask.name}.",
            role=AgentRole.TESTER,
            acceptance_criteria=["Failure repair evidence is attached to the run."],
            expected_artifacts=["verification_report"],
            execution_configuration=ExecutionConfiguration(
                runtime_kind=RuntimeKind.HOST_TOOLS,
                tool_requirements=[ToolGroup.ARTIFACT, ToolGroup.MEMORY],
                skill_profiles=[],
            ),
            dependencies=[repair_subtask.id],
            metadata={
                "run_id": run.id,
                "plan_source": "repair_failure",
                "repair_attempt": attempt,
                "repair_source_subtask_id": subtask.id,
            },
        )
        review_subtask = SubTask(
            id=str(uuid.uuid4()),
            task_id=task.id,
            name=f"review-repair-{subtask.name}-failure-attempt-{attempt}",
            description=f"Review the failure repair result for {subtask.name}.",
            role=AgentRole.REVIEWER,
            acceptance_criteria=["A final review decision is recorded for the failure repair."],
            expected_artifacts=["review_decision"],
            execution_configuration=ExecutionConfiguration(
                runtime_kind=RuntimeKind.HOST_TOOLS,
                tool_requirements=[ToolGroup.ARTIFACT, ToolGroup.MEMORY],
                skill_profiles=[],
            ),
            dependencies=[verify_subtask.id],
            metadata={
                "run_id": run.id,
                "plan_source": "repair_failure",
                "repair_attempt": attempt,
                "repair_source_subtask_id": subtask.id,
            },
        )

        subtask.metadata["repair_generated"] = True
        subtask.metadata["repair_generated_at"] = event.event_id
        await self._subtask_repository.save(subtask)
        await self._cancel_descendant_subtasks(run.id, subtask.id, preserve_ids={repair_subtask.id, verify_subtask.id, review_subtask.id})
        await self._subtask_repository.create_many([repair_subtask, verify_subtask, review_subtask])

        run.attach_subtasks([*run.subtask_ids, repair_subtask.id, verify_subtask.id, review_subtask.id])
        await self._run_repository.save(run)

        await self._event_bus.publish(
            DomainEvent(
                event_id=str(uuid.uuid4()),
                topic="subtask.repair_requested",
                tenant_id=event.tenant_id,
                session_id=event.session_id,
                task_id=task.id,
                run_id=run.id,
                subtask_id=subtask.id,
                payload={
                    "repair_attempt": attempt,
                    "generated_subtask_ids": [repair_subtask.id, verify_subtask.id, review_subtask.id],
                },
            )
        )

    async def _cancel_descendant_subtasks(self, run_id: str, source_subtask_id: str, preserve_ids: set[str]) -> None:
        subtasks = await self._subtask_repository.list_for_run(run_id)
        descendants = self._collect_descendant_subtask_ids(subtasks, source_subtask_id)
        for candidate in subtasks:
            if candidate.id not in descendants or candidate.id in preserve_ids:
                continue
            if candidate.status in {SubTaskStatus.SUCCEEDED, SubTaskStatus.FAILED, SubTaskStatus.CANCELLED}:
                continue
            candidate.status = SubTaskStatus.CANCELLED
            candidate.metadata["cancelled_reason"] = f"Superseded by repair chain for {source_subtask_id}"
            candidate.metadata["cancelled_at"] = utc_now().isoformat()
            await self._subtask_repository.save(candidate)

    @staticmethod
    def _collect_descendant_subtask_ids(subtasks: list[SubTask], source_subtask_id: str) -> set[str]:
        descendants: set[str] = set()
        pending = [source_subtask_id]
        while pending:
            current_id = pending.pop(0)
            for candidate in subtasks:
                if current_id not in candidate.dependencies or candidate.id in descendants:
                    continue
                descendants.add(candidate.id)
                pending.append(candidate.id)
        return descendants

    @staticmethod
    def _find_rework_target(subtask: SubTask, subtask_map: dict[str, SubTask]) -> SubTask | None:
        pending_ids = list(subtask.dependencies)
        visited: set[str] = set()
        while pending_ids:
            dependency_id = pending_ids.pop(0)
            if dependency_id in visited:
                continue
            visited.add(dependency_id)
            dependency = subtask_map.get(dependency_id)
            if dependency is None:
                continue
            if dependency.role in {
                AgentRole.CODER,
                AgentRole.WRITER,
                AgentRole.RESEARCHER,
            }:
                return dependency
            pending_ids.extend(dependency.dependencies)
        return None

    @staticmethod
    def _clone_execution_configuration(
        execution_configuration: ExecutionConfiguration | None,
        *,
        task,
        role: AgentRole,
    ) -> ExecutionConfiguration:
        if execution_configuration is not None:
            return execution_configuration.model_copy(deep=True)
        tool_requirements = [ToolGroup.WORKSPACE]
        runtime_kind = RuntimeKind.HOST_TOOLS
        if role in {AgentRole.CODER, AgentRole.TESTER}:
            tool_requirements = [ToolGroup.WORKSPACE, ToolGroup.CODE_EXEC]
            runtime_kind = RuntimeKind.SANDBOX
        return ExecutionConfiguration(
            runtime_kind=runtime_kind,
            tool_requirements=tool_requirements,
            sandbox_profile=(str(task.metadata.get("profile", "py-basic")) if runtime_kind == RuntimeKind.SANDBOX else None),
        )

