"""Task models for SwarmMind."""

from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

from swarmmind.models.capability import AgentRole, ToolGroup


class TaskStatus(str, Enum):
    """Task status enum."""

    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    REVIEWING = "reviewing"
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = Field(default=None, description="Task start time")
    finished_at: datetime | None = Field(default=None, description="Task finish time")
    result: dict[str, Any] | None = Field(default=None, description="Task result")
    error: str | None = Field(default=None, description="Error message if failed")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    def start(self) -> None:
        """Mark task as started."""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def succeed(self, result: dict[str, Any]) -> None:
        """Mark task as succeeded."""
        self.status = TaskStatus.SUCCEEDED
        self.result = result
        self.finished_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def fail(self, error: str) -> None:
        """Mark task as failed."""
        self.status = TaskStatus.FAILED
        self.error = error
        self.finished_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()


class SubTask(BaseModel):
    """Sub-task model."""

    id: str = Field(..., description="Unique sub-task identifier")
    task_id: str = Field(..., description="Parent task ID")
    name: str = Field(..., description="Sub-task name")
    description: str = Field(..., description="Sub-task description")
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    agent_id: str | None = Field(default=None, description="Agent assigned to this sub-task")
    role: AgentRole = Field(default=AgentRole.EXECUTOR, description="Logical executor role")
    preferred_skill: str | None = Field(default=None, description="Preferred skill profile")
    required_tool_groups: list[ToolGroup] = Field(
        default_factory=list,
        description="Tool groups required by this sub-task",
    )
    sandbox_profile: str | None = Field(default=None, description="Sandbox profile")
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Acceptance criteria for validation and review",
    )
    result: dict[str, Any] | None = Field(default=None)
    error: str | None = Field(default=None)
    dependencies: list[str] = Field(default_factory=list, description="Sub-task IDs this depends on")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional execution metadata")

    def complete(self, result: dict[str, Any]) -> None:
        """Mark sub-task as completed."""
        self.status = TaskStatus.SUCCEEDED
        self.result = result

    def fail(self, error: str) -> None:
        """Mark sub-task as failed."""
        self.status = TaskStatus.FAILED
        self.error = error


class TaskRequest(BaseModel):
    """Task request model for API/CLI."""

    goal: str = Field(..., description="Task goal")
    constraints: dict[str, Any] = Field(default_factory=dict)
    priority: TaskPriority = Field(default=TaskPriority.NORMAL)
    profile: str = Field(default="py-basic", description="Sandbox profile")
    preferred_skill: str | None = Field(default=None, description="Preferred top-level skill")
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
