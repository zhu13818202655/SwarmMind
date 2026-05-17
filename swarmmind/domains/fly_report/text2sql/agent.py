"""Vanna 2.0 Agent-based Text-to-SQL client for the FlyReport domain.

Ported from ``docs/FlyReport/dikong/t2s/client.py`` and adapted to read
all runtime configuration from :func:`swarmmind.config.settings.get_settings`
instead of loading a local ``.env``.

Design (mirrors the dikong reference):

* The LLM drives a multi-turn agent loop that decides when to call SQL
  introspection / business-knowledge tools and when to run a SELECT.
* All SQL execution flows through :class:`tools.GuardedRunSqlTool`, which
  rejects anything that is not ``SELECT`` / ``WITH`` or touches a
  blacklisted table (Quartz / PostGIS / MQTT / audit). PG-side safety
  comes from a connection DSN with ``options=-c statement_timeout=…``.
* Business knowledge (focus tables, JOIN hints, metric definitions,
  golden Q→SQL pairs, blacklist) is hand-curated YAML under
  :attr:`FlyReportText2SqlConfig.knowledge_path`.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vanna import Agent, AgentConfig
from vanna.core.registry import ToolRegistry
from vanna.core.system_prompt.default import DefaultSystemPromptBuilder
from vanna.core.user import RequestContext, User, UserResolver
from vanna.integrations.local import LocalFileSystem
from vanna.integrations.local.agent_memory import DemoAgentMemory
from vanna.integrations.openai import OpenAILlmService
from vanna.integrations.postgres import PostgresRunner
from vanna.tools.agent_memory import (
    SaveTextMemoryTool,
    SearchSavedCorrectToolUsesTool,
)

from swarmmind.config.schema import FlyReportText2SqlConfig, ModelConfig
from swarmmind.config.settings import get_settings
from swarmmind.domains.fly_report.text2sql.errors import (
    Text2SqlConfigError,
    Text2SqlGenerationError,
)
from swarmmind.domains.fly_report.text2sql.knowledge import (
    Knowledge,
    load_knowledge,
)
from swarmmind.domains.fly_report.text2sql.prompt import build_system_prompt
from swarmmind.domains.fly_report.text2sql.tools import (
    FindGoldenExamplesTool,
    GuardedRunSqlTool,
    ListAllowedTablesTool,
    LookupMetricTool,
    LookupTableInfoTool,
    SqlCaptureBuffer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class Text2SqlAgentResult:
    """Outcome of one agent turn."""

    question: str
    answer: str
    sql: str | None = None
    rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    conversation_id: str = ""
    success: bool = True
    error: str | None = None
    trace: list[dict[str, Any]] = field(default_factory=list)
    sql_attempts: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------
_SILENT_RICH_TYPES = {
    "ComponentType.TASK_TRACKER_UPDATE",
    "ComponentType.CHAT_INPUT_UPDATE",
}
_NOISE_SUFFIXES = ("**IMPORTANT: FOR VISUALIZE_DATA USE FILENAME:",)
_FINAL_HINTS = ("**总结**", "**sql**", "**结果**", "**summary**", "**result**")


def _component_text(component) -> tuple[str | None, str | None]:
    """Return ``(text, semantic_type)`` for a streamed component."""
    rich = getattr(component, "rich_component", None)
    simple = getattr(component, "simple_component", None)
    rich_type = str(getattr(rich, "type", "")) if rich is not None else ""
    if rich_type in _SILENT_RICH_TYPES:
        return None, None

    for obj in (simple, rich):
        if obj is None:
            continue
        for attr in ("text", "content", "message", "markdown"):
            val = getattr(obj, attr, None)
            if isinstance(val, str):
                lines = [
                    ln
                    for ln in val.splitlines()
                    if not any(ln.lstrip().startswith(s) for s in _NOISE_SUFFIXES)
                ]
                txt = "\n".join(lines).strip()
                if not txt:
                    return None, None
                sem = getattr(obj, "semantic_type", None)
                return txt, str(sem) if sem else None
    return None, None


def _pick_final_answer(texts: list[str]) -> str:
    """Heuristic pick of the model's final reply out of the streamed turn."""
    for t in reversed(texts):
        low = t.lower()
        if any(h in low for h in _FINAL_HINTS):
            return t
    return texts[-1]


# ---------------------------------------------------------------------------
# Helpers — single permissive user (no ACL surface in FlyReport today).
# ---------------------------------------------------------------------------
class _FlyReportUserResolver(UserResolver):
    async def resolve_user(self, request_context: RequestContext) -> User:
        return User(
            id="fly-report-bot",
            username="fly-report-bot",
            email="bot@fly-report.local",
            group_memberships=["admin", "user"],
        )


def _augment_dsn_with_timeout(dsn: str, ms: int) -> str:
    if "statement_timeout" in dsn:
        return dsn
    sep = "&" if "?" in dsn else "?"
    return f"{dsn}{sep}options=-c%20statement_timeout%3D{int(ms)}"


