from __future__ import annotations

from pathlib import Path

import pytest

from swarmmind.agents.agent_skill import (
    build_agent_skill_catalog,
    build_agent_skill_details,
    resolve_agent_skill_dirs,
    resolve_agent_skill_entries,
)
from swarmmind.agents.config import AgentConfig, AgentScopeConfig
from swarmmind.agents.factory import AgentFactory
from swarmmind.models.capability import ToolGroup
from swarmmind.sandbox import LocalSandboxAdapter, SandboxManager
from swarmmind.skill_system.catalog import (
    build_compact_catalog,
    build_compact_catalog_payload,
    build_expanded_catalog,
    build_expanded_catalog_payload,
)
from swarmmind.skill_system.executor import SkillScriptExecutor
from swarmmind.skill_system.loader import get_skill_package_root, load_skill_dir, load_skill_entries, load_skill_registry
from swarmmind.skill_system.models import SkillInstallState, SkillSourceType
from swarmmind.skill_system.models import SkillScriptExecutionPolicy
from swarmmind.skill_system.parser import parse_skill_dir
from swarmmind.skill_system.resources import read_skill_resource
from swarmmind.skill_system.validator import validate_parsed_skill


def _write_skill(
    root: Path,
    name: str,
    description: str = "Test skill description.",
    body: str = "# Test Skill\n\nBody.",
) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        "---\n\n"
        f"{body}\n",
        encoding="utf-8",
    )
    return skill_dir


def test_parse_skill_dir_indexes_resources(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path, "demo_skill", body="# Demo\n\nSee (references/guide.md)")
    (skill_dir / "references").mkdir()
    (skill_dir / "references" / "guide.md").write_text("guide", encoding="utf-8")
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "run.sh").write_text("echo demo", encoding="utf-8")

    parsed = parse_skill_dir(skill_dir)

    assert parsed.metadata.name == "demo_skill"
    assert parsed.resources.references == ["references/guide.md"]
    assert parsed.resources.scripts == ["scripts/run.sh"]
    assert read_skill_resource(skill_dir, "references/guide.md") == "guide"


def test_validate_parsed_skill_reports_missing_referenced_resource(tmp_path: Path) -> None:
    skill_dir = _write_skill(
        tmp_path,
        "broken_skill",
        body="# Broken\n\nRead (references/missing.md) before use.",
    )

    parsed = parse_skill_dir(skill_dir)
    errors = validate_parsed_skill(parsed)

    assert errors == ["Referenced resource does not exist: references/missing.md"]


def test_load_skill_entries_filters_invalid_skills(tmp_path: Path) -> None:
    valid_dir = _write_skill(tmp_path, "valid_skill")
    invalid_dir = _write_skill(tmp_path, "invalid_skill")
    (invalid_dir / "SKILL.md").write_text(
        "---\nname: different_name\ndescription: bad\n---\n\n# Bad\n",
        encoding="utf-8",
    )

    entries = load_skill_entries(tmp_path)
    entry_map = {entry.name: entry for entry in entries}

    assert entry_map["valid_skill"].valid is True
    assert entry_map["different_name"].valid is False
    assert "Skill name 'different_name' must match directory name 'invalid_skill'" in entry_map["different_name"].errors
    assert load_skill_dir(valid_dir).valid is True


def test_load_skill_dir_returns_invalid_entry_for_malformed_frontmatter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "malformed_skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Missing frontmatter\n", encoding="utf-8")

    entry = load_skill_dir(skill_dir)

    assert entry.valid is False
    assert entry.name == "malformed_skill"
    assert "YAML frontmatter" in entry.errors[0]


def test_get_skill_package_root_prefers_current_local_skill_root() -> None:
    root = get_skill_package_root()

    assert root.name in {"skills", "agent_skills"}
    assert root.is_dir()


def test_pptx_skill_exposes_from_scratch_creation_script() -> None:
    skill_root = get_skill_package_root()
    entry = load_skill_dir(skill_root / "pptx")

    assert entry.valid is True
    spec_by_path = {spec.path: spec for spec in entry.metadata.script_specs}
    create_spec = spec_by_path["scripts/create_presentation.py"]

    assert create_spec.argument_names == ["deck_spec", "output_file"]
    assert create_spec.artifacts == ["{output_file}"]
    assert "from scratch" in create_spec.description.lower()


