"""Session models for SwarmMind."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from swarmmind.utils import utc_now


class SessionStatus(str, Enum):
    """Session lifecycle status."""

    ACTIVE = "active"
    CLOSED = "closed"


class Session(BaseModel):
    """Conversation and task grouping context."""

    id: str = Field(..., description="Unique session identifier")
    tenant_id: str = Field(..., description="Tenant identifier")
    actor_id: str = Field(..., description="User or service principal identifier")
    status: SessionStatus = Field(default=SessionStatus.ACTIVE)
    task_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def attach_task(self, task_id: str) -> None:
        """Attach a task to the session if not already attached."""
        if task_id not in self.task_ids:
            self.task_ids.append(task_id)
            self.updated_at = utc_now()
