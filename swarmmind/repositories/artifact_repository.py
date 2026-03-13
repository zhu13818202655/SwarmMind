"""Artifact repository protocol."""

from __future__ import annotations

from typing import Protocol

from swarmmind.models.artifact import Artifact


class ArtifactRepository(Protocol):
    """Persistence contract for artifacts."""

    async def create(self, artifact: Artifact) -> Artifact:
        ...

    async def list_for_run(self, run_id: str) -> list[Artifact]:
        ...
