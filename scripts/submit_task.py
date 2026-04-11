"""Submit a task to a running SwarmMind service.

Usage examples:

    python scripts/submit_task.py
    python scripts/submit_task.py --goal "实现一个导出 Excel 功能并补测试"
    python scripts/submit_task.py --base-url http://127.0.0.1:8000 --poll
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}
RUN_TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(description="Submit a task to SwarmMind API")
    parser.add_argument("--goal", help="Task goal text. If omitted, the script will prompt for input.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="SwarmMind API base URL")
    parser.add_argument("--profile", default="aio", help="Sandbox profile")
    parser.add_argument("--agent-profile-id", help="Optional default agent profile id for the task")
    parser.add_argument("--preferred-strategy", help="Optional preferred top-level execution strategy")
    parser.add_argument("--priority", default="normal", help="Task priority")
    parser.add_argument(
        "--constraints-json",
        default="{}",
        help="JSON object string for task constraints, for example '{\"language\": \"python\"}'",
    )
    parser.add_argument(
        "--handoff-request",
        action="append",
        default=[],
        help="Optional handoff mapping in the form subtask_name=target_profile_id. Can be passed multiple times.",
    )
    parser.add_argument(
        "--handoff-target-profile-id",
        help="Optional default handoff target profile id used when no subtask-specific mapping is provided.",
    )
    parser.add_argument("--poll", action="store_true", help="Poll task status until it reaches a terminal state")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds")
    parser.add_argument("--timeout", type=float, default=3000.0, help="Polling timeout in seconds")
    parser.add_argument(
        "--wait-for-service",
        type=float,
        default=0.0,
        help="Wait up to N seconds for the API health endpoint before submitting the task",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=1800.0,
        help="HTTP request timeout in seconds for submit/query calls",
    )
    return parser


def read_goal(initial_goal: str | None) -> str:
    """Read the task goal from args or stdin."""
    if initial_goal and initial_goal.strip():
        return initial_goal.strip()

    print("请输入任务内容，结束后按回车：")
    goal = input("> ").strip()
    if not goal:
        raise ValueError("task goal must not be empty")
    return goal


def parse_constraints(raw: str) -> dict[str, object]:
    """Parse the constraints JSON string."""
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"constraints JSON is invalid: {exc}") from exc

    if not isinstance(value, dict):
        raise ValueError("constraints JSON must decode to an object")
    return value


def merge_cli_constraints(
    constraints: dict[str, object],
    *,
    handoff_requests: list[str],
    handoff_target_profile_id: str | None,
) -> dict[str, object]:
    """Merge convenience CLI flags into the task constraints object."""
    merged = dict(constraints)

    parsed_handoff_requests: dict[str, str] = {}
    for entry in handoff_requests:
        key, separator, value = entry.partition("=")
        key = key.strip()
        value = value.strip()
        if separator != "=" or not key or not value:
            raise ValueError(
                f"handoff request must be in the form subtask_name=target_profile_id, got: {entry!r}"
            )
        parsed_handoff_requests[key] = value

    if parsed_handoff_requests:
        existing = merged.get("handoff_requests")
        if existing is not None and not isinstance(existing, dict):
            raise ValueError("constraints.handoff_requests must be an object when provided")
        merged["handoff_requests"] = {
            **(existing if isinstance(existing, dict) else {}),
            **parsed_handoff_requests,
        }

    if handoff_target_profile_id:
        merged["handoff_target_profile_id"] = handoff_target_profile_id.strip()

    return merged


def submit_task(
    client: httpx.Client,
    base_url: str,
    payload: dict[str, object],
    request_timeout: float,
) -> dict[str, object]:
    """Submit the task and return the API response."""
    response = client.post(f"{base_url}/v1/tasks", json=payload, timeout=request_timeout)
    response.raise_for_status()
    return response.json()


def wait_for_service(client: httpx.Client, base_url: str, timeout: float) -> None:
    """Wait until the API health endpoint responds successfully."""
    if timeout <= 0:
        return

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            response = client.get(f"{base_url}/health", timeout=5.0)
            response.raise_for_status()
            return
        except httpx.HTTPError:
            time.sleep(1.0)

    raise TimeoutError(f"service did not become healthy within {timeout} seconds")


def fetch_task(client: httpx.Client, base_url: str, task_id: str, request_timeout: float) -> dict[str, object]:
    """Fetch the latest task state."""
    response = client.get(f"{base_url}/v1/tasks/{task_id}", timeout=request_timeout)
    response.raise_for_status()
    return response.json()


def fetch_run(client: httpx.Client, base_url: str, run_id: str, request_timeout: float) -> dict[str, object]:
    """Fetch the latest run detail."""
    response = client.get(f"{base_url}/v1/runs/{run_id}", timeout=request_timeout)
    response.raise_for_status()
    return response.json()


def poll_task(
    client: httpx.Client,
    base_url: str,
    task_id: str,
    interval: float,
    timeout: float,
    request_timeout: float,
) -> dict[str, object]:
    """Poll the task until it reaches a terminal state or timeout."""
    deadline = time.monotonic() + timeout
    last_payload: dict[str, object] | None = None

    while time.monotonic() < deadline:
        last_payload = fetch_task(client, base_url, task_id, request_timeout)
        status = str(last_payload.get("status", "")).lower()
        print(f"[poll] task_id={task_id} status={status}")
        if status in TERMINAL_STATUSES:
            return last_payload
        time.sleep(interval)

    raise TimeoutError(f"timed out waiting for task {task_id} after {timeout} seconds")


def poll_run(
    client: httpx.Client,
    base_url: str,
    run_id: str,
    interval: float,
    timeout: float,
    request_timeout: float,
) -> dict[str, object]:
    """Poll the run detail until it reaches a terminal state or timeout."""
    deadline = time.monotonic() + timeout
    last_payload: dict[str, object] | None = None

    while time.monotonic() < deadline:
        last_payload = fetch_run(client, base_url, run_id, request_timeout)
        run = last_payload.get("run", {}) if isinstance(last_payload, dict) else {}
        status = str(run.get("status", "")).lower() if isinstance(run, dict) else ""
        phase = str(run.get("phase", "")) if isinstance(run, dict) else ""
        subtasks = last_payload.get("subtasks", []) if isinstance(last_payload, dict) else []
        subtask_count = len(subtasks) if isinstance(subtasks, list) else 0
        print(f"[poll] run_id={run_id} status={status} phase={phase} subtasks={subtask_count}")
        if status in RUN_TERMINAL_STATUSES:
            return last_payload
        time.sleep(interval)

    raise TimeoutError(f"timed out waiting for run {run_id} after {timeout} seconds")


def print_run_summary(run_payload: dict[str, object]) -> None:
    """Print a compact run summary for manual testing."""
    run = run_payload.get("run", {}) if isinstance(run_payload, dict) else {}
    subtasks_raw = run_payload.get("subtasks", []) if isinstance(run_payload, dict) else []
    artifacts_raw = run_payload.get("artifacts", []) if isinstance(run_payload, dict) else []
    subtasks = subtasks_raw if isinstance(subtasks_raw, list) else []
    artifacts = artifacts_raw if isinstance(artifacts_raw, list) else []

    print("Run 摘要：")
    print(
        json.dumps(
            {
                "run_id": run.get("id") if isinstance(run, dict) else None,
                "status": run.get("status") if isinstance(run, dict) else None,
                "phase": run.get("phase") if isinstance(run, dict) else None,
                "subtasks": [
                    {
                        "id": subtask.get("id"),
                        "name": subtask.get("name"),
                        "status": subtask.get("status"),
                        "role": subtask.get("role"),
                    }
                    for subtask in subtasks
                    if isinstance(subtask, dict)
                ],
                "artifact_count": len(artifacts),
                "artifacts": [
                    {
                        "id": artifact.get("id"),
                        "name": artifact.get("name"),
                        "type": artifact.get("type"),
                    }
                    for artifact in artifacts
                    if isinstance(artifact, dict)
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        goal = read_goal(args.goal)
        constraints = merge_cli_constraints(
            parse_constraints(args.constraints_json),
            handoff_requests=args.handoff_request,
            handoff_target_profile_id=args.handoff_target_profile_id,
        )
    except ValueError as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 2

    payload = {
        "goal": goal,
        "constraints": constraints,
        "priority": args.priority,
        "profile": args.profile,
    }
    if args.agent_profile_id:
        payload["agent_profile_id"] = args.agent_profile_id
    if args.preferred_strategy:
        payload["preferred_strategy"] = args.preferred_strategy

    with httpx.Client() as client:
        try:
            wait_for_service(client, args.base_url.rstrip("/"), args.wait_for_service)
            created = submit_task(
                client,
                args.base_url.rstrip("/"),
                payload,
                request_timeout=args.request_timeout,
            )
        except (httpx.HTTPError, TimeoutError) as exc:
            print(f"request failed: {exc}", file=sys.stderr)
            return 1

        print("任务已提交：")
        print(json.dumps(created, ensure_ascii=False, indent=2))

        if not args.poll:
            run_id = str(created.get("run_id", ""))
            if run_id:
                try:
                    run_detail = fetch_run(
                        client,
                        args.base_url.rstrip("/"),
                        run_id,
                        request_timeout=args.request_timeout,
                    )
                    print_run_summary(run_detail)
                except httpx.HTTPError:
                    pass
            return 0

        task_id = str(created.get("task_id", ""))
        run_id = str(created.get("run_id", ""))
        if not task_id and not run_id:
            print("response missing both task_id and run_id, cannot poll", file=sys.stderr)
            return 1

        try:
            if run_id:
                final_state = poll_run(
                    client,
                    args.base_url.rstrip("/"),
                    run_id,
                    interval=args.interval,
                    timeout=args.timeout,
                    request_timeout=args.request_timeout,
                )
            else:
                final_state = poll_task(
                    client,
                    args.base_url.rstrip("/"),
                    task_id,
                    interval=args.interval,
                    timeout=args.timeout,
                    request_timeout=args.request_timeout,
                )
        except (httpx.HTTPError, TimeoutError) as exc:
            print(f"poll failed: {exc}", file=sys.stderr)
            return 1

    print("最终查询结果：")
    print(json.dumps(final_state, ensure_ascii=False, indent=2))
    if run_id:
        print_run_summary(final_state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())