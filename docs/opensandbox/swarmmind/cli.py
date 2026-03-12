"""CLI for running data analysis inside OpenSandbox."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from swarmmind.config import load_settings
from swarmmind.sandbox.opensandbox_adapter import OpenSandboxAdapter
from swarmmind.services.data_analysis_service import DataAnalysisRequest, DataAnalysisService


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run sandboxed Python data analysis")
    parser.add_argument("--input", required=True, help="Path to input JSON file (array of objects)")
    parser.add_argument("--task-id", required=True, help="Task id for traceability")
    parser.add_argument("--agent-id", default="data-agent", help="Agent id")
    parser.add_argument("--subtask-id", default="analysis-01", help="Subtask id")
    parser.add_argument("--profile", default="data-medium", help="Sandbox profile")
    return parser


async def _run(args: argparse.Namespace) -> int:
    settings = load_settings()
    adapter = OpenSandboxAdapter(
        api_key=settings.open_sandbox_api_key,
        base_url=settings.open_sandbox_base_url,
        create_retry_count=settings.create_retry_count,
        create_retry_backoff_seconds=settings.create_retry_backoff_seconds,
    )

    input_path = Path(args.input)
    rows = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("Input file must be a JSON array")

    service = DataAnalysisService(adapter, profile=args.profile)
    result = await service.run(
        DataAnalysisRequest(
            task_id=args.task_id,
            agent_id=args.agent_id,
            subtask_id=args.subtask_id,
            rows=rows,
        )
    )

    print(
        json.dumps(
            {
                "task_id": result.task_id,
                "sandbox_id": result.sandbox_id,
                "success": result.success,
                "exit_code": result.exit_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "result": result.result,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.success else 1


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
