from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import traceback
from datetime import timedelta

import httpx
from opensandbox import Sandbox
from opensandbox.models import WriteEntry

from swarmmind.sandbox.opensandbox_adapter import OpenSandboxAdapter
from swarmmind.sandbox.profiles import DEFAULT_PROFILES, normalize_sandbox_profile_name
from swarmmind.sandbox.provider import WriteFileEntry


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manually verify OpenSandbox create/run/read/write flow against the current SwarmMind adapter.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("OPEN_SANDBOX_BASE_URL", "http://localhost:45698"),
        help="OpenSandbox base URL",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("OPEN_SANDBOX_API_KEY"),
        help="OpenSandbox API key",
    )
    parser.add_argument("--profile", default="aio", help="Sandbox profile name")
    parser.add_argument("--mode", choices=["adapter", "sdk"], default="adapter", help="Use SwarmMind adapter or direct OpenSandbox SDK")
    parser.add_argument("--request-timeout", type=int, default=180, help="OpenSandbox request timeout in seconds")
    parser.add_argument("--skip-health", action="store_true", help="Skip GET /health before create")
    parser.add_argument(
        "--keep-alive-seconds",
        type=int,
        default=300,
        help="Keep the sandbox alive for this many seconds after the probe succeeds; use 0 to disable.",
    )
    return parser


