"""Configuration schema models for SwarmMind."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from swarmmind.config.env import resolve_env_value
from swarmmind.defaults import DEFAULT_SANDBOX_PROFILE


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
    default_profile: str = Field(default=DEFAULT_SANDBOX_PROFILE, description="Default sandbox profile")
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
        return resolve_env_value(value, "OPEN_SANDBOX_BASE_URL")

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


class RepositoryConfig(ValidatedDefaultsModel):
    """Repository backend configuration for development and testing."""

    replay_backend: str = Field(default="memory", description="Replay repository backend: memory, file, postgres")
    artifact_backend: str = Field(default="memory", description="Artifact repository backend: memory, file, postgres")
    file_base_path: str = Field(default="./data", description="Base directory for file-backed repositories")

    @field_validator("replay_backend", mode="before")
    @classmethod
    def resolve_replay_backend(cls, value: Any) -> Any:
        return resolve_env_value(value, "SWARMMIND_REPOSITORIES__REPLAY_BACKEND")

    @field_validator("artifact_backend", mode="before")
    @classmethod
    def resolve_artifact_backend(cls, value: Any) -> Any:
        return resolve_env_value(value, "SWARMMIND_REPOSITORIES__ARTIFACT_BACKEND")

    @field_validator("file_base_path", mode="before")
    @classmethod
    def resolve_file_base_path(cls, value: Any) -> Any:
        return resolve_env_value(value, "SWARMMIND_REPOSITORIES__FILE_BASE_PATH")


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


class SearchConfig(ValidatedDefaultsModel):
    """Search provider configuration for result-page retrieval."""

    provider: str = Field(default="duckduckgo", description="Search provider: duckduckgo, brave, bing, serpapi, tavily, google_cse")
    api_key: str | None = Field(default=None, description="Provider API key when required")
    base_url: str | None = Field(default=None, description="Optional provider endpoint override")
    timeout_seconds: float = Field(default=10.0, description="Timeout in seconds for search calls")
    default_max_results: int = Field(default=5, description="Default maximum number of results")
    google_cse_id: str | None = Field(default=None, description="Google Custom Search engine identifier")
    market: str = Field(default="en-US", description="Regional market hint for supported providers")
    safe_search: str = Field(default="moderate", description="Safe search mode where supported")

    @field_validator("provider", mode="before")
    @classmethod
    def resolve_provider(cls, value: Any) -> Any:
        resolved = resolve_env_value(None if value == "duckduckgo" else value, "SWARMMIND_SEARCH__PROVIDER")
        return "duckduckgo" if resolved is None else resolved

    @field_validator("api_key", mode="before")
    @classmethod
    def resolve_api_key(cls, value: Any) -> Any:
        return resolve_env_value(
            value,
            "SWARMMIND_SEARCH__API_KEY",
            "TAVILY_API_KEY",
            "BRAVE_SEARCH_API_KEY",
            "SERPAPI_API_KEY",
            "BING_SEARCH_API_KEY",
            "GOOGLE_SEARCH_API_KEY",
        )

    @field_validator("base_url", mode="before")
    @classmethod
    def resolve_base_url(cls, value: Any) -> Any:
        return resolve_env_value(value, "SWARMMIND_SEARCH__BASE_URL")

    @field_validator("timeout_seconds", mode="before")
    @classmethod
    def resolve_timeout_seconds(cls, value: Any) -> Any:
        resolved = resolve_env_value(None if value == 10.0 else value, "SWARMMIND_SEARCH__TIMEOUT_SECONDS", cast_type=float)
        return 10.0 if resolved is None else resolved

    @field_validator("default_max_results", mode="before")
    @classmethod
    def resolve_default_max_results(cls, value: Any) -> Any:
        resolved = resolve_env_value(None if value == 5 else value, "SWARMMIND_SEARCH__DEFAULT_MAX_RESULTS", cast_type=int)
        return 5 if resolved is None else resolved

    @field_validator("google_cse_id", mode="before")
    @classmethod
    def resolve_google_cse_id(cls, value: Any) -> Any:
        return resolve_env_value(value, "SWARMMIND_SEARCH__GOOGLE_CSE_ID", "GOOGLE_CSE_ID")

    @field_validator("market", mode="before")
    @classmethod
    def resolve_market(cls, value: Any) -> Any:
        resolved = resolve_env_value(None if value == "en-US" else value, "SWARMMIND_SEARCH__MARKET")
        return "en-US" if resolved is None else resolved

    @field_validator("safe_search", mode="before")
    @classmethod
    def resolve_safe_search(cls, value: Any) -> Any:
        resolved = resolve_env_value(None if value == "moderate" else value, "SWARMMIND_SEARCH__SAFE_SEARCH")
        return "moderate" if resolved is None else resolved


class BrowserConfig(ValidatedDefaultsModel):
    """Browser/detail retrieval configuration."""

    detail_provider: str = Field(default="direct", description="Detail provider: direct, reader, or jina_reader")
    reader_base_url: str = Field(default="https://r.jina.ai/http://", description="Reader API prefix for article extraction")
    timeout_seconds: float = Field(default=30.0, description="Timeout in seconds for detail fetches")
    user_agent: str = Field(default="SwarmMindBrowser/1.0", description="Default user agent for outbound browser requests")

    @field_validator("detail_provider", mode="before")
    @classmethod
    def resolve_detail_provider(cls, value: Any) -> Any:
        resolved = resolve_env_value(None if value == "direct" else value, "SWARMMIND_BROWSER__DETAIL_PROVIDER")
        if resolved is None:
            return "direct"
        normalized = str(resolved).strip().lower()
        if normalized == "jina":
            return "jina_reader"
        return normalized

    @field_validator("reader_base_url", mode="before")
    @classmethod
    def resolve_reader_base_url(cls, value: Any) -> Any:
        resolved = resolve_env_value(None if value == "https://r.jina.ai/http://" else value, "SWARMMIND_BROWSER__READER_BASE_URL")
        return "https://r.jina.ai/http://" if resolved is None else resolved

    @field_validator("timeout_seconds", mode="before")
    @classmethod
    def resolve_timeout_seconds(cls, value: Any) -> Any:
        resolved = resolve_env_value(None if value == 30.0 else value, "SWARMMIND_BROWSER__TIMEOUT_SECONDS", cast_type=float)
        return 30.0 if resolved is None else resolved

    @field_validator("user_agent", mode="before")
    @classmethod
    def resolve_user_agent(cls, value: Any) -> Any:
        resolved = resolve_env_value(None if value == "SwarmMindBrowser/1.0" else value, "SWARMMIND_BROWSER__USER_AGENT")
        return "SwarmMindBrowser/1.0" if resolved is None else resolved


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

class FlyReportDikongConfig(ValidatedDefaultsModel):
    """Dikong upstream API configuration for the FlyReport domain."""

    base_url: str = Field(
        default="http://127.0.0.1:50284",
        description="Dikong API base URL (no trailing slash)",
    )
    token: str | None = Field(
        default=None,
        description="Bearer / API token forwarded to dikong",
    )
    tenant_header: str = Field(
        default="X-Tenant-Id",
        description="Header name used to forward tenant id to dikong",
    )
    request_timeout_seconds: float = Field(
        default=15.0,
        description="Per-request timeout in seconds",
    )
    max_retries: int = Field(
        default=2,
        ge=0,
        description="Number of retries on transient failures (5xx / connect)",
    )
    retry_backoff_seconds: float = Field(
        default=0.5,
        ge=0.0,
        description="Base backoff for retries (exponential)",
    )
    max_concurrency: int = Field(
        default=8,
        ge=1,
        description="Max concurrent in-flight requests per client",
    )
    rate_limit_per_second: float = Field(
        default=10.0,
        gt=0.0,
        description="Token-bucket rate limit (req/s) enforced via aiolimiter",
    )

    @field_validator("base_url", mode="before")
    @classmethod
    def resolve_base_url(cls, value: Any) -> Any:
        return resolve_env_value(value, "DIKONG_BASE_URL")

    @field_validator("token", mode="before")
    @classmethod
    def resolve_token(cls, value: Any) -> Any:
        return resolve_env_value(value, "DIKONG_TOKEN")


class FlyReportConfig(ValidatedDefaultsModel):
    """Domain-level configuration for FlyReport."""

    enabled: bool = Field(default=True, description="Toggle for the FlyReport domain")
    dikong: FlyReportDikongConfig = Field(default_factory=FlyReportDikongConfig)
    intent: "FlyReportIntentConfig" = Field(
        default_factory=lambda: FlyReportIntentConfig(),
        description="Intent-parser wiring (rule-based vs LLM)",
    )

    @field_validator("enabled", mode="before")
    @classmethod
    def resolve_enabled(cls, value: Any) -> Any:
        return resolve_env_value(value, "SWARMMIND_FLY_REPORT__ENABLED", cast_type=bool)


class FlyReportIntentConfig(ValidatedDefaultsModel):
    """IntentParser configuration for FlyReport (DESIGN-3 R1.1)."""

    parser_kind: str = Field(
        default="rule",
        description="Which intent parser to use: 'rule' (no LLM) or 'llm'",
    )

    @field_validator("parser_kind", mode="before")
    @classmethod
    def resolve_parser_kind(cls, value: Any) -> Any:
        resolved = resolve_env_value(
            value, "SWARMMIND_FLY_REPORT__INTENT__PARSER_KIND"
        )
        if resolved is None:
            return "rule"
        normalized = str(resolved).lower().strip()
        if normalized not in {"rule", "llm"}:
            raise ValueError(
                f"fly_report.intent.parser_kind must be 'rule' or 'llm'; got {resolved!r}"
            )
        return normalized


FlyReportConfig.model_rebuild()
