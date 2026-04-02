"""File-backed repository implementations for local development durability."""

from __future__ import annotations

from pathlib import Path

from swarmmind.models.artifact import Artifact
from swarmmind.models.replay import ReplayRoot


class FileArtifactRepository:
    """Persist artifacts as JSON files under a run-scoped directory tree."""

    def __init__(self, base_path: str | Path):
        self._base_path = Path(base_path)
        self._root = self._base_path / "artifacts"
        self._root.mkdir(parents=True, exist_ok=True)

    async def create(self, artifact: Artifact) -> Artifact:
        path = self._artifact_path(artifact.run_id, artifact.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
        return artifact

    async def list_for_run(self, run_id: str) -> list[Artifact]:
        run_dir = self._root / run_id
        if not run_dir.exists():
            return []
        return sorted(
            [Artifact.model_validate_json(path.read_text(encoding="utf-8")) for path in run_dir.glob("*.json")],
            key=lambda artifact: artifact.created_at,
        )

    async def list_for_subtask(self, run_id: str, subtask_id: str) -> list[Artifact]:
        artifacts = await self.list_for_run(run_id)
        return [artifact for artifact in artifacts if artifact.subtask_id == subtask_id]

    def _artifact_path(self, run_id: str, artifact_id: str) -> Path:
        return self._root / run_id / f"{artifact_id}.json"


class FileReplayRepository:
    """Persist run replay roots as JSON files."""

    def __init__(self, base_path: str | Path):
        self._base_path = Path(base_path)
        self._root = self._base_path / "replays"
        self._root.mkdir(parents=True, exist_ok=True)

    async def create(self, replay: ReplayRoot) -> ReplayRoot:
        return await self.save(replay)

    async def get_by_run(self, run_id: str) -> ReplayRoot | None:
        path = self._replay_path(run_id)
        if not path.exists():
            return None
        return ReplayRoot.model_validate_json(path.read_text(encoding="utf-8"))

    async def save(self, replay: ReplayRoot) -> ReplayRoot:
        path = self._replay_path(replay.run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(replay.model_dump_json(indent=2), encoding="utf-8")
        return replay

    def _replay_path(self, run_id: str) -> Path:
        return self._root / f"{run_id}.json"