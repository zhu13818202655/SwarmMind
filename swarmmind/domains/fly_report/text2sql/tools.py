"""Custom tools for the Dikong Text-to-SQL agent.

- `GuardedRunSqlTool`        — wraps RunSqlTool. Blocks DML and banned tables,
                               and records each SQL run into a shared buffer
                               so the Text2SQL client can extract the final
                               SQL + result rows from a turn.
- `LookupTableInfoTool`      — return YAML summary + live DDL + sample rows
                               for one table (for tables NOT in focus).
- `LookupMetricTool`         — return the canonical definition + SQL template
                               for a business metric.
- `FindGoldenExamplesTool`   — keyword match against golden_qa.yaml.
- `ListAllowedTablesTool`    — list whitelisted tables + their summaries.
"""
from __future__ import annotations

import re
from typing import Any, List, Type

import pandas as pd
from pydantic import BaseModel, Field

from vanna.capabilities.sql_runner.base import SqlRunner
from vanna.capabilities.sql_runner.models import RunSqlToolArgs
from vanna.core.tool import Tool, ToolContext, ToolResult
from vanna.tools import RunSqlTool

from .knowledge import Knowledge


# ---------------------------------------------------------------------------
# Shared per-call capture buffer.
#
# The Text2SQL client clears this dict before each `agent.send_message`, then
# the GuardedRunSqlTool appends every SQL + result into `runs[conversation_id]`.
# After the agent finishes, the client reads the *last successful* entry to
# populate `Text2SQLResult.sql` / `.rows`.
# ---------------------------------------------------------------------------
class SqlCaptureBuffer:
    def __init__(self) -> None:
        self._runs: dict[str, list[dict[str, Any]]] = {}

    def clear(self, conversation_id: str) -> None:
        self._runs[conversation_id] = []

    def record(self, conversation_id: str, entry: dict[str, Any]) -> None:
        self._runs.setdefault(conversation_id, []).append(entry)

    def runs(self, conversation_id: str) -> list[dict[str, Any]]:
        return list(self._runs.get(conversation_id, []))

    def last_successful(self, conversation_id: str) -> dict[str, Any] | None:
        for r in reversed(self._runs.get(conversation_id, [])):
            if r.get("success"):
                return r
        return None


# ---------------------------------------------------------------------------
# Guarded SQL tool
# ---------------------------------------------------------------------------
_WRITE_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|truncate|alter|create|grant|revoke|vacuum|"
    r"reindex|cluster|comment|lock|copy|do|call)\b",
    re.IGNORECASE,
)
_IDENT_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")


def _referenced_tables(sql: str) -> set[str]:
    """Extract identifiers appearing after FROM / JOIN."""
    out: set[str] = set()
    pattern = re.compile(r"\b(?:from|join)\s+([\"a-zA-Z0-9_\.,\s]+)", re.IGNORECASE)
    for chunk in pattern.findall(sql):
        # chunk could be "schema.table alias, other_table"
        for piece in chunk.split(","):
            piece = piece.strip().strip('"')
            if not piece:
                continue
            tok = piece.split()[0]  # drop alias
            tok = tok.split(".")[-1]  # drop schema
            tok = tok.strip('"').lower()
            if tok:
                out.add(tok)
    return out


class GuardedRunSqlTool(RunSqlTool):
    """RunSqlTool with read-only / banned-table guards and SQL capture."""

    def __init__(
        self,
        sql_runner: SqlRunner,
        knowledge: Knowledge,
        capture: SqlCaptureBuffer,
        *,
        max_rows: int = 500,
        file_system=None,
    ) -> None:
        super().__init__(
            sql_runner=sql_runner,
            file_system=file_system,
            custom_tool_name=None,
            custom_tool_description=None,
        )
        self._knowledge = knowledge
        self._capture = capture
        self._banned = {t.name.lower() for t in knowledge.excluded_tables()}
        self._max_rows = max_rows

    async def execute(self, context: ToolContext, args: RunSqlToolArgs) -> ToolResult:
        sql = (args.sql or "").strip().rstrip(";")
        conv = context.conversation_id

        # ---- 1) only SELECT / WITH ----
        head = sql.lstrip().lower()
        if not (head.startswith("select") or head.startswith("with")):
            msg = "Blocked: only SELECT / WITH queries are allowed."
            self._capture.record(conv, {"sql": sql, "success": False, "error": msg})
            return ToolResult(success=False, result_for_llm=msg)

        # Belt-and-suspenders: even inside SELECT, refuse write keywords.
        if _WRITE_KEYWORDS.search(sql):
            msg = "Blocked: query contains a write keyword."
            self._capture.record(conv, {"sql": sql, "success": False, "error": msg})
            return ToolResult(success=False, result_for_llm=msg)

        # ---- 2) banned tables ----
        refs = _referenced_tables(sql)
        bad = refs & self._banned
        if bad:
            msg = (
                f"Blocked: query references banned table(s): {sorted(bad)}. "
                "Use the allowed tables only — see the focus list and "
                "lookup_table_info."
            )
            self._capture.record(conv, {"sql": sql, "success": False, "error": msg})
            return ToolResult(success=False, result_for_llm=msg)

        # ---- 3) delegate to upstream RunSqlTool ----
        result = await super().execute(context, RunSqlToolArgs(sql=sql))

        # ---- 4) capture for the client to read back ----
        raw_payload = result.result_for_llm if result.success else ""
        rows = _parse_csv_payload(raw_payload)
        if len(rows) > self._max_rows:
            rows = rows[: self._max_rows]
        self._capture.record(
            conv,
            {
                "sql": sql,
                "success": bool(result.success),
                "error": None if result.success else (result.result_for_llm or "")[:500],
                "rows": rows,
                "row_count": len(rows),
                "raw": raw_payload[:2000],
            },
        )
        return result


