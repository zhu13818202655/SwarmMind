"""Parser for local SKILL.md-based packages."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

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
    "runtime_requirements",
    "script_specs",
}
_FIELD_ALIASES = {
    "source-url": "source_url",
    "source-type": "source_type",
    "allowed-tools": "allowed_tools",
    "required-env": "required_env",
    "required-bins": "required_bins",
    "runtime-requirements": "runtime_requirements",
    "script-specs": "script_specs",
    "required-python-packages": "required_python_packages",
    "python-packages": "required_python_packages",
    "dependencies": "required_python_packages",
    "python-index-url": "python_index_url",
    "node-registry-url": "node_registry_url",
}

_RUNTIME_REQUIREMENT_FIELDS = {
    "python_packages",
    "node_packages",
    "system_packages",
    "bootstrap_commands",
    "python_index_url",
    "node_registry_url",
}

_RUNTIME_REQUIREMENT_FIELD_ALIASES = {
    "python-packages": "python_packages",
    "node-packages": "node_packages",
    "system-packages": "system_packages",
    "bootstrap-commands": "bootstrap_commands",
    "python-index-url": "python_index_url",
    "node-registry-url": "node_registry_url",
}

_SCRIPT_SPEC_FIELD_ALIASES = {
    "args-schema": "args_schema",
    "argument-names": "argument_names",
}


def _normalize_runtime_requirements(normalized_data: dict[str, Any]) -> None:
    runtime_requirements = normalized_data.get("runtime_requirements")
    if not isinstance(runtime_requirements, dict):
        runtime_requirements = {}

    runtime_requirements = {
        _RUNTIME_REQUIREMENT_FIELD_ALIASES.get(str(key), str(key)): value
        for key, value in runtime_requirements.items()
    }

    legacy_python_packages = normalized_data.pop("required_python_packages", None)
    if isinstance(legacy_python_packages, list):
        existing = runtime_requirements.get("python_packages")
        if not isinstance(existing, list):
            runtime_requirements["python_packages"] = list(legacy_python_packages)
        else:
            runtime_requirements["python_packages"] = [*existing, *legacy_python_packages]

    for field_name in list(normalized_data):
        if field_name not in _RUNTIME_REQUIREMENT_FIELDS:
            continue
        runtime_requirements[field_name] = normalized_data.pop(field_name)

    normalized_data["runtime_requirements"] = runtime_requirements


def _normalize_script_specs(normalized_data: dict[str, Any]) -> None:
    raw_script_specs = normalized_data.get("script_specs")
    if raw_script_specs is None:
        normalized_data["script_specs"] = []
        return

    normalized_specs: list[dict[str, Any]] = []
    if isinstance(raw_script_specs, dict):
        for raw_path, raw_spec in raw_script_specs.items():
            if isinstance(raw_spec, dict):
                normalized_specs.append(
                    {
                        "path": str(raw_path),
                        **{
                            _SCRIPT_SPEC_FIELD_ALIASES.get(str(key), str(key)): value
                            for key, value in raw_spec.items()
                        },
                    }
                )
            else:
                normalized_specs.append({"path": str(raw_path)})
        normalized_data["script_specs"] = normalized_specs
        return

    if isinstance(raw_script_specs, list):
        for item in raw_script_specs:
            if isinstance(item, dict):
                normalized_specs.append(
                    {
                        _SCRIPT_SPEC_FIELD_ALIASES.get(str(key), str(key)): value
                        for key, value in item.items()
                    }
                )
        normalized_data["script_specs"] = normalized_specs
        return

    normalized_data["script_specs"] = []


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
    _normalize_runtime_requirements(normalized_data)
    _normalize_script_specs(normalized_data)

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
