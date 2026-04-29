from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import yaml

from swarmmind.domains.fly_report.lm import LMOutputFormat, OpenAICompatibleLMClient


SYSTEM_PROMPT = "你是一个人工智能助手"
REPO_ROOT = Path(__file__).resolve().parents[1]


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
    if isinstance(model, dict) and isinstance(model.get("name"), str) and model["name"].strip():
        return model["name"].strip()
    return "gpt-5.2-chat"


async def test_text(client: OpenAICompatibleLMClient) -> None:
    text = await client.chat(
        system_prompt=SYSTEM_PROMPT,
        user_prompt="介绍下鲁迅",
        output_format=LMOutputFormat.TEXT,
        max_tokens=128,
    )
    print("\n=== TEXT ===")
    print(text)


async def test_markdown(client: OpenAICompatibleLMClient) -> None:
    markdown = await client.chat(
        system_prompt="You write compact Markdown. Return only Markdown.",
        user_prompt="Create a tiny checklist with three items for testing an LM client.",
        output_format=LMOutputFormat.MARKDOWN,
        max_tokens=160,
    )
    print("\n=== MARKDOWN ===")
    print(markdown)


async def test_json(client: OpenAICompatibleLMClient) -> None:
    response = await client.chat_response(
        request=client_request_json(),
    )
    print("\n=== JSON TEXT ===")
    print(response.text)
    print("\n=== JSON PARSED ===")
    print(json.dumps(response.parsed, ensure_ascii=False, indent=2))


def client_request_json():
    from swarmmind.domains.fly_report.lm import LMChatRequest

    return LMChatRequest(
        system_prompt="Only return a JSON object. Do not include Markdown or explanation.",
        user_prompt=(
            "Return a JSON object with keys: status, format, message. "
            "Use status='ok', format='json', and a short Chinese message."
        ),
        output_format=LMOutputFormat.JSON,
        response_format={"type": "json_object"},
        max_tokens=160,
    )


async def main() -> int:
    dotenv = _load_dotenv(REPO_ROOT / ".env")
    model_name = dotenv.get("OPENAI_MODEL") or _load_default_model_name()
    base_url = dotenv.get("OPENAI_BASE_URL")
    api_key = dotenv.get("OPENAI_API_KEY")

    print("FlyReport lightweight LM probe")
    print(f"  .env: {REPO_ROOT / '.env'}")
    print(f"  model: {model_name}")
    print(f"  base_url: {base_url or '<missing>'}")
    print(f"  api_key: {_mask_secret(api_key)}")

    if not api_key:
        print("LM probe failed: OPENAI_API_KEY is missing in .env", file=sys.stderr)
        return 2
    if not base_url:
        print("LM probe failed: OPENAI_BASE_URL is missing in .env", file=sys.stderr)
        return 2

    client = OpenAICompatibleLMClient(
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=1.0,
        max_tokens=16384,
        timeout_sec=30.0,
    )

    try:
        await test_text(client)
        # await test_markdown(client)
        # await test_json(client)
    except Exception as exc:
        print(f"LM probe failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
