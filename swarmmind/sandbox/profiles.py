"""Sandbox profiles configuration."""

from dataclasses import dataclass


@dataclass
class SandboxProfile:
    """Sandbox profile configuration."""

    name: str
    image: str
    entrypoint: str = "/bin/bash"
    timeout_seconds: int = 300
    env: dict[str, str] | None = None
    resource_limits: dict[str, int] | None = None


# Default sandbox profiles
DEFAULT_PROFILES: dict[str, SandboxProfile] = {
    "py-basic": SandboxProfile(
        name="py-basic",
        image="opensandbox/code-interpreter:python3.11",
        timeout_seconds=300,
        env={"PYTHONPATH": "/tmp"},
        resource_limits={"cpu": 2, "memory": 2048},
    ),
    "py-full": SandboxProfile(
        name="py-full",
        image="opensandbox/code-interpreter:python3.11-full",
        timeout_seconds=600,
        env={"PYTHONPATH": "/tmp"},
        resource_limits={"cpu": 4, "memory": 4096},
    ),
    "node-basic": SandboxProfile(
        name="node-basic",
        image="opensandbox/code-interpreter:node20",
        timeout_seconds=300,
        resource_limits={"cpu": 2, "memory": 2048},
    ),
    "secure-offline": SandboxProfile(
        name="secure-offline",
        image="opensandbox/code-interpreter:python3.11-secure",
        timeout_seconds=300,
        env={"ALLOW_NETWORK": "false"},
        resource_limits={"cpu": 1, "memory": 1024},
    ),
}
