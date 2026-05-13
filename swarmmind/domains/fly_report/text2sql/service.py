"""Service facade for the FlyReport Text-to-SQL pipeline.

Backed by :class:`Text2SqlAgent` (Vanna 2.0 multi-tool agent loop over a
hand-curated YAML knowledge base). The service preserves the response
shape (:class:`Text2SqlAnswer`) consumed by
:mod:`swarmmind.domains.fly_report.service` so the rest of the FlyReport
pipeline keeps working unchanged.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

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

logger = logging.getLogger(__name__)


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
    ) -> Text2SqlAnswer:
        question = (question or "").strip()
        if not question:
            return Text2SqlAnswer(question=question, error="question is empty")

        try:
            result = await self._agent.ask(
                question, conversation_id=conversation_id
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

    chart: ChartArtifact | None = None
    if executed and rows:
        chart = build_chart_for_text2sql(
            rows=rows, question=result.question, sql=result.sql
        )
        if chart is not None:
            answer_text = _append_chart_markdown(answer_text, chart)

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
