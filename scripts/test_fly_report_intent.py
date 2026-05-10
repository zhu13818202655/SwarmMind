"""Manual smoke test for :class:`IntentClassifier` against the real LLM.

Not part of the automated test suite — model calls cost money and are
non-deterministic. Use this script to sanity-check that the prompt still
maps representative utterances to the expected bucket whenever the model
or prompt changes.

Mirrors the wiring in ``scripts/test_fly_report_lm.py``: read ``.env``
explicitly and pass model/base_url/api_key into the LM client, so the
script does not silently rely on ``get_settings()`` picking the right
values up.

Usage::

    python scripts/test_fly_report_intent.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import yaml

from swarmmind.domains.fly_report.intent.classifier import IntentClassifier
from swarmmind.domains.fly_report.lm import OpenAICompatibleLMClient

REPO_ROOT = Path(__file__).resolve().parents[1]

CASES: list[tuple[str, str]] = [
    ("chitchat", "你好呀"),
    ("chitchat", "谢谢，辛苦了"),
    ("chitchat", "今天心情不错"),
    ("report", "帮我生成本周武义县资规局的飞行报告"),
    ("report", "导出上周全县的算法识别月报为 docx"),
    ("report", "再生成一份本月的飞行 + 媒体统计"),
    ("data_query", "上周哪个部门的飞行次数最多？"),
    ("data_query", "查一下昨天 12:00-14:00 违停告警的明细"),
    ("data_query", "本月违建识别一共发生了多少次？"),
]


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
        # configs/default.yaml uses ``${OPENAI_MODEL}`` placeholders that
        # ``yaml.safe_load`` does not expand. Treat unresolved placeholders
        # as "no value" so we fall through to the safe default.
        if name and "${" not in name:
            return name
    return "gpt-5.2-chat"


def _build_classifier() -> IntentClassifier:
    dotenv = _load_dotenv(REPO_ROOT / ".env")
    model_name = dotenv.get("OPENAI_MODEL") or _load_default_model_name()
    base_url = dotenv.get("OPENAI_BASE_URL")
    api_key = dotenv.get("OPENAI_API_KEY")

    print("FlyReport intent classifier probe")
    print(f"  .env: {REPO_ROOT / '.env'}")
    print(f"  model: {model_name}")
    print(f"  base_url: {base_url or '<missing>'}")
    print(f"  api_key: {_mask_secret(api_key)}")

    if not api_key:
        raise SystemExit("intent probe failed: OPENAI_API_KEY is missing in .env")
    if not base_url:
        raise SystemExit("intent probe failed: OPENAI_BASE_URL is missing in .env")

    client = OpenAICompatibleLMClient(
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=1.0,
        max_tokens=128,
        timeout_sec=30.0,
    )
    return IntentClassifier(client=client)


async def main() -> int:
    classifier = _build_classifier()
    correct = 0
    for expected, text in CASES:
        actual = await classifier.classify(text)
        mark = "✓" if actual == expected else "✗"
        if actual == expected:
            correct += 1
        print(f"{mark} expected={expected:<10} actual={actual:<10}  {text}")
    print(f"\n{correct}/{len(CASES)} matched")
    return 0 if correct == len(CASES) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130)
