from __future__ import annotations

from swarmmind.config.schema import ModelConfig, SandboxConfig


def test_model_config_resolves_base_url_from_env_without_explicit_input(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/openai")

    config = ModelConfig()

    assert config.base_url == "https://example.invalid/openai"


def test_sandbox_config_prefers_env_base_url_over_default(monkeypatch) -> None:
    monkeypatch.setenv("OPEN_SANDBOX_BASE_URL", "http://127.0.0.1:9999")

    config = SandboxConfig(base_url="${OPEN_SANDBOX_BASE_URL}")

    assert config.base_url == "http://127.0.0.1:9999"


def test_sandbox_config_falls_back_to_default_when_placeholder_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("OPEN_SANDBOX_BASE_URL", raising=False)

    config = SandboxConfig(base_url="${OPEN_SANDBOX_BASE_URL}")

    assert config.base_url == "http://localhost:45698"


def test_sandbox_config_falls_back_to_default_when_env_is_null_string(monkeypatch) -> None:
    monkeypatch.setenv("OPEN_SANDBOX_BASE_URL", "null")

    config = SandboxConfig(base_url="${OPEN_SANDBOX_BASE_URL}")

    assert config.base_url == "http://localhost:45698"