from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import yaml
from openai import APIConnectionError, APIStatusError, AsyncOpenAI, AuthenticationError, RateLimitError


def _mask_secret(value: str | None) -> str:
	if not value:
		return "<missing>"
	if len(value) <= 8:
		return "*" * len(value)
	return f"{value[:4]}...{value[-4:]}"


def _build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Probe the configured chat completion endpoint.")
	parser.add_argument("--prompt", default="Reply with exactly: model access ok", help="User prompt to send")
	parser.add_argument("--model", help="Override model name")
	parser.add_argument("--base-url", help="Override base URL")
	parser.add_argument("--api-key", help="Override API key")
	parser.add_argument("--max-tokens", type=int, default=64, help="Max completion tokens")
	"""
	api status error: status=400 body={'message': "litellm.BadRequestError: AzureException BadRequestError - Unsupported value: 'temperature' does not support 0.7 with this model. Only the default (1) value is supported.. Received Model Group=gpt-5.2-chat\nAvailable Model Group Fallbacks=None", 'type': 'invalid_request_error', 'param': 'temperature', 'code': '400'}
	"""
	parser.add_argument("--temperature", type=float, default=1.0, help="Sampling temperature; omit to let the model use its default")
	parser.add_argument("--timeout", type=float, default=30.0, help="Request timeout in seconds")
	parser.add_argument("--dump-json", action="store_true", help="Print the raw response JSON")
	return parser


def _load_dotenv(path: Path) -> dict[str, str]:
	values: dict[str, str] = {}
	if not path.exists():
		return values

	for raw_line in path.read_text(encoding="utf-8").splitlines():
		line = raw_line.strip()
		if not line or line.startswith("#") or "=" not in line:
			continue
		key, value = line.split("=", 1)
		values[key.strip()] = value.strip()
	return values


def _load_default_model_name(config_path: Path) -> str:
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


def _resolve_runtime_config(args: argparse.Namespace) -> dict[str, Any]:
	repo_root = Path(__file__).resolve().parents[1]
	dotenv_values = _load_dotenv(repo_root / ".env")
	default_model_name = _load_default_model_name(repo_root / "configs" / "default.yaml")
	return {
		"model": args.model or dotenv_values.get("OPENAI_MODEL") or default_model_name,
		"api_key": args.api_key or dotenv_values.get("OPENAI_API_KEY"),
		"base_url": args.base_url or dotenv_values.get("OPENAI_BASE_URL"),
		"temperature": args.temperature,
		"max_tokens": args.max_tokens,
		"timeout": args.timeout,
		"prompt": args.prompt,
	}


async def _run_probe(args: argparse.Namespace) -> int:
	runtime = _resolve_runtime_config(args)
	model = runtime["model"]
	api_key = runtime["api_key"]
	base_url = runtime["base_url"]

	print("Resolved model probe config:")
	print(f"  model: {model}")
	print(f"  base_url: {base_url or '<missing>'}")
	print(f"  api_key: {_mask_secret(api_key)}")
	print(f"  timeout: {runtime['timeout']}s")

	if not model:
		print("error: model is missing", file=sys.stderr)
		return 2
	if not api_key:
		print("error: api_key is missing", file=sys.stderr)
		return 2
	if not base_url:
		print("error: base_url is missing", file=sys.stderr)
		return 2

	client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=runtime["timeout"])

	try:
		request_kwargs: dict[str, Any] = {
			"model": model,
			"messages": [
				{"role": "system", "content": "You are a connectivity probe. Respond briefly and plainly."},
				{"role": "user", "content": runtime["prompt"]},
			],
			"max_tokens": runtime["max_tokens"],
		}
		if runtime["temperature"] is not None:
			request_kwargs["temperature"] = runtime["temperature"]

		response = await client.chat.completions.create(**request_kwargs)
	except AuthenticationError as exc:
		print(f"authentication failed: {exc}", file=sys.stderr)
		return 1
	except RateLimitError as exc:
		print(f"rate limit hit: {exc}", file=sys.stderr)
		return 1
	except APIStatusError as exc:
		print(f"api status error: status={exc.status_code} body={exc.body}", file=sys.stderr)
		return 1
	except APIConnectionError as exc:
		print(f"connection failed: {exc}", file=sys.stderr)
		return 1
	except Exception as exc:
		print(f"unexpected error: {type(exc).__name__}: {exc}", file=sys.stderr)
		return 1
	finally:
		await client.close()

	first_choice = response.choices[0] if response.choices else None
	first_message = first_choice.message if first_choice is not None else None
	text_content = first_message.content if first_message is not None else None

	print("Probe succeeded.")
	print(f"  id: {response.id}")
	print(f"  model: {response.model}")
	print(f"  finish_reason: {first_choice.finish_reason if first_choice is not None else '<missing>'}")
	if response.usage is not None:
		print(
			"  usage: prompt_tokens={0} completion_tokens={1} total_tokens={2}".format(
				response.usage.prompt_tokens,
				response.usage.completion_tokens,
				response.usage.total_tokens,
			)
		)
	print("  first_reply:")
	print(text_content if text_content else "  <empty>")

	if args.dump_json:
		print("\nRaw response JSON:")
		print(json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2))

	return 0


def main() -> int:
	parser = _build_parser()
	args = parser.parse_args()
	print(args)
	return asyncio.run(_run_probe(args))


if __name__ == "__main__":
	raise SystemExit(main())