async def _check_health(base_url: str, api_key: str | None) -> None:
    headers = {"OPEN-SANDBOX-API-KEY": api_key} if api_key else {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(f"{base_url.rstrip('/')}/health", headers=headers)
        print(f"[health] status={response.status_code}")
        print(f"[health] body={response.text[:500]}")
        response.raise_for_status()


async def _sleep_if_requested(keep_alive_seconds: int, *, sandbox_id: str, mode: str) -> None:
    if keep_alive_seconds <= 0:
        return
    print(f"[hold] mode={mode} sandbox_id={sandbox_id} keep_alive_seconds={keep_alive_seconds}")
    await asyncio.sleep(keep_alive_seconds)


async def _run_with_adapter(
    base_url: str,
    api_key: str | None,
    profile: str,
    request_timeout: int,
    keep_alive_seconds: int,
) -> int:
    adapter = OpenSandboxAdapter(
        api_key=api_key,
        base_url=base_url,
        request_timeout_seconds=request_timeout,
        create_retry_count=1,
    )

    handle = None
    try:
        handle = await adapter.create(
            profile,
            metadata={"source": "manual-script", "mode": "adapter"},
        )
        print(f"[create] sandbox_id={handle.sandbox_id} profile={handle.profile} image={handle.image}")

        await adapter.write_files(
            handle.sandbox_id,
            [
                WriteFileEntry(
                    path="/tmp/swarmmind_manual_probe.py",
                    data=(
                        "from pathlib import Path\n"
                        "Path('/tmp/manual-output.txt').write_text('adapter-ok', encoding='utf-8')\n"
                        "print('hello-from-adapter')\n"
                    ),
                )
            ],
        )
        print("[write] wrote /tmp/swarmmind_manual_probe.py")

        execution = await adapter.run_command(
            handle.sandbox_id,
            "python /tmp/swarmmind_manual_probe.py",
        )
        print(f"[exec] exit_code={execution.exit_code}")
        print(f"[exec] stdout={execution.stdout[:1000]!r}")
        print(f"[exec] stderr={execution.stderr[:1000]!r}")

        output = await adapter.read_file(handle.sandbox_id, "/tmp/manual-output.txt")
        print(f"[read] /tmp/manual-output.txt={output!r}")

        await _sleep_if_requested(keep_alive_seconds, sandbox_id=handle.sandbox_id, mode="adapter")

        return 0 if execution.exit_code == 0 else execution.exit_code
    finally:
        if handle is not None:
            await adapter.kill(handle.sandbox_id)
            print(f"[kill] sandbox_id={handle.sandbox_id}")


async def _run_with_sdk(
    base_url: str,
    api_key: str | None,
    profile: str,
    request_timeout: int,
    keep_alive_seconds: int,
) -> int:
    resolved_profile = normalize_sandbox_profile_name(profile)
    selected = DEFAULT_PROFILES[resolved_profile]
    connection_config = OpenSandboxAdapter._build_connection_config(  # type: ignore[attr-defined]
        api_key=api_key,
        base_url=base_url,
        request_timeout_seconds=request_timeout,
    )

    sandbox = None
    try:
        sandbox = await Sandbox.create(
            selected.image,
            entrypoint=selected.entrypoint,
            timeout=timedelta(seconds=selected.timeout_seconds),
            env=selected.env,
            resource=selected.resource_limits,
            metadata={"source": "manual-script", "mode": "sdk"},
            connection_config=connection_config,
        )
        sandbox_id = getattr(sandbox, "id", None) or getattr(sandbox, "sandbox_id", None)
        print(f"[create] sandbox_id={sandbox_id} profile={resolved_profile} image={selected.image}")
        await sandbox.files.write_files(
            [
                WriteEntry(
                path="/tmp/swarmmind_manual_probe.py",
                data=(
                    "from pathlib import Path\n"
                    "Path('/tmp/manual-output.txt').write_text('sdk-ok', encoding='utf-8')\n"
                    "print('hello-from-sdk')\n"
                ),
                mode=0o644,
            )
            ]
        )
        print("[write] wrote /tmp/swarmmind_manual_probe.py")

        execution = await sandbox.commands.run("python /tmp/swarmmind_manual_probe.py")
        stdout = "".join(getattr(item, "text", "") for item in getattr(getattr(execution, "logs", None), "stdout", []))
        stderr = "".join(getattr(item, "text", "") for item in getattr(getattr(execution, "logs", None), "stderr", []))
        exit_code = getattr(execution, "exit_code", None)
        if not isinstance(exit_code, int):
            exit_code = getattr(execution, "exitCode", 0)
        print(f"[exec] exit_code={exit_code}")
        print(f"[exec] stdout={stdout[:1000]!r}")
        print(f"[exec] stderr={stderr[:1000]!r}")

        output = await sandbox.files.read_file("/tmp/manual-output.txt")
        print(f"[read] /tmp/manual-output.txt={output!r}")

        if sandbox_id is not None:
            await _sleep_if_requested(keep_alive_seconds, sandbox_id=str(sandbox_id), mode="sdk")

        return int(exit_code or 0)
    finally:
        if sandbox is not None:
            try:
                await sandbox.kill()
                print("[kill] sandbox killed")
            finally:
                await sandbox.close()


async def _main(args: argparse.Namespace) -> int:
    resolved_profile = normalize_sandbox_profile_name(args.profile)
    selected = DEFAULT_PROFILES.get(resolved_profile)
    print(
        "[config] "
        + json.dumps(
            {
                "base_url": args.base_url,
                "profile": resolved_profile,
                "mode": args.mode,
                "image": selected.image if selected else None,
                "entrypoint": selected.entrypoint if selected else None,
                "request_timeout": args.request_timeout,
                "keep_alive_seconds": args.keep_alive_seconds,
                "api_key_present": bool(args.api_key),
            },
            ensure_ascii=False,
        )
    )

    if not args.skip_health:
        await _check_health(args.base_url, args.api_key)

    if args.mode == "adapter":
        return await _run_with_adapter(
            args.base_url,
            args.api_key,
            resolved_profile,
            args.request_timeout,
            args.keep_alive_seconds,
        )
    return await _run_with_sdk(
        args.base_url,
        args.api_key,
        resolved_profile,
        args.request_timeout,
        args.keep_alive_seconds,
    )


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        exit_code = asyncio.run(_main(args))
    except Exception as exc:
        print(f"[error] {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc()
        raise SystemExit(1) from exc
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()