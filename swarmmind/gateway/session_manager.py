"""Session creation helpers for the gateway."""

from __future__ import annotations

import uuid

from swarmmind.identity.models import IdentityContext
from swarmmind.models.session import Session
from swarmmind.repositories.session_repository import SessionRepository


class GatewaySessionManager:
    """Create or load sessions for task submissions."""

    def __init__(self, session_repository: SessionRepository):
        self._session_repository = session_repository

    async def get_or_create(self, session_id: str | None, identity: IdentityContext) -> Session:
        """Return an existing session or create a new one."""
        if session_id:
            existing = await self._session_repository.get(session_id)
            if existing is not None:
                return existing

        session = Session(
            id=str(uuid.uuid4()),
            tenant_id=identity.tenant_id,
            actor_id=identity.principal_id,
        )
        return await self._session_repository.create(session)
