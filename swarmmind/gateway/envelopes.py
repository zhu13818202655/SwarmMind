"""Gateway-level request and response envelopes."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from swarmmind.models.artifact import Artifact
from swarmmind.models.run import Run
from swarmmind.models.session import Session
from swarmmind.models.task import SubTask, Task, TaskPriority, TaskStatus
from swarmmind.utils import utc_now


class TaskSubmitRequest(BaseModel):
    """External task submission request."""

    model_config = ConfigDict(populate_by_name=True)

    goal: str = Field(..., description="Task goal")
    constraints: dict[str, Any] = Field(default_factory=dict)
    priority: TaskPriority = Field(default=TaskPriority.NORMAL)
    profile: str = Field(default="py-basic")
    session_id: str | None = None
    agent_profile_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionContext(BaseModel):
    """Normalized session context created by the gateway."""

    session_id: str
    tenant_id: str
    actor_id: str


class RunContext(BaseModel):
    """Normalized run context created by the gateway."""

    run_id: str
    task_id: str
    session_id: str


class TaskEnvelope(BaseModel):
    """Normalized control-plane envelope for orchestration."""

    task: Task
    session: Session
    run: Run
    request: TaskSubmitRequest
    created_at: datetime = Field(default_factory=utc_now)


class TaskSubmissionResult(BaseModel):
    """Return value for a submitted task."""

    task_id: str
    session_id: str
    run_id: str
    status: TaskStatus


class RunDetail(BaseModel):
    """Aggregated run detail view."""

    run: Run
    subtasks: list[SubTask] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)


class TaskDetail(BaseModel):
    """Aggregated task detail view."""

    task: Task
    session: Session | None = None
    runs: list[RunDetail] = Field(default_factory=list)
