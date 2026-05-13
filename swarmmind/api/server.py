"""FastAPI server for SwarmMind."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import Response, StreamingResponse

from swarmmind.app import get_container
from swarmmind.config import SwarmMindConfig, get_settings
from swarmmind.defaults import DEFAULT_SANDBOX_PROFILE
from swarmmind.domains.fly_report.data_fetcher import DataFetcher
from swarmmind.domains.fly_report.intent.parser import IntentParser
from swarmmind.gateway import RunDetail, TaskDetail, TaskSubmitRequest
from swarmmind.models.run import RunPhase, RunStatus
from swarmmind.models.task import TaskPriority, TaskStatus


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager."""
    app.state.container = await get_container(app.state.settings)
    # Apply Alembic migrations once per process when PG is enabled. The
    # container itself runs the same upgrade for the core tables, so this
    # call is a no-op on subsequent invocations (Alembic compares revision
    # state in ``alembic_version``).
    if getattr(app.state, "fly_report_repo_init_required", False):
        try:
            from swarmmind.repositories.migrations import upgrade_head

            await upgrade_head(app.state.settings.postgres.dsn)
        except Exception:  # pragma: no cover - log + continue
            import logging

            logging.getLogger(__name__).exception(
                "fly_report.repo_init_failed"
            )
    yield


class TaskCreateRequest(BaseModel):
    """HTTP request model for creating a task."""

    model_config = ConfigDict(populate_by_name=True)

    goal: str = Field(..., description="Task goal description")
    constraints: dict[str, Any] = Field(default_factory=dict)
    priority: TaskPriority = Field(default=TaskPriority.NORMAL)
    profile: str = Field(default=DEFAULT_SANDBOX_PROFILE)
    agent_profile_id: str | None = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskStatusResponse(BaseModel):
    """Compact task status response."""

    task_id: str
    session_id: str | None = None
    run_id: str | None = None
    status: TaskStatus
    goal: str
    created_at: str
    result: dict[str, Any] | None = None
    error: str | None = None


class RunStatusResponse(BaseModel):
    """Compact run status response."""

    run_id: str
    task_id: str
    session_id: str
    status: RunStatus
    phase: RunPhase
    subtask_count: int = 0
    artifact_count: int = 0
    error: str | None = None


class RunDetailResponse(BaseModel):
    """Full run detail response."""

    run: dict[str, Any]
    subtasks: list[dict[str, Any]]
    artifacts: list[dict[str, Any]]


class TaskDetailResponse(BaseModel):
    """Full task detail response."""

    task: dict[str, Any]
    session: dict[str, Any] | None = None
    runs: list[RunDetailResponse] = Field(default_factory=list)


class RunEventResponse(BaseModel):
    """Single run replay event item."""

    cursor: int
    event_type: str
    timestamp: str
    payload: dict[str, Any] = Field(default_factory=dict)


class RunEventsResponse(BaseModel):
    """Paged run replay events."""

    run_id: str
    next_cursor: int
    events: list[RunEventResponse] = Field(default_factory=list)


class SubTaskEventsResponse(BaseModel):
    """Paged replay events for a single subtask."""

    run_id: str
    subtask_id: str
    next_cursor: int
    events: list[RunEventResponse] = Field(default_factory=list)


class ArtifactResponse(BaseModel):
    """Serialized artifact item."""

    artifact: dict[str, Any]


class SubTaskArtifactsResponse(BaseModel):
    """Artifacts associated with a single subtask."""

    run_id: str
    subtask_id: str
    artifacts: list[dict[str, Any]] = Field(default_factory=list)


async def resolve_identity(request: Request):
    """Resolve the current identity context from the container."""
    container = request.app.state.container
    return await container.identity_resolver.resolve()


def to_task_status_response(task, session_id: str | None = None, run_id: str | None = None) -> TaskStatusResponse:
    """Serialize a task summary response."""
    return TaskStatusResponse(
        task_id=task.id,
        session_id=session_id,
        run_id=run_id,
        status=task.status,
        goal=task.goal,
        created_at=task.created_at.isoformat(),
        result=task.result,
        error=task.error,
    )


def to_run_status_response(run_detail: RunDetail) -> RunStatusResponse:
    """Serialize a run summary response."""
    return RunStatusResponse(
        run_id=run_detail.run.id,
        task_id=run_detail.run.task_id,
        session_id=run_detail.run.session_id,
        status=run_detail.run.status,
        phase=run_detail.run.phase,
        subtask_count=len(run_detail.subtasks),
        artifact_count=len(run_detail.artifacts),
        error=run_detail.run.error,
    )


