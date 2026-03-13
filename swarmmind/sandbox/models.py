"""Sandbox control-plane models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SandboxStatus(str, Enum):
    """Lifecycle status for a sandbox lease."""

    REQUESTED = "requested"
    READY = "ready"
    ACTIVE = "active"
    TERMINATED = "terminated"
    FAILED = "failed"


class SandboxLeaseRequest(BaseModel):
    """Request to acquire a sandbox for a run or subtask."""

    profile: str
    task_id: str
    run_id: str
    subtask_id: str | None = None


class SandboxLease(BaseModel):
    """Leased sandbox context."""

    lease_id: str
    sandbox_id: str
    profile: str
    status: SandboxStatus = Field(default=SandboxStatus.READY)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CommandRequest(BaseModel):
    """Command execution request."""

    command: str
    cwd: str | None = None


class SandboxExecution(BaseModel):
    """Normalized command execution record."""

    sandbox_id: str
    command: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    executed_at: datetime = Field(default_factory=datetime.utcnow)
