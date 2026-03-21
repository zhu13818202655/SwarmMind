"""Artifact models for SwarmMind."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from swarmmind.utils import utc_now


class ArtifactType(str, Enum):
    """Supported artifact categories."""

    LOG = "log"
    REPORT = "report"
    PATCH = "patch"
    TEST_RESULT = "test_result"
    TRANSCRIPT = "transcript"
    FILE = "file"
    OTHER = "other"


class Artifact(BaseModel):
    """Metadata for a persisted execution output."""

    id: str = Field(..., description="Artifact identifier")
    task_id: str = Field(..., description="Parent task identifier")
    run_id: str = Field(..., description="Owning run identifier")
    subtask_id: str | None = Field(default=None)
    name: str = Field(..., description="Artifact name")
    type: ArtifactType = Field(default=ArtifactType.OTHER)
    storage_ref: str | None = Field(default=None, description="Object-store or local reference")
    content_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
