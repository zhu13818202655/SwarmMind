"""Helpers for indexing skill package resource directories."""

from __future__ import annotations

from pathlib import Path

from swarmmind.skill_system.models import SkillResourceIndex


def _collect_relative_files(root: Path, directory_name: str) -> list[str]:
    resource_dir = root / directory_name
    if not resource_dir.is_dir():
        return []

    return sorted(
        str(path.relative_to(root))
        for path in resource_dir.rglob("*")
        if path.is_file()
    )


def build_resource_index(skill_root: Path) -> SkillResourceIndex:
    """Build a resource index for a skill package root."""
    return SkillResourceIndex(
        scripts=_collect_relative_files(skill_root, "scripts"),
        references=_collect_relative_files(skill_root, "references"),
        assets=_collect_relative_files(skill_root, "assets"),
    )


def read_skill_resource(skill_root: Path, relative_path: str) -> str:
    """Read a single resource file relative to a skill root."""
    target = (skill_root / relative_path).resolve()
    if skill_root.resolve() not in target.parents and target != skill_root.resolve():
        raise ValueError(f"Resource path escapes skill root: {relative_path}")
    return target.read_text(encoding="utf-8")


def collect_skill_files(skill_root: Path) -> list[tuple[str, str]]:
    """Collect all files in a skill package as relative path and text content pairs."""
    root = skill_root.resolve()
    collected: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative_path = str(path.relative_to(root))
        collected.append((relative_path, path.read_text(encoding="utf-8")))
    return collected
