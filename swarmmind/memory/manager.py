"""Memory manager using AgentScope."""

from typing import Any
from agentscope.memory import InMemoryMemory


class MemoryManager:
    """Memory manager using AgentScope memory."""

    def __init__(self, max_session_blocks: int = 10):
        self._max_session_blocks = max_session_blocks
        self._memory = InMemoryMemory()

    @property
    def memory(self) -> InMemoryMemory:
        """Get the underlying AgentScope memory."""
        return self._memory

    async def add(self, message: Any) -> None:
        """Add a message to memory."""
        await self._memory.add(message)
        await self._trim_memory()

    async def get(self, k: int | None = None) -> list[Any]:
        """Get messages from memory."""
        messages = await self._memory.get_memory(prepend_summary=False)
        if k is None:
            return messages
        if k <= 0:
            return []
        return messages[-k:]

    async def clear(self) -> None:
        """Clear memory."""
        await self._memory.clear()

    async def size(self) -> int:
        """Get memory size."""
        return await self._memory.size()

    async def _trim_memory(self) -> None:
        """Keep only the most recent session messages."""
        if self._max_session_blocks <= 0:
            return

        messages = await self._memory.get_memory(prepend_summary=False)
        overflow = len(messages) - self._max_session_blocks
        if overflow <= 0:
            return

        await self._memory.delete([msg.id for msg in messages[:overflow]])
