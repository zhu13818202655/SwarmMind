"""Manual smoke test for the chitchat branch of FlyReportService.

Specifically exercises :meth:`FlyReportService._run_plain_text_interaction`
end-to-end:

1. Starts a session.
2. Submits a chitchat utterance via ``start_streaming_message``.
3. Subscribes to ``stream_interaction_events`` and prints every event the
   service publishes (``interaction.started`` → ``message.delta`` chunks
   → ``message.item`` → ``interaction.completed``).

Skips the heavy report pipeline by injecting trivial stubs for
``intent_parser`` / ``data_fetcher`` — neither is exercised on the
chitchat branch — but uses a real :class:`IntentClassifier` so the LLM
actually decides the route. Wiring mirrors ``test_fly_report_intent.py``.

Usage::

    python scripts/test_fly_report_chitchat.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

from swarmmind.domains.fly_report.intent.classifier import IntentClassifier
from swarmmind.domains.fly_report.lm import OpenAICompatibleLMClient
from swarmmind.domains.fly_report.service import FlyReportService

REPO_ROOT = Path(__file__).resolve().parents[1]

CHITCHAT_TEXT = "介绍一下 VIT"


# ---------- .env / model wiring (kept in sync with test_fly_report_intent.py)


def _mask_secret(value: str | None) -> str:
    if not value:
        return "<missing>"
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _load_default_model_name() -> str:
    config_path = REPO_ROOT / "configs" / "default.yaml"
    if not config_path.exists():
        return "gpt-5.2-chat"
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return "gpt-5.2-chat"
    agent = data.get("agent") if isinstance(data, dict) else None
    model = agent.get("model") if isinstance(agent, dict) else None
    if isinstance(model, dict) and isinstance(model.get("name"), str):
        name = model["name"].strip()
        if name and "${" not in name:
            return name
    return "gpt-5.2-chat"


def _build_lm_clients() -> tuple[OpenAICompatibleLMClient, OpenAICompatibleLMClient]:
    """Return ``(classifier_client, chitchat_client)`` wired from .env.

    The classifier only needs to emit a small JSON object so a tight token
    budget is fine; the chitchat reply needs more room and a longer timeout.
    """
    dotenv = _load_dotenv(REPO_ROOT / ".env")
    model_name = dotenv.get("OPENAI_MODEL") or _load_default_model_name()
    base_url = dotenv.get("OPENAI_BASE_URL")
    api_key = dotenv.get("OPENAI_API_KEY")

    print("FlyReport chitchat probe")
    print(f"  .env: {REPO_ROOT / '.env'}")
    print(f"  model: {model_name}")
    print(f"  base_url: {base_url or '<missing>'}")
    print(f"  api_key: {_mask_secret(api_key)}")

    if not api_key:
        raise SystemExit("chitchat probe failed: OPENAI_API_KEY is missing in .env")
    if not base_url:
        raise SystemExit("chitchat probe failed: OPENAI_BASE_URL is missing in .env")

    classifier_client = OpenAICompatibleLMClient(
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=1.0,
        max_tokens=128,
        timeout_sec=30.0,
    )
    chitchat_client = OpenAICompatibleLMClient(
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=1.0,
        max_tokens=512,
        timeout_sec=60.0,
    )
    return classifier_client, chitchat_client


# ---------- minimal stubs for fields the chitchat branch never touches


class _UnusedIntentParser:
    """Placeholder — chitchat path does not call ``parse``."""

    async def parse(self, **_: Any) -> Any:  # pragma: no cover - safety net
        raise AssertionError("intent parser should not be invoked on chitchat path")


class _UnusedDataFetcher:
    """Placeholder — chitchat path does not call any fetcher method."""

    async def fetch(self, *_: Any, **__: Any) -> Any:  # pragma: no cover
        raise AssertionError("data fetcher should not be invoked on chitchat path")

    async def get_department_name_list_by_id_list(
        self, *_: Any, **__: Any
    ) -> list[str]:  # pragma: no cover
        raise AssertionError("data fetcher should not be invoked on chitchat path")


def _build_service() -> FlyReportService:
    classifier_client, chitchat_client = _build_lm_clients()
    return FlyReportService(
        intent_parser=_UnusedIntentParser(),  # type: ignore[arg-type]
        data_fetcher=_UnusedDataFetcher(),  # type: ignore[arg-type]
        output_root=Path(tempfile.mkdtemp(prefix="fly_report_chitchat_")),
        intent_classifier=IntentClassifier(client=classifier_client),
        chitchat_client=chitchat_client,
    )


# ---------- the actual probe


async def main() -> int:
    service = _build_service()

    session_id = await service.start_session(
        tenant_id="probe-tenant", user_id="probe-user"
    )
    print(f"\nsession_id = {session_id}")

    interaction = await service.start_streaming_message(
        session_id, CHITCHAT_TEXT, user_id="probe-user"
    )
    print(f"interaction_id = {interaction.id}")
    print(f"input_text     = {CHITCHAT_TEXT!r}\n")

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

    messages = await service.list_messages(
        session_id, user_id="probe-user", limit=20
    )
    print("\n--- messages ---")
    for msg in messages:
        print(f"[{msg.role:<9}] ({msg.message_type}) {msg.text}")

    ok = (
        final.status == "completed"
        and any(m.role == "assistant" and m.message_type == "plain_text" for m in messages)
    )
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130)
