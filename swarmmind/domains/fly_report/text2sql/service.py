"""Service facade for the FlyReport Text-to-SQL pipeline.

Backed by :class:`Text2SqlAgent` (Vanna 2.0 multi-tool agent loop over a
hand-curated YAML knowledge base). The service preserves the response
shape (:class:`Text2SqlAnswer`) consumed by
:mod:`swarmmind.domains.fly_report.service` so the rest of the FlyReport
pipeline keeps working unchanged.
"""

from __future__ import annotations

from loguru import logger
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from swarmmind.config.schema import FlyReportText2SqlConfig
from swarmmind.config.settings import get_settings
from swarmmind.domains.fly_report.text2sql.agent import (
    Text2SqlAgent,
    Text2SqlAgentResult,
)
from swarmmind.domains.fly_report.text2sql.chart import (
    ChartArtifact,
    build_chart_for_text2sql,
)
from swarmmind.domains.fly_report.text2sql.errors import (
    Text2SqlConfigError,
    Text2SqlGenerationError,
)



@dataclass
class QueryResult:
    """Subset of the columns/rows shape the FlyReport UI consumes."""

    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False


@dataclass
class Text2SqlAnswer:
    """Structured payload returned to the FlyReport conversation layer."""

    question: str
    sql: str | None = None
    answer_text: str | None = None
    """Final natural-language reply produced by the agent (Markdown).
    Already contains the SQL / Result / Summary blocks per the system
    prompt — the UI layer can surface it as-is."""
    result: QueryResult | None = None
    error: str | None = None
    executed: bool = False
    conversation_id: str | None = None
    sql_attempts: list[dict[str, Any]] = field(default_factory=list)
    chart_url: str | None = None
    chart_path: str | None = None
    chart_type: str | None = None

    def is_success(self) -> bool:
        return self.error is None and self.sql is not None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "question": self.question,
            "sql": self.sql,
            "executed": self.executed,
        }
        if self.answer_text:
            payload["answer_text"] = self.answer_text
        if self.conversation_id:
            payload["conversation_id"] = self.conversation_id
        if self.result is not None:
            payload["result"] = {
                "columns": self.result.columns,
                "rows": self.result.rows,
                "row_count": self.result.row_count,
                "truncated": self.result.truncated,
            }
        if self.sql_attempts:
            payload["sql_attempts"] = self.sql_attempts
        if self.chart_url:
            payload["chart"] = {
                "url": self.chart_url,
                "path": self.chart_path,
                "type": self.chart_type,
            }
        if self.error:
            payload["error"] = self.error
        return payload


