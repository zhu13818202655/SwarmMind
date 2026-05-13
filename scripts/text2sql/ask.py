"""Interactive Text-to-SQL CLI powered by the FlyReport Vanna 2.0 agent.

Usage:
    python scripts/text2sql/ask.py                      # interactive REPL
    python scripts/text2sql/ask.py "your question"      # one-shot

Inside the REPL, type `:q` or Ctrl-D to exit. Use `:new` to start a
fresh conversation (drops the per-turn agent memory).
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from swarmmind.config.settings import get_settings
from swarmmind.domains.fly_report.text2sql import (
    Text2SqlAgent,
    Text2SqlAgentResult,
    Text2SqlConfigError,
)


async def _ask(
    agent: Text2SqlAgent,
    question: str,
    conversation_id: str | None,
) -> Text2SqlAgentResult:
    return await agent.ask(question, conversation_id=conversation_id)


def _render(result: Text2SqlAgentResult) -> None:
    print()
    print(result.answer)
    if result.sql:
        print(f"\n[captured SQL] {result.sql}")
    if result.row_count:
        print(f"[rows] {result.row_count}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "question", nargs="*", help="one-shot question (otherwise REPL)"
    )
    args = ap.parse_args()

    settings = get_settings()
    cfg = settings.fly_report.text2sql
    print(f"[knowledge] {cfg.knowledge_path}")
    print(f"[postgres ] {'<set>' if cfg.postgres_dsn else '<missing>'}")

    try:
        agent = Text2SqlAgent()
    except Text2SqlConfigError as exc:
        print(f"[fatal] {exc}", file=sys.stderr)
        return 1

    if args.question:
        question = " ".join(args.question)
        result = asyncio.run(_ask(agent, question, None))
        _render(result)
        return 0

    conv_id: str | None = None
    print("FlyReport Text-to-SQL REPL — type :q to quit, :new for new turn\n")
    while True:
        try:
            q = input("ask> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not q:
            continue
        if q in (":q", ":quit", ":exit"):
            return 0
        if q == ":new":
            conv_id = None
            print("(new conversation)")
            continue
        result = asyncio.run(_ask(agent, q, conv_id))
        conv_id = result.conversation_id or conv_id
        _render(result)


if __name__ == "__main__":
    raise SystemExit(main())
