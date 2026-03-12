"""FastAPI server for SwarmMind."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from swarmmind.gateway.gateway import Gateway
from swarmmind.models.task import Task, TaskRequest, TaskResponse, TaskStatus
from swarmmind.models.config import SwarmMindConfig


# Global state
_gateway: Gateway | None = None
_config: SwarmMindConfig | None = None


def get_gateway() -> Gateway:
    """Get the gateway instance."""
    global _gateway
    if _gateway is None:
        _gateway = Gateway()
    return _gateway


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager."""
    global _config
    _config = SwarmMindConfig()

    # Initialize gateway
    get_gateway()

    yield

    # Cleanup
    # Note: Add cleanup logic here


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="SwarmMind API",
        description="A general-purpose AI task assistant API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Request/Response models
    class TaskCreateRequest(BaseModel):
        goal: str = Field(..., description="Task goal description")
        constraints: dict[str, Any] = Field(default_factory=dict)
        priority: str = Field(default="normal")
        profile: str = Field(default="py-basic")

    class TaskStatusResponse(BaseModel):
        task_id: str
        status: TaskStatus
        goal: str
        created_at: str
        result: dict[str, Any] | None = None
        error: str | None = None

    # Routes
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
    async def create_task(request: TaskCreateRequest):
        """Create a new task."""
        gateway = get_gateway()

        task_request = TaskRequest(
            goal=request.goal,
            constraints=request.constraints,
            priority=request.priority,
            profile=request.profile,
        )

        task = await gateway.create_task(task_request)

        return TaskStatusResponse(
            task_id=task.id,
            status=task.status,
            goal=task.goal,
            created_at=task.created_at.isoformat(),
            result=task.result,
            error=task.error,
        )

    @app.get("/v1/tasks", response_model=list[TaskStatusResponse])
    async def list_tasks(status: TaskStatus | None = None):
        """List all tasks."""
        gateway = get_gateway()
        tasks = await gateway.list_tasks(status)

        return [
            TaskStatusResponse(
                task_id=task.id,
                status=task.status,
                goal=task.goal,
                created_at=task.created_at.isoformat(),
                result=task.result,
                error=task.error,
            )
            for task in tasks
        ]

    @app.get("/v1/tasks/{task_id}", response_model=TaskStatusResponse)
    async def get_task(task_id: str):
        """Get a task by ID."""
        gateway = get_gateway()
        task = await gateway.get_task(task_id)

        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {task_id}",
            )

        return TaskStatusResponse(
            task_id=task.id,
            status=task.status,
            goal=task.goal,
            created_at=task.created_at.isoformat(),
            result=task.result,
            error=task.error,
        )

    @app.delete("/v1/tasks/{task_id}")
    async def delete_task(task_id: str):
        """Delete a task."""
        gateway = get_gateway()
        task = await gateway.get_task(task_id)

        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {task_id}",
            )

        # Mark as cancelled
        task.status = TaskStatus.CANCELLED
        await gateway.update_task(task)

        return {"message": "Task cancelled", "task_id": task_id}

    return app


# CLI command for running the server
def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Run the API server."""
    import uvicorn
    from swarmmind.api.server import create_app

    app = create_app()
    uvicorn.run(app, host=host, port=port, reload=reload)


if __name__ == "__main__":
    run_server()
