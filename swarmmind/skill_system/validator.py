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

    runtime_requirements = metadata.runtime_requirements
    for field_name in ("python_packages", "node_packages", "system_packages", "bootstrap_commands"):
        field_value = getattr(runtime_requirements, field_name)
        if any(not isinstance(item, str) or not item.strip() for item in field_value):
            errors.append(f"Runtime requirement field '{field_name}' must contain only non-empty strings")

    for field_name in ("python_index_url", "node_registry_url"):
        field_value = getattr(runtime_requirements, field_name)
        if field_value is not None and not str(field_value).strip():
            errors.append(f"Runtime requirement field '{field_name}' must not be blank when provided")

    indexed_scripts = set(parsed_skill.resources.scripts)
    seen_script_specs: set[str] = set()
    for script_spec in metadata.script_specs:
        script_path = script_spec.path.strip().lstrip("/")
        if not script_path:
            errors.append("Each script_spec must define a non-empty path")
            continue
        if script_path in seen_script_specs:
            errors.append(f"Duplicate script_spec path: {script_path}")
        seen_script_specs.add(script_path)
        if script_path not in indexed_scripts:
            errors.append(f"script_spec path must reference a declared script: {script_path}")
        if script_spec.runtime is not None and not script_spec.runtime.strip():
            errors.append(f"script_spec runtime must not be blank: {script_path}")
        if script_spec.description is not None and not script_spec.description.strip():
            errors.append(f"script_spec description must not be blank: {script_path}")
        if any(not isinstance(item, str) or not item.strip() for item in script_spec.argument_names):
            errors.append(f"script_spec argument_names must contain only non-empty strings: {script_path}")
        if not isinstance(script_spec.args_schema, dict):
            errors.append(f"script_spec args_schema must be an object: {script_path}")
        if any(not isinstance(item, str) or not item.strip() for item in script_spec.artifacts):
            errors.append(f"script_spec artifacts must contain only non-empty strings: {script_path}")
        if any(not isinstance(key, str) or not key.strip() or not isinstance(value, str) for key, value in script_spec.environment.items()):
            errors.append(f"script_spec environment must be a string-to-string mapping: {script_path}")
        if any(not isinstance(example, dict) for example in script_spec.examples):
            errors.append(f"script_spec examples must be objects: {script_path}")

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
