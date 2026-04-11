"""Sandbox profiles configuration."""

from dataclasses import dataclass

from swarmmind.defaults import DEFAULT_AIO_IMAGE, DEFAULT_SANDBOX_PROFILE
LEGACY_SANDBOX_PROFILE_ALIASES: dict[str, str] = {
    "py-basic": DEFAULT_SANDBOX_PROFILE,
    "py-full": DEFAULT_SANDBOX_PROFILE,
    "node-basic": DEFAULT_SANDBOX_PROFILE,
    "research-net": DEFAULT_SANDBOX_PROFILE,
    "browser-playwright": DEFAULT_SANDBOX_PROFILE,
    "secure-offline": DEFAULT_SANDBOX_PROFILE,
}


@dataclass
class SandboxProfile:
    """Sandbox profile configuration."""

    name: str
    image: str
    entrypoint: list[str] | None = None
    timeout_seconds: int = 300
    env: dict[str, str] | None = None
    resource_limits: dict[str, str] | None = None


def normalize_sandbox_profile_name(profile: str | None) -> str:
    """Resolve a requested sandbox profile to the canonical profile name."""
    normalized = (profile or DEFAULT_SANDBOX_PROFILE).strip()
    if not normalized:
        return DEFAULT_SANDBOX_PROFILE
    return LEGACY_SANDBOX_PROFILE_ALIASES.get(normalized, normalized)


# Default sandbox profiles
DEFAULT_PROFILES: dict[str, SandboxProfile] = {
    DEFAULT_SANDBOX_PROFILE: SandboxProfile(
        name=DEFAULT_SANDBOX_PROFILE,
        image=DEFAULT_AIO_IMAGE,
        entrypoint=["/opt/opensandbox/code-interpreter.sh"],
        timeout_seconds=600,
        env={"PYTHONPATH": "/tmp", "PYTHON_VERSION": "3.11"},
        resource_limits={"cpu": "2000m", "memory": "2048Mi"},
    ),
}