def test_load_skill_registry_and_catalog_skip_disabled_and_invalid_entries(tmp_path: Path) -> None:
    _write_skill(tmp_path, "alpha")
    disabled_dir = _write_skill(tmp_path, "disabled_skill")
    (disabled_dir / "SKILL.md").write_text(
        "---\nname: disabled_skill\ndescription: hidden\ndisabled: true\n---\n\n# Hidden\n",
        encoding="utf-8",
    )
    invalid_dir = _write_skill(tmp_path, "invalid_skill")
    (invalid_dir / "SKILL.md").write_text(
        "---\nname: wrong_name\ndescription: invalid\n---\n\n# Invalid\n",
        encoding="utf-8",
    )

    registry = load_skill_registry(tmp_path)
    entries = registry.list_entries()

    assert registry.get_by_name("alpha") is not None
    assert len(entries) == 3

    compact = build_compact_catalog(entries)
    expanded = build_expanded_catalog(entries)

    assert compact[0].name == "alpha"
    assert compact[0].source_type == SkillSourceType.REPO_LOCAL
    assert expanded[0].name == "alpha"
    assert expanded[0].metadata.disabled is False
    assert build_compact_catalog_payload(entries) == [
        {
            "name": "alpha",
            "description": "Test skill description.",
        }
    ]
    assert build_expanded_catalog_payload(entries)[0]["metadata"]["disabled"] is False


def test_resolve_agent_skill_dirs_returns_only_valid_requested_skills(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_skill(tmp_path, "alpha")
    invalid_dir = _write_skill(tmp_path, "beta")
    (invalid_dir / "SKILL.md").write_text(
        "---\nname: wrong_name\ndescription: bad\n---\n\n# Broken\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("swarmmind.agents.agent_skill.get_agent_skill_root", lambda: tmp_path)

    resolved = resolve_agent_skill_dirs(["alpha", "beta"])

    assert resolved == [tmp_path / "alpha"]


def test_parse_skill_dir_supports_kebab_case_governance_fields(tmp_path: Path) -> None:
    skill_dir = tmp_path / "governed_skill"
    skill_dir.mkdir()
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "run.py").write_text("print('ok')\n", encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: governed_skill\n"
        "description: governed\n"
        "version: 1.2.3\n"
        "license: MIT\n"
        "compatibility:\n"
        "  - linux\n"
        "source-url: https://example.com/repo\n"
        "source-type: downloaded\n"
        "allowed-tools:\n"
        "  - read_file\n"
        "required-env:\n"
        "  - API_KEY\n"
        "required-bins:\n"
        "  - python\n"
        "runtime-requirements:\n"
        "  python-packages:\n"
        "    - defusedxml\n"
        "script-specs:\n"
        "  scripts/run.py:\n"
        "    runtime: python\n"
        "    argument_names:\n"
        "      - input_file\n"
        "    args_schema:\n"
        "      type: object\n"
        "      properties:\n"
        "        input_file:\n"
        "          type: string\n"
        "---\n\n"
        "# Governed\n",
        encoding="utf-8",
    )

    parsed = parse_skill_dir(skill_dir)

    assert parsed.metadata.version == "1.2.3"
    assert parsed.metadata.license == "MIT"
    assert parsed.metadata.compatibility == ["linux"]
    assert parsed.metadata.source_url == "https://example.com/repo"
    assert parsed.metadata.source_type == SkillSourceType.DOWNLOADED
    assert parsed.metadata.allowed_tools == ["read_file"]
    assert parsed.metadata.required_env == ["API_KEY"]
    assert parsed.metadata.required_bins == ["python"]
    assert parsed.metadata.runtime_requirements.python_packages == ["defusedxml"]
    assert parsed.metadata.script_specs[0].path == "scripts/run.py"
    assert parsed.metadata.script_specs[0].argument_names == ["input_file"]


def test_parse_skill_dir_promotes_legacy_required_python_packages_into_runtime_requirements(tmp_path: Path) -> None:
    skill_dir = tmp_path / "legacy_runtime"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: legacy_runtime\n"
        "description: legacy runtime\n"
        "required-python-packages:\n"
        "  - defusedxml\n"
        "---\n\n"
        "# Legacy\n",
        encoding="utf-8",
    )

    parsed = parse_skill_dir(skill_dir)

    assert parsed.metadata.runtime_requirements.python_packages == ["defusedxml"]


def test_validate_parsed_skill_rejects_invalid_governance_fields(tmp_path: Path) -> None:
    skill_dir = tmp_path / "invalid_governance"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: invalid_governance\n"
        "description: bad governance\n"
        "version: '   '\n"
        "license: '   '\n"
        "source-url: not-a-url\n"
        "compatibility:\n"
        "  - ''\n"
        "---\n\n"
        "# Invalid\n",
        encoding="utf-8",
    )

    parsed = parse_skill_dir(skill_dir)
    errors = validate_parsed_skill(parsed)

    assert "Frontmatter field 'version' must not be blank" in errors
    assert "Frontmatter field 'license' must not be blank" in errors
    assert "Frontmatter field 'source_url' must be a valid http(s) URL" in errors
    assert "Frontmatter field 'compatibility' must contain only non-empty strings" in errors


