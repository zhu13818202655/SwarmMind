"""Memory module for SwarmMind.

The package intentionally avoids importing heavyweight optional dependencies at
module import time. Import concrete helpers such as `MemoryManager` or
`Transcript` from their submodules when needed.
"""

__all__: list[str] = []
