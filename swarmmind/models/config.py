"""Compatibility shim for legacy config imports.

Prefer importing from `swarmmind.config` going forward.
"""

from swarmmind.config import (
    AgentConfig,
    ApiConfig,
    IdentityConfig,
    MemoryConfig,
    ModelConfig,
    PostgresConfig,
    RateLimitConfig,
    RedisConfig,
    SandboxConfig,
    SwarmMindConfig,
    VectorStoreConfig,
    get_settings,
)

__all__ = [
    "AgentConfig",
    "ApiConfig",
    "IdentityConfig",
    "MemoryConfig",
    "ModelConfig",
    "PostgresConfig",
    "RateLimitConfig",
    "RedisConfig",
    "SandboxConfig",
    "SwarmMindConfig",
    "VectorStoreConfig",
    "get_settings",
]
