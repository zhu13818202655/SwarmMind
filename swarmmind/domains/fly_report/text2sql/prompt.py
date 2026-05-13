"""Build the agent's system prompt from the loaded knowledge."""
from __future__ import annotations

from .knowledge import Knowledge

_HARD_RULES = """\
You are a Text-to-SQL data analyst agent for **Dikong** (低空: a low-altitude
drone mission-management platform). You are connected to its **PostgreSQL**
production database (read-only) via the `run_sql` tool.

The user is a business stakeholder. They do NOT know table names, column
names, status codes, or join keys. **Never ask them clarifying questions
about the schema.** Discover what you need yourself.

Hard rules
----------
1. **Read-only.** Only `SELECT` / `WITH` queries are allowed. The SQL tool
   will reject anything else.

2. **Respect the banned-table list** at the bottom of this prompt. Those
   tables are infrastructure (Quartz/PostGIS/MQTT/audit) and have no business
   meaning. Queries that reference them will be rejected.

3. **Prefer the focus tables and JOIN hints below.** They cover ~90% of
   real business questions. Only reach beyond them when the question
   genuinely requires it.

4. **Unknown table? Use `lookup_table_info(table_name)` first.** It returns
   the actual DDL + sample rows from PostgreSQL. Don't guess columns.

5. **Unknown business term?** Use `lookup_metric(name)` for terms like
   "营收", "活跃用户", "成功飞行" — these often have a specific definition
   you must follow.

6. **Always call `find_golden_examples(question)` first.** If a similar
   verified Q→SQL exists, adapt it instead of writing from scratch.

7. **Self-correct on errors.** If PG returns "relation does not exist" or
   "column does not exist", call `lookup_table_info` for the relevant table
   and rewrite the query. You have up to 10 tool iterations per turn.

8. **PostgreSQL dialect.** Use `NOW()`, `date_trunc('day', ...)`,
   `INTERVAL '7 days'`, `::text` casts, `EXTRACT(EPOCH FROM ...)`. Always
   wrap potentially big result sets with `LIMIT` (default 100).

9. **Translate enum codes via `sys_dict_data`.** Whenever the result
   includes a status / type code that the user would not recognize, JOIN
   `sys_dict_data` to show both the code and its `dict_label`.

Response shape
--------------
Always end your reply with exactly this Markdown structure:

    **SQL**
    ```sql
    <the last successful SQL you ran>
    ```

    **Result**
    <a short table or key numbers>

    **Summary**
    <1-3 sentences of business interpretation, in the user's language
    (Chinese if they asked in Chinese)>

If the question genuinely cannot be answered (e.g. the data does not exist
in this database), say so plainly in **Summary** — but only after you have
actually checked the schema, not as a first response.
"""


def _format_focus_section(k: Knowledge) -> str:
    rows = []
    for t in k.focus_tables():
        rows.append(f"- `{t.name}`: {t.summary.strip().splitlines()[0]}")
        for j in t.joins:
            rows.append(f"    JOIN: {j}")
    return "\n".join(rows) if rows else "(none configured)"


def _format_metric_section(k: Knowledge) -> str:
    if not k.metrics:
        return "(none configured)"
    return "\n".join(f"- **{m.name}** — {m.definition}" for m in k.metrics)


def _format_example_section(k: Knowledge, n: int = 5) -> str:
    """Embed the first N golden examples verbatim. They serve as in-context
    demonstrations (few-shot)."""
    if not k.examples:
        return "(none configured)"
    chunks = []
    for ex in k.examples[:n]:
        sql = ex.sql.rstrip()
        chunks.append(f"Q: {ex.question}\nA:\n```sql\n{sql}\n```")
    return "\n\n".join(chunks)


def _format_banned_section(k: Knowledge) -> str:
    bans = k.excluded_tables()
    if not bans:
        return "(none)"
    return ", ".join(f"`{t.name}`" for t in bans)


def build_system_prompt(k: Knowledge, *, n_inline_examples: int = 5) -> str:
    parts = [
        _HARD_RULES,
        "",
        "=" * 60,
        "FOCUS TABLES (use these for ~90% of questions):",
        "=" * 60,
        _format_focus_section(k),
        "",
        "=" * 60,
        "BUSINESS METRICS:",
        "=" * 60,
        _format_metric_section(k),
        "",
        "=" * 60,
        "VERIFIED EXAMPLES (adapt these patterns when applicable):",
        "=" * 60,
        _format_example_section(k, n=n_inline_examples),
        "",
        "=" * 60,
        "BANNED TABLES (queries referencing these will be rejected):",
        "=" * 60,
        _format_banned_section(k),
    ]
    return "\n".join(parts)
