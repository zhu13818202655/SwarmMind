"""Load and index the YAML knowledge assets under dikong/knowledge/."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class TableInfo:
    name: str
    summary: str = ""
    focus: bool = False
    excluded: bool = False
    reason: str = ""
    joins: list[str] = field(default_factory=list)
    enums: dict[str, Any] = field(default_factory=dict)

    @property
    def included(self) -> bool:
        """Anything not explicitly excluded and not '待定'-only is included."""
        return not self.excluded


@dataclass
class MetricInfo:
    name: str
    definition: str
    sql_template: str = ""
    notes: str = ""


@dataclass
class GoldenExample:
    question: str
    sql: str
    tags: list[str] = field(default_factory=list)
    verified_by: str = ""
    verified_at: str = ""


@dataclass
class Knowledge:
    tables: list[TableInfo]
    metrics: list[MetricInfo]
    examples: list[GoldenExample]
    root: Path

    # ---- convenience indexes ----
    def focus_tables(self) -> list[TableInfo]:
        return [t for t in self.tables if t.focus and not t.excluded]

    def excluded_tables(self) -> list[TableInfo]:
        return [t for t in self.tables if t.excluded]

    def known_table(self, name: str) -> TableInfo | None:
        for t in self.tables:
            if t.name == name:
                return t
        return None

    def is_excluded(self, name: str) -> bool:
        t = self.known_table(name)
        return bool(t and t.excluded)

    def find_examples(self, query: str, limit: int = 5) -> list[GoldenExample]:
        """Cheap keyword-overlap match.

        We tokenize on Chinese chars + ascii words, score by intersection size.
        This avoids requiring an embedding service just for example lookup.
        """
        q_tokens = _tokenize(query)
        scored: list[tuple[int, GoldenExample]] = []
        for ex in self.examples:
            ex_tokens = _tokenize(ex.question + " " + " ".join(ex.tags))
            score = len(q_tokens & ex_tokens)
            if score:
                scored.append((score, ex))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ex for _, ex in scored[:limit]]


_CN_RE = re.compile(r"[\u4e00-\u9fff]")
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]+")


def _tokenize(text: str) -> set[str]:
    text = text.lower()
    toks: set[str] = set()
    toks.update(_TOKEN_RE.findall(text))
    toks.update(_CN_RE.findall(text))
    return toks


def load_knowledge(root: Path | str | None = None) -> Knowledge:
    """Load tables.yaml + metrics.yaml + golden_qa.yaml from `knowledge/`."""
    if root is None:
        root = Path(__file__).resolve().parents[1] / "knowledge"
    root = Path(root)

    tables_doc = yaml.safe_load((root / "tables.yaml").read_text(encoding="utf-8")) or {}
    metrics_doc = yaml.safe_load((root / "metrics.yaml").read_text(encoding="utf-8")) or {}
    qa_doc = yaml.safe_load((root / "golden_qa.yaml").read_text(encoding="utf-8")) or {}

    tables = [
        TableInfo(
            name=t["name"],
            summary=t.get("summary", "").strip(),
            focus=bool(t.get("focus", False)),
            excluded=bool(t.get("excluded", False)),
            reason=t.get("reason", "").strip(),
            joins=list(t.get("joins") or []),
            enums=dict(t.get("enums") or {}),
        )
        for t in (tables_doc.get("tables") or [])
    ]
    metrics = [
        MetricInfo(
            name=m["name"],
            definition=m.get("definition", "").strip(),
            sql_template=(m.get("sql_template") or "").strip(),
            notes=(m.get("notes") or "").strip(),
        )
        for m in (metrics_doc.get("metrics") or [])
    ]
    examples = [
        GoldenExample(
            question=e["question"],
            sql=e["sql"].strip(),
            tags=list(e.get("tags") or []),
            verified_by=e.get("verified_by", ""),
            verified_at=str(e.get("verified_at", "")),
        )
        for e in (qa_doc.get("examples") or [])
    ]
    return Knowledge(tables=tables, metrics=metrics, examples=examples, root=root)
