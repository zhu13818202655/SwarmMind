"""Query service for first-round task and run inspection."""

from swarmmind.gateway.envelopes import RunDetail, TaskDetail
from swarmmind.identity.models import IdentityContext
from swarmmind.identity.policy import AuthorizationPolicy
from swarmmind.repositories import (
    ArtifactRepository,
    RunRepository,
    SessionRepository,
    SubTaskRepository,
    TaskRepository,
)


class QueryService:
    """Aggregate task and run state for read APIs and scripts."""

    def __init__(
        self,
        task_repository: TaskRepository,
        session_repository: SessionRepository,
        run_repository: RunRepository,
        subtask_repository: SubTaskRepository,
        artifact_repository: ArtifactRepository,
        authorization_policy: AuthorizationPolicy,
    ):
        self._task_repository = task_repository
        self._session_repository = session_repository
        self._run_repository = run_repository
        self._subtask_repository = subtask_repository
        self._artifact_repository = artifact_repository
        self._authorization_policy = authorization_policy

    async def get_task_detail(self, task_id: str, identity: IdentityContext) -> TaskDetail | None:
        """Return an aggregated task view."""
        self._authorization_policy.ensure_can_read_task(identity)

        task = await self._task_repository.get(task_id)
        if task is None:
            return None

        session_id = task.metadata.get("session_id")
        session = await self._session_repository.get(session_id) if session_id else None
        runs = await self._run_repository.list_for_task(task.id)
        run_details = [await self.get_run_detail(run.id, identity) for run in runs]
        return TaskDetail(task=task, session=session, runs=[detail for detail in run_details if detail])

    async def get_run_detail(self, run_id: str, identity: IdentityContext) -> RunDetail | None:
        """Return an aggregated run view."""
        self._authorization_policy.ensure_can_read_run(identity)

        run = await self._run_repository.get(run_id)
        if run is None:
            return None

        subtasks = await self._subtask_repository.list_for_run(run.id)
        artifacts = await self._artifact_repository.list_for_run(run.id)
        return RunDetail(run=run, subtasks=subtasks, artifacts=artifacts)
