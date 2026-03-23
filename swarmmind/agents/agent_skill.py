"""Helpers for native AgentScope agent-skill registration."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys

from swarmmind.skill_system.catalog import build_compact_catalog_payload, build_expanded_catalog_payload
from swarmmind.skill_system.loader import get_skill_package_root, load_skill_registry
from swarmmind.skill_system.models import SkillEntry


def get_agent_skill_root() -> Path:
    """Return the directory containing native AgentScope skill folders."""
    return get_skill_package_root()


def resolve_agent_skill_dirs(skill_names: list[str] | None) -> list[Path]:
    """Resolve configured skill names into valid local skill directories."""
    return [entry.root_dir for entry in resolve_agent_skill_entries(skill_names)]


def resolve_agent_skill_entries(
    skill_names: list[str] | None,
    available_tool_names: set[str] | None = None,
) -> list[SkillEntry]:
    """Resolve configured skill names into usable local skill entries."""
    registry = load_skill_registry(get_agent_skill_root(), skill_names)
    entries = registry.list_entries(include_invalid=False)
    return [entry for entry in entries if _is_skill_entry_usable(entry, available_tool_names or set())]


def build_agent_skill_catalog(
    skill_names: list[str] | None,
    available_tool_names: set[str] | None = None,
) -> list[dict[str, str]]:
    """Build a compact catalog of usable local skills for an agent."""
    return build_compact_catalog_payload(resolve_agent_skill_entries(skill_names, available_tool_names))


def build_agent_skill_details(
    skill_names: list[str] | None,
    available_tool_names: set[str] | None = None,
) -> list[dict[str, object]]:
    """Build an expanded catalog of usable local skills for explicit inspection."""
    return build_expanded_catalog_payload(resolve_agent_skill_entries(skill_names, available_tool_names))


def _is_skill_entry_usable(entry: SkillEntry, available_tool_names: set[str]) -> bool:
    if entry.metadata.disabled or not entry.valid:
        return False

    if any(not os.environ.get(var_name) for var_name in entry.metadata.required_env):
        return False

    if any(shutil.which(binary_name) is None for binary_name in entry.metadata.required_bins):
        return False

    if entry.metadata.allowed_tools and not set(entry.metadata.allowed_tools).issubset(available_tool_names):
        return False

    if entry.metadata.compatibility and not set(entry.metadata.compatibility).intersection(_current_compatibility_tags()):
        return False

    return True


def _current_compatibility_tags() -> set[str]:
    platform_tags = {sys.platform, os.name, "any"}
    if sys.platform.startswith("linux"):
        platform_tags.add("linux")
    elif sys.platform == "darwin":
        platform_tags.add("macos")
    elif sys.platform in {"win32", "cygwin"}:
        platform_tags.add("windows")
    return platform_tags