from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class TableColumn:
    key: str
    label: str
    align: str | None = None
    width: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass(slots=True)
class TableRow:
    cells: dict[str, Any]
    key: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def get(self, column_key: str, default: Any = None) -> Any:
        return self.cells.get(column_key, default)

    def pick(self, column_keys: list[str]) -> dict[str, Any]:
        return {column_key: self.cells.get(column_key) for column_key in column_keys}

    def to_dict(self) -> dict[str, Any]:
        payload = dict(self.cells)
        if self.key is not None:
            payload["key"] = self.key
        if self.meta:
            payload["meta"] = dict(self.meta)
        return payload


@dataclass(slots=True)
class DataTable:
    title: str
    columns: list[TableColumn]
    rows: list[TableRow] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def add_row(
        self,
        cells: dict[str, Any],
        *,
        key: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> TableRow:
        row = TableRow(cells=cells, key=key, meta=meta or {})
        self.rows.append(row)
        return row

    def row_by_key(self, key: str) -> TableRow | None:
        return next((row for row in self.rows if row.key == key), None)

    def values_for(self, column_key: str) -> list[Any]:
        return [row.get(column_key) for row in self.rows]

    def display_rows(self) -> list[dict[str, Any]]:
        column_keys = [column.key for column in self.columns]
        return [row.pick(column_keys) for row in self.rows]

    def extract_summary(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "column_count": len(self.columns),
            "row_count": len(self.rows),
            "columns": [column.label for column in self.columns],
            "row_keys": [row.key for row in self.rows if row.key is not None],
        }

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "title": self.title,
            "columns": [column.to_dict() for column in self.columns],
            "rows": [row.to_dict() for row in self.rows],
        }
        if self.meta:
            payload["meta"] = dict(self.meta)
        return payload

    def to_json(self, *, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


__all__ = ["DataTable", "TableColumn", "TableRow"]