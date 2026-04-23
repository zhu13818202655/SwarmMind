#!/usr/bin/env python3
"""Pure FlyReport HTTP client — exercises ``/v1/fly-reports/*`` end-to-end.

This script is *only* an HTTP client. All business logic lives on the server.
Start the server yourself (e.g. via the ``Run SwarmMind API`` task), then run::

    python scripts/fly_report_chat.py "生成农业局上周飞行周报"

Each request and response is printed verbatim so you can debug every layer
server-side. The script walks the canonical client flow:

    1. GET  /health                                    (sanity)
    2. GET  /v1/fly-reports/templates                  (discover renderers)
    3. POST /v1/fly-reports/sessions                   (open session w/ initial query)
    4. GET  /v1/fly-reports/sessions/{id}              (initial snapshot)
    5. GET  /v1/fly-reports/sessions/{id}/turns        (initial assistant reply)
    6. REPL: send messages / confirm / snapshot / cancel

REPL commands::

    /help                           — list commands
    /snapshot                       — GET session snapshot
    /turns                          — GET full chat history
    /templates [format]             — re-list templates
    /confirm [fmt] [template_ref]   — POST confirm (defaults: docx / built-in)
    /cancel                         — POST cancel
    /quit  /exit                    — leave
    <anything else>                 — POST messages with the text
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

import httpx


# ---------------------------------------------------------------------------
# pretty-print helpers
# ---------------------------------------------------------------------------


def _dump(payload: Any) -> str:
    if payload is None or payload == "":
        return "<empty>"
    if isinstance(payload, (dict, list)):
        return json.dumps(payload, ensure_ascii=False, indent=2)
    return str(payload)


def _print_request(method: str, url: str, body: Any | None = None) -> None:
    print(f"\n[req ] {method} {url}")
    if body is not None:
        print("[req ] body:")
        for line in _dump(body).splitlines():
            print(f"       {line}")


def _print_response(resp: httpx.Response) -> None:
    print(f"[resp] {resp.status_code} {resp.reason_phrase}")
    try:
        data = resp.json()
    except ValueError:
        text = resp.text
        if text:
            print("[resp] body (text):")
            for line in text.splitlines():
                print(f"       {line}")
        return
    print("[resp] body:")
    for line in _dump(data).splitlines():
        print(f"       {line}")


# ---------------------------------------------------------------------------
# client
# ---------------------------------------------------------------------------


class FlyReportHTTPClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        tenant_id: str,
        user_id: str,
    ) -> None:
        self._c = client
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.session_id: str | None = None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
    ) -> httpx.Response:
        url = path
        if params:
            qs = "&".join(
                f"{k}={v}" for k, v in params.items() if v is not None
            )
            if qs:
                url = f"{path}?{qs}"
        _print_request(method, url, body=json_body)
        try:
            resp = await self._c.request(
                method, path, params=params, json=json_body
            )
        except httpx.HTTPError as exc:
            print(f"[resp] <transport error> {type(exc).__name__}: {exc}")
            raise
        _print_response(resp)
        return resp

    async def health(self) -> None:
        await self._request("GET", "/health")

    async def list_templates(
        self, output_format: str | None = None
    ) -> None:
        params = {"output_format": output_format} if output_format else None
        await self._request(
            "GET", "/v1/fly-reports/templates", params=params
        )

    async def start_session(self, initial_query: str | None) -> None:
        body = {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "initial_query": initial_query,
        }
        resp = await self._request(
            "POST", "/v1/fly-reports/sessions", json_body=body
        )
        if resp.status_code == 201:
            self.session_id = resp.json()["session_id"]
            print(f"[ok  ] session_id = {self.session_id}")
        else:
            raise SystemExit(
                f"start_session failed: {resp.status_code} {resp.text}"
            )

    async def snapshot(self) -> None:
        self._require_session()
        await self._request(
            "GET",
            f"/v1/fly-reports/sessions/{self.session_id}",
            params={"user_id": self.user_id},
        )

    async def list_turns(self) -> None:
        self._require_session()
        await self._request(
            "GET",
            f"/v1/fly-reports/sessions/{self.session_id}/turns",
            params={"user_id": self.user_id},
        )

    async def send_message(self, text: str) -> None:
        self._require_session()
        await self._request(
            "POST",
            f"/v1/fly-reports/sessions/{self.session_id}/messages",
            json_body={"user_id": self.user_id, "text": text},
        )

    async def confirm(
        self, output_format: str, template_ref: str | None
    ) -> None:
        self._require_session()
        body: dict[str, Any] = {
            "user_id": self.user_id,
            "output_format": output_format,
        }
        if template_ref:
            body["template_ref"] = template_ref
        await self._request(
            "POST",
            f"/v1/fly-reports/sessions/{self.session_id}/confirm",
            json_body=body,
        )

    async def cancel(self) -> None:
        self._require_session()
        await self._request(
            "POST",
            f"/v1/fly-reports/sessions/{self.session_id}/cancel",
            json_body={"user_id": self.user_id},
        )

    def _require_session(self) -> None:
        if not self.session_id:
            raise SystemExit("no active session_id; start_session first")


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------


HELP = """\
commands:
  /help                          this help
  /snapshot                      GET   /v1/fly-reports/sessions/{id}
  /turns                         GET   /v1/fly-reports/sessions/{id}/turns
  /templates [format]            GET   /v1/fly-reports/templates
  /confirm [fmt] [template_ref]  POST  /v1/fly-reports/sessions/{id}/confirm
                                 fmt ∈ {docx,pdf,markdown}, default docx
  /cancel                        POST  /v1/fly-reports/sessions/{id}/cancel
  /quit  /exit                   leave
  <text>                         POST  /v1/fly-reports/sessions/{id}/messages
