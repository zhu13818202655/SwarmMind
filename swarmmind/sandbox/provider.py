"""Sandbox provider abstraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from swarmmind.utils import utc_now


@dataclass(slots=True)
class SandboxHandle:
    """Sandbox handle."""

    sandbox_id: str
    profile: str
    image: str
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class ExecResult:
    """Execution result."""

    exit_code: int
    stdout: str
    stderr: str


@dataclass(slots=True)
class WriteFileEntry:
    """File entry for writing to sandbox."""

    path: str
    data: str
    mode: int = 0o644


class SandboxProvider(Protocol):
    """Sandbox provider protocol."""

    async def create(self, profile: str, metadata: dict[str, str] | None = None) -> SandboxHandle:
        """Create a sandbox."""
        ...

    async def run_command(self, sandbox_id: str, cmd: str, cwd: str | None = None) -> ExecResult:
        """Run a command in the sandbox."""
        ...

    async def write_files(self, sandbox_id: str, files: list[WriteFileEntry]) -> None:
        """Write files to the sandbox."""
        ...

    async def read_file(self, sandbox_id: str, path: str, *, encoding: str = "utf-8") -> str | bytes:
        """Read a file from the sandbox."""
        ...

    async def kill(self, sandbox_id: str) -> None:
        """Kill a sandbox."""
        ...