def _parse_csv_payload(payload: str) -> list[dict[str, Any]]:
    """RunSqlTool returns its `result_for_llm` as CSV text. Parse it back to
    list[dict] so external callers don't have to."""
    if not payload or "\n" not in payload:
        return []
    # The payload includes trailing notes (e.g. "Results saved to file ...").
    # Drop everything from the first blank line onwards.
    csv_part = payload.split("\n\n", 1)[0].strip()
    if not csv_part:
        return []
    try:
        from io import StringIO

        df = pd.read_csv(StringIO(csv_part))
        return df.to_dict(orient="records")
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Lookup table info
# ---------------------------------------------------------------------------
class LookupTableArgs(BaseModel):
    table_name: str = Field(description="Table name to introspect (lowercase).")


class LookupTableInfoTool(Tool[LookupTableArgs]):
    """Return YAML summary + live DDL + 3 sample rows for a single table.

    Use this whenever the agent wants to use a table that is NOT in the
    `FOCUS TABLES` section of the system prompt.
    """

    def __init__(self, sql_runner: SqlRunner, knowledge: Knowledge) -> None:
        self._runner = sql_runner
        self._knowledge = knowledge

    @property
    def name(self) -> str:
        return "lookup_table_info"

    @property
    def description(self) -> str:
        return (
            "Return the live DDL, column list and 3 sample rows for one "
            "PostgreSQL table, plus any business summary we have on file. "
            "Call this before joining or filtering on a table that is not in "
            "the FOCUS TABLES list."
        )

    @property
    def access_groups(self) -> List[str]:
        return []

    def get_args_schema(self) -> Type[LookupTableArgs]:
        return LookupTableArgs

    async def execute(self, context: ToolContext, args: LookupTableArgs) -> ToolResult:
        name = args.table_name.strip().strip('"').split(".")[-1].lower()
        if self._knowledge.is_excluded(name):
            return ToolResult(
                success=False,
                result_for_llm=f"Table `{name}` is on the banned list and cannot be used.",
            )

        info = self._knowledge.known_table(name)
        sections: list[str] = [f"# Table: {name}"]
        if info and info.summary:
            sections.append(f"\n## Business summary\n{info.summary}")
        if info and info.joins:
            sections.append("\n## Common joins\n" + "\n".join(f"- {j}" for j in info.joins))

        # Live columns (information_schema)
        try:
            cols_args = RunSqlToolArgs(
                sql=(
                    "SELECT column_name, data_type, is_nullable "
                    "FROM information_schema.columns "
                    f"WHERE table_schema='public' AND table_name='{name}' "
                    "ORDER BY ordinal_position"
                )
            )
            cols_df = await self._runner.run_sql(cols_args, context)
            if cols_df is None or len(cols_df) == 0:
                return ToolResult(
                    success=False,
                    result_for_llm=f"Table `{name}` not found in schema `public`.",
                )
            sections.append("\n## Columns\n" + cols_df.to_csv(index=False))
        except Exception as e:  # noqa: BLE001
            return ToolResult(success=False, result_for_llm=f"Schema lookup failed: {e}")

        # Sample rows (best-effort; ignore errors silently)
        try:
            sample_args = RunSqlToolArgs(sql=f'SELECT * FROM "{name}" LIMIT 3')
            sample_df = await self._runner.run_sql(sample_args, context)
            if sample_df is not None and len(sample_df) > 0:
                sections.append("\n## Sample rows\n" + sample_df.to_csv(index=False))
        except Exception:
            pass

        return ToolResult(success=True, result_for_llm="\n".join(sections))


