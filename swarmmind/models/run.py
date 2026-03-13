"""Run models for SwarmMind."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    """Execution status for a run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunPhase(str, Enum):
    """High-level phase for the current run."""

    INTAKE = "intake"
    PLANNING = "planning"
    COORDINATING = "coordinating"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    DELIVERING = "delivering"


class Run(BaseModel):
    """A concrete execution attempt for a task."""

    id: str = Field(..., description="Unique run identifier")
    task_id: str = Field(..., description="Parent task identifier")
    session_id: str = Field(..., description="Owning session identifier")
    status: RunStatus = Field(default=RunStatus.PENDING)
    phase: RunPhase = Field(default=RunPhase.INTAKE)
    subtask_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def start(self) -> None:
        """Mark the run as active."""
        self.status = RunStatus.RUNNING
        self.started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def set_phase(self, phase: RunPhase) -> None:
        """Advance the run phase."""
        self.phase = phase
        self.updated_at = datetime.utcnow()

    def attach_subtasks(self, subtask_ids: list[str]) -> None:
        """Attach subtasks to this run."""
        self.subtask_ids = list(subtask_ids)
        self.updated_at = datetime.utcnow()

    def succeed(self) -> None:
        """Mark the run as successful."""
        self.status = RunStatus.SUCCEEDED
        self.finished_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def fail(self, error: str) -> None:
        """Mark the run as failed."""
        self.status = RunStatus.FAILED
        self.error = error
        self.finished_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