def to_run_detail_response(run_detail: RunDetail) -> RunDetailResponse:
    """Serialize a full run detail response."""
    return RunDetailResponse(
        run=run_detail.run.model_dump(mode="json"),
        subtasks=[subtask.model_dump(mode="json") for subtask in run_detail.subtasks],
        artifacts=[to_artifact_response_payload(artifact) for artifact in run_detail.artifacts],
    )


def to_task_detail_response(task_detail: TaskDetail) -> TaskDetailResponse:
    """Serialize a full task detail response."""
    return TaskDetailResponse(
        task=task_detail.task.model_dump(mode="json"),
        session=task_detail.session.model_dump(mode="json") if task_detail.session else None,
        runs=[to_run_detail_response(run_detail) for run_detail in task_detail.runs],
    )


def to_artifact_response_payload(artifact) -> dict[str, Any]:
    """Serialize a single artifact with download metadata when available."""
    payload = artifact.model_dump(mode="json")
    if artifact.type.value == "file":
        payload["download_url"] = f"/v1/runs/{artifact.run_id}/artifacts/{artifact.id}/content"
    return payload


def build_run_events_response(
    run_id: str,
    replay,
    cursor: int,
    limit: int,
    *,
    topic: str | None = None,
    tool_name: str | None = None,
) -> RunEventsResponse:
    """Build a paged replay response from a replay root."""
    entries = _filter_replay_entries(replay.entries, topic=topic, tool_name=tool_name)
    events, next_cursor = _build_event_page(entries, cursor, limit)

    return RunEventsResponse(
        run_id=run_id,
        next_cursor=next_cursor,
        events=events,
    )


def build_subtask_events_response(
    run_id: str,
    subtask_id: str,
    replay,
    cursor: int,
    limit: int,
    *,
    topic: str | None = None,
    tool_name: str | None = None,
) -> SubTaskEventsResponse:
    """Build a paged replay response filtered to a single subtask."""
    entries = [entry for entry in replay.entries if entry.payload.get("subtask_id") == subtask_id]
    entries = _filter_replay_entries(entries, topic=topic, tool_name=tool_name)
    events, next_cursor = _build_event_page(entries, cursor, limit)

    return SubTaskEventsResponse(
        run_id=run_id,
        subtask_id=subtask_id,
        next_cursor=next_cursor,
        events=events,
    )


def replay_contains_subtask(replay, subtask_id: str) -> bool:
    """Return whether the replay contains at least one event for the subtask."""

    return any(str((entry.payload or {}).get("subtask_id") or "") == subtask_id for entry in replay.entries)


def _filter_replay_entries(entries, *, topic: str | None = None, tool_name: str | None = None):
    """Filter replay entries by event topic and tool name."""
    filtered = entries
    if topic:
        filtered = [entry for entry in filtered if entry.event_type == topic]
    if tool_name:
        filtered = [entry for entry in filtered if str((entry.payload or {}).get("tool_name") or "") == tool_name]
    return filtered


def _build_event_page(entries, cursor: int, limit: int) -> tuple[list[RunEventResponse], int]:
    """Build a paged replay slice from a list of entries."""
    start = max(0, cursor)
    selected_entries = entries[start : start + max(1, limit)]

    events: list[RunEventResponse] = []
    for offset, entry in enumerate(selected_entries):
        events.append(
            RunEventResponse(
                cursor=start + offset,
                event_type=entry.event_type,
                timestamp=entry.timestamp.isoformat(),
                payload=entry.payload,
            )
        )
    return events, start + len(events)


