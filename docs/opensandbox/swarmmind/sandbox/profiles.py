"""Sandbox profile presets for different workloads."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SandboxProfile:
    image: str
    entrypoint: list[str]
    timeout_seconds: int
    resource_limits: dict[str, str] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)


DEFAULT_PROFILES: dict[str, SandboxProfile] = {
    "py-basic": SandboxProfile(
        image="python:3.11-slim",
        entrypoint=["tail", "-f", "/dev/null"],
        timeout_seconds=900,
        resource_limits={"cpu": "500m", "memory": "1Gi"},
        env={"PYTHONUNBUFFERED": "1"},
    ),
    "data-medium": SandboxProfile(
        image="python:3.11-slim",
        entrypoint=["tail", "-f", "/dev/null"],
        timeout_seconds=1800,
        resource_limits={"cpu": "1", "memory": "2Gi"},
        env={"PYTHONUNBUFFERED": "1"},
    ),
    "data-heavy": SandboxProfile(
        image="python:3.11-slim",
        entrypoint=["tail", "-f", "/dev/null"],
        timeout_seconds=3600,
        resource_limits={"cpu": "2", "memory": "4Gi"},
        env={"PYTHONUNBUFFERED": "1"},
    ),
}
