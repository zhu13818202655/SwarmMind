"""Session repository protocol."""

from __future__ import annotations

from typing import Protocol

from swarmmind.models.session import Session


class SessionRepository(Protocol):
    """Persistence contract for sessions."""

    async def create(self, session: Session) -> Session:
        ...

    async def get(self, session_id: str) -> Session | None:
        ...

    async def save(self, session: Session) -> Session:
        ...
