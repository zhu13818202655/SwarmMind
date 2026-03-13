"""Replay models for SwarmMind."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ReplayEntry(BaseModel):
    """Single replay timeline entry."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ReplayRoot(BaseModel):
    """Replay root record for a run."""

    id: str = Field(..., description="Replay root identifier")
    task_id: str = Field(..., description="Parent task identifier")
    run_id: str = Field(..., description="Owning run identifier")
    entries: list[ReplayEntry] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def append(self, entry: ReplayEntry) -> None:
        """Append a new timeline entry."""
        self.entries.append(entry)
        self.updated_at = datetime.utcnow()
