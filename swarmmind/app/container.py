"""Application container for first-round bootstrap."""

from swarmmind.cache import CacheStore, InMemoryCacheStore, RedisCacheStore
from swarmmind.agents import AgentProfileStore
from swarmmind.config import SwarmMindConfig, get_settings
from swarmmind.events import EventBus, InMemoryEventBus, RedisBufferedEventBus
from swarmmind.gateway.gateway import Gateway
from swarmmind.identity import AuthorizationPolicy, StaticIdentityResolver
from swarmmind.locks import InMemoryLockManager, LockManager, RedisLockManager
from swarmmind.memory import LongTermMemoryBase, create_long_term_memory
from swarmmind.orchestration import (
    Coordinator,
    ExecutionRunner,
    Planner,
    RunStateService,
    Scheduler,
    TaskOrchestrator,
)
from swarmmind.query import QueryService
from swarmmind.repositories import (
    ArtifactRepository,
    InMemoryArtifactRepository,
    InMemoryReplayRepository,
    InMemoryRunRepository,
    InMemorySessionRepository,
    InMemorySubTaskRepository,
    InMemoryTaskRepository,
    PostgresArtifactRepository,
    PostgresReplayRepository,
    PostgresRunRepository,
    PostgresSessionRepository,
    PostgresStore,
    PostgresSubTaskRepository,
    PostgresTaskRepository,
    ReplayRepository,
    RunRepository,
    SessionRepository,
    SubTaskRepository,
    TaskRepository,
)
from swarmmind.execution_strategies import ExecutionStrategyRegistry
from swarmmind.skill_system import SkillExecutionService, SkillScriptExecutor
from swarmmind.sandbox import ArtifactCollector, LocalSandboxAdapter, ReplayRecorder, SandboxManager
from swarmmind.sandbox.opensandbox_adapter import OpenSandboxAdapter
from swarmmind.tools import ToolRegistry


class AppContainer:
    """Shared application services."""

    settings: SwarmMindConfig
    event_bus: EventBus
    cache_store: CacheStore
    lock_manager: LockManager
    agent_profile_store: AgentProfileStore
    long_term_memory: LongTermMemoryBase
    identity_resolver: StaticIdentityResolver
    authorization_policy: AuthorizationPolicy
    task_repository: TaskRepository
    session_repository: SessionRepository
    run_repository: RunRepository
    subtask_repository: SubTaskRepository
    artifact_repository: ArtifactRepository
    replay_repository: ReplayRepository
    sandbox_manager: SandboxManager
    artifact_collector: ArtifactCollector
    replay_recorder: ReplayRecorder
    skill_execution_service: SkillExecutionService
    run_state_service: RunStateService
    execution_runner: ExecutionRunner
    execution_strategy_registry: ExecutionStrategyRegistry
    tool_registry: ToolRegistry
    gateway: Gateway
    orchestrator: TaskOrchestrator
    query_service: QueryService

    __slots__ = (
        "settings",
        "event_bus",
        "cache_store",
        "lock_manager",
        "agent_profile_store",
        "long_term_memory",
        "identity_resolver",
        "authorization_policy",
        "task_repository",
        "session_repository",
        "run_repository",
        "subtask_repository",
        "artifact_repository",
        "replay_repository",
        "sandbox_manager",
        "artifact_collector",
        "replay_recorder",
        "skill_execution_service",
        "run_state_service",
        "execution_runner",
        "execution_strategy_registry",
        "tool_registry",
        "gateway",
        "orchestrator",
        "query_service",
    )

    def __init__(
        self,
        settings: SwarmMindConfig,
        event_bus: EventBus,
        cache_store: CacheStore,
        lock_manager: LockManager,
        agent_profile_store: AgentProfileStore,
        long_term_memory: LongTermMemoryBase,
        identity_resolver: StaticIdentityResolver,
        authorization_policy: AuthorizationPolicy,
        task_repository: TaskRepository,
        session_repository: SessionRepository,
        run_repository: RunRepository,
        subtask_repository: SubTaskRepository,
        artifact_repository: ArtifactRepository,
        replay_repository: ReplayRepository,
        sandbox_manager: SandboxManager,
        artifact_collector: ArtifactCollector,
        replay_recorder: ReplayRecorder,
        skill_execution_service: SkillExecutionService,
        run_state_service: RunStateService,
        execution_runner: ExecutionRunner,
        execution_strategy_registry: ExecutionStrategyRegistry,
        tool_registry: ToolRegistry,
        gateway: Gateway,
        orchestrator: TaskOrchestrator,
        query_service: QueryService,
    ) -> None:
        self.settings = settings
        self.event_bus = event_bus
        self.cache_store = cache_store
        self.lock_manager = lock_manager
        self.agent_profile_store = agent_profile_store
        self.long_term_memory = long_term_memory
        self.identity_resolver = identity_resolver
        self.authorization_policy = authorization_policy
        self.task_repository = task_repository
        self.session_repository = session_repository
        self.run_repository = run_repository
        self.subtask_repository = subtask_repository
        self.artifact_repository = artifact_repository
        self.replay_repository = replay_repository
        self.sandbox_manager = sandbox_manager
        self.artifact_collector = artifact_collector
        self.replay_recorder = replay_recorder
        self.skill_execution_service = skill_execution_service
        self.run_state_service = run_state_service
        self.execution_runner = execution_runner
        self.execution_strategy_registry = execution_strategy_registry
        self.tool_registry = tool_registry
        self.gateway = gateway
        self.orchestrator = orchestrator
        self.query_service = query_service