# ---------------------------------------------------------------------------
# Lookup metric
# ---------------------------------------------------------------------------
class LookupMetricArgs(BaseModel):
    name: str = Field(description="Business metric name, e.g. '飞行架次', 'sortie'.")


class LookupMetricTool(Tool[LookupMetricArgs]):
    """Return the canonical definition + SQL template for a business metric."""

    def __init__(self, knowledge: Knowledge) -> None:
        self._knowledge = knowledge

    @property
    def name(self) -> str:
        return "lookup_metric"

    @property
    def description(self) -> str:
        return (
            "Return the canonical business definition and SQL template for a "
            "named metric (e.g. '飞行架次', '活跃无人机'). Use this whenever "
            "the user's question mentions a business term you are not 100% "
            "sure about."
        )

    @property
    def access_groups(self) -> List[str]:
        return []

    def get_args_schema(self) -> Type[LookupMetricArgs]:
        return LookupMetricArgs

    async def execute(self, context: ToolContext, args: LookupMetricArgs) -> ToolResult:
        q = args.name.strip().lower()
        # Match any alias listed in the YAML `name:` field (split by '/').
        for m in self._knowledge.metrics:
            aliases = [a.strip().lower() for a in m.name.split("/")]
            if any(a and a in q for a in aliases) or any(q in a for a in aliases):
                body = (
                    f"# Metric: {m.name}\n"
                    f"Definition: {m.definition}\n\n"
                    f"SQL template:\n```sql\n{m.sql_template}\n```\n"
                )
                if m.notes:
                    body += f"\nNotes: {m.notes}\n"
                return ToolResult(success=True, result_for_llm=body)
        return ToolResult(
            success=False,
            result_for_llm=(
                f"No metric matching '{args.name}' is on file. Proceed with a "
                "best-effort interpretation and state your assumption."
            ),
        )


# ---------------------------------------------------------------------------
# Find golden examples
# ---------------------------------------------------------------------------
class FindGoldenArgs(BaseModel):
    question: str = Field(description="The user's natural-language question.")
    limit: int = Field(default=3, description="Max examples to return.")


class FindGoldenExamplesTool(Tool[FindGoldenArgs]):
    """Keyword-overlap search over the verified Q→SQL pairs."""

    def __init__(self, knowledge: Knowledge) -> None:
        self._knowledge = knowledge

    @property
    def name(self) -> str:
        return "find_golden_examples"

    @property
    def description(self) -> str:
        return (
            "Search the team-curated, verified Q→SQL examples for ones similar "
            "to the user's question. If a strong match exists, adapt its SQL "
            "rather than writing from scratch. Call this BEFORE the first "
            "run_sql call of each turn."
        )

    @property
    def access_groups(self) -> List[str]:
        return []

    def get_args_schema(self) -> Type[FindGoldenArgs]:
        return FindGoldenArgs

    async def execute(self, context: ToolContext, args: FindGoldenArgs) -> ToolResult:
        hits = self._knowledge.find_examples(args.question, limit=args.limit)
        if not hits:
            return ToolResult(
                success=True,
                result_for_llm="No similar verified examples found.",
            )
        chunks = []
        for ex in hits:
            chunks.append(
                f"Q: {ex.question}\nA:\n```sql\n{ex.sql.rstrip()}\n```\n"
                f"(verified_by={ex.verified_by or 'n/a'})"
            )
        return ToolResult(success=True, result_for_llm="\n\n".join(chunks))


# ---------------------------------------------------------------------------
# List allowed tables
# ---------------------------------------------------------------------------
class _NoArgs(BaseModel):
    pass


class ListAllowedTablesTool(Tool[_NoArgs]):
    """Return the full list of allowed tables with one-line summaries."""

    def __init__(self, knowledge: Knowledge) -> None:
        self._knowledge = knowledge

    @property
    def name(self) -> str:
        return "list_allowed_tables"

    @property
    def description(self) -> str:
        return (
            "Return every table the agent is allowed to query, with a one-line "
            "business summary. Use this when the question hints at a table "
            "outside the FOCUS list."
        )

    @property
    def access_groups(self) -> List[str]:
        return []

    def get_args_schema(self) -> Type[_NoArgs]:
        return _NoArgs

    async def execute(self, context: ToolContext, args: _NoArgs) -> ToolResult:
        lines = []
        for t in self._knowledge.tables:
            if t.excluded:
                continue
            tier = "★★★" if t.focus else "   "
            summary = t.summary.splitlines()[0] if t.summary else ""
            lines.append(f"{tier} {t.name} — {summary}")
        return ToolResult(success=True, result_for_llm="\n".join(lines))