class Text2SqlService:
    """Async-friendly wrapper around :class:`Text2SqlAgent`."""

    def __init__(
        self,
        *,
        config: FlyReportText2SqlConfig,
        agent: Text2SqlAgent,
    ) -> None:
        self._config = config
        self._agent = agent

    @property
    def config(self) -> FlyReportText2SqlConfig:
        return self._config

    @property
    def agent(self) -> Text2SqlAgent:
        return self._agent

    async def answer(
        self,
        question: str,
        *,
        conversation_id: str | None = None,
        on_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> Text2SqlAnswer:
        question = (question or "").strip()
        if not question:
            return Text2SqlAnswer(question=question, error="question is empty")

        try:
            result = await self._agent.ask(
                question,
                conversation_id=conversation_id,
                on_event=on_event,
            )
            logger.info(
                "fly_report.text2sql.agent_success",
                extra={
                    "question_preview": question[:120], 
                    "sql": result.sql,
                    "row_count": result.row_count,
                    "executed": result.sql is not None and result.row_count is not None,
                },
            )
        except Text2SqlGenerationError as exc:
            logger.warning(
                "fly_report.text2sql.agent_failed",
                extra={
                    "question_preview": question[:120],
                    "error": str(exc),
                },
            )
            return Text2SqlAnswer(
                question=question,
                error=f"SQL 生成失败：{exc}",
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("fly_report.text2sql.agent_unhandled")
            return Text2SqlAnswer(
                question=question,
                error=f"SQL 处理时发生未知错误：{exc}",
            )

        return _to_answer(result, max_rows=int(self._config.max_rows))


def _to_answer(result: Text2SqlAgentResult, *, max_rows: int) -> Text2SqlAnswer:
    rows = result.rows or []
    columns = list(rows[0].keys()) if rows else []
    truncated = result.row_count >= max_rows

    query_result: QueryResult | None = None
    executed = False
    if result.sql_attempts:
        executed = any(a.get("success") for a in result.sql_attempts)
    if executed:
        query_result = QueryResult(
            columns=columns,
            rows=rows,
            row_count=result.row_count,
            truncated=truncated,
        )

    error: str | None = None
    if not executed and result.sql_attempts:
        last_error = next(
            (a.get("error") for a in reversed(result.sql_attempts) if a.get("error")),
            None,
        )
        if last_error:
            error = last_error
    if not result.success:
        error = result.error or error

    # Strip the raw SQL block from the user-facing answer; the SQL is
    # surfaced separately via the ``sql`` field / payload so end users see
    # interpretation, not query text.
    answer_text = _strip_sql_block(result.answer)

    # ------------------------------------------------------------------
    # Friendly fallbacks for "no usable data" cases. We override the LLM's
    # templated **SQL** / **结果** / **总结** reply in these scenarios so
    # the user does not see placeholder cells or a confident summary built
    # on top of zero rows.
    # ------------------------------------------------------------------
    if not executed:
        # SQL never ran successfully (generation failed, all attempts
        # rejected by guards, PG errors, …). Surface a single plain
        # sentence instead of the template.
        answer_text = _friendly_no_data_message(
            question=result.question,
            executed=False,
            error=error,
        )
    elif not rows:
        # SQL ran but returned zero rows — likely time range / filter is
        # too narrow, or the data simply does not exist.
        answer_text = _friendly_no_data_message(
            question=result.question,
            executed=True,
            error=None,
        )
    elif _has_placeholder(answer_text):
        # SQL returned rows but the LLM still left placeholder cells like
        # "(见查询结果)" in the **结果** block. Rewrite that block from
        # the real query rows so the user never sees a template stub.
        answer_text = _replace_result_block_with_rows(
            answer_text, rows=rows, columns=columns
        )

    # NOTE: 暂时关闭 Text2SQL 结果的图表生成（按需后续再开启）。
    chart: ChartArtifact | None = None
    # if executed and rows:
    #     chart = build_chart_for_text2sql(
    #         rows=rows, question=result.question, sql=result.sql
    #     )
    #     if chart is not None:
    #         answer_text = _append_chart_markdown(answer_text, chart)

    return Text2SqlAnswer(
        question=result.question,
        sql=result.sql,
        answer_text=answer_text,
        result=query_result,
        error=error,
        executed=executed,
        conversation_id=result.conversation_id,
        sql_attempts=result.sql_attempts,
        chart_url=chart.url if chart else None,
        chart_path=str(chart.path) if chart else None,
        chart_type=chart.chart_type if chart else None,
    )


# ----------------------------------------------------------------------
# Answer text post-processing
# ----------------------------------------------------------------------
# Matches the **SQL** heading followed by a fenced ```sql ... ``` block.
# The agent's system prompt always emits this exact shape (see
# ``swarmmind.domains.fly_report.text2sql.prompt``).
_SQL_BLOCK_RE = re.compile(
    r"\*\*SQL\*\*\s*\n+```sql\s*\n.*?\n```\s*\n*",
    flags=re.IGNORECASE | re.DOTALL,
)


def _strip_sql_block(text: str | None) -> str | None:
    if not text:
        return text
    cleaned = _SQL_BLOCK_RE.sub("", text)
    # Collapse the >2 blank lines we may leave behind.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned or None


# Common placeholder strings the LLM may emit when it forgets to fill in the
# **结果** block with real numbers. Detection is intentionally loose — we
# only need to know *whether* the answer text needs rewriting from the rows.
_PLACEHOLDER_RE = re.compile(
    r"(?:见查询结果|待填|待查询|待补充|暂无数据|查询结果待填|"
    r"\bTBD\b|\bTODO\b|\bN/?A\b|<\s*value\s*>|<\s*数值\s*>)",
    flags=re.IGNORECASE,
)
# Matches the **结果** section up to (but not including) **总结** or end of
# string. Used to surgically replace just that block.
_RESULT_BLOCK_RE = re.compile(
    r"(\*\*结果\*\*\s*\n)(.*?)(?=\n\*\*总结\*\*|\Z)",
    flags=re.DOTALL,
)


def _has_placeholder(text: str | None) -> bool:
    if not text:
        return False
    return bool(_PLACEHOLDER_RE.search(text))


def _friendly_no_data_message(
    *,
    question: str,
    executed: bool,
    error: str | None,
) -> str:
    """Compose a short, human-friendly reply for empty / failed queries.

    No `**SQL** / **结果** / **总结**` template — just a plain sentence
    the user can read at a glance. The raw SQL is still preserved on the
    payload's ``sql`` field for debugging.
    """
    q = (question or "").strip()
    q_clause = f"「{q}」" if q else "这次"

    if not executed:
        # SQL never ran successfully — generation failed or all attempts
        # were rejected. Keep the error short and non-technical.
        lines = [
            f"抱歉，{q_clause}没能查到数据，可能是这个口径暂时无法直接从数据库取到，"
            "或者查询语句执行失败了。",
            "你可以换个说法再试一次，比如缩小时间范围、指定具体的单位或机型，"
            "我会再尝试生成查询。",
        ]
        if error:
            # Keep technical details out of the main message, but expose a
            # short hint so power users can see what went wrong.
            lines.append(f"\n_技术原因：{error[:200]}_")
        return "\n\n".join(lines)

    # executed == True, but zero rows.
    return (
        f"已经按{q_clause}的口径查询了数据库，但在当前条件下没有命中任何记录。\n\n"
        "可能是时间范围、地区或筛选条件偏窄。你可以换一个时间段或更宽的条件再问一次，"
        "我再帮你查。"
    )


def _rows_to_markdown_table(
    rows: list[dict[str, Any]], columns: list[str], *, max_rows: int = 20
) -> str:
    """Render the query rows as a simple Markdown table."""
    if not rows or not columns:
        return ""
    head = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    body_rows = rows[:max_rows]
    body = "\n".join(
        "| "
        + " | ".join(
            "" if r.get(c) is None else str(r.get(c)) for c in columns
        )
        + " |"
        for r in body_rows
    )
    extra = (
        f"\n\n_（共 {len(rows)} 行，仅展示前 {max_rows} 行）_"
        if len(rows) > max_rows
        else ""
    )
    return f"{head}\n{sep}\n{body}{extra}"


def _replace_result_block_with_rows(
    text: str | None,
    *,
    rows: list[dict[str, Any]],
    columns: list[str],
) -> str | None:
    """Overwrite the **结果** section with a Markdown table built from rows.

    Falls back to appending a fresh **结果** block when the answer does not
    yet contain one.
    """
    table = _rows_to_markdown_table(rows, columns)
    if not table:
        return text
    replacement_body = f"{table}\n\n"
    if not text:
        return f"**结果**\n{replacement_body}".rstrip()
    if _RESULT_BLOCK_RE.search(text):
        return _RESULT_BLOCK_RE.sub(
            lambda m: f"{m.group(1)}{replacement_body}", text, count=1
        ).rstrip()
    return f"{text.rstrip()}\n\n**结果**\n{replacement_body}".rstrip()


def _append_chart_markdown(
    answer_text: str | None, chart: ChartArtifact
) -> str:
    image_md = f"![chart]({chart.url})"
    if not answer_text:
        return image_md
    return f"{answer_text.rstrip()}\n\n{image_md}"


# ----------------------------------------------------------------------
# Factory helpers
# ----------------------------------------------------------------------


def build_text2sql_service_from_settings(
    *,
    agent: Text2SqlAgent | None = None,
) -> Text2SqlService:
    """Build a :class:`Text2SqlService` from the global settings."""
    settings = get_settings()
    config = settings.fly_report.text2sql
    if not config.enabled:
        raise Text2SqlConfigError("FlyReport text2sql is disabled in config")

    if agent is None:
        agent = Text2SqlAgent(config=config, model_config=settings.agent.model)

    return Text2SqlService(config=config, agent=agent)


__all__ = [
    "QueryResult",
    "Text2SqlAnswer",
    "Text2SqlService",
    "build_text2sql_service_from_settings",
]
