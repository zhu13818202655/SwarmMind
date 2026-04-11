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


def normalize_skill_profile_names(skill_names: list[str] | None) -> list[str]:
    """Normalize configured skill names to unique installed skill names."""
    if not skill_names:
        return []

    registry = load_skill_registry(get_agent_skill_root())
    installed_names = {entry.name for entry in registry.list_entries(include_invalid=True)}
    normalized: list[str] = []
    for raw_name in skill_names:
        name = str(raw_name).strip()
        if not name:
            continue
        if name in installed_names and name not in normalized:
            normalized.append(name)
    return normalized


def list_installed_skill_profile_names(*, include_invalid: bool = False) -> list[str]:
    """List installed skill profile names available in the local skill registry."""
    registry = load_skill_registry(get_agent_skill_root())
    return sorted({entry.name for entry in registry.list_entries(include_invalid=include_invalid)})


def resolve_agent_skill_entries(
    skill_names: list[str] | None,
    available_tool_names: set[str] | None = None,
) -> list[SkillEntry]:
    """Resolve configured skill names into usable local skill entries."""
    normalized_names = normalize_skill_profile_names(skill_names)
    if not normalized_names:
        return []

    registry = load_skill_registry(get_agent_skill_root(), normalized_names)
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