"""Local sandbox adapter for development and tests."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import uuid
from pathlib import Path

from swarmmind.sandbox.provider import ExecResult, SandboxHandle, SandboxProvider, WriteFileEntry


class LocalSandboxAdapter(SandboxProvider):
    """A lightweight sandbox provider backed by local temp directories."""

    def __init__(self) -> None:
        self._sandboxes: dict[str, Path] = {}

    async def create(self, profile: str, metadata: dict[str, str] | None = None) -> SandboxHandle:
        """Create a local temp directory sandbox."""
        sandbox_id = str(uuid.uuid4())
        root = Path(tempfile.mkdtemp(prefix=f"swarmmind-{profile}-"))
        self._sandboxes[sandbox_id] = root
        return SandboxHandle(sandbox_id=sandbox_id, profile=profile, image=f"local:{profile}")

    async def run_command(self, sandbox_id: str, cmd: str, cwd: str | None = None) -> ExecResult:
        """Run a shell command inside the local sandbox root."""
        root = self._require_root(sandbox_id)
        workdir = self._resolve_path(root, cwd or ".")
        workdir.mkdir(parents=True, exist_ok=True)

        process = await asyncio.create_subprocess_shell(
            cmd,
            cwd=str(workdir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await process.communicate()
        return ExecResult(
            exit_code=process.returncode or 0,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
        )

    async def write_files(self, sandbox_id: str, files: list[WriteFileEntry]) -> None:
        """Write files inside the local sandbox root."""
        root = self._require_root(sandbox_id)
        for entry in files:
            target = self._resolve_path(root, entry.path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(entry.data, encoding="utf-8")
            target.chmod(entry.mode)

    async def read_file(self, sandbox_id: str, path: str, *, encoding: str | None = "utf-8") -> str | bytes:
        """Read a file inside the local sandbox root."""
        root = self._require_root(sandbox_id)
        target = self._resolve_path(root, path)
        if encoding:
            return target.read_text(encoding=encoding)
        return target.read_bytes()

    async def kill(self, sandbox_id: str) -> None:
        """Destroy the temp directory sandbox."""
        root = self._sandboxes.pop(sandbox_id, None)
        if root is None:
            return
        shutil.rmtree(root, ignore_errors=True)

    def _require_root(self, sandbox_id: str) -> Path:
        root = self._sandboxes.get(sandbox_id)
        if root is None:
            raise KeyError(f"Sandbox not found: {sandbox_id}")
        return root

    @staticmethod
    def _resolve_path(root: Path, path: str) -> Path:
        normalized = path.strip() or "."
        if normalized.startswith("/"):
            normalized = normalized.lstrip("/")
        candidate = (root / normalized).resolve()
        candidate.relative_to(root.resolve())
        return candidate