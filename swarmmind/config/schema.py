"""Configuration schema models for SwarmMind."""

from __future__ import annotations

from typing import Any, Literal

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
    temperature: float = Field(default=1.0, description="Temperature")
    max_tokens: int = Field(default=4096, description="Max tokens")

    @field_validator("api_key", mode="before")
    @classmethod
    def resolve_api_key(cls, value: Any) -> Any:
        return resolve_env_value(value, "OPENAI_API_KEY")

    @field_validator("base_url", mode="before")
    @classmethod
    def resolve_base_url(cls, value: Any) -> Any:
        return resolve_env_value(value, "OPENAI_BASE_URL")
    
    @field_validator("name", mode="before")
    @classmethod
    def resolve_name(cls, value: Any) -> Any:
        return resolve_env_value(value, "OPENAI_MODEL")


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
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed CORS origins",
    )
    cors_allow_credentials: bool = Field(
        default=False,
        description="Allow credentials in CORS requests",
    )


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
        default="http://127.0.0.1:50001",
        description="Dikong API base URL (no trailing slash)",
    )
    account: str | None = Field(
        default=None,
        description="Dikong login account (env: DIKONG_ACCOUNT)",
    )
    password: str | None = Field(
        default=None,
        description="Dikong login password (env: DIKONG_PASSWORD)",
    )
    token_ttl_seconds: int = Field(
        default=720,
        ge=1,
        description="Lifetime of an access token (dikong default is 720s)",
    )
    token_refresh_skew_seconds: int = Field(
        default=60,
        ge=0,
        description=(
            "Refresh the token this many seconds before expiry to avoid "
            "tail-latency 401s under clock skew."
        ),
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

    department_id_list: list[str] = Field(
        default_factory=list,
        description="Optional list of department IDs to filter reports by; if empty, no department filtering is applied",
    )

    @field_validator("base_url", mode="before")
    @classmethod
    def resolve_base_url(cls, value: Any) -> Any:
        return resolve_env_value(value, "DIKONG_BASE_URL")

    @field_validator("account", mode="before")
    @classmethod
    def resolve_account(cls, value: Any) -> Any:
        return resolve_env_value(value, "DIKONG_ACCOUNT")

    @field_validator("password", mode="before")
    @classmethod
    def resolve_password(cls, value: Any) -> Any:
        return resolve_env_value(value, "DIKONG_PASSWORD")


class FlyReportPostgresConfig(ValidatedDefaultsModel):
    """PostgreSQL connection settings for the FlyReport SQL data fetcher.

    Used by :class:`swarmmind.domains.fly_report.dikong_sql.client.DikongSqlClient`
    to drive a single ``psycopg_pool.AsyncConnectionPool`` per process.
    Credentials must come from environment variables – never commit a real DSN.
    """

    dsn: str | None = Field(
        default=None,
        description=(
            "PostgreSQL DSN, e.g. ``postgresql://user:pwd@host:port/dbname``. "
            "Resolved from env: FLY_REPORT_DIKONG_PG_DSN."
        ),
    )
    pool_min_size: int = Field(default=2, ge=0)
    pool_max_size: int = Field(default=10, ge=1)
    pool_timeout_seconds: float = Field(default=10.0, gt=0.0)
    statement_timeout_ms: int = Field(default=30_000, ge=100)
    server_side_cursor_itersize: int = Field(default=5_000, ge=1)
    application_name: str = Field(default="swarmmind-fly-report")
    fly_job_logs_row_cap: int = Field(
        default=1_000_000,
        ge=1,
        description="Hard SQL-side LIMIT applied to fly_job_logs to avoid OOM.",
    )

    @field_validator("dsn", mode="before")
    @classmethod
    def resolve_dsn(cls, value: Any) -> Any:
        return resolve_env_value(
            value,
            "FLY_REPORT_DIKONG_PG_DSN",
            "SWARMMIND_FLY_REPORT__DIKONG_SQL__POSTGRES__DSN",
        )


class FlyReportTDengineConfig(ValidatedDefaultsModel):
    """TDengine REST connection settings for the FlyReport SQL data fetcher.

    Talks to taosAdapter (default port 6041). Credentials come from env.
    """

    base_url: str = Field(
        default="http://127.0.0.1:6041",
        description="taosAdapter base URL, e.g. http://host:6041",
    )
    database: str = Field(default="dikong")
    username: str = Field(default="root")
    password: str | None = Field(default=None)
    timeout_seconds: float = Field(default=30.0, gt=0.0)
    max_connections: int = Field(default=10, ge=1)
    max_keepalive_connections: int = Field(default=5, ge=0)
    verify_tls: bool = Field(default=True)
    max_retries: int = Field(default=1, ge=0)
    retry_backoff_seconds: float = Field(default=0.5, ge=0.0)

    @field_validator("base_url", mode="before")
    @classmethod
    def resolve_base_url(cls, value: Any) -> Any:
        return resolve_env_value(
            value,
            "FLY_REPORT_DIKONG_TDENGINE_URL",
            "SWARMMIND_FLY_REPORT__DIKONG_SQL__TDENGINE__BASE_URL",
        )

    @field_validator("database", mode="before")
    @classmethod
    def resolve_database(cls, value: Any) -> Any:
        return resolve_env_value(
            value, "FLY_REPORT_DIKONG_TDENGINE_DB"
        )

    @field_validator("username", mode="before")
    @classmethod
    def resolve_username(cls, value: Any) -> Any:
        return resolve_env_value(
            value, "FLY_REPORT_DIKONG_TDENGINE_USER"
        )

    @field_validator("password", mode="before")
    @classmethod
    def resolve_password(cls, value: Any) -> Any:
        return resolve_env_value(
            value, "FLY_REPORT_DIKONG_TDENGINE_PASSWORD"
        )


class FlyReportDikongSqlConfig(ValidatedDefaultsModel):
    """Combined PG + TDengine settings driving the SQL data fetcher."""

    postgres: FlyReportPostgresConfig = Field(default_factory=FlyReportPostgresConfig)
    tdengine: FlyReportTDengineConfig = Field(default_factory=FlyReportTDengineConfig)


class FlyReportText2SqlConfig(ValidatedDefaultsModel):
    """Configuration for the FlyReport Text-to-SQL data-query pipeline.

    Backed by a Vanna 2.0 multi-tool agent. Business knowledge lives in
    hand-curated YAML files under :attr:`knowledge_path`
    (``tables.yaml`` / ``metrics.yaml`` / ``golden_qa.yaml``). The agent
    drives a tool loop that calls schema introspection, business-knowledge
    lookups, and a guarded SQL runner against PostgreSQL.
    """

    enabled: bool = Field(
        default=True,
        description="Toggle for the Text-to-SQL data-query branch",
    )
    knowledge_path: str = Field(
        default="./data/fly_report_text2sql/knowledge",
        description=(
            "Directory containing tables.yaml / metrics.yaml / "
            "golden_qa.yaml — the agent's business knowledge base."
        ),
    )
    postgres_dsn: str | None = Field(
        default=None,
        description=(
            "PostgreSQL DSN used by the agent's guarded SQL tool. "
            "Required when the data-query branch is enabled."
        ),
    )
    statement_timeout_ms: int = Field(
        default=15000,
        ge=100,
        description="Per-statement timeout (ms) appended to the DSN options",
    )
    max_rows: int = Field(
        default=200,
        ge=1,
        description="Row cap applied when capturing tool results",
    )
    max_tool_iterations: int = Field(
        default=10,
        ge=1,
        description="Upper bound on the agent's tool-call loop per turn",
    )

    @field_validator("enabled", mode="before")
    @classmethod
    def resolve_enabled(cls, value: Any) -> Any:
        return resolve_env_value(
            value, "SWARMMIND_FLY_REPORT__TEXT2SQL__ENABLED", cast_type=bool
        )

    @field_validator("knowledge_path", mode="before")
    @classmethod
    def resolve_knowledge_path(cls, value: Any) -> Any:
        return resolve_env_value(
            value, "SWARMMIND_FLY_REPORT__TEXT2SQL__KNOWLEDGE_PATH"
        )

    @field_validator("postgres_dsn", mode="before")
    @classmethod
    def resolve_postgres_dsn(cls, value: Any) -> Any:
        return resolve_env_value(
            value,
            "SWARMMIND_FLY_REPORT__TEXT2SQL__POSTGRES_DSN",
            "FLY_REPORT_TEXT2SQL_DSN",
        )


class FlyReportConfig(ValidatedDefaultsModel):
    """Domain-level configuration for FlyReport."""

    enabled: bool = Field(default=True, description="Toggle for the FlyReport domain")
    source: Literal["http", "sql"] = Field(
        default="http",
        description=(
            "Data source for the FlyReport pipeline. ``http`` uses the dikong "
            "REST client; ``sql`` reads PostgreSQL + TDengine directly via "
            ":class:`DikongSqlClient`."
        ),
    )
    dikong: FlyReportDikongConfig = Field(default_factory=FlyReportDikongConfig)
    dikong_sql: FlyReportDikongSqlConfig = Field(
        default_factory=FlyReportDikongSqlConfig,
        description="PG + TDengine settings used when ``source == 'sql'``.",
    )
    text2sql: FlyReportText2SqlConfig = Field(default_factory=FlyReportText2SqlConfig)

    @field_validator("enabled", mode="before")
    @classmethod
    def resolve_enabled(cls, value: Any) -> Any:
        return resolve_env_value(value, "SWARMMIND_FLY_REPORT__ENABLED", cast_type=bool)

    @field_validator("source", mode="before")
    @classmethod
    def resolve_source(cls, value: Any) -> Any:
        return resolve_env_value(value, "SWARMMIND_FLY_REPORT__SOURCE")
