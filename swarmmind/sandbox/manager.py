"""Sandbox manager for lifecycle management."""

from __future__ import annotations

import uuid

from swarmmind.models.artifact import Artifact, ArtifactType
from swarmmind.sandbox.models import (
    CommandRequest,
    SandboxExecution,
    SandboxLease,
    SandboxLeaseRequest,
    SandboxStatus,
)
from swarmmind.sandbox.provider import ExecResult, SandboxHandle, SandboxProvider, WriteFileEntry


class SandboxManager:
    """Sandbox manager for lifecycle management."""

    def __init__(self, provider: SandboxProvider):
        self._provider = provider
        self._active_sandboxes: dict[str, SandboxHandle] = {}
        self._leases: dict[str, SandboxLease] = {}

    async def acquire(self, request: SandboxLeaseRequest) -> SandboxLease:
        """Acquire a managed sandbox lease for a run or subtask."""
        handle = await self.create(
            request.profile,
            metadata={
                "task_id": request.task_id,
                "run_id": request.run_id,
                "subtask_id": request.subtask_id or "",
            },
        )
        lease = SandboxLease(
            lease_id=str(uuid.uuid4()),
            sandbox_id=handle.sandbox_id,
            profile=handle.profile,
            status=SandboxStatus.READY,
        )
        self._leases[lease.lease_id] = lease
        return lease

    async def create(self, profile: str, metadata: dict[str, str] | None = None) -> SandboxHandle:
        """Create a sandbox and track it."""
        handle = await self._provider.create(profile, metadata)
        self._active_sandboxes[handle.sandbox_id] = handle
        return handle

    async def run_command(
        self,
        sandbox_id: str,
        cmd: str,
        cwd: str | None = None,
    ) -> ExecResult:
        """Run a command in the sandbox."""
        return await self._provider.run_command(sandbox_id, cmd, cwd)

    async def execute(self, lease: SandboxLease, request: CommandRequest) -> SandboxExecution:
        """Execute a normalized command request."""
        result = await self.run_command(lease.sandbox_id, request.command, cwd=request.cwd)
        lease.status = SandboxStatus.ACTIVE
        return SandboxExecution(
            sandbox_id=lease.sandbox_id,
            command=request.command,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    async def write_files(self, sandbox_id: str, files: list[WriteFileEntry]) -> None:
        """Write files to the sandbox."""
        await self._provider.write_files(sandbox_id, files)

    async def read_file(self, sandbox_id: str, path: str, *, encoding: str | None = "utf-8") -> str | bytes:
        """Read a file from the sandbox."""
        return await self._provider.read_file(sandbox_id, path, encoding=encoding)

    async def destroy(self, sandbox_id: str) -> None:
        """Destroy a sandbox and remove from tracking."""
        await self._provider.kill(sandbox_id)
        self._active_sandboxes.pop(sandbox_id, None)

    async def release(self, lease_id: str) -> None:
        """Release a managed sandbox lease."""
        lease = self._leases.pop(lease_id, None)
        if lease is None:
            return
        lease.status = SandboxStatus.TERMINATED
        await self.destroy(lease.sandbox_id)

    async def destroy_all(self) -> None:
        """Destroy all active sandboxes."""
        for sandbox_id in list(self._active_sandboxes.keys()):
            await self.destroy(sandbox_id)

    def get_active(self) -> dict[str, SandboxHandle]:
        """Get all active sandboxes."""
        return self._active_sandboxes.copy()

    async def collect_artifacts(self, lease: SandboxLease) -> list[Artifact]:
        """Return placeholder artifact metadata for the lease.

        The first round does not persist object-store content yet. This method
        exists to stabilize the control-plane contract for later rounds.
        """
        return [
            Artifact(
                id=str(uuid.uuid4()),
                task_id="unknown",
                run_id="unknown",
                name=f"sandbox-{lease.sandbox_id}-stdout.log",
                type=ArtifactType.LOG,
                storage_ref=f"sandbox://{lease.sandbox_id}/stdout",
            )
        ]

    async def execute_in_sandbox(
        self,
        profile: str,
        code: str,
        files: list[WriteFileEntry] | None = None,
        cwd: str = "/tmp",
    ) -> ExecResult:
        """Execute code in a sandbox (convenience method)."""
        handle = await self.create(profile)

        try:
            if files:
                await self.write_files(handle.sandbox_id, files)

            result = await self.run_command(handle.sandbox_id, f"python {cwd}/main.py", cwd=cwd)
            return result
        finally:
            await self.destroy(handle.sandbox_id)
