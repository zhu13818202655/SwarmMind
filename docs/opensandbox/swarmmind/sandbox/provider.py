"""Common sandbox abstraction used by higher-level services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(slots=True)
class SandboxHandle:
    sandbox_id: str
    profile: str
    image: str
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str


@dataclass(slots=True)
class WriteFileEntry:
    path: str
    data: str
    mode: int = 0o644


class SandboxProvider(Protocol):
    async def create(self, profile: str, metadata: dict[str, str] | None = None) -> SandboxHandle:
        ...

    async def run_command(self, sandbox_id: str, cmd: str, cwd: str | None = None) -> ExecResult:
        ...

    async def write_files(self, sandbox_id: str, files: list[WriteFileEntry]) -> None:
        ...

    async def read_file(self, sandbox_id: str, path: str, *, encoding: str = "utf-8") -> str | bytes:
        ...

    async def kill(self, sandbox_id: str) -> None:
        ...
