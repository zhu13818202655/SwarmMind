"""Replay repository protocol."""

from __future__ import annotations

from typing import Protocol

from swarmmind.models.replay import ReplayRoot


class ReplayRepository(Protocol):
    """Persistence contract for replay roots."""

    async def create(self, replay: ReplayRoot) -> ReplayRoot:
        ...

    async def get_by_run(self, run_id: str) -> ReplayRoot | None:
        ...

    async def save(self, replay: ReplayRoot) -> ReplayRoot:
        ...
