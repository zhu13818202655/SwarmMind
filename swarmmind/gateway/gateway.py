"""Gateway for request normalization, admission, and task submission."""

from __future__ import annotations

import uuid
from typing import Any

from swarmmind.events import InMemoryEventBus
from swarmmind.gateway.admission import AdmissionController
from swarmmind.gateway.dispatcher import GatewayDispatcher
from swarmmind.gateway.envelopes import TaskDetail, TaskSubmitRequest, TaskSubmissionResult
from swarmmind.gateway.request_normalizer import RequestNormalizer
from swarmmind.gateway.session_manager import GatewaySessionManager
from swarmmind.identity import AuthorizationPolicy, IdentityContext, StaticIdentityResolver
from swarmmind.memory.transcript import Transcript
from swarmmind.models.event import DomainEvent
from swarmmind.models.replay import ReplayRoot
from swarmmind.models.run import Run
from swarmmind.models.task import Task, TaskRequest, TaskStatus
from swarmmind.query import QueryService
from swarmmind.repositories import (
    InMemoryArtifactRepository,
    InMemoryReplayRepository,
    InMemoryRunRepository,
    InMemorySessionRepository,
    InMemorySubTaskRepository,
    InMemoryTaskRepository,
)


class Gateway:
    """Gateway service used by API, CLI, and scripts."""

    def __init__(
        self,
        task_repository: InMemoryTaskRepository | None = None,
        session_repository: InMemorySessionRepository | None = None,
        run_repository: InMemoryRunRepository | None = None,
        subtask_repository: InMemorySubTaskRepository | None = None,
        artifact_repository: InMemoryArtifactRepository | None = None,
        replay_repository: InMemoryReplayRepository | None = None,
        event_bus: InMemoryEventBus | None = None,
        identity_resolver: StaticIdentityResolver | None = None,
        authorization_policy: AuthorizationPolicy | None = None,
        query_service: QueryService | None = None,
    ):
        self._task_repository = task_repository or InMemoryTaskRepository()
        self._session_repository = session_repository or InMemorySessionRepository()
        self._run_repository = run_repository or InMemoryRunRepository()
        self._subtask_repository = subtask_repository or InMemorySubTaskRepository()
        self._artifact_repository = artifact_repository or InMemoryArtifactRepository()
        self._replay_repository = replay_repository or InMemoryReplayRepository()
        self._event_bus = event_bus or InMemoryEventBus()
        self._identity_resolver = identity_resolver or StaticIdentityResolver()
        self._authorization_policy = authorization_policy or AuthorizationPolicy()
        self._query_service = query_service or QueryService(
            task_repository=self._task_repository,
            session_repository=self._session_repository,
            run_repository=self._run_repository,
            subtask_repository=self._subtask_repository,
            artifact_repository=self._artifact_repository,
            authorization_policy=self._authorization_policy,
        )
        self._normalizer = RequestNormalizer()
        self._admission = AdmissionController()
        self._session_manager = GatewaySessionManager(self._session_repository)
        self._dispatcher = GatewayDispatcher(self._event_bus)
        self._compat_sessions: dict[str, dict[str, Any]] = {}

    async def submit_task(
        self,
        request: TaskSubmitRequest,
        identity: IdentityContext,
    ) -> TaskSubmissionResult:
        """Submit a new task into the orchestration pipeline."""
        self._authorization_policy.ensure_can_submit_task(identity)
        self._admission.validate(request, identity)

        normalized_request = self._normalizer.normalize(request)
        session = await self._session_manager.get_or_create(request.session_id, identity)

        task = Task(
            id=str(uuid.uuid4()),
            goal=normalized_request.goal,
            constraints=normalized_request.constraints,
            priority=normalized_request.priority,
            metadata={
                **normalized_request.metadata,
                "tenant_id": identity.tenant_id,
                "principal_id": identity.principal_id,
                "session_id": session.id,
                "profile": normalized_request.profile,
                "preferred_skill": normalized_request.preferred_skill,
            },
        )
        await self._task_repository.create(task)

        session.attach_task(task.id)
        await self._session_repository.save(session)

        run = Run(id=str(uuid.uuid4()), task_id=task.id, session_id=session.id)
        await self._run_repository.create(run)
        await self._replay_repository.create(
            ReplayRoot(id=str(uuid.uuid4()), task_id=task.id, run_id=run.id)
        )

        await self._dispatcher.dispatch(
            DomainEvent(
                event_id=str(uuid.uuid4()),
                topic="run.created",
                tenant_id=identity.tenant_id,
                session_id=session.id,
                task_id=task.id,
                run_id=run.id,
            )
        )
        await self._dispatcher.dispatch(
            DomainEvent(
                event_id=str(uuid.uuid4()),
                topic="task.created",
                tenant_id=identity.tenant_id,
                session_id=session.id,
                task_id=task.id,
                run_id=run.id,
                payload={"goal": task.goal},
            )
        )

        return TaskSubmissionResult(
            task_id=task.id,
            session_id=session.id,
            run_id=run.id,
            status=task.status,
        )

    async def create_task(self, request: TaskRequest) -> Task:
        """Backward-compatible wrapper around the new submit flow."""
        identity = await self._identity_resolver.resolve()
        result = await self.submit_task(
            TaskSubmitRequest(
                goal=request.goal,
                constraints=request.constraints,
                priority=request.priority,
                profile=request.profile,
                preferred_skill=request.preferred_skill,
                metadata=request.metadata,
            ),
            identity=identity,
        )
        task = await self._task_repository.get(result.task_id)
        if task is None:
            raise RuntimeError("task was created but could not be loaded")
        return task

    async def get_task(self, task_id: str) -> Task | None:
        """Get a task by identifier."""
        return await self._task_repository.get(task_id)

    async def update_task(self, task: Task) -> None:
        """Persist a task mutation."""
        await self._task_repository.save(task)

    async def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        """List tasks by status."""
        return await self._task_repository.list_by_status(status)

    async def get_task_detail(self, task_id: str, identity: IdentityContext) -> TaskDetail | None:
        """Return an aggregated task view."""
        return await self._query_service.get_task_detail(task_id, identity)

    def create_session(self, task_id: str) -> dict[str, Any]:
        """Backward-compatible transcript session helper."""
        session = {
            "task_id": task_id,
            "transcript": Transcript(task_id),
            "context": {},
        }
        self._compat_sessions[task_id] = session
        return session

    def get_session(self, task_id: str) -> dict[str, Any] | None:
        """Return the compatibility transcript session."""
        return self._compat_sessions.get(task_id)

    async def close_session(self, task_id: str) -> None:
        """Close the compatibility transcript session."""
        self._compat_sessions.pop(task_id, None)

