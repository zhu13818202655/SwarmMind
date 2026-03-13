"""Application container for first-round bootstrap."""

from dataclasses import dataclass

from swarmmind.events import InMemoryEventBus
from swarmmind.gateway.gateway import Gateway
from swarmmind.identity import AuthorizationPolicy, StaticIdentityResolver
from swarmmind.orchestration import Coordinator, Planner, Scheduler, TaskOrchestrator
from swarmmind.query import QueryService
from swarmmind.repositories import (
    InMemoryArtifactRepository,
    InMemoryReplayRepository,
    InMemoryRunRepository,
    InMemorySessionRepository,
    InMemorySubTaskRepository,
    InMemoryTaskRepository,
)


@dataclass(slots=True)
class AppContainer:
    """Shared application services."""

    event_bus: InMemoryEventBus
    identity_resolver: StaticIdentityResolver
    authorization_policy: AuthorizationPolicy
    task_repository: InMemoryTaskRepository
    session_repository: InMemorySessionRepository
    run_repository: InMemoryRunRepository
    subtask_repository: InMemorySubTaskRepository
    artifact_repository: InMemoryArtifactRepository
    replay_repository: InMemoryReplayRepository
    gateway: Gateway
    orchestrator: TaskOrchestrator
    query_service: QueryService


async def build_container() -> AppContainer:
    """Construct the default in-memory container."""
    event_bus = InMemoryEventBus()
    identity_resolver = StaticIdentityResolver()
    authorization_policy = AuthorizationPolicy()

    task_repository = InMemoryTaskRepository()
    session_repository = InMemorySessionRepository()
    run_repository = InMemoryRunRepository()
    subtask_repository = InMemorySubTaskRepository()
    artifact_repository = InMemoryArtifactRepository()
    replay_repository = InMemoryReplayRepository()

    planner = Planner()
    coordinator = Coordinator()
    scheduler = Scheduler()

    orchestrator = TaskOrchestrator(
        task_repository=task_repository,
        run_repository=run_repository,
        subtask_repository=subtask_repository,
        event_bus=event_bus,
        planner=planner,
        coordinator=coordinator,
        scheduler=scheduler,
    )

    query_service = QueryService(
        task_repository=task_repository,
        session_repository=session_repository,
        run_repository=run_repository,
        subtask_repository=subtask_repository,
        artifact_repository=artifact_repository,
        authorization_policy=authorization_policy,
    )

    gateway = Gateway(
        task_repository=task_repository,
        session_repository=session_repository,
        run_repository=run_repository,
        subtask_repository=subtask_repository,
        artifact_repository=artifact_repository,
        replay_repository=replay_repository,
        event_bus=event_bus,
        identity_resolver=identity_resolver,
        authorization_policy=authorization_policy,
        query_service=query_service,
    )

    await event_bus.subscribe("task.created", orchestrator.handle_task_created)

    return AppContainer(
        event_bus=event_bus,
        identity_resolver=identity_resolver,
        authorization_policy=authorization_policy,
        task_repository=task_repository,
        session_repository=session_repository,
        run_repository=run_repository,
        subtask_repository=subtask_repository,
        artifact_repository=artifact_repository,
        replay_repository=replay_repository,
        gateway=gateway,
        orchestrator=orchestrator,
        query_service=query_service,
    )
