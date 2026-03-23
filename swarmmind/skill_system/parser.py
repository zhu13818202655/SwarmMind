"""Parser for local SKILL.md-based packages."""

from __future__ import annotations

from pathlib import Path
import re

import yaml

from swarmmind.skill_system.models import ParsedSkill, SkillMetadata
from swarmmind.skill_system.resources import build_resource_index


_FRONTMATTER_PATTERN = re.compile(
    r"\A---\s*\n(?P<frontmatter>.*?)\n---\s*\n?(?P<body>.*)\Z",
    re.DOTALL,
)
_KNOWN_METADATA_FIELDS = {
    "name",
    "description",
    "version",
    "license",
    "compatibility",
    "source_url",
    "source_type",
    "disabled",
    "allowed_tools",
    "required_env",
    "required_bins",
}
_FIELD_ALIASES = {
    "source-url": "source_url",
    "source-type": "source_type",
    "allowed-tools": "allowed_tools",
    "required-env": "required_env",
    "required-bins": "required_bins",
}


def parse_skill_text(text: str) -> tuple[SkillMetadata, str]:
    """Parse frontmatter and markdown body from SKILL.md text."""
    match = _FRONTMATTER_PATTERN.match(text)
    if match is None:
        raise ValueError("SKILL.md must start with a YAML frontmatter block delimited by ---")

    frontmatter_text = match.group("frontmatter")
    body = match.group("body").strip()
    raw_data = yaml.safe_load(frontmatter_text) or {}
    if not isinstance(raw_data, dict):
        raise ValueError("SKILL.md frontmatter must be a mapping")

    normalized_data = {
        _FIELD_ALIASES.get(key, key): value
        for key, value in raw_data.items()
    }

    modeled_data = {
        key: value for key, value in normalized_data.items() if key in _KNOWN_METADATA_FIELDS
    }
    extra_data = {
        key: value for key, value in normalized_data.items() if key not in _KNOWN_METADATA_FIELDS
    }
    metadata = SkillMetadata(**modeled_data, extra=extra_data)
    return metadata, body


def parse_skill_dir(skill_dir: Path) -> ParsedSkill:
    """Parse a local skill directory into a structured representation."""
    root_dir = skill_dir.resolve()
    skill_file = root_dir / "SKILL.md"
    if not skill_file.is_file():
        raise FileNotFoundError(f"SKILL.md not found under {root_dir}")

    metadata, body = parse_skill_text(skill_file.read_text(encoding="utf-8"))
    return ParsedSkill(
        root_dir=root_dir,
        skill_file=skill_file,
        metadata=metadata,
        body=body,
        resources=build_resource_index(root_dir),
    )
