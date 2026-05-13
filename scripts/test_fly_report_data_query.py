"""Manual smoke test for the data-query branch of FlyReportService.

Specifically exercises :meth:`FlyReportService._run_data_query_interaction`
end-to-end, i.e. the Text-to-SQL pipeline:

1. Starts a session.
2. Submits a data-query utterance via ``start_streaming_message``.
3. Subscribes to ``stream_interaction_events`` and prints every event the
   service publishes (``interaction.started`` → phase updates →
   ``message.item`` for the SQL/result → ``interaction.completed``).

A real :class:`IntentClassifier` is wired up so the LLM actually decides
the route, and a real :class:`Text2SqlService` is built from
``configs/default.yaml`` + ``configs/fly_report.yaml`` + ``.env`` so the
generated SQL is executed against PostgreSQL just like in production.

The chitchat path's heavy report fields (intent_parser / data_fetcher)
are stubbed out — neither is touched on the data-query branch.

Usage::

    python scripts/test_fly_report_data_query.py
    python scripts/test_fly_report_data_query.py "本月每个部门的飞行任务数"
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from swarmmind.config.settings import get_settings
from swarmmind.domains.fly_report.intent.classifier import IntentClassifier
from swarmmind.domains.fly_report.lm import OpenAICompatibleLMClient
from swarmmind.domains.fly_report.service import FlyReportService
from swarmmind.domains.fly_report.text2sql import (
    build_text2sql_service_from_settings,
)
from swarmmind.domains.fly_report.text2sql.errors import Text2SqlError

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DATA_QUERY_TEXT = "上个月每个部门的飞行任务数"


# ---------- model wiring (configuration-driven, mirrors composer)


def _mask_secret(value: str | None) -> str:
    if not value:
        return "<missing>"
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _build_lm_clients() -> tuple[OpenAICompatibleLMClient, OpenAICompatibleLMClient]:
    """Return ``(classifier_client, chitchat_client)`` wired from settings.

    Both clients hit the same chat endpoint declared in ``agent.model``.
    The classifier emits a small JSON object (tight token budget); the
    chitchat fallback needs more room for the natural-language reply.
    """
    settings = get_settings()
    model = settings.agent.model

    print("FlyReport data-query probe")
    print(f"  model: {model.name}")
    print(f"  base_url: {model.base_url or '<missing>'}")
    print(f"  api_key: {_mask_secret(model.api_key)}")
    print(f"  text2sql.knowledge_path: {settings.fly_report.text2sql.knowledge_path}")
    print(
        "  text2sql.postgres_dsn:",
        "<set>" if settings.fly_report.text2sql.postgres_dsn else "<missing>",
    )

    if not model.api_key:
        raise SystemExit(
            "data-query probe failed: agent.model.api_key is not configured."
        )
    if not model.base_url:
        raise SystemExit(
            "data-query probe failed: agent.model.base_url is not configured."
        )

    classifier_client = OpenAICompatibleLMClient(
        model_name=model.name,
        api_key=model.api_key,
        base_url=model.base_url,
        temperature=float(model.temperature),
        max_tokens=128,
        timeout_sec=30.0,
    )
    chitchat_client = OpenAICompatibleLMClient(
        model_name=model.name,
        api_key=model.api_key,
        base_url=model.base_url,
        temperature=float(model.temperature),
        max_tokens=512,
        timeout_sec=60.0,
    )
    return classifier_client, chitchat_client


# ---------- minimal stubs for fields the data-query branch never touches


class _UnusedIntentParser:
    """Placeholder — data-query path does not call ``parse``."""

    async def parse(self, **_: Any) -> Any:  # pragma: no cover - safety net
        raise AssertionError(
            "intent parser should not be invoked on data-query path"
        )


class _UnusedDataFetcher:
    """Placeholder — data-query path does not call any fetcher method."""

    async def fetch(self, *_: Any, **__: Any) -> Any:  # pragma: no cover
        raise AssertionError(
            "data fetcher should not be invoked on data-query path"
        )

    async def get_department_name_list_by_id_list(
        self, *_: Any, **__: Any
    ) -> list[str]:  # pragma: no cover
        raise AssertionError(
            "data fetcher should not be invoked on data-query path"
        )


def _build_service() -> FlyReportService:
    classifier_client, chitchat_client = _build_lm_clients()

    try:
        text2sql_service = build_text2sql_service_from_settings()
    except Text2SqlError as exc:
        raise SystemExit(
            f"data-query probe failed: text2sql service unavailable — {exc}"
        ) from exc

    print(
        "  text2sql service ready"
    )

    return FlyReportService(
        intent_parser=_UnusedIntentParser(),  # type: ignore[arg-type]
        data_fetcher=_UnusedDataFetcher(),  # type: ignore[arg-type]
        output_root=Path(tempfile.mkdtemp(prefix="fly_report_data_query_")),
        intent_classifier=IntentClassifier(client=classifier_client),
        chitchat_client=chitchat_client,
        text2sql_service=text2sql_service,
    )


# ---------- the actual probe


async def main(query_text: str) -> int:
    service = _build_service()

    session_id = await service.start_session(
        tenant_id="probe-tenant", user_id="probe-user"
    )
    print(f"\nsession_id = {session_id}")

    interaction = await service.start_streaming_message(
        session_id, query_text, user_id="probe-user"
    )
    print(f"interaction_id = {interaction.id}")
    print(f"input_text     = {query_text!r}\n")

    print("--- stream events ---")
    seen_events: list[str] = []
    async for event in service.stream_interaction_events(interaction.id):
        seen_events.append(event["event"])
        print(json.dumps(event, ensure_ascii=False, default=str))

    final = await service.get_interaction(interaction.id)
    print("\n--- summary ---")
    print(f"status         = {final.status}")
    print(f"phase          = {final.phase}")
    print(f"message_count  = {final.message_count}")
    print(f"events         = {seen_events}")
    if final.error:
        print(f"error          = {final.error}")

    messages = await service.list_messages(
        session_id, user_id="probe-user", limit=20
    )
    print("\n--- messages ---")
    for msg in messages:
        print(f"[{msg.role:<9}] ({msg.message_type}) {msg.text}")
        if isinstance(msg.payload, dict):
            data = msg.payload.get("data") or {}
            if data.get("intent") == "data_query":
                print("  payload.data:")
                print(
                    "   ",
                    json.dumps(
                        {
                            k: v
                            for k, v in data.items()
                            if k != "result"  # printed below in tabular form
                        },
                        ensure_ascii=False,
                        default=str,
                    ),
                )
                result = data.get("result")
                if isinstance(result, dict):
                    print(
                        "  result:"
                        f" columns={result.get('columns')}"
                        f" row_count={result.get('row_count')}"
                        f" truncated={result.get('truncated')}"
                    )
                    rows = result.get("rows") or []
                    for row in rows[:10]:
                        print("   ", row)
                    if len(rows) > 10:
                        print(f"    ... (+{len(rows) - 10} more rows)")

    ok = final.status == "completed" and any(
        isinstance(m.payload, dict)
        and (m.payload.get("data") or {}).get("intent") == "data_query"
        and (m.payload.get("data") or {}).get("sql")
        for m in messages
    )
    return 0 if ok else 1


if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DATA_QUERY_TEXT
    try:
        raise SystemExit(asyncio.run(main(text)))
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130)
