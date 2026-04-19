"""Settings loader and cache for SwarmMind."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import (
    JsonConfigSettingsSource,
    TomlConfigSettingsSource,
    YamlConfigSettingsSource,
)

from swarmmind.config.env import PROJECT_ROOT, SECRETS_DIR
from swarmmind.config.schema import (
    AgentConfig,
    ApiConfig,
    BrowserConfig,
    FlyReportConfig,
    IdentityConfig,
    PostgresConfig,
    RateLimitConfig,
    RedisConfig,
    RepositoryConfig,
    SandboxConfig,
    SearchConfig,
    VectorStoreConfig,
)


class SwarmMindConfig(BaseSettings):
    """SwarmMind configuration."""

    model_config = SettingsConfigDict(
        env_prefix="SWARMMIND_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        env_nested_delimiter="__",
        json_file=[PROJECT_ROOT / "config.json"],
        yaml_file=[
            PROJECT_ROOT / "configs/default.yaml",
            PROJECT_ROOT / "configs/fly_report.yaml",
            PROJECT_ROOT / "config.yaml",
        ],
        yaml_file_encoding="utf-8",
        toml_file=[PROJECT_ROOT / "config.toml"],
        secrets_dir=SECRETS_DIR if SECRETS_DIR.is_dir() else None,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            JsonConfigSettingsSource(settings_cls, deep_merge=True),
            YamlConfigSettingsSource(settings_cls, deep_merge=True),
            TomlConfigSettingsSource(settings_cls, deep_merge=True),
            file_secret_settings,
        )

    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)
    repositories: RepositoryConfig = Field(default_factory=RepositoryConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    identity: IdentityConfig = Field(default_factory=IdentityConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    fly_report: FlyReportConfig = Field(default_factory=FlyReportConfig)
    log_level: str = Field(default="INFO", description="Log level")
    storage_path: str = Field(default="./data", description="Data storage path")

    def safe_summary(self) -> dict[str, Any]:
        """Return a masked summary that is safe to log."""
        data = self.model_dump(mode="json")

        sandbox = data.get("sandbox")
        if isinstance(sandbox, dict) and sandbox.get("api_key"):
            sandbox["api_key"] = "********"

        agent = data.get("agent")
        if isinstance(agent, dict):
            model = agent.get("model")
            if isinstance(model, dict) and model.get("api_key"):
                model["api_key"] = "********"

        fly_report = data.get("fly_report")
        if isinstance(fly_report, dict):
            dikong = fly_report.get("dikong")
            if isinstance(dikong, dict) and dikong.get("token"):
                dikong["token"] = "********"

        return data


@lru_cache(maxsize=1)
def get_settings() -> SwarmMindConfig:
    """Return cached application settings."""
    return SwarmMindConfig()