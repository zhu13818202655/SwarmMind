"""Identity models for SwarmMind."""

from typing import Any

from pydantic import BaseModel, Field


class IdentityContext(BaseModel):
    """Resolved identity attached to each request."""

    tenant_id: str = Field(..., description="Tenant identifier")
    principal_id: str = Field(..., description="User or service principal identifier")
    principal_type: str = Field(default="user")
    scopes: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    auth_method: str = Field(default="dev")
    metadata: dict[str, Any] = Field(default_factory=dict)
