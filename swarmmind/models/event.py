"""Domain event models for SwarmMind."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from swarmmind.utils import utc_now


class DomainEvent(BaseModel):
    """A platform event with normalized execution context."""

    event_id: str = Field(..., description="Unique event identifier")
    topic: str = Field(..., description="Event topic")
    tenant_id: str = Field(..., description="Tenant identifier")
    session_id: str | None = Field(default=None)
    task_id: str | None = Field(default=None)
    run_id: str | None = Field(default=None)
    subtask_id: str | None = Field(default=None)
    sandbox_id: str | None = Field(default=None)
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=utc_now)
