"""Data models for local skill packages."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel, Field

from swarmmind.defaults import DEFAULT_SANDBOX_PROFILE

from swarmmind.utils import utc_now


class SkillSourceType(str, Enum):
    """Where a skill package came from."""

    BUILT_IN = "built-in"
    REPO_LOCAL = "repo-local"
    DOWNLOADED = "downloaded"
    GENERATED = "generated"


class SkillInstallState(str, Enum):
    """Current lifecycle state of a skill entry."""

    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    INVALID = "invalid"


class SkillMetadata(BaseModel):
    """Metadata parsed from a skill package frontmatter block."""

    name: str = Field(description="Unique skill name")
    description: str = Field(description="Short description used for discovery and triggering")
    version: str | None = Field(default=None, description="Optional skill version")
    license: str | None = Field(default=None, description="Optional license identifier")
    compatibility: list[str] = Field(default_factory=list, description="Compatibility tags")
    source_url: str | None = Field(default=None, description="Source repository or origin URL")
    source_type: SkillSourceType | None = Field(default=None, description="Optional source classification")
    disabled: bool = Field(default=False, description="Whether the skill is disabled")
    allowed_tools: list[str] = Field(default_factory=list, description="Optional tool allowlist")
    required_env: list[str] = Field(default_factory=list, description="Required environment variables")
    required_bins: list[str] = Field(default_factory=list, description="Required binaries")
    extra: dict[str, object] = Field(default_factory=dict, description="Unmodeled frontmatter fields")


class SkillResourceIndex(BaseModel):
    """Discovered resource files that belong to a skill package."""

    scripts: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)


class ParsedSkill(BaseModel):
    """Fully parsed local skill package."""

    root_dir: Path
    skill_file: Path
    metadata: SkillMetadata
    body: str
    resources: SkillResourceIndex = Field(default_factory=SkillResourceIndex)


class SkillEntry(BaseModel):
    """Registry entry for a local skill package."""

    skill_id: str
    root_dir: Path
    skill_file: Path
    metadata: SkillMetadata
    body: str
    resources: SkillResourceIndex = Field(default_factory=SkillResourceIndex)
    source_type: SkillSourceType = Field(default=SkillSourceType.BUILT_IN)
    install_state: SkillInstallState = Field(default=SkillInstallState.ENABLED)
    valid: bool = True
    errors: list[str] = Field(default_factory=list)

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def description(self) -> str:
        return self.metadata.description


class CompactSkillCatalogEntry(BaseModel):
    """Compact catalog view for prompt-time discovery."""

    name: str
    description: str
    source_type: SkillSourceType
    install_state: SkillInstallState


class ExpandedSkillCatalogEntry(BaseModel):
    """Expanded catalog view for explicit inspection and UI surfaces."""

    name: str
    description: str
    body: str
    source_type: SkillSourceType
    install_state: SkillInstallState
    resources: SkillResourceIndex
    metadata: SkillMetadata


class SkillScriptExecutionPolicy(BaseModel):
    """Policy and runtime options for skill script execution."""

    allow_sandbox_exec: bool = Field(default=False)
    sandbox_profile: str = Field(default=DEFAULT_SANDBOX_PROFILE)
    sandbox_root: str = Field(default="/workspace/skill")
    environment: dict[str, str] = Field(default_factory=dict)
    artifact_paths: list[str] = Field(default_factory=list)
    script_args: list[str] = Field(default_factory=list)


class SkillExecutionContext(BaseModel):
    """Execution context used for audit, replay, and artifact persistence."""

    tenant_id: str = Field(default="system")
    session_id: str | None = Field(default=None)
    task_id: str | None = Field(default=None)
    run_id: str | None = Field(default=None)
    subtask_id: str | None = Field(default=None)


class SkillScriptExecutionResult(BaseModel):
    """Normalized result of running a skill script in a sandbox."""

    skill_name: str
    script_path: str
    sandbox_id: str
    command: str
    cwd: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    artifacts: dict[str, str] = Field(default_factory=dict)
    artifact_payloads: dict[str, bytes] = Field(default_factory=dict, exclude=True)
    executed_at: datetime = Field(default_factory=utc_now)