def test_validate_parsed_skill_rejects_invalid_script_specs(tmp_path: Path) -> None:
    skill_dir = tmp_path / "invalid_specs"
    skill_dir.mkdir()
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "run.py").write_text("print('ok')\n", encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: invalid_specs\n"
        "description: invalid specs\n"
        "script_specs:\n"
        "  - path: scripts/missing.py\n"
        "    argument_names:\n"
        "      - ''\n"
        "---\n\n"
        "# Invalid\n",
        encoding="utf-8",
    )

    parsed = parse_skill_dir(skill_dir)
    errors = validate_parsed_skill(parsed)

    assert "script_spec path must reference a declared script: scripts/missing.py" in errors
    assert "script_spec argument_names must contain only non-empty strings: scripts/missing.py" in errors


def test_resolve_agent_skill_entries_filters_by_env_bin_and_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    eligible = _write_skill(tmp_path, "eligible")
    (eligible / "SKILL.md").write_text(
        "---\n"
        "name: eligible\n"
        "description: usable\n"
        "allowed-tools:\n"
        "  - read_file\n"
        "required-env:\n"
        "  - PRESENT_ENV\n"
        "required-bins:\n"
        "  - python3\n"
        "compatibility:\n"
        "  - linux\n"
        "---\n\n"
        "# Eligible\n",
        encoding="utf-8",
    )
    _write_skill(tmp_path, "missing_env", body="# Missing env\n")
    ((tmp_path / "missing_env") / "SKILL.md").write_text(
        "---\n"
        "name: missing_env\n"
        "description: blocked\n"
        "required-env:\n"
        "  - ABSENT_ENV\n"
        "---\n\n"
        "# Missing\n",
        encoding="utf-8",
    )
    _write_skill(tmp_path, "missing_tool", body="# Missing tool\n")
    ((tmp_path / "missing_tool") / "SKILL.md").write_text(
        "---\n"
        "name: missing_tool\n"
        "description: blocked\n"
        "allowed-tools:\n"
        "  - write_file\n"
        "---\n\n"
        "# Missing tool\n",
        encoding="utf-8",
    )
    incompatible = _write_skill(tmp_path, "incompatible")
    (incompatible / "SKILL.md").write_text(
        "---\n"
        "name: incompatible\n"
        "description: blocked\n"
        "compatibility:\n"
        "  - windows\n"
        "---\n\n"
        "# Incompatible\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("swarmmind.agents.agent_skill.get_agent_skill_root", lambda: tmp_path)
    monkeypatch.setenv("PRESENT_ENV", "1")

    entries = resolve_agent_skill_entries(
        ["eligible", "missing_env", "missing_tool", "incompatible"],
        {"read_file", "list_files"},
    )

    assert [entry.name for entry in entries] == ["eligible"]
    assert build_agent_skill_catalog(
        ["eligible", "missing_env", "missing_tool", "incompatible"],
        {"read_file", "list_files"},
    ) == [
        {"name": "eligible", "description": "usable"}
    ]


def test_load_skill_dir_tracks_source_type_and_install_state(tmp_path: Path) -> None:
    downloaded_dir = _write_skill(tmp_path, "downloaded_skill")
    (downloaded_dir / "SKILL.md").write_text(
        "---\n"
        "name: downloaded_skill\n"
        "description: downloaded\n"
        "source-type: downloaded\n"
        "disabled: true\n"
        "---\n\n"
        "# Downloaded\n",
        encoding="utf-8",
    )

    entry = load_skill_dir(downloaded_dir)

    assert entry.source_type == SkillSourceType.DOWNLOADED
    assert entry.install_state == SkillInstallState.DISABLED


def test_agent_skill_details_expose_expanded_catalog_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_skill(tmp_path, "writing-plans", body="# Writing Plans\n\nBody text.")
    monkeypatch.setattr("swarmmind.agents.agent_skill.get_agent_skill_root", lambda: tmp_path)

    details = build_agent_skill_details(["writing-plans"], {"read_file", "list_files", "file_exists"})

    assert details[0]["name"] == "writing-plans"
    assert details[0]["body"] == "# Writing Plans\n\nBody text."
    assert details[0]["source_type"] == "repo-local"


def test_agent_factory_exposes_filtered_skill_catalog_on_toolkit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_skill(tmp_path, "writing-plans")
    gated = _write_skill(tmp_path, "blocked-skill")
    (gated / "SKILL.md").write_text(
        "---\n"
        "name: blocked-skill\n"
        "description: gated\n"
        "allowed-tools:\n"
        "  - nonexistent_tool\n"
        "---\n\n"
        "# Blocked Skill\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("swarmmind.agents.agent_skill.get_agent_skill_root", lambda: tmp_path)

    factory = AgentFactory(
        AgentConfig(
            name="catalog-agent",
            scope_config=AgentScopeConfig(model_name="gpt-4o"),
            skill_profiles=["writing-plans", "blocked-skill"],
        )
    )

    toolkit = factory.create_toolkit([], tool_groups=[ToolGroup.WORKSPACE])
    prompt = toolkit.get_agent_skill_prompt()

    assert getattr(toolkit, "_swarmmind_skill_catalog") == [
        {
            "name": "writing-plans",
            "description": "Test skill description.",
        }
    ]
    assert getattr(toolkit, "_swarmmind_skill_details")[0]["name"] == "writing-plans"
    assert "writing-plans" in prompt
    assert "blocked-skill" not in prompt


@pytest.mark.asyncio
async def test_skill_script_executor_runs_declared_script_and_collects_artifacts(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path, "scripted_skill")
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "run.sh").write_text(
        "cat references/message.txt\nprintf '%s' \"$GREETING\" > out/result.txt\n",
        encoding="utf-8",
    )
    (skill_dir / "references").mkdir()
    (skill_dir / "references" / "message.txt").write_text("hello from reference\n", encoding="utf-8")
    parsed_entry = load_skill_dir(skill_dir)

    executor = SkillScriptExecutor(SandboxManager(LocalSandboxAdapter()))
    result = await executor.execute(
        parsed_entry,
        "scripts/run.sh",
        SkillScriptExecutionPolicy(
            allow_sandbox_exec=True,
            environment={"GREETING": "artifact-output"},
            artifact_paths=["out/result.txt"],
        ),
    )

    assert result.exit_code == 0
    assert "hello from reference" in result.stdout
    assert result.artifacts == {"out/result.txt": "artifact-output"}


@pytest.mark.asyncio
async def test_skill_script_executor_appends_script_args_to_command(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path, "argv_skill")
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "run.py").write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "Path('out').mkdir(exist_ok=True)\n"
        "Path('out/result.txt').write_text('|'.join(sys.argv[1:]), encoding='utf-8')\n",
        encoding="utf-8",
    )
    parsed_entry = load_skill_dir(skill_dir)

    executor = SkillScriptExecutor(SandboxManager(LocalSandboxAdapter()))
    result = await executor.execute(
        parsed_entry,
        "scripts/run.py",
        SkillScriptExecutionPolicy(
            allow_sandbox_exec=True,
            artifact_paths=["out/result.txt"],
            script_args=["alpha", "beta gamma"],
        ),
    )

    assert result.exit_code == 0
    assert result.command.endswith("scripts/run.py alpha 'beta gamma'")
    assert result.artifacts == {"out/result.txt": "alpha|beta gamma"}


