"""Task models for SwarmMind."""

from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from swarmmind.defaults import DEFAULT_SANDBOX_PROFILE
from swarmmind.models.capability import AgentRole, RuntimeKind, ToolGroup
from swarmmind.models.execution import ExecutionConfiguration
from swarmmind.utils import utc_now


class TaskStatus(str, Enum):
    """Task status enum."""

    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    REVIEWING = "reviewing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SubTaskStatus(str, Enum):
    """Detailed lifecycle states for subtask execution."""

    QUEUED = "queued"
    READY = "ready"
    ASSIGNED = "assigned"
    SANDBOX_CREATING = "sandbox_creating"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Task priority enum."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class Task(BaseModel):
    """Task model."""

    id: str = Field(..., description="Unique task identifier")
    goal: str = Field(..., description="Task goal description")
    constraints: dict[str, Any] = Field(default_factory=dict, description="Task constraints")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Task status")
    priority: TaskPriority = Field(default=TaskPriority.NORMAL, description="Task priority")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = Field(default=None, description="Task start time")
    finished_at: datetime | None = Field(default=None, description="Task finish time")
    result: dict[str, Any] | None = Field(default=None, description="Task result")
    error: str | None = Field(default=None, description="Error message if failed")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    def start(self) -> None:
        """Mark task as started."""
        self.status = TaskStatus.RUNNING
        self.started_at = utc_now()
        self.updated_at = utc_now()

    def succeed(self, result: dict[str, Any]) -> None:
        """Mark task as succeeded."""
        self.status = TaskStatus.SUCCEEDED
        self.result = result
        self.finished_at = utc_now()
        self.updated_at = utc_now()

    def fail(self, error: str) -> None:
        """Mark task as failed."""
        self.status = TaskStatus.FAILED
        self.error = error
        self.finished_at = utc_now()
        self.updated_at = utc_now()


class SubTask(BaseModel):
    """Sub-task model."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Unique sub-task identifier")
    task_id: str = Field(..., description="Parent task ID")
    name: str = Field(..., description="Sub-task name")
    description: str = Field(..., description="Sub-task description")
    status: SubTaskStatus = Field(default=SubTaskStatus.QUEUED)
    agent_id: str | None = Field(default=None, description="Agent assigned to this sub-task")
    agent_profile_id: str | None = Field(default=None, description="Preferred agent profile for this sub-task")
    role: AgentRole = Field(default=AgentRole.CODER, description="Logical agent role")
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Acceptance criteria for validation and review",
    )
    expected_artifacts: list[str] = Field(default_factory=list, description="Expected artifact kinds")
    execution_configuration: ExecutionConfiguration | None = Field(default=None)
    result: dict[str, Any] | None = Field(default=None)
    error: str | None = Field(default=None)
    dependencies: list[str] = Field(default_factory=list, description="Sub-task IDs this depends on")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional execution metadata")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)

    def mark_ready(self) -> None:
        """Mark sub-task as ready for assignment."""
        self.status = SubTaskStatus.READY
        self.updated_at = utc_now()

    def assign(self, execution_profile: dict[str, Any], run_id: str) -> None:
        """Assign execution metadata and transition to assigned state."""
        self.status = SubTaskStatus.ASSIGNED
        self.metadata["assigned_execution"] = execution_profile
        self.metadata["execution_profile"] = execution_profile
        self.metadata["resolved_execution_profile"] = execution_profile
        self.metadata["assigned_run_id"] = run_id
        self.metadata["assigned_at"] = utc_now().isoformat()
        self.updated_at = utc_now()

    def mark_sandbox_creating(self) -> None:
        """Mark sub-task as waiting for sandbox creation."""
        self.status = SubTaskStatus.SANDBOX_CREATING
        self.updated_at = utc_now()

    def start_execution(self) -> None:
        """Mark sub-task as executing."""
        self.status = SubTaskStatus.EXECUTING
        self.started_at = self.started_at or utc_now()
        self.updated_at = utc_now()

    def start_verification(self) -> None:
        """Mark sub-task as running verification/review logic."""
        self.status = SubTaskStatus.VERIFYING
        self.started_at = self.started_at or utc_now()
        self.updated_at = utc_now()

    def complete(self, result: dict[str, Any]) -> None:
        """Mark sub-task as completed."""
        self.status = SubTaskStatus.SUCCEEDED
        self.result = result
        self.error = None
        self.finished_at = utc_now()
        self.updated_at = utc_now()

    def fail(self, error: str) -> None:
        """Mark sub-task as failed."""
        self.status = SubTaskStatus.FAILED
        self.error = error
        self.finished_at = utc_now()
        self.updated_at = utc_now()


class TaskRequest(BaseModel):
    """Task request model for API/CLI."""

    model_config = ConfigDict(populate_by_name=True)

    goal: str = Field(..., description="Task goal")
    constraints: dict[str, Any] = Field(default_factory=dict)
    priority: TaskPriority = Field(default=TaskPriority.NORMAL)
    profile: str = Field(default=DEFAULT_SANDBOX_PROFILE, description="Sandbox profile")
    agent_profile_id: str | None = Field(default=None, description="Default agent profile for generated subtasks")
    required_tool_groups: list[ToolGroup] = Field(
        default_factory=list,
        description="Tool groups required for the task by policy or user request",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)



class TaskResponse(BaseModel):
    """Task response model."""

    task_id: str
    status: TaskStatus
    result: dict[str, Any] | None = None
    error: str | None = None