"""


async def _repl(client: FlyReportHTTPClient) -> None:
    print("\nentering REPL — /help for commands.")

    def _read() -> str | None:
        try:
            return input("\n> ").strip()
        except EOFError:
            return None

    while True:
        line = await asyncio.to_thread(_read)
        if line is None or line in ("/quit", "/exit"):
            print("(bye)")
            return
        if not line:
            continue

        try:
            if line == "/help":
                print(HELP)
            elif line == "/snapshot":
                await client.snapshot()
            elif line == "/turns":
                await client.list_turns()
            elif line.startswith("/templates"):
                parts = line.split()
                fmt = parts[1] if len(parts) > 1 else None
                await client.list_templates(fmt)
            elif line.startswith("/confirm"):
                parts = line.split()
                fmt = parts[1] if len(parts) > 1 else "docx"
                tpl = parts[2] if len(parts) > 2 else None
                await client.confirm(fmt, tpl)
            elif line == "/cancel":
                await client.cancel()
            elif line.startswith("/"):
                print(f"unknown command: {line!r} (try /help)")
            else:
                await client.send_message(line)
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            print(f"[err ] {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# entry
# ---------------------------------------------------------------------------


async def _amain(args: argparse.Namespace) -> int:
    timeout = httpx.Timeout(args.timeout)
    async with httpx.AsyncClient(
        base_url=args.base_url, timeout=timeout
    ) as http:
        client = FlyReportHTTPClient(
            http, tenant_id=args.tenant_id, user_id=args.user_id
        )

        print("=== sanity ===")
        try:
            await client.health()
        except httpx.ConnectError:
            print(
                f"\n[fatal] cannot reach {args.base_url} — start the server first "
                f"(e.g. `Run SwarmMind API` task)."
            )
            return 2

        print("\n=== discover templates ===")
        await client.list_templates()

        print("\n=== open session ===")
        await client.start_session(initial_query=args.question)

        print("\n=== initial snapshot ===")
        await client.snapshot()

        print("\n=== initial turns ===")
        await client.list_turns()

        await _repl(client)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Pure HTTP client for /v1/fly-reports/*. Prints every request "
            "and response so you can debug the server."
        )
    )
    p.add_argument(
        "question",
        nargs="?",
        default="生成公安局上周飞行周报",
        help="initial_query passed to POST /v1/fly-reports/sessions",
    )
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--tenant-id", default="local")
    p.add_argument("--user-id", default="cli-user")
    p.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="per-request timeout (s)",
    )
    args = p.parse_args()
    try:
        return asyncio.run(_amain(args))
    except KeyboardInterrupt:
        print("\n(interrupted)")
        return 130


if __name__ == "__main__":
    sys.exit(main())