async def build_container(settings: SwarmMindConfig | None = None) -> AppContainer:
    """Construct the application container from configured adapters."""
    settings = settings or get_settings()
    event_bus = _build_event_bus(settings)
    cache_store = _build_cache_store(settings)
    lock_manager = _build_lock_manager(settings)
    agent_profile_store = AgentProfileStore()
    long_term_memory = _build_long_term_memory(settings)
    identity_resolver = StaticIdentityResolver(
        default_tenant_id=settings.identity.default_tenant_id,
        default_principal_id=settings.identity.default_principal_id,
        default_scopes=settings.identity.default_scopes,
        default_roles=settings.identity.default_roles,
        auth_method=settings.identity.auth_method,
    )
    authorization_policy = AuthorizationPolicy()

    (
        task_repository,
        session_repository,
        run_repository,
        subtask_repository,
        artifact_repository,
        replay_repository,
    ) = await _build_repositories(settings)

    sandbox_manager = SandboxManager(_build_sandbox_provider(settings))
    artifact_collector = ArtifactCollector()
    replay_recorder = ReplayRecorder(replay_repository)
    execution_strategy_registry = ExecutionStrategyRegistry()
    tool_registry = ToolRegistry()
    skill_execution_service = SkillExecutionService(
        executor=SkillScriptExecutor(sandbox_manager),
        event_bus=event_bus,
        artifact_repository=artifact_repository,
    )

    planner = Planner(
        model_name=settings.agent.model.name,
        model_api_key=settings.agent.model.api_key,
        model_base_url=settings.agent.model.base_url,
        model_temperature=settings.agent.model.temperature,
        model_max_tokens=settings.agent.model.max_tokens,
        agent_profile_store=agent_profile_store,
        long_term_memory=long_term_memory,
    )
    coordinator = Coordinator(agent_profile_store=agent_profile_store)
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

    run_state_service = RunStateService(
        task_repository=task_repository,
        run_repository=run_repository,
        subtask_repository=subtask_repository,
        artifact_repository=artifact_repository,
        event_bus=event_bus,
    )

    execution_runner = ExecutionRunner(
        task_repository=task_repository,
        run_repository=run_repository,
        subtask_repository=subtask_repository,
        artifact_repository=artifact_repository,
        event_bus=event_bus,
        sandbox_manager=sandbox_manager,
        artifact_collector=artifact_collector,
        run_state_service=run_state_service,
        execution_strategy_registry=execution_strategy_registry,
        tool_registry=tool_registry,
        skill_execution_service=skill_execution_service,
        agent_profile_store=agent_profile_store,
        model_name=settings.agent.model.name,
        model_api_key=settings.agent.model.api_key,
        model_base_url=settings.agent.model.base_url,
        model_temperature=settings.agent.model.temperature,
        model_max_tokens=settings.agent.model.max_tokens,
        long_term_memory=long_term_memory,
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

    # TODO 怎么区分不同的task，多个用户传不同的任务，怎么区分
    await event_bus.subscribe("*", replay_recorder.handle_event)
    await event_bus.subscribe("task.created", orchestrator.handle_task_created)
    await event_bus.subscribe("subtask.completed", orchestrator.handle_subtask_terminal)
    await event_bus.subscribe("subtask.failed", orchestrator.handle_subtask_terminal)
    await event_bus.subscribe("subtask.assigned", execution_runner.handle_subtask_assigned)

    return AppContainer(
        settings=settings,
        event_bus=event_bus,
        cache_store=cache_store,
        lock_manager=lock_manager,
        agent_profile_store=agent_profile_store,
        long_term_memory=long_term_memory,
        identity_resolver=identity_resolver,
        authorization_policy=authorization_policy,
        task_repository=task_repository,
        session_repository=session_repository,
        run_repository=run_repository,
        subtask_repository=subtask_repository,
        artifact_repository=artifact_repository,
        replay_repository=replay_repository,
        sandbox_manager=sandbox_manager,
        artifact_collector=artifact_collector,
        replay_recorder=replay_recorder,
        skill_execution_service=skill_execution_service,
        run_state_service=run_state_service,
        execution_runner=execution_runner,
        execution_strategy_registry=execution_strategy_registry,
        tool_registry=tool_registry,
        gateway=gateway,
        orchestrator=orchestrator,
        query_service=query_service,
    )


def _build_sandbox_provider(settings: SwarmMindConfig):
    """Create the configured sandbox provider with a local fallback."""
    provider_name = settings.sandbox.provider.strip().lower()
    if provider_name == "local":
        return LocalSandboxAdapter()

    if provider_name == "opensandbox" and settings.sandbox.api_key:
        return OpenSandboxAdapter(
            api_key=settings.sandbox.api_key,
            base_url=settings.sandbox.base_url,
            create_retry_count=settings.sandbox.create_retries,
            create_retry_backoff_seconds=settings.sandbox.create_backoff,
            request_timeout_seconds=settings.sandbox.request_timeout_seconds,
        )

    return LocalSandboxAdapter()


async def _build_repositories(
    settings: SwarmMindConfig,
) -> tuple[
    TaskRepository,
    SessionRepository,
    RunRepository,
    SubTaskRepository,
    ArtifactRepository,
    ReplayRepository,
]:
    if settings.postgres.enabled:
        store = PostgresStore(settings.postgres.dsn)
        if settings.postgres.auto_init_schema:
            await store.initialize()
        return (
            PostgresTaskRepository(store),
            PostgresSessionRepository(store),
            PostgresRunRepository(store),
            PostgresSubTaskRepository(store),
            PostgresArtifactRepository(store),
            PostgresReplayRepository(store),
        )

    return (
        InMemoryTaskRepository(),
        InMemorySessionRepository(),
        InMemoryRunRepository(),
        InMemorySubTaskRepository(),
        InMemoryArtifactRepository(),
        InMemoryReplayRepository(),
    )


def _build_event_bus(settings: SwarmMindConfig) -> EventBus:
    if settings.redis.enabled:
        return RedisBufferedEventBus(
            url=settings.redis.url,
            stream_name=settings.redis.event_stream,
            channel_prefix=settings.redis.channel_prefix,
        )
    return InMemoryEventBus()


def _build_cache_store(settings: SwarmMindConfig) -> CacheStore:
    if settings.redis.enabled:
        return RedisCacheStore(settings.redis.url, prefix=settings.redis.cache_prefix)
    return InMemoryCacheStore()


def _build_lock_manager(settings: SwarmMindConfig) -> LockManager:
    if settings.redis.enabled:
        return RedisLockManager(settings.redis.url, prefix=settings.redis.lock_prefix)
    return InMemoryLockManager()


def _build_long_term_memory(settings: SwarmMindConfig) -> LongTermMemoryBase:
    provider = settings.vector_store.provider.strip().lower()
    if settings.vector_store.enabled and provider == "qdrant":
        return create_long_term_memory(
            storage_type="qdrant",
            url=settings.vector_store.qdrant_url,
            collection=settings.vector_store.collection,
            dimensions=settings.vector_store.embedding_dimension,
        )
    if provider == "chroma":
        return create_long_term_memory(storage_type="chroma")
    return create_long_term_memory(storage_type="memory")
