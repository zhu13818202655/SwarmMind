"""Artifact repository protocol."""

from __future__ import annotations

from typing import Protocol

from swarmmind.models.artifact import Artifact


class ArtifactRepository(Protocol):
    """Persistence contract for artifacts."""

    async def create(self, artifact: Artifact, payload: bytes | None = None) -> Artifact:
        ...

    async def get(self, artifact_id: str) -> Artifact | None:
        ...

    async def list_for_run(self, run_id: str) -> list[Artifact]:
        ...

    async def list_for_subtask(self, run_id: str, subtask_id: str) -> list[Artifact]:
        ...

    async def read_content(self, artifact: Artifact) -> bytes | None:
        ...
