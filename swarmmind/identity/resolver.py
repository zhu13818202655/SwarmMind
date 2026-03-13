"""Identity resolution helpers."""

from __future__ import annotations

from typing import Protocol

from swarmmind.identity.models import IdentityContext


class IdentityResolver(Protocol):
    """Resolve a request identity from credentials."""

    async def resolve(self, api_key: str | None = None) -> IdentityContext:
        """Resolve the current identity context."""
        ...


class StaticIdentityResolver:
    """Minimal resolver used for local development and tests."""

    def __init__(self, default_tenant_id: str = "local", default_principal_id: str = "developer"):
        self._default_tenant_id = default_tenant_id
        self._default_principal_id = default_principal_id

    async def resolve(self, api_key: str | None = None) -> IdentityContext:
        """Return a static identity context.

        The optional API key is accepted to keep the interface stable for later
        integration with a real identity backend.
        """
        _ = api_key
        return IdentityContext(
            tenant_id=self._default_tenant_id,
            principal_id=self._default_principal_id,
            scopes=["tasks:submit", "tasks:read", "runs:read"],
            roles=["developer"],
            auth_method="static",
        )
