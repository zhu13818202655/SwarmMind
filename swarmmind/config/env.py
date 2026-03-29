"""Environment helper utilities for SwarmMind settings."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SECRETS_DIR = PROJECT_ROOT / ".secrets"
ENV_PLACEHOLDER_PATTERN = re.compile(r"^\$\{([A-Z0-9_]+)\}$")


def _normalize_env_scalar(value: Any) -> Any:
    if isinstance(value, str) and value.strip().lower() in {"null", "none"}:
        return None
    return value


def resolve_env_value(value: Any, *env_names: str, cast_type: type | None = None) -> Any:
    """Resolve ${VAR} placeholders and well-known environment fallbacks."""
    if isinstance(value, str):
        matched = ENV_PLACEHOLDER_PATTERN.fullmatch(value.strip())
        if matched:
            env_value = _normalize_env_scalar(os.getenv(matched.group(1)))
            if env_value is None:
                return None
            value = env_value

    value = _normalize_env_scalar(value)

    if value in (None, ""):
        for env_name in env_names:
            env_value = _normalize_env_scalar(os.getenv(env_name))
            if env_value not in (None, ""):
                value = env_value
                break

    if value is None or cast_type is None:
        return value

    if cast_type is bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    return cast_type(value)