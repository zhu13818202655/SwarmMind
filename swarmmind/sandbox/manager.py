"""Sandbox manager for lifecycle management."""

from typing import Any
from swarmmind.sandbox.provider import SandboxProvider, SandboxHandle, ExecResult, WriteFileEntry


class SandboxManager:
    """Sandbox manager for lifecycle management."""

    def __init__(self, provider: SandboxProvider):
        self._provider = provider
        self._active_sandboxes: dict[str, SandboxHandle] = {}

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

    async def write_files(self, sandbox_id: str, files: list[WriteFileEntry]) -> None:
        """Write files to the sandbox."""
        await self._provider.write_files(sandbox_id, files)

    async def read_file(self, sandbox_id: str, path: str) -> str | bytes:
        """Read a file from the sandbox."""
        return await self._provider.read_file(sandbox_id, path)

    async def destroy(self, sandbox_id: str) -> None:
        """Destroy a sandbox and remove from tracking."""
        await self._provider.kill(sandbox_id)
        self._active_sandboxes.pop(sandbox_id, None)

    async def destroy_all(self) -> None:
        """Destroy all active sandboxes."""
        for sandbox_id in list(self._active_sandboxes.keys()):
            await self.destroy(sandbox_id)

    def get_active(self) -> dict[str, SandboxHandle]:
        """Get all active sandboxes."""
        return self._active_sandboxes.copy()

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
