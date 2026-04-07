"""Sandbox profiles configuration."""

from dataclasses import dataclass


@dataclass
class SandboxProfile:
    """Sandbox profile configuration."""

    name: str
    image: str
    entrypoint: list[str] | None = None
    timeout_seconds: int = 300
    env: dict[str, str] | None = None
    resource_limits: dict[str, str] | None = None


# Default sandbox profiles
DEFAULT_INTERPRETER_IMAGE = "sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.0.1"
DEFAULT_PLAYWRIGHT_IMAGE = "sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/playwright:latest"

DEFAULT_PROFILES: dict[str, SandboxProfile] = {
    "py-basic": SandboxProfile(
        name="py-basic",
        image=DEFAULT_INTERPRETER_IMAGE,
        entrypoint=["/opt/opensandbox/code-interpreter.sh"],
        timeout_seconds=300,
        env={"PYTHONPATH": "/tmp", "PYTHON_VERSION": "3.11"},
        resource_limits={"cpu": "1000m", "memory": "1024Mi"},
    ),
    "py-full": SandboxProfile(
        name="py-full",
        image=DEFAULT_INTERPRETER_IMAGE,
        entrypoint=["/opt/opensandbox/code-interpreter.sh"],
        timeout_seconds=600,
        env={"PYTHONPATH": "/tmp", "PYTHON_VERSION": "3.11"},
        resource_limits={"cpu": "2000m", "memory": "2048Mi"},
    ),
    "node-basic": SandboxProfile(
        name="node-basic",
        image=DEFAULT_INTERPRETER_IMAGE,
        entrypoint=["/opt/opensandbox/code-interpreter.sh"],
        timeout_seconds=300,
        resource_limits={"cpu": "1000m", "memory": "1024Mi"},
    ),
    "browser-playwright": SandboxProfile(
        name="browser-playwright",
        image=DEFAULT_PLAYWRIGHT_IMAGE,
        timeout_seconds=300,
        resource_limits={"cpu": "1000m", "memory": "1024Mi"},
    ),
    "secure-offline": SandboxProfile(
        name="secure-offline",
        image=DEFAULT_INTERPRETER_IMAGE,
        entrypoint=["/opt/opensandbox/code-interpreter.sh"],
        timeout_seconds=300,
        env={"ALLOW_NETWORK": "false", "PYTHON_VERSION": "3.11"},
        resource_limits={"cpu": "500m", "memory": "512Mi"},
    ),
}
