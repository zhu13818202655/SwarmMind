"""In-memory registry for local skill package entries."""

from __future__ import annotations

from swarmmind.skill_system.models import SkillEntry


class SkillRegistry:
    """Simple registry for parsed local skills."""

    def __init__(self) -> None:
        self._entries: dict[str, SkillEntry] = {}

    def register(self, entry: SkillEntry) -> None:
        self._entries[entry.skill_id] = entry

    def get(self, skill_id: str) -> SkillEntry | None:
        return self._entries.get(skill_id)

    def get_by_name(self, name: str) -> SkillEntry | None:
        for entry in self._entries.values():
            if entry.name == name:
                return entry
        return None

    def list_entries(self, include_invalid: bool = True) -> list[SkillEntry]:
        if include_invalid:
            return list(self._entries.values())
        return [entry for entry in self._entries.values() if entry.valid and not entry.metadata.disabled]
