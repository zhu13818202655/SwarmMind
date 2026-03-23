"""Loading helpers for local skill packages."""

from __future__ import annotations

from pathlib import Path

from swarmmind.skill_system.models import SkillEntry, SkillInstallState, SkillSourceType
from swarmmind.skill_system.parser import parse_skill_dir
from swarmmind.skill_system.registry import SkillRegistry
from swarmmind.skill_system.validator import validate_parsed_skill


def get_skill_package_root() -> Path:
    """Return the local skill package root."""
    package_root = Path(__file__).resolve().parent.parent
    return package_root / "skills"


def iter_skill_dirs(root: Path | None = None) -> list[Path]:
    """List skill directories under a local root."""
    skill_root = (root or get_skill_package_root()).resolve()
    if not skill_root.is_dir():
        return []

    return sorted(
        [child for child in skill_root.iterdir() if child.is_dir() and (child / "SKILL.md").is_file()],
        key=lambda path: path.name,
    )


def load_skill_dir(skill_dir: Path) -> SkillEntry:
    """Load a single skill directory into a registry entry."""
    resolved_dir = skill_dir.resolve()
    skill_file = resolved_dir / "SKILL.md"
    source_type = _infer_source_type(resolved_dir)
    try:
        parsed_skill = parse_skill_dir(resolved_dir)
    except Exception as exc:
        return SkillEntry(
            skill_id=resolved_dir.name,
            root_dir=resolved_dir,
            skill_file=skill_file,
            metadata={"name": resolved_dir.name, "description": ""},
            body="",
            source_type=source_type,
            install_state=SkillInstallState.INVALID,
            valid=False,
            errors=[str(exc)],
        )

    errors = validate_parsed_skill(parsed_skill)
    effective_source_type = parsed_skill.metadata.source_type or source_type
    install_state = SkillInstallState.INVALID if errors else (
        SkillInstallState.DISABLED if parsed_skill.metadata.disabled else SkillInstallState.ENABLED
    )
    return SkillEntry(
        skill_id=parsed_skill.metadata.name,
        root_dir=parsed_skill.root_dir,
        skill_file=parsed_skill.skill_file,
        metadata=parsed_skill.metadata,
        body=parsed_skill.body,
        resources=parsed_skill.resources,
        source_type=effective_source_type,
        install_state=install_state,
        valid=not errors,
        errors=errors,
    )


def load_skill_entries(root: Path | None = None, skill_names: list[str] | None = None) -> list[SkillEntry]:
    """Load all matching skill entries from the local skill root."""
    entries = [load_skill_dir(skill_dir) for skill_dir in iter_skill_dirs(root)]
    if skill_names:
        requested = set(skill_names)
        entries = [entry for entry in entries if entry.name in requested]
    return entries


def load_skill_registry(root: Path | None = None, skill_names: list[str] | None = None) -> SkillRegistry:
    """Load matching local skills into an in-memory registry."""
    registry = SkillRegistry()
    for entry in load_skill_entries(root, skill_names):
        registry.register(entry)
    return registry


def _infer_source_type(skill_dir: Path) -> SkillSourceType:
    package_root = Path(__file__).resolve().parent.parent.resolve()
    built_in_roots = [package_root / "skills"]
    if any(root.resolve() in skill_dir.parents for root in built_in_roots if root.exists()):
        return SkillSourceType.BUILT_IN
    return SkillSourceType.REPO_LOCAL
