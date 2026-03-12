"""Application configuration loaded from environment variables."""

from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(slots=True)
class Settings:
    open_sandbox_api_key: str
    open_sandbox_base_url: str = "http://localhost:45698"
    create_retry_count: int = 3
    create_retry_backoff_seconds: float = 1.0


def load_settings() -> Settings:
    """Load runtime settings with strict API key validation."""
    api_key = os.getenv("OPEN_SANDBOX_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPEN_SANDBOX_API_KEY is required")

    base_url = os.getenv("OPEN_SANDBOX_BASE_URL", "http://localhost:45698").strip()
    retry_count = int(os.getenv("OPEN_SANDBOX_CREATE_RETRIES", "3"))
    retry_backoff = float(os.getenv("OPEN_SANDBOX_CREATE_BACKOFF_SECONDS", "1.0"))

    return Settings(
        open_sandbox_api_key=api_key,
        open_sandbox_base_url=base_url,
        create_retry_count=retry_count,
        create_retry_backoff_seconds=retry_backoff,
    )
