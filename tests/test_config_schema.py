from __future__ import annotations

from swarmmind.config.schema import BrowserConfig, ModelConfig, SandboxConfig, SearchConfig


def test_model_config_resolves_base_url_from_env_without_explicit_input(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/openai")

    config = ModelConfig()

    assert config.base_url == "https://example.invalid/openai"


def test_sandbox_config_prefers_env_base_url_over_default(monkeypatch) -> None:
    monkeypatch.setenv("OPEN_SANDBOX_BASE_URL", "http://127.0.0.1:9999")

    config = SandboxConfig(base_url="${OPEN_SANDBOX_BASE_URL}")

    assert config.base_url == "http://127.0.0.1:9999"


def test_search_config_resolves_provider_specific_values_from_env(monkeypatch) -> None:
    monkeypatch.setenv("SWARMMIND_SEARCH__PROVIDER", "bing")
    monkeypatch.setenv("SWARMMIND_SEARCH__API_KEY", "search-secret")
    monkeypatch.setenv("SWARMMIND_SEARCH__DEFAULT_MAX_RESULTS", "8")

    config = SearchConfig()

    assert config.provider == "bing"
    assert config.api_key == "search-secret"
    assert config.default_max_results == 8


def test_browser_config_resolves_detail_provider_from_env(monkeypatch) -> None:
    monkeypatch.setenv("SWARMMIND_BROWSER__DETAIL_PROVIDER", "reader")
    monkeypatch.setenv("SWARMMIND_BROWSER__READER_BASE_URL", "https://reader.example/")

    config = BrowserConfig()

    assert config.detail_provider == "reader"
    assert config.reader_base_url == "https://reader.example/"