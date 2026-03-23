"""Catalog builders for local skill packages."""

from __future__ import annotations

from swarmmind.skill_system.models import CompactSkillCatalogEntry, ExpandedSkillCatalogEntry, SkillEntry


def _iter_visible_entries(entries: list[SkillEntry]) -> list[SkillEntry]:
    return [entry for entry in entries if entry.valid and not entry.metadata.disabled]


def build_compact_catalog(entries: list[SkillEntry]) -> list[CompactSkillCatalogEntry]:
    """Build a compact list of name and description for prompt-time discovery."""
    return [
        CompactSkillCatalogEntry(
            name=entry.name,
            description=entry.description,
            source_type=entry.source_type,
            install_state=entry.install_state,
        )
        for entry in _iter_visible_entries(entries)
    ]


def build_expanded_catalog(entries: list[SkillEntry]) -> list[ExpandedSkillCatalogEntry]:
    """Build an expanded view including metadata and indexed resources."""
    return [
        ExpandedSkillCatalogEntry(
            name=entry.name,
            description=entry.description,
            body=entry.body,
            source_type=entry.source_type,
            install_state=entry.install_state,
            resources=entry.resources,
            metadata=entry.metadata,
        )
        for entry in _iter_visible_entries(entries)
    ]


def build_compact_catalog_payload(entries: list[SkillEntry]) -> list[dict[str, str]]:
    """Build a prompt-friendly compact payload."""
    return [
        {
            "name": entry.name,
            "description": entry.description,
        }
        for entry in build_compact_catalog(entries)
    ]


def build_expanded_catalog_payload(entries: list[SkillEntry]) -> list[dict[str, object]]:
    """Build a JSON-friendly expanded payload."""
    return [entry.model_dump(mode="json") for entry in build_expanded_catalog(entries)]