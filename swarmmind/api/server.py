"""FastAPI server for SwarmMind."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field

from swarmmind.app import get_container
from swarmmind.gateway import RunDetail, TaskDetail, TaskSubmitRequest
from swarmmind.models.run import RunPhase, RunStatus
from swarmmind.models.task import TaskPriority, TaskStatus


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager."""
    app.state.container = await get_container()
    yield


class TaskCreateRequest(BaseModel):
    """HTTP request model for creating a task."""

    goal: str = Field(..., description="Task goal description")
    constraints: dict[str, Any] = Field(default_factory=dict)
    priority: TaskPriority = Field(default=TaskPriority.NORMAL)
    profile: str = Field(default="py-basic")
    preferred_skill: str | None = Field(default=None)
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
        artifacts=[artifact.model_dump(mode="json") for artifact in run_detail.artifacts],
    )


def to_task_detail_response(task_detail: TaskDetail) -> TaskDetailResponse:
    """Serialize a full task detail response."""
    return TaskDetailResponse(
        task=task_detail.task.model_dump(mode="json"),
        session=task_detail.session.model_dump(mode="json") if task_detail.session else None,
        runs=[to_run_detail_response(run_detail) for run_detail in task_detail.runs],
    )


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="SwarmMind API",
        description="A general-purpose AI task assistant API",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "name": "SwarmMind API",
            "version": "0.1.0",
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
                preferred_skill=request.preferred_skill,
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


def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Run the API server."""
    import uvicorn
    from swarmmind.api.server import create_app

    app = create_app()
    uvicorn.run(app, host=host, port=port, reload=reload)


if __name__ == "__main__":
    run_server()
