#!/usr/bin/env python3
"""Smoke-test the dikong_sql queries against real PG + TDengine.

Connects to:
- PostgreSQL: 127.0.0.1:51543 / dikong (user=dikong, pwd=dikong123)
- TDengine REST: 127.0.0.1:51741 / dikong (user=root, pwd=taosdata)

Runs each SQL query constant from queries_pg.py and queries_td.py with
a safe parameter set and prints row counts + sample rows.

Usage:
    python scripts/test_dikong_sql_queries.py
    # Or with env overrides:
    PGHOST=x PGPORT=y PGUSER=z PGPASSWORD=w python scripts/test_dikong_sql_queries.py
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Any

# ---------------------------------------------------------------------------
# Setup: ensure project root is on sys.path
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ---------------------------------------------------------------------------
# PG connection
# ---------------------------------------------------------------------------
PG_DSN = os.getenv(
    "FLY_REPORT_DIKONG_PG_DSN",
    "postgresql://dikong:dikong123@127.0.0.1:51543/dikong",
)

# ---------------------------------------------------------------------------
# TDengine connection
# ---------------------------------------------------------------------------
TD_URL = os.getenv("TDENGINE_URL", "http://127.0.0.1:51741")
TD_USER = os.getenv("TDENGINE_USER", "root")
TD_PASSWORD = os.getenv("TDENGINE_PASSWORD", "taosdata")
TD_DB = os.getenv("TDENGINE_DB", "dikong")


# ---------------------------------------------------------------------------
# Test time window: last 90 days
# ---------------------------------------------------------------------------
END_DATE = datetime.now()
START_DATE = END_DATE - timedelta(days=90)
START_TS = START_DATE.strftime("%Y-%m-%d 00:00:00")
END_TS = END_DATE.strftime("%Y-%m-%d 23:59:59")

# Department IDs to test (from fly_report.yaml config)
DEPT_IDS = [380, 375, 382, 381, 395, 394, 384]


def _trunc(val: Any, maxlen: int = 80) -> str:
    s = str(val)
    return s[:maxlen] + "..." if len(s) > maxlen else s


# ---------------------------------------------------------------------------
# PostgreSQL tests
# ---------------------------------------------------------------------------
async def test_pg() -> None:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        print("SKIP PG tests: psycopg not installed")
        return

    from swarmmind.domains.fly_report.dikong_sql.queries_pg import (
        SQL_DEPT_NAMES,
        SQL_FLY_JOB_LOGS,
        SQL_FLY_PERIOD_DRONE_SNS,
        SQL_FLY_STATIS_COUNTS,
        SQL_MEDIA_STATIC,
        SQL_ROUTE_PLAN_COUNT,
        SQL_WARN_STATIC,
    )

    print("\n" + "=" * 72)
    print("PostgreSQL tests")
    print("=" * 72)

    async with await psycopg.AsyncConnection.connect(
        PG_DSN, row_factory=dict_row, autocommit=True
    ) as conn:
        async with conn.cursor() as cur:
            # --- SQL_ROUTE_PLAN_COUNT ---
            print("\n--- SQL_ROUTE_PLAN_COUNT ---")
            await cur.execute(SQL_ROUTE_PLAN_COUNT)
            rows = await cur.fetchall()
            print(f"  result: {rows}")

            # --- SQL_DEPT_NAMES ---
            print("\n--- SQL_DEPT_NAMES ---")
            await cur.execute(SQL_DEPT_NAMES, {"dept_ids": [str(d) for d in DEPT_IDS]})
            rows = await cur.fetchall()
            print(f"  rows: {len(rows)}")
            for r in rows[:5]:
                print(f"    {r}")

            # --- SQL_FLY_STATIS_COUNTS (with dept filter) ---
            print(f"\n--- SQL_FLY_STATIS_COUNTS (dept_ids={DEPT_IDS[:3]}) ---")
            await cur.execute(
                SQL_FLY_STATIS_COUNTS,
                {"start_ts": START_TS, "end_ts": END_TS, "dept_ids": DEPT_IDS},
            )
            rows = await cur.fetchall()
            print(f"  result: {rows}")

            # --- SQL_FLY_STATIS_COUNTS (no dept filter) ---
            print("\n--- SQL_FLY_STATIS_COUNTS (no dept filter) ---")
            await cur.execute(
                SQL_FLY_STATIS_COUNTS,
                {"start_ts": START_TS, "end_ts": END_TS, "dept_ids": None},
            )
            rows = await cur.fetchall()
            print(f"  result: {rows}")

            # --- SQL_FLY_PERIOD_DRONE_SNS ---
            print(f"\n--- SQL_FLY_PERIOD_DRONE_SNS ---")
            await cur.execute(
                SQL_FLY_PERIOD_DRONE_SNS,
                {"start_ts": START_TS, "end_ts": END_TS, "dept_ids": DEPT_IDS},
            )
            drone_rows = await cur.fetchall()
            drone_sns = sorted({r["device_sn"] for r in drone_rows if r.get("device_sn")})
            print(f"  drone_sn count: {len(drone_sns)}")
            for sn in drone_sns[:10]:
                print(f"    {sn}")

            # --- SQL_FLY_JOB_LOGS ---
            print(f"\n--- SQL_FLY_JOB_LOGS (with dept filter, LIMIT 5) ---")
            await cur.execute(
                SQL_FLY_JOB_LOGS,
                {
                    "start_ts": START_TS,
                    "end_ts": END_TS,
                    "dept_ids": DEPT_IDS,
                    "row_cap": 5,
                },
            )
            rows = await cur.fetchall()
            print(f"  rows: {len(rows)}")
            for r in rows:
                print(f"    job_log_id={r.get('job_log_id')} sn={r.get('device_sn')} "
                      f"status={r.get('status')} start={r.get('start_time')} "
                      f"deptids_tag_name={_trunc(r.get('deptids_tag_name'), 40)}")

            # --- SQL_FLY_JOB_LOGS (no dept filter) ---
            print(f"\n--- SQL_FLY_JOB_LOGS (no dept filter, LIMIT 5) ---")
            await cur.execute(
                SQL_FLY_JOB_LOGS,
                {
                    "start_ts": START_TS,
                    "end_ts": END_TS,
                    "dept_ids": None,
                    "row_cap": 5,
                },
            )
            rows = await cur.fetchall()
            print(f"  rows: {len(rows)}")
            for r in rows:
                print(f"    job_log_id={r.get('job_log_id')} sn={r.get('device_sn')} "
                      f"status={r.get('status')} start={r.get('start_time')}")

            # --- SQL_WARN_STATIC (with dept filter) ---
            print(f"\n--- SQL_WARN_STATIC (with dept filter) ---")
            await cur.execute(
                SQL_WARN_STATIC,
                {
                    "start_ts": START_TS,
                    "end_ts": END_TS,
                    "dept_ids": DEPT_IDS,
                },
            )
            rows = await cur.fetchall()
            print(f"  rows: {len(rows)}")
            for r in rows[:5]:
                print(f"    id={r.get('id')} alg={r.get('algorithm_name')} "
                      f"dept_name={r.get('dept_name')} "
                      f"status={r.get('status')} addr={_trunc(r.get('address'), 30)}")

            # --- SQL_WARN_STATIC (no dept filter) ---
            print(f"\n--- SQL_WARN_STATIC (no dept filter) ---")
            await cur.execute(
                SQL_WARN_STATIC,
                {
                    "start_ts": START_TS,
                    "end_ts": END_TS,
                    "dept_ids": None,
                },
            )
            rows = await cur.fetchall()
            print(f"  rows: {len(rows)}")
            for r in rows[:5]:
                print(f"    id={r.get('id')} alg={r.get('algorithm_name')} "
                      f"dept_name={r.get('dept_name')} "
                      f"deptids_tag_name={_trunc(r.get('deptids_tag_name'), 40)}")

            # --- SQL_MEDIA_STATIC (with dept filter) ---
            print(f"\n--- SQL_MEDIA_STATIC (with dept filter) ---")
            await cur.execute(
                SQL_MEDIA_STATIC,
                {
                    "start_ts": START_TS,
                    "end_ts": END_TS,
                    "dept_ids": DEPT_IDS,
                },
            )
            rows = await cur.fetchall()
            print(f"  result: {rows}")

            # --- SQL_MEDIA_STATIC (no dept filter) ---
            print(f"\n--- SQL_MEDIA_STATIC (no dept filter) ---")
            await cur.execute(
                SQL_MEDIA_STATIC,
                {
                    "start_ts": START_TS,
                    "end_ts": END_TS,
                    "dept_ids": None,
                },
            )
            rows = await cur.fetchall()
            print(f"  result: {rows}")

    return drone_sns


# ---------------------------------------------------------------------------
# TDengine tests
# ---------------------------------------------------------------------------
async def test_td(drone_sns: list[str]) -> None:
    import httpx

    from swarmmind.domains.fly_report.dikong_sql.queries_td import (
        sql_flight_day_trend,
        sql_flight_overall,
        sql_flight_per_job,
    )

    print("\n" + "=" * 72)
    print("TDengine tests")
    print("=" * 72)

    token = base64.b64encode(f"{TD_USER}:{TD_PASSWORD}".encode()).decode()
    url = f"{TD_URL.rstrip('/')}/rest/sql/{TD_DB}"

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        headers={"Authorization": f"Basic {token}", "Content-Type": "text/plain"},
    ) as client:
        # --- connectivity ---
        print("\n--- TDengine connectivity ---")
        resp = await client.post(url, content=b"SHOW DATABASES")
        body = resp.json()
        if body.get("code", 0) != 0:
            print(f"  ERROR: {body}")
            return
        print(f"  OK, databases: {body.get('rows', 0)} rows")

        if not drone_sns:
            print("  SKIP flight queries: no drone_sns from PG")
            return

        test_sns = drone_sns[:5]
        print(f"\n  Using drone_sns: {test_sns}")

        # --- sql_flight_overall ---
        print(f"\n--- sql_flight_overall ---")
        sql = sql_flight_overall(START_TS, END_TS, test_sns)
        print(f"  SQL: {_trunc(sql, 120)}")
        resp = await client.post(url, content=sql.encode("utf-8"))
        body = resp.json()
        if body.get("code", 0) != 0:
            print(f"  ERROR: code={body.get('code')}, desc={body.get('desc')}")
        else:
            cols = [c[0] for c in body.get("column_meta", [])]
            data = body.get("data", [])
            rows = [dict(zip(cols, row)) for row in data]
            print(f"  result: {rows}")

        # --- sql_flight_day_trend ---
        print(f"\n--- sql_flight_day_trend ---")
        sql = sql_flight_day_trend(START_TS, END_TS, test_sns)
        print(f"  SQL: {_trunc(sql, 120)}")
        resp = await client.post(url, content=sql.encode("utf-8"))
        body = resp.json()
        if body.get("code", 0) != 0:
            print(f"  ERROR: code={body.get('code')}, desc={body.get('desc')}")
        else:
            cols = [c[0] for c in body.get("column_meta", [])]
            data = body.get("data", [])
            rows = [dict(zip(cols, row)) for row in data]
            print(f"  rows: {len(rows)}")
            for r in rows[:5]:
                print(f"    sn={r.get('drone_sn')} day={r.get('day_start')} "
                      f"dur_sec={r.get('day_duration_sec')}")

        # --- sql_flight_per_job (single drone, full window) ---
        sn = test_sns[0]
        print(f"\n--- sql_flight_per_job (sn={sn}) ---")
        sql = sql_flight_per_job(sn, START_TS, END_TS)
        print(f"  SQL: {_trunc(sql, 120)}")
        resp = await client.post(url, content=sql.encode("utf-8"))
        body = resp.json()
        if body.get("code", 0) != 0:
            print(f"  ERROR: code={body.get('code')}, desc={body.get('desc')}")
        else:
            cols = [c[0] for c in body.get("column_meta", [])]
            data = body.get("data", [])
            rows = [dict(zip(cols, row)) for row in data]
            print(f"  result: {rows}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main() -> None:
    print(f"Time window: {START_TS} → {END_TS}")
    print(f"Dept IDs: {DEPT_IDS}")
    print(f"PG DSN: {PG_DSN.split('@')[1] if '@' in PG_DSN else PG_DSN}")  # hide creds
    print(f"TD URL: {TD_URL}")

    drone_sns: list[str] = []
    try:
        result = await test_pg()
        if result:
            drone_sns = result
    except Exception as exc:
        print(f"\nPG FAILED: {exc}")
        import traceback
        traceback.print_exc()

    try:
        await test_td(drone_sns)
    except Exception as exc:
        print(f"\nTD FAILED: {exc}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 72)
    print("DONE")


if __name__ == "__main__":
    asyncio.run(main())
