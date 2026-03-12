"""Memory manager using AgentScope."""

from typing import Any
from agentscope.memory import InMemoryMemory


class MemoryManager:
    """Memory manager using AgentScope memory."""

    def __init__(self, max_session_blocks: int = 10):
        self._memory = InMemoryMemory(
            memory_config={"max_session_blocks": max_session_blocks}
        )

    @property
    def memory(self) -> InMemoryMemory:
        """Get the underlying AgentScope memory."""
        return self._memory

    async def add(self, message: Any) -> None:
        """Add a message to memory."""
        self._memory.add(message)

    async def get(self, k: int | None = None) -> list[Any]:
        """Get messages from memory."""
        return self._memory.get_memory(k=k)

    async def clear(self) -> None:
        """Clear memory."""
        self._memory.clear()

    async def size(self) -> int:
        """Get memory size."""
        return self._memory.size()
