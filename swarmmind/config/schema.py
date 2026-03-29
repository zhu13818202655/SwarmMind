"""Configuration schema models for SwarmMind."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from swarmmind.config.env import resolve_env_value


class ValidatedDefaultsModel(BaseModel):
    """Base config model that validates defaulted fields."""

    model_config = ConfigDict(validate_default=True)


class ModelConfig(ValidatedDefaultsModel):
    """LLM model configuration."""

    provider: str = Field(default="openai", description="Model provider")
    name: str = Field(default="gpt-4o", description="Model name")
    api_key: str | None = Field(default=None, description="API key")
    base_url: str | None = Field(default=None, description="Base URL for API")
    temperature: float = Field(default=0.7, description="Temperature")
    max_tokens: int = Field(default=4096, description="Max tokens")

    @field_validator("api_key", mode="before")
    @classmethod
    def resolve_api_key(cls, value: Any) -> Any:
        return resolve_env_value(value, "OPENAI_API_KEY")

    @field_validator("base_url", mode="before")
    @classmethod
    def resolve_base_url(cls, value: Any) -> Any:
        return resolve_env_value(value, "OPENAI_BASE_URL")


class SandboxConfig(ValidatedDefaultsModel):
    """Sandbox configuration."""

    provider: str = Field(default="opensandbox", description="Sandbox provider")
    api_key: str | None = Field(default=None, description="API key")
    base_url: str = Field(default="http://localhost:45698", description="Base URL")
    default_profile: str = Field(default="py-basic", description="Default sandbox profile")
    create_retries: int = Field(default=3, description="Number of retries for sandbox creation")
    create_backoff: float = Field(default=1.0, description="Backoff seconds between retries")
    request_timeout_seconds: int = Field(
        default=300,
        description="HTTP request timeout (seconds) when calling OpenSandbox server",
    )

    @field_validator("api_key", mode="before")
    @classmethod
    def resolve_api_key(cls, value: Any) -> Any:
        return resolve_env_value(value, "OPEN_SANDBOX_API_KEY")

    @field_validator("base_url", mode="before")
    @classmethod
    def resolve_base_url(cls, value: Any) -> Any:
        resolved = resolve_env_value(value, "OPEN_SANDBOX_BASE_URL")
        if resolved in (None, ""):
            return cls.model_fields["base_url"].default
        return resolved

    @field_validator("create_retries", mode="before")
    @classmethod
    def resolve_create_retries(cls, value: Any) -> Any:
        return resolve_env_value(value, "OPEN_SANDBOX_CREATE_RETRIES", cast_type=int)

    @field_validator("create_backoff", mode="before")
    @classmethod
    def resolve_create_backoff(cls, value: Any) -> Any:
        return resolve_env_value(value, "OPEN_SANDBOX_CREATE_BACKOFF_SECONDS", cast_type=float)

    @field_validator("request_timeout_seconds", mode="before")
    @classmethod
    def resolve_request_timeout_seconds(cls, value: Any) -> Any:
        return resolve_env_value(value, "OPEN_SANDBOX_REQUEST_TIMEOUT_SECONDS", cast_type=int)


class PostgresConfig(ValidatedDefaultsModel):
    """PostgreSQL infrastructure configuration."""

    enabled: bool = Field(default=False, description="Enable PostgreSQL-backed repositories")
    dsn: str = Field(
        default="postgresql://swarmmind:swarmmind@127.0.0.1:5432/swarmmind",
        description="PostgreSQL connection string",
    )
    auto_init_schema: bool = Field(default=True, description="Create repository tables on startup")

    @field_validator("enabled", mode="before")
    @classmethod
    def resolve_enabled(cls, value: Any) -> Any:
        return resolve_env_value(value, "SWARMMIND_POSTGRES__ENABLED", cast_type=bool)

    @field_validator("dsn", mode="before")
    @classmethod
    def resolve_dsn(cls, value: Any) -> Any:
        return resolve_env_value(value, "POSTGRES_DSN", "DATABASE_URL")


class RedisConfig(ValidatedDefaultsModel):
    """Redis infrastructure configuration."""

    enabled: bool = Field(default=False, description="Enable Redis-backed cache, locks, and event buffering")
    url: str = Field(default="redis://127.0.0.1:6379/0", description="Redis connection URL")
    event_stream: str = Field(default="swarmmind:events", description="Redis stream name for buffered events")
    channel_prefix: str = Field(default="swarmmind", description="Redis pubsub channel prefix")
    cache_prefix: str = Field(default="swarmmind:cache", description="Cache key prefix")
    lock_prefix: str = Field(default="swarmmind:lock", description="Lock key prefix")
    default_lock_ttl: int = Field(default=30, description="Default lock TTL in seconds")

    @field_validator("enabled", mode="before")
    @classmethod
    def resolve_enabled(cls, value: Any) -> Any:
        return resolve_env_value(value, "SWARMMIND_REDIS__ENABLED", cast_type=bool)

    @field_validator("url", mode="before")
    @classmethod
    def resolve_url(cls, value: Any) -> Any:
        return resolve_env_value(value, "REDIS_URL")


class VectorStoreConfig(ValidatedDefaultsModel):
    """Vector store and long-term memory configuration."""

    provider: str = Field(default="memory", description="Vector provider: memory or qdrant")
    enabled: bool = Field(default=False, description="Enable external vector storage")
    qdrant_url: str = Field(default="http://127.0.0.1:6333", description="Qdrant endpoint URL")
    collection: str = Field(default="swarmmind", description="Qdrant collection name")
    embedding_dimension: int = Field(default=256, description="Embedding vector dimension")

    @field_validator("provider", mode="before")
    @classmethod
    def resolve_provider(cls, value: Any) -> Any:
        return resolve_env_value(value, "SWARMMIND_VECTOR_STORE__PROVIDER")

    @field_validator("enabled", mode="before")
    @classmethod
    def resolve_enabled(cls, value: Any) -> Any:
        return resolve_env_value(value, "SWARMMIND_VECTOR_STORE__ENABLED", cast_type=bool)

    @field_validator("qdrant_url", mode="before")
    @classmethod
    def resolve_qdrant_url(cls, value: Any) -> Any:
        return resolve_env_value(value, "QDRANT_URL")


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


class RateLimitConfig(BaseModel):
    """Rate limit configuration."""

    enabled: bool = Field(default=False, description="Enable rate limiting")
    per_minute: int = Field(default=60, description="Requests per minute")


class ApiConfig(BaseModel):
    """HTTP API configuration."""

    title: str = Field(default="SwarmMind API", description="API title")
    description: str = Field(
        default="A general-purpose AI task assistant API",
        description="API description",
    )
    version: str = Field(default="0.1.0", description="API version")
    host: str = Field(default="127.0.0.1", description="API bind host")
    port: int = Field(default=8000, ge=1, le=65535, description="API bind port")
    reload: bool = Field(default=False, description="Enable uvicorn reload")


class IdentityConfig(BaseModel):
    """Default identity configuration for local development."""

    default_tenant_id: str = Field(default="local", description="Default tenant id")
    default_principal_id: str = Field(default="developer", description="Default principal id")
    default_scopes: list[str] = Field(
        default_factory=lambda: ["tasks:submit", "tasks:read", "runs:read"],
        description="Default scopes for static identity resolution",
    )
    default_roles: list[str] = Field(
        default_factory=lambda: ["developer"],
        description="Default roles for static identity resolution",
    )
    auth_method: str = Field(default="static", description="Default auth method label")