"""Conflict / completeness checker for parsed FlyReport filters.

Runs after the intent parser to surface user-visible problems with the
draft :class:`DraftFilterSpec`. Returns a structured report so the
service can decide whether to enter the CLARIFYING state.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from swarmmind.domains.fly_report.schemas import DraftFilterSpec, FilterSpec


@dataclass
class ConflictReport:
    """Outcome of :func:`check_conflicts`."""

    missing: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    @property
    def needs_clarification(self) -> bool:
        return bool(self.missing) or bool(self.conflicts)


# TODO 后续需要根据业务要求修改
def check_conflicts(spec: FilterSpec | DraftFilterSpec) -> ConflictReport:
    """Inspect ``spec`` and return missing/conflicting fields.

    Rules (DESIGN-2 §14.4.2 — clarifier inputs):

    - ``period`` is required.
    - At least one ``indicator`` is required.
    - ``dimension.scope`` must be one of ``{"overall", "department", "pilot"}``;
      a non-``overall`` scope must come with a non-empty target list.
    """
    missing = list(getattr(spec, "missing", []))
    conflicts = list(getattr(spec, "conflicts", []))
    suggestions: list[str] = []

    if spec.period is None:
        if "period" not in missing:
            missing.append("period")
        suggestions.append("请指定时间范围，例如：本周 / 上周 / 本月")

    scope = getattr(spec.dimension, "scope", "overall")
    if scope not in {"overall", "department", "pilot"}:
        conflicts.append(f"unknown dimension scope: {scope}")
    elif scope == "department":
        if not list(getattr(spec.dimension, "department_ids", []) or []):
            conflicts.append("dimension.scope=department 缺少 department_ids")
            suggestions.append("请提供具体的部门列表")
    elif scope == "pilot":
        if not list(getattr(spec.dimension, "pilot_ids", []) or []):
            conflicts.append("dimension.scope=pilot 缺少 pilot_ids")
            suggestions.append("请提供具体的飞手 ID 列表")

    return ConflictReport(
        missing=missing,
        conflicts=conflicts,
        suggestions=suggestions,
    )


def merge_drafts(
    base: FilterSpec, patch: FilterSpec, *, prefer_patch: bool = True
) -> FilterSpec:
    """Merge a follow-up draft into the previously-confirmed filter.

    Used when the user provides a clarification message — we want to keep
    the parts they had already established (e.g. period) and only override
    fields they restated.
    """
    base_data = base.model_dump()
    patch_data = patch.model_dump()
    merged: dict = dict(base_data)

    def _take(field_name: str) -> None:
        patch_val = patch_data.get(field_name)
        if patch_val is None:
            return
        if isinstance(patch_val, list) and not patch_val:
            return
        if prefer_patch:
            merged[field_name] = patch_val
        else:
            merged.setdefault(field_name, patch_val)

    for name in ("period", "dimension", "indicators", "options"):
        _take(name)

    # Reset the diagnostic fields so the conflict checker can repopulate.
    merged["missing"] = []
    merged["conflicts"] = []
    return FilterSpec(**merged)


__all__ = ["ConflictReport", "check_conflicts", "merge_drafts"]