def _extract_sql_from_answer(text: str) -> str | None:
    """Best-effort: pull the ``\\`\\`\\`sql ... \\`\\`\\``` block out of a markdown reply."""
    if not text:
        return None
    m = re.search(r"```sql\s*(.+?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if not m:
        return None
    sql = m.group(1).strip().rstrip(";").strip()
    return sql or None


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------
class Text2SqlAgent:
    """High-level Vanna 2.0 agent wrapper for FlyReport Text-to-SQL.

    Construction is heavyweight (loads YAML knowledge, opens a PG runner,
    builds the agent and tool registry). Re-use a single instance across
    requests.
    """

    def __init__(
        self,
        *,
        config: FlyReportText2SqlConfig | None = None,
        model_config: ModelConfig | None = None,
        knowledge_root: Path | str | None = None,
    ) -> None:
        settings = get_settings()
        self._config = config or settings.fly_report.text2sql
        self._model = model_config or settings.agent.model

        if not self._config.enabled:
            raise Text2SqlConfigError("FlyReport text2sql is disabled in config")
        if not self._model.api_key:
            raise Text2SqlConfigError(
                "agent.model.api_key is not configured (OPENAI_API_KEY)."
            )
        if not self._config.postgres_dsn:
            raise Text2SqlConfigError(
                "fly_report.text2sql.postgres_dsn is not configured."
            )

        # ---- 1. knowledge ----
        kn_root = Path(knowledge_root or self._config.knowledge_path).expanduser()
        if not kn_root.exists():
            raise Text2SqlConfigError(
                f"text2sql knowledge directory not found: {kn_root}"
            )
        self._knowledge: Knowledge = load_knowledge(kn_root)

        # ---- 2. LLM ----
        llm = OpenAILlmService(
            api_key=self._model.api_key,
            base_url=self._model.base_url or None,
            model=self._model.name,
        )

        # ---- 3. PG runner (read-only via DSN options) ----
        dsn = _augment_dsn_with_timeout(
            self._config.postgres_dsn,
            self._config.statement_timeout_ms,
        )
        sql_runner = PostgresRunner(connection_string=dsn)

        # ---- 4. shared SQL capture buffer ----
        self._capture = SqlCaptureBuffer()

        # ---- 5. tools ----
        agent_work_root = Path(self._config.knowledge_path).expanduser().parent
        fs = LocalFileSystem(
            working_directory=str(agent_work_root / "agent_work")
        )
        tools = ToolRegistry()
        tools.register_local_tool(
            GuardedRunSqlTool(
                sql_runner=sql_runner,
                knowledge=self._knowledge,
                capture=self._capture,
                max_rows=self._config.max_rows,
                file_system=fs,
            ),
            access_groups=[],
        )
        tools.register_local_tool(
            LookupTableInfoTool(sql_runner, self._knowledge), []
        )
        tools.register_local_tool(LookupMetricTool(self._knowledge), [])
        tools.register_local_tool(FindGoldenExamplesTool(self._knowledge), [])
        tools.register_local_tool(ListAllowedTablesTool(self._knowledge), [])
        tools.register_local_tool(SearchSavedCorrectToolUsesTool(), [])
        tools.register_local_tool(SaveTextMemoryTool(), [])

        # ---- 6. memory (always in-process for now) ----
        self._memory = DemoAgentMemory(max_items=2000)

        # ---- 7. agent ----
        system_prompt = build_system_prompt(self._knowledge)
        self._agent = Agent(
            llm_service=llm,
            tool_registry=tools,
            user_resolver=_FlyReportUserResolver(),
            agent_memory=self._memory,
            config=AgentConfig(
                stream_responses=False,
                temperature=float(self._model.temperature),
                max_tool_iterations=int(self._config.max_tool_iterations),
            ),
            system_prompt_builder=DefaultSystemPromptBuilder(
                base_prompt=system_prompt
            ),
            lifecycle_hooks=[],
        )
        self._request_context = RequestContext()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def knowledge(self) -> Knowledge:
        return self._knowledge

    async def ask(
        self,
        question: str,
        *,
        conversation_id: str | None = None,
    ) -> Text2SqlAgentResult:
        """Run one agent turn and return a structured result."""
        question = (question or "").strip()
        if not question:
            return Text2SqlAgentResult(
                question=question,
                answer="",
                success=False,
                error="question is empty",
            )

        cid = conversation_id or f"t2s-{uuid.uuid4().hex[:8]}"
        self._capture.clear(cid)

        trace: list[dict[str, Any]] = []
        intermediate_texts: list[str] = []

        try:
            async for component in self._agent.send_message(
                request_context=self._request_context,
                message=question,
                conversation_id=cid,
            ):
                txt, sem = _component_text(component)
                if txt is None:
                    continue
                trace.append({"semantic_type": sem, "text": txt})
                if sem is None or "TEXT" in sem.upper() or "MESSAGE" in sem.upper():
                    intermediate_texts.append(txt)
        except Exception as exc:  # noqa: BLE001
            logger.exception("fly_report.text2sql.agent_failed")
            raise Text2SqlGenerationError(str(exc)) from exc

        final_text = (
            _pick_final_answer(intermediate_texts) if intermediate_texts else ""
        )

        last_ok = self._capture.last_successful(cid)
        all_attempts = self._capture.runs(cid)

        sql = (last_ok or {}).get("sql") if last_ok else None
        if sql is None:
            # Fallback: scrape the ```sql``` block from the rendered answer.
            sql = _extract_sql_from_answer(final_text)

        return Text2SqlAgentResult(
            question=question,
            answer=final_text or "（无回答）",
            sql=sql,
            rows=(last_ok or {}).get("rows", []),
            row_count=(last_ok or {}).get("row_count", 0),
            conversation_id=cid,
            success=True,
            trace=trace,
            sql_attempts=all_attempts,
        )


__all__ = ["Text2SqlAgent", "Text2SqlAgentResult"]
