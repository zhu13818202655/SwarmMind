"""Configuration models for SwarmMind."""

from typing import Any
from pydantic import BaseModel, Field
from swarmmind.models.task import TaskPriority


class ModelConfig(BaseModel):
    """LLM model configuration."""

    provider: str = Field(default="openai", description="Model provider")
    name: str = Field(default="gpt-4o", description="Model name")
    api_key: str | None = Field(default=None, description="API key")
    base_url: str | None = Field(default=None, description="Base URL for API")
    temperature: float = Field(default=0.7, description="Temperature")
    max_tokens: int = Field(default=4096, description="Max tokens")


class SandboxConfig(BaseModel):
    """Sandbox configuration."""

    provider: str = Field(default="opensandbox", description="Sandbox provider")
    api_key: str | None = Field(default=None, description="API key")
    base_url: str = Field(default="http://localhost:45698", description="Base URL")
    default_profile: str = Field(default="py-basic", description="Default sandbox profile")
    create_retries: int = Field(default=3, description="Number of retries for sandbox creation")
    create_backoff: float = Field(default=1.0, description="Backoff seconds between retries")


class MemoryConfig(BaseModel):
    """Memory configuration."""

    short_term_max_blocks: int = Field(default=10, description="Max blocks in short-term memory")
    long_term_enabled: bool = Field(default=False, description="Enable long-term memory")
    long_term_storage_type: str = Field(default="memory", description="Storage type: memory, redis, sqlite")


class AgentConfig(BaseModel):
    """Agent configuration."""

    model: ModelConfig = Field(default_factory=ModelConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    max_steps: int = Field(default=100, description="Max steps per task")
    timeout: int = Field(default=300, description="Timeout in seconds")


class SwarmMindConfig(BaseModel):
    """SwarmMind configuration."""

    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    rate_limit_enabled: bool = Field(default=False, description="Enable rate limiting")
    rate_limit_per_minute: int = Field(default=60, description="Requests per minute")
    log_level: str = Field(default="INFO", description="Log level")
    storage_path: str = Field(default="./data", description="Data storage path")