@pytest.mark.asyncio
async def test_skill_script_executor_rejects_undeclared_script(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path, "scripted_skill")
    parsed_entry = load_skill_dir(skill_dir)
    executor = SkillScriptExecutor(SandboxManager(LocalSandboxAdapter()))

    with pytest.raises(ValueError, match="not declared"):
        await executor.execute(
            parsed_entry,
            "scripts/run.sh",
            SkillScriptExecutionPolicy(allow_sandbox_exec=True),
        )


@pytest.mark.asyncio
async def test_skill_script_executor_requires_explicit_policy_and_required_env(tmp_path: Path) -> None:
    skill_dir = tmp_path / "env_skill"
    skill_dir.mkdir()
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "run.py").write_text("print('ok')\n", encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: env_skill\n"
        "description: env gated\n"
        "required-env:\n"
        "  - API_TOKEN\n"
        "---\n\n"
        "# Env Skill\n",
        encoding="utf-8",
    )
    parsed_entry = load_skill_dir(skill_dir)
    executor = SkillScriptExecutor(SandboxManager(LocalSandboxAdapter()))

    with pytest.raises(ValueError, match="allow_sandbox_exec"):
        await executor.execute(
            parsed_entry,
            "scripts/run.py",
            SkillScriptExecutionPolicy(),
        )

    with pytest.raises(ValueError, match="Missing required environment variable"):
        await executor.execute(
            parsed_entry,
            "scripts/run.py",
            SkillScriptExecutionPolicy(allow_sandbox_exec=True),
        )