"""Validation helpers for local skill packages."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from swarmmind.skill_system.models import ParsedSkill


_RELATIVE_RESOURCE_LINK_PATTERN = re.compile(
    r"(?:\(|:\s*)(?P<path>(?:scripts|references|assets)/[^)\s]+)"
)


def validate_parsed_skill(parsed_skill: ParsedSkill) -> list[str]:
    """Validate a parsed local skill package and return a list of errors."""
    errors: list[str] = []
    metadata = parsed_skill.metadata

    if not metadata.name.strip():
        errors.append("Frontmatter field 'name' must be a non-empty string")

    if not metadata.description.strip():
        errors.append("Frontmatter field 'description' must be a non-empty string")

    if metadata.version is not None and not metadata.version.strip():
        errors.append("Frontmatter field 'version' must not be blank")

    if metadata.license is not None and not metadata.license.strip():
        errors.append("Frontmatter field 'license' must not be blank")

    if metadata.source_url is not None:
        parsed_url = urlparse(metadata.source_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            errors.append("Frontmatter field 'source_url' must be a valid http(s) URL")

    for field_name in ("compatibility", "allowed_tools", "required_env", "required_bins"):
        field_value = getattr(metadata, field_name)
        if any(not isinstance(item, str) or not item.strip() for item in field_value):
            errors.append(f"Frontmatter field '{field_name}' must contain only non-empty strings")

    expected_dir_name = parsed_skill.root_dir.name
    if metadata.name != expected_dir_name:
        errors.append(
            f"Skill name '{metadata.name}' must match directory name '{expected_dir_name}'"
        )

    if not parsed_skill.body.strip():
        errors.append("SKILL.md body must not be empty")

    for match in _RELATIVE_RESOURCE_LINK_PATTERN.finditer(parsed_skill.body):
        relative_path = match.group("path")
        if not (parsed_skill.root_dir / relative_path).is_file():
            errors.append(f"Referenced resource does not exist: {relative_path}")

    for relative_path in (
        *parsed_skill.resources.scripts,
        *parsed_skill.resources.references,
        *parsed_skill.resources.assets,
    ):
        target = parsed_skill.root_dir / relative_path
        if not target.is_file():
            errors.append(f"Indexed resource does not exist: {relative_path}")

    return errors