def create_app(settings: SwarmMindConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = settings or get_settings()
    app = FastAPI(
        title=settings.api.title,
        description=settings.api.description,
        version=settings.api.version,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_allow_origins,
        allow_credentials=settings.api.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings

    # FlyReport domain router (DESIGN-2 §13 step 7 + §14.4.1 PG persistence).
    from swarmmind.domains.fly_report.api import create_fly_report_router
    from swarmmind.domains.fly_report.repository import (
        InMemoryFlyReportRepository,
        PostgresFlyReportRepository,
    )
    from swarmmind.domains.fly_report.service import FlyReportService
    from swarmmind.repositories.postgres import PostgresStore

    if settings.postgres.enabled:
        fly_report_repo = PostgresFlyReportRepository(
            PostgresStore(settings.postgres.dsn)
        )
        if settings.postgres.auto_init_schema:
            app.state.fly_report_repo_init_required = True
        else:
            app.state.fly_report_repo_init_required = False
    else:
        fly_report_repo = InMemoryFlyReportRepository()
        app.state.fly_report_repo_init_required = False

    app.state.fly_report_repo = fly_report_repo
    # Best-effort event bus for fly_report.* topics (DESIGN-3 §2.8 R8.1).
    try:
        from swarmmind.events.in_memory_bus import InMemoryEventBus

        fly_report_event_bus = InMemoryEventBus()
    except Exception:  # pragma: no cover - optional dep
        fly_report_event_bus = None
    app.state.fly_report_event_bus = fly_report_event_bus

    # Intent parser selection (DESIGN-3 R1.1). ``llm`` falls back to ``rule``
    # on build failure so offline / first-run deployments stay usable.

    from swarmmind.domains.fly_report.agents.factory import build_intent_agent
    from swarmmind.domains.fly_report.dikong.client import DikongClient

    intent_parser = IntentParser(build_intent_agent(settings.agent.model))
    dikong_client = DikongClient(settings.fly_report.dikong)
    data_fetcher = DataFetcher(dikong_client)
    app.state.fly_report_service = FlyReportService(
        repository=fly_report_repo,
        event_bus=fly_report_event_bus,
        intent_parser=intent_parser,
        data_fetcher=data_fetcher,
    )
    app.include_router(
        create_fly_report_router(app.state.fly_report_service)
    )

    # Static mount for Text-to-SQL auto-generated charts. The Text-to-SQL
    # pipeline drops PNGs into ``CHART_OUTPUT_ROOT`` and embeds
    # ``![chart](/v1/fly-reports/charts/<file>.png)`` markdown in the
    # assistant reply; clients fetch the image straight from this mount.
    from fastapi.staticfiles import StaticFiles

    from swarmmind.domains.fly_report.text2sql.chart import (
        CHART_OUTPUT_ROOT,
        CHART_URL_PREFIX,
    )

    CHART_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    app.mount(
        CHART_URL_PREFIX,
        StaticFiles(directory=str(CHART_OUTPUT_ROOT)),
        name="fly-report-charts",
    )

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "name": settings.api.title,
            "version": settings.api.version,
            "status": "running",
        }

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "healthy"}

    @app.post("/v1/tasks", response_model=TaskStatusResponse)
    async def create_task(request: TaskCreateRequest, raw_request: Request):
        """Create a new task."""
        container = raw_request.app.state.container
        identity = await resolve_identity(raw_request)

        submission = await container.gateway.submit_task(
            TaskSubmitRequest(
                goal=request.goal,
                constraints=request.constraints,
                priority=request.priority,
                profile=request.profile,
                agent_profile_id=request.agent_profile_id,
                metadata=request.metadata,
            ),
            identity=identity,
        )

        task = await container.gateway.get_task(submission.task_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Task was submitted but could not be loaded",
            )

        return to_task_status_response(task, session_id=submission.session_id, run_id=submission.run_id)

    @app.get("/v1/tasks", response_model=list[TaskStatusResponse])
    async def list_tasks(raw_request: Request, status: TaskStatus | None = None):
        """List all tasks."""
        container = raw_request.app.state.container
        identity = await resolve_identity(raw_request)
        tasks = await container.gateway.list_tasks(status)

        responses: list[TaskStatusResponse] = []
        for task in tasks:
            task_detail = await container.query_service.get_task_detail(task.id, identity)
            latest_run_id = None
            if task_detail and task_detail.runs:
                latest_run_id = task_detail.runs[-1].run.id
            responses.append(
                to_task_status_response(
                    task,
                    session_id=task.metadata.get("session_id"),
                    run_id=latest_run_id,
                )
            )
        return responses

    @app.get("/v1/tasks/{task_id}", response_model=TaskStatusResponse)
    async def get_task(task_id: str, raw_request: Request):
        """Get a task by ID."""
        container = raw_request.app.state.container
        identity = await resolve_identity(raw_request)
        task = await container.gateway.get_task(task_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {task_id}",
            )

        task_detail = await container.query_service.get_task_detail(task_id, identity)
        latest_run_id = None
        if task_detail and task_detail.runs:
            latest_run_id = task_detail.runs[-1].run.id

        return to_task_status_response(
            task,
            session_id=task.metadata.get("session_id"),
            run_id=latest_run_id,
        )

    @app.get("/v1/tasks/{task_id}/detail", response_model=TaskDetailResponse)
    async def get_task_detail(task_id: str, raw_request: Request):
        """Get the aggregated task detail."""
        container = raw_request.app.state.container
        identity = await resolve_identity(raw_request)
        task_detail = await container.query_service.get_task_detail(task_id, identity)
        if task_detail is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {task_id}",
            )
        return to_task_detail_response(task_detail)

    @app.get("/v1/runs/{run_id}", response_model=RunDetailResponse)
    async def get_run_detail(run_id: str, raw_request: Request):
        """Get the aggregated run detail."""
        container = raw_request.app.state.container
        identity = await resolve_identity(raw_request)
        run_detail = await container.query_service.get_run_detail(run_id, identity)
        if run_detail is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run not found: {run_id}",
            )
        return to_run_detail_response(run_detail)

    @app.get("/v1/runs/{run_id}/status", response_model=RunStatusResponse)
    async def get_run_status(run_id: str, raw_request: Request):
        """Get a compact run status view."""
        container = raw_request.app.state.container
        identity = await resolve_identity(raw_request)
        run_detail = await container.query_service.get_run_detail(run_id, identity)
        if run_detail is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run not found: {run_id}",
            )
        return to_run_status_response(run_detail)

    @app.get("/v1/runs/{run_id}/events", response_model=RunEventsResponse)
    async def get_run_events(
        run_id: str,
        raw_request: Request,
        cursor: int = 0,
        limit: int = 100,
        topic: str | None = None,
        tool_name: str | None = None,
    ):
        """Get paged replay events for a run."""
        container = raw_request.app.state.container
        identity = await resolve_identity(raw_request)
        container.authorization_policy.ensure_can_read_run(identity)

        replay = await container.replay_repository.get_by_run(run_id)
        if replay is None:
            run_detail = await container.query_service.get_run_detail(run_id, identity)
            if run_detail is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Run not found: {run_id}",
                )
            return RunEventsResponse(run_id=run_id, next_cursor=max(0, cursor), events=[])

        return build_run_events_response(run_id, replay, cursor, limit, topic=topic, tool_name=tool_name)

    @app.get("/v1/runs/{run_id}/subtasks/{subtask_id}/events", response_model=SubTaskEventsResponse)
    async def get_subtask_events(
        run_id: str,
        subtask_id: str,
        raw_request: Request,
        cursor: int = 0,
        limit: int = 100,
        topic: str | None = None,
        tool_name: str | None = None,
    ):
        """Get paged replay events for a single subtask within a run."""
        container = raw_request.app.state.container
        identity = await resolve_identity(raw_request)
        container.authorization_policy.ensure_can_read_run(identity)

        replay = await container.replay_repository.get_by_run(run_id)
        if replay is None:
            run_detail = await container.query_service.get_run_detail(run_id, identity)
            if run_detail is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Run not found: {run_id}",
                )
            return SubTaskEventsResponse(run_id=run_id, subtask_id=subtask_id, next_cursor=max(0, cursor), events=[])

        if not replay_contains_subtask(replay, subtask_id):
            subtask = await container.subtask_repository.get(subtask_id)
            if subtask is None or subtask.metadata.get("run_id") != run_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Subtask not found for run: {subtask_id}",
                )

        return build_subtask_events_response(
            run_id,
            subtask_id,
            replay,
            cursor,
            limit,
            topic=topic,
            tool_name=tool_name,
        )

    @app.get("/v1/runs/{run_id}/subtasks/{subtask_id}/artifacts", response_model=SubTaskArtifactsResponse)
    async def get_subtask_artifacts(run_id: str, subtask_id: str, raw_request: Request):
        """Get artifacts associated with a single subtask within a run."""
        container = raw_request.app.state.container
        identity = await resolve_identity(raw_request)
        container.authorization_policy.ensure_can_read_run(identity)

        artifacts = await container.artifact_repository.list_for_subtask(run_id, subtask_id)
        if not artifacts:
            run_detail = await container.query_service.get_run_detail(run_id, identity)
            if run_detail is None:
                replay = await container.replay_repository.get_by_run(run_id)
                if replay is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Run not found: {run_id}",
                    )
            if run_detail is not None and not any(subtask.id == subtask_id for subtask in run_detail.subtasks):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Subtask not found for run: {subtask_id}",
                )

        return SubTaskArtifactsResponse(
            run_id=run_id,
            subtask_id=subtask_id,
            artifacts=[to_artifact_response_payload(artifact) for artifact in artifacts],
        )

    @app.get("/v1/runs/{run_id}/artifacts/{artifact_id}/content")
    async def download_artifact_content(run_id: str, artifact_id: str, raw_request: Request):
        """Download the raw content for a persisted artifact."""
        container = raw_request.app.state.container
        identity = await resolve_identity(raw_request)
        container.authorization_policy.ensure_can_read_run(identity)

        artifact = await container.artifact_repository.get(artifact_id)
        if artifact is None or artifact.run_id != run_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifact not found for run: {artifact_id}",
            )

        content = await container.artifact_repository.read_content(artifact)
        if content is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifact content is not available: {artifact_id}",
            )

        file_name = artifact.metadata.get("file_name")
        if not isinstance(file_name, str) or not file_name:
            file_name = Path(artifact.name).name or f"artifact-{artifact.id}"

        return Response(
            content=content,
            media_type=artifact.content_type or "application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
        )

    @app.get("/v1/runs/{run_id}/stream")
    async def stream_run_events(
        run_id: str,
        raw_request: Request,
        cursor: int = 0,
        poll_interval: float = 0.5,
    ):
        """Stream run replay events as Server-Sent Events."""
        container = raw_request.app.state.container
        identity = await resolve_identity(raw_request)
        container.authorization_policy.ensure_can_read_run(identity)

        run_detail = await container.query_service.get_run_detail(run_id, identity)
        if run_detail is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run not found: {run_id}",
            )

        async def event_stream():
            next_cursor = max(0, cursor)
            heartbeat_tick = 0

            while True:
                replay = await container.replay_repository.get_by_run(run_id)
                if replay is not None:
                    page = build_run_events_response(run_id, replay, next_cursor, 256)
                    for item in page.events:
                        payload = {
                            "run_id": run_id,
                            "cursor": item.cursor,
                            "event_type": item.event_type,
                            "timestamp": item.timestamp,
                            "payload": item.payload,
                        }
                        yield (
                            f"id: {item.cursor}\n"
                            "event: run.event\n"
                            f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                        )
                    next_cursor = page.next_cursor

                latest = await container.query_service.get_run_detail(run_id, identity)
                if latest is not None and latest.run.status in {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED}:
                    replay = await container.replay_repository.get_by_run(run_id)
                    if replay is not None:
                        page = build_run_events_response(run_id, replay, next_cursor, 256)
                        for item in page.events:
                            payload = {
                                "run_id": run_id,
                                "cursor": item.cursor,
                                "event_type": item.event_type,
                                "timestamp": item.timestamp,
                                "payload": item.payload,
                            }
                            yield (
                                f"id: {item.cursor}\n"
                                "event: run.event\n"
                                f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                            )
                    terminal_payload = {
                        "run_id": run_id,
                        "status": latest.run.status,
                        "phase": latest.run.phase,
                        "subtask_count": len(latest.subtasks),
                        "artifact_count": len(latest.artifacts),
                    }
                    yield (
                        "event: run.terminal\n"
                        f"data: {json.dumps(terminal_payload, ensure_ascii=False)}\n\n"
                    )
                    break

                heartbeat_tick += 1
                if heartbeat_tick % 20 == 0:
                    yield ": keep-alive\n\n"
                await asyncio.sleep(max(0.1, poll_interval))

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.delete("/v1/tasks/{task_id}")
    async def delete_task(task_id: str, raw_request: Request):
        """Delete a task."""
        container = raw_request.app.state.container
        task = await container.gateway.get_task(task_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {task_id}",
            )

        task.status = TaskStatus.CANCELLED
        await container.gateway.update_task(task)
        return {"message": "Task cancelled", "task_id": task_id}

    return app


def run_server(host: str | None = None, port: int | None = None, reload: bool | None = None):
    """Run the API server."""
    import uvicorn

    settings = get_settings()
    app = create_app(settings)
    uvicorn.run(
        app,
        host=host or settings.api.host,
        port=port or settings.api.port,
        reload=settings.api.reload if reload is None else reload,
    )


if __name__ == "__main__":
    run_server()
