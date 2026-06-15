#!/usr/bin/env python3
"""Seed rich FlyReport mock data for PostgreSQL (and optionally TDengine).

This script is designed for demo environments where FlyReport returns 0 rows
because route department tags do not match configured department filters.

Safety defaults:
- Dry-run by default (no writes unless --apply is provided)
- Uses deterministic IDs and idempotent UPSERT logic
- Writes only records prefixed with "MOCK-FR" for easy cleanup/audit
"""

from __future__ import annotations

import argparse
import os
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
import psycopg


# TDengine connection defaults (overridable via CLI args).
TD_BASE_URL = "http://61.169.171.82:51741"
TD_USER = "root"
TD_PASSWORD = "taosdata"
TD_DATABASE = "dikong"

DEPTS: list[tuple[int, str]] = [
    (380, "资规局"),
    (375, "公安局"),
    (382, "交通运输局"),
    (381, "建设局"),
    (395, "市生态环境局分局"),
    (394, "综合行政执法局（城市管理局）"),
    (384, "农业农村局"),
]

# Deterministic mock IDs to keep script idempotent.
BASE_ROUTE_ID = 920000
BASE_MISSION_ID = 930000
BASE_JOB_ID = 940000
BASE_ALGO_ID = 950000000000000000


@dataclass(frozen=True)
class MockRoute:
    route_id: int
    dept_id: int
    dept_name: str
    route_name: str


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def _mask_dsn(dsn: str) -> str:
    parsed = urlparse(dsn)
    if parsed.password is None:
        return dsn
    netloc = parsed.netloc.replace(f":{parsed.password}", ":***")
    return urlunparse(parsed._replace(netloc=netloc))


def _replace_user_pass(dsn: str, *, user: str | None, password: str | None) -> str:
    if user is None and password is None:
        return dsn
    parsed = urlparse(dsn)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("Only postgres/postgresql DSN is supported")

    host_part = parsed.hostname or ""
    if parsed.port:
        host_part = f"{host_part}:{parsed.port}"

    auth_user = user or parsed.username or ""
    auth_pass = password if password is not None else (parsed.password or "")
    if auth_user and auth_pass:
        auth = f"{auth_user}:{auth_pass}@"
    elif auth_user:
        auth = f"{auth_user}@"
    else:
        auth = ""

    new_netloc = f"{auth}{host_part}"
    return urlunparse(parsed._replace(netloc=new_netloc))


def _build_routes() -> list[MockRoute]:
    routes: list[MockRoute] = []
    for idx, (dept_id, dept_name) in enumerate(DEPTS, start=1):
        routes.append(
            MockRoute(
                route_id=BASE_ROUTE_ID + idx,
                dept_id=dept_id,
                dept_name=dept_name,
                route_name=f"MOCK-FR-{dept_name}-巡查航线",
            )
        )
    return routes


def _pick_existing_drone_sns(conn: psycopg.Connection) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT device_sn
              FROM t_drone_device
             WHERE device_sn IS NOT NULL
               AND device_sn <> ''
             ORDER BY id
            """
        )
        rows = cur.fetchall()
    sns = [str(r[0]) for r in rows if r and r[0]]
    if not sns:
        raise RuntimeError("No rows found in t_drone_device; cannot seed missions")
    return sns


def _upsert_routes(conn: psycopg.Connection, routes: Iterable[MockRoute], *, dry_run: bool) -> int:
    sql = """
    INSERT INTO t_route_planning (
      id, name, state, route_type,
      total_action, total_photo_action, total_video_action,
      total_area, estimated_duration_minute,
      del_flag, create_time, update_time,
      deptids_tag, deptids_tag_name
    ) VALUES (
      %(id)s, %(name)s, 1, 1,
      10, 6, 4,
      3000.0, 26.0,
      false, NOW(), NOW(),
      %(deptids_tag)s, %(deptids_tag_name)s
    )
    ON CONFLICT (id) DO UPDATE SET
      name = EXCLUDED.name,
      del_flag = false,
      deptids_tag = EXCLUDED.deptids_tag,
      deptids_tag_name = EXCLUDED.deptids_tag_name,
      update_time = NOW()
    """
    count = 0
    for route in routes:
        count += 1
        if dry_run:
            continue
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "id": route.route_id,
                    "name": route.route_name,
                    "deptids_tag": str(route.dept_id),
                    "deptids_tag_name": route.dept_name,
                },
            )
    return count


def _upsert_missions(
    conn: psycopg.Connection,
    routes: list[MockRoute],
    drone_sns: list[str],
    *,
    dry_run: bool,
) -> int:
    sql = """
    INSERT INTO t_missions (
      id, name, device_sn, route_id,
      dept_id, dept_name,
      emergency_action, del_flag,
      create_time, update_time,
      type, status
    ) VALUES (
      %(id)s, %(name)s, %(device_sn)s, %(route_id)s,
      %(dept_id)s, %(dept_name)s,
      0, false,
      NOW(), NOW(),
      1, 1
    )
    ON CONFLICT (id) DO UPDATE SET
      name = EXCLUDED.name,
      device_sn = EXCLUDED.device_sn,
      route_id = EXCLUDED.route_id,
      dept_id = EXCLUDED.dept_id,
      dept_name = EXCLUDED.dept_name,
      del_flag = false,
      update_time = NOW()
    """
    count = 0
    for idx, route in enumerate(routes, start=1):
        mission_id = BASE_MISSION_ID + idx
        device_sn = drone_sns[(idx - 1) % len(drone_sns)]
        count += 1
        if dry_run:
            continue
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "id": mission_id,
                    "name": f"MOCK-FR-{route.dept_name}-飞行任务",
                    "device_sn": device_sn,
                    "route_id": route.route_id,
                    "dept_id": route.dept_id,
                    "dept_name": route.dept_name,
                },
            )
    return count


def _upsert_sys_job(
    conn: psycopg.Connection,
    routes: list[MockRoute],
    *,
    dry_run: bool,
) -> int:
    delete_sql = "DELETE FROM sys_job WHERE job_id = %(job_id)s"
    insert_sql = """
    INSERT INTO sys_job (
      job_id, job_name, job_group, invoke_target,
      cron_expression, misfire_policy,
      create_by, create_time, update_by, update_time,
      remark, mission_id, status, concurrent
    ) VALUES (
      %(job_id)s, %(job_name)s, 'MISSION', 'mock.fly.report.run',
      '0 0 6 * * ?', '1',
      'mock', NOW(), 'mock', NOW(),
      'MOCK-FR seeded', %(mission_id)s, '0', '1'
    )
    """
    count = 0
    for idx, route in enumerate(routes, start=1):
        count += 1
        if dry_run:
            continue
        with conn.cursor() as cur:
            cur.execute(delete_sql, {"job_id": BASE_JOB_ID + idx})
            cur.execute(
                insert_sql,
                {
                    "job_id": BASE_JOB_ID + idx,
                    "job_name": f"MOCK-FR-{route.dept_name}-定时任务",
                    "mission_id": BASE_MISSION_ID + idx,
                },
            )
    return count


def _insert_job_logs(
    conn: psycopg.Connection,
    routes: list[MockRoute],
    drone_sns: list[str],
    *,
    days: int,
    flights_range: tuple[int, int],
    dry_run: bool,
) -> int:
    delete_sql = "DELETE FROM sys_job_log WHERE job_log_id LIKE 'mock-fr-%'"
    insert_sql = """
    INSERT INTO sys_job_log (
      job_log_id, job_log_no, job_id, job_name, job_group,
      invoke_target, job_message, status,
      create_time, start_time, stop_time, mission_id, data_status
    ) VALUES (
      %(job_log_id)s, %(job_log_no)s, %(job_id)s, %(job_name)s, 'MISSION',
      'mock.fly.report.run', %(job_message)s, %(status)s,
      NOW(), %(start_time)s, %(stop_time)s, %(mission_id)s, 1
    )
    """

    if not dry_run:
        with conn.cursor() as cur:
            cur.execute(delete_sql)

    now = datetime.now(UTC).replace(microsecond=0)
    rng = random.Random(42)
    inserted = 0

    for route_idx, route in enumerate(routes, start=1):
        flights_per_dept = rng.randint(flights_range[0], flights_range[1])
        mission_id = BASE_MISSION_ID + route_idx
        device_sn = drone_sns[(route_idx - 1) % len(drone_sns)]
        for i in range(flights_per_dept):
            # Spread uniformly across [0, days) so every day has data
            day_offset = rng.randint(0, max(days - 1, 0))
            start_dt = now - timedelta(days=day_offset, hours=rng.randint(6, 17), minutes=rng.randint(0, 59))
            duration_min = 15 + rng.randint(0, 35) + (route_idx % 4)
            stop_dt = start_dt + timedelta(minutes=duration_min)
            status = "2" if i % 7 != 0 else "4"
            job_log_id = f"mock-fr-{route.dept_id}-{i:03d}"
            inserted += 1
            if dry_run:
                continue
            with conn.cursor() as cur:
                cur.execute(
                    insert_sql,
                    {
                        "job_log_id": job_log_id,
                        "job_log_no": f"MOCK-FR-NO-{route.dept_id}-{i:03d}",
                        "job_id": BASE_JOB_ID + route_idx,
                        "job_name": f"MOCK-FR-{route.dept_name}-定时任务",
                        "job_message": f"MOCK-FR run {i} for {device_sn}",
                        "status": status,
                        "start_time": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "stop_time": stop_dt.strftime("%Y-%m-%d %H:%M:%S") if status == "2" else "",
                        "mission_id": mission_id,
                    },
                )
    return inserted


def _insert_algorithm_records(
    conn: psycopg.Connection,
    routes: list[MockRoute],
    *,
    algo_range: tuple[int, int],
    dry_run: bool,
) -> int:
    delete_sql = "DELETE FROM t_algorithm_record WHERE mission_name LIKE 'MOCK-FR-%'"
    insert_sql = """
    INSERT INTO t_algorithm_record (
      id, file_type, algorithm_id, algorithm_name, algorithm_result,
      mission_id, mission_name, device_sn, status,
      create_time, level, longitude, latitude,
      address, push_status, push_result, extra_result
    ) VALUES (
      %(id)s, 'image', %(algorithm_id)s, %(algorithm_name)s, %(algorithm_result)s,
      %(mission_id)s, %(mission_name)s, %(device_sn)s, 1,
      %(create_time)s, 2, %(longitude)s, %(latitude)s,
      %(address)s, 1, 'mock push ok', %(extra_result)s::jsonb
    )
    """

    # Read real algorithm names from t_algorithm table
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM t_algorithm WHERE status = true ORDER BY id")
        algo_rows = cur.fetchall()
    if algo_rows:
        algorithm_ids = [int(r[0]) for r in algo_rows]
        algorithm_names = [str(r[1]) for r in algo_rows]
    else:
        # Fallback if table is empty
        algorithm_ids = [1, 2, 5, 6, 7, 9, 10, 11, 14, 18, 19]
        algorithm_names = [
            "松线虫害识别", "河道淤积识别", "车牌识别", "交通拥堵识别",
            "路面破损识别", "人群聚集识别", "非法垂钓识别", "施工识别",
            "占道经营识别", "烟火识别", "光伏板缺陷检测",
        ]

    if not dry_run:
        with conn.cursor() as cur:
            cur.execute(delete_sql)

    now = datetime.now(UTC).replace(microsecond=0)
    rng = random.Random(7)
    inserted = 0

    for route_idx, route in enumerate(routes, start=1):
        per_dept = rng.randint(algo_range[0], algo_range[1])
        mission_id = BASE_MISSION_ID + route_idx
        for i in range(per_dept):
            inserted += 1
            if dry_run:
                continue
            algo_id = BASE_ALGO_ID + route_idx * 1000 + i
            algo_idx = i % len(algorithm_names)
            create_time = now - timedelta(days=i % 10, hours=rng.randint(0, 20))
            with conn.cursor() as cur:
                cur.execute(
                    insert_sql,
                    {
                        "id": algo_id,
                        "algorithm_id": algorithm_ids[algo_idx],
                        "algorithm_name": algorithm_names[algo_idx],
                        "algorithm_result": f"{algorithm_names[algo_idx]}预警",
                        "mission_id": mission_id,
                        "mission_name": f"MOCK-FR-{route.dept_name}-飞行任务",
                        "device_sn": f"MOCK-FR-SN-{route_idx}",
                        "create_time": create_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "longitude": f"120.{rng.randint(1000, 9999)}",
                        "latitude": f"29.{rng.randint(1000, 9999)}",
                        "address": f"{route.dept_name}示范路段{i + 1}号",
                        "extra_result": '{"targets":["vehicle","smoke"],"source":"mock-fr"}',
                    },
                )
    return inserted


# ---------------------------------------------------------------------------
# TDengine OSD mock data
# ---------------------------------------------------------------------------

def _seed_tdengine_osd(
    drone_sns: list[str],
    *,
    days: int,
    td_url: str,
    td_user: str,
    td_password: str,
    dry_run: bool,
) -> int:
    """Insert mock OSD telemetry into TDengine so flight duration/distance are non-zero.

    For each drone_sn, we create one child table and insert two OSD snapshots
    per day (morning start + afternoon end) with cumulative counters.
    The ``sql_flight_overall()`` query in the analyzer computes:
      total_time = LAST(total_flight_time) - FIRST(total_flight_time)
      total_dist = LAST(total_flight_distance) - FIRST(total_flight_distance)
    so we need monotonically increasing values per drone.
    """
    if not drone_sns:
        return 0

    import re
    # Only keep SNs that produce valid TDengine table names (alphanumeric + underscore)
    valid_sns = [sn for sn in drone_sns if re.fullmatch(r'[A-Za-z0-9_\-]+', sn)]
    if not valid_sns:
        print("  No valid drone SNs for TDengine (all contain special chars)")
        return 0

    url = f"{td_url.rstrip('/')}/rest/sql/{TD_DATABASE}"
    auth = (td_user, td_password)
    now = datetime.now(UTC).replace(microsecond=0)
    rng = random.Random(77)

    rows_planned = 0
    sqls: list[str] = []

    # Clean up old mock OSD tables
    drop_sqls: list[str] = []
    for sn in valid_sns:
        table_name = f"sub_drone_osd_mock_{sn.lower().replace('-', '_')}"
        drop_sqls.append(f"DROP TABLE IF EXISTS {table_name}")

    for sn in valid_sns:
        table_name = f"sub_drone_osd_mock_{sn.lower().replace('-', '_')}"
        # Cumulative counters start at a plausible baseline
        cum_time = rng.uniform(3600, 18000)      # seconds
        cum_dist = rng.uniform(20000, 80000)      # meters
        cum_sorties = rng.randint(20, 80)

        for day in range(days - 1, -1, -1):       # oldest → newest
            base_dt = now - timedelta(days=day)

            # Morning start snapshot
            ts_start = base_dt.replace(hour=6, minute=0, second=0)
            lat = 29.0 + rng.uniform(0.01, 0.1)
            lon = 120.0 + rng.uniform(0.01, 0.1)
            sqls.append(
                f"INSERT INTO {table_name} USING st_drone_osd "
                f"TAGS('{sn}', 'v100') "
                f"VALUES ("
                f"'{ts_start.strftime('%Y-%m-%d %H:%M:%S.000')}', "
                f"{lat:.6f}, {lon:.6f}, 100.0, 0, '', '', 50.0, "
                f"0.0, 0.0, 0.0, 200.0, 8.0, 0.0, 3.0, 0, "
                f"{cum_dist:.1f}, {cum_time:.1f}, 0, 80, 0, 900, 0, "
                f"0, 0, 0, 500, 120, {cum_sorties}, false, false, false, "
                f"'mock-{day:02d}')"
            )
            rows_planned += 1

            # Afternoon end snapshot (add day's flying)
            day_time = rng.uniform(900, 3600)     # 15 min ~ 1 hr of flying
            day_dist = rng.uniform(3000, 15000)   # 3 ~ 15 km
            day_sorties = rng.randint(1, 4)
            cum_time += day_time
            cum_dist += day_dist
            cum_sorties += day_sorties

            ts_end = base_dt.replace(hour=17, minute=30, second=0)
            sqls.append(
                f"INSERT INTO {table_name} USING st_drone_osd "
                f"TAGS('{sn}', 'v100') "
                f"VALUES ("
                f"'{ts_end.strftime('%Y-%m-%d %H:%M:%S.000')}', "
                f"{lat + 0.002:.6f}, {lon + 0.003:.6f}, 120.0, 0, '', '', 55.0, "
                f"10.0, -2.0, 1.0, 350.0, 10.0, -0.5, 4.0, 1, "
                f"{cum_dist:.1f}, {cum_time:.1f}, 0, 65, 0, 600, 0, "
                f"0, 0, 0, 500, 120, {cum_sorties}, false, false, false, "
                f"'mock-{day:02d}-e')"
            )
            rows_planned += 1

    if dry_run:
        return rows_planned

    with httpx.Client(timeout=30.0) as client:
        # Drop old mock tables first
        for sql in drop_sqls:
            client.post(url, content=sql.encode(), auth=auth)

        # Insert new data
        for sql in sqls:
            resp = client.post(url, content=sql.encode(), auth=auth)
            body = resp.json()
            if body.get("code", 0) != 0:
                print(f"  TDengine error: {body.get('desc', '')}")
                print(f"  SQL: {sql[:200]}")

    return rows_planned


def _insert_media_files(
    conn: psycopg.Connection,
    *,
    planned_job_count: int,
    media_range: tuple[int, int],
    dry_run: bool,
) -> int:
    delete_sql = "DELETE FROM t_media_file WHERE file_name LIKE 'MOCK-FR-%'"
    insert_sql = """
    INSERT INTO t_media_file (
      file_id, file_name, file_type, file_size,
      bucket_name, object_key, oss_endpoint,
      workspace_id, metadata, tags,
      device_sn, biz_id, biz_type,
      deleted, created_at, created_by, updated_at, updated_by,
      lable
    ) VALUES (
      %(file_id)s, %(file_name)s, %(file_type)s, %(file_size)s,
      'mock-bucket', %(object_key)s, 'mock-oss',
      'MOCK-FR-WORKSPACE', %(metadata)s::jsonb, %(tags)s::json,
      %(device_sn)s, %(biz_id)s, 'MISSION',
      false, NOW(), 1, NOW(), 1,
      %(lable)s
    )
    """

    if dry_run:
        # In dry-run mode job logs are not persisted, so estimate media volume
        # from the planned number of mock jobs (use midpoint of range).
        avg = (media_range[0] + media_range[1]) // 2
        return planned_job_count * avg

    with conn.cursor() as cur:
        cur.execute("SELECT job_log_id, mission_id FROM sys_job_log WHERE job_log_id LIKE 'mock-fr-%'")
        job_rows = cur.fetchall()

    if not dry_run:
        with conn.cursor() as cur:
            cur.execute(delete_sql)

    rng = random.Random(99)
    inserted = 0
    for job_log_id, mission_id in job_rows:
        per_job = rng.randint(media_range[0], media_range[1])
        for i in range(per_job):
            is_video = i % 5 == 0
            file_type = 4 if is_video else 3
            file_id = uuid.uuid4().hex[:32]
            inserted += 1
            if dry_run:
                continue
            with conn.cursor() as cur:
                cur.execute(
                    insert_sql,
                    {
                        "file_id": file_id,
                        "file_name": f"MOCK-FR-{job_log_id}-{i}{'.mp4' if is_video else '.jpg'}",
                        "file_type": file_type,
                        "file_size": 1024 * (300 if is_video else 8),
                        "object_key": f"mock-fr/{job_log_id}/{file_id}",
                        "metadata": '{"durationSec":"180"}' if is_video else '{}',
                        "tags": '["mock-fr","demo"]',
                        "device_sn": f"MOCK-FR-MISSION-{mission_id}",
                        "biz_id": str(job_log_id),
                        "lable": "mock-label" if not is_video else None,
                    },
                )
    return inserted


def _verify(conn: psycopg.Connection) -> None:
    checks = [
        (
            "Recent MISSION logs filtered by configured dept IDs",
            """
            WITH route_dept AS (
              SELECT rp.id AS route_id,
                     NULLIF(trim(d.id_str), '')::int8 AS dept_id
                FROM t_route_planning rp
                LEFT JOIN LATERAL unnest(string_to_array(COALESCE(rp.deptids_tag, ''), ','))
                     AS d(id_str) ON TRUE
               WHERE rp.del_flag = false
            )
            SELECT COUNT(*)
              FROM sys_job_log jl
              JOIN t_missions m ON m.id = jl.mission_id
             WHERE jl.job_group = 'MISSION'
               AND CAST(jl.start_time AS timestamp) >= NOW() - INTERVAL '14 days'
               AND EXISTS (
                    SELECT 1 FROM route_dept rd
                     WHERE rd.route_id = m.route_id
                       AND rd.dept_id = ANY(ARRAY[380,375,382,381,395,394,384]::int8[])
               )
            """,
        ),
        (
            "Mock routes with dept tag",
            "SELECT COUNT(*) FROM t_route_planning WHERE id BETWEEN 920001 AND 920099 AND del_flag = false",
        ),
        (
            "Mock missions",
            "SELECT COUNT(*) FROM t_missions WHERE id BETWEEN 930001 AND 930099",
        ),
        (
            "Mock job logs",
            "SELECT COUNT(*) FROM sys_job_log WHERE job_log_id LIKE 'mock-fr-%'",
        ),
        (
            "Mock algorithm records",
            "SELECT COUNT(*) FROM t_algorithm_record WHERE mission_name LIKE 'MOCK-FR-%'",
        ),
        (
            "Mock media files",
            "SELECT COUNT(*) FROM t_media_file WHERE file_name LIKE 'MOCK-FR-%'",
        ),
    ]

    with conn.cursor() as cur:
        print("\nVerification:")
        for title, sql in checks:
            cur.execute(sql)
            count = cur.fetchone()[0]
            print(f"- {title}: {count}")


def _parse_range(value: str) -> tuple[int, int]:
    """Parse '5' or '3:8' into (min, max) tuple."""
    if ":" in value:
        lo, hi = value.split(":", 1)
        lo_int, hi_int = int(lo), int(hi)
        if lo_int > hi_int:
            lo_int, hi_int = hi_int, lo_int
        return (lo_int, hi_int)
    v = int(value)
    return (v, v)


def seed(*, dsn: str, dry_run: bool, days: int, flights_range: tuple[int, int], algo_range: tuple[int, int], media_range: tuple[int, int], td_url: str, td_user: str, td_password: str) -> None:
    print(f"Using DSN: {_mask_dsn(dsn)}")
    print(f"Mode: {'DRY-RUN' if dry_run else 'APPLY'}")

    routes = _build_routes()

    with psycopg.connect(dsn, autocommit=False) as conn:
        drone_sns = _pick_existing_drone_sns(conn)
        print(f"Found {len(drone_sns)} drone SNs in t_drone_device")

        print(f"Flights per dept: {flights_range[0]}~{flights_range[1]}")
        print(f"Algo per dept:    {algo_range[0]}~{algo_range[1]}")
        print(f"Media per job:    {media_range[0]}~{media_range[1]}")
        print(f"TDengine:         {'enabled' if td_url else 'disabled'}")

        route_count = _upsert_routes(conn, routes, dry_run=dry_run)
        mission_count = _upsert_missions(conn, routes, drone_sns, dry_run=dry_run)
        job_count = _upsert_sys_job(conn, routes, dry_run=dry_run)
        log_count = _insert_job_logs(
            conn,
            routes,
            drone_sns,
            days=days,
            flights_range=flights_range,
            dry_run=dry_run,
        )
        algo_count = _insert_algorithm_records(conn, routes, algo_range=algo_range, dry_run=dry_run)
        media_count = _insert_media_files(
            conn,
            planned_job_count=log_count,
            media_range=media_range,
            dry_run=dry_run,
        )

        # TDengine OSD data (flight duration / distance / sorties)
        td_count = 0
        if td_url:
            td_count = _seed_tdengine_osd(
                drone_sns,
                days=days,
                td_url=td_url,
                td_user=td_user,
                td_password=td_password,
                dry_run=dry_run,
            )

        print("\nPlanned/Inserted:")
        print(f"- routes: {route_count}")
        print(f"- missions: {mission_count}")
        print(f"- sys_job: {job_count}")
        print(f"- sys_job_log: {log_count}")
        print(f"- t_algorithm_record: {algo_count}")
        print(f"- t_media_file: {media_count}")
        print(f"- st_drone_osd (TDengine): {td_count}")

        if dry_run:
            conn.rollback()
            print("\nDry-run complete. No data was written.")
            return

        conn.commit()
        print("\nSeed committed successfully.")
        _verify(conn)


def _resolve_default_dsn() -> str:
    root = Path(__file__).resolve().parents[1]
    _load_dotenv(root / "deploy" / ".env")
    _load_dotenv(root / ".env")

    dsn = (
        os.getenv("FLY_REPORT_DIKONG_PG_WRITE_DSN")
        or os.getenv("FLY_REPORT_DIKONG_PG_DSN")
        or os.getenv("FLY_REPORT_TEXT2SQL_DSN")
    )
    if not dsn:
        raise RuntimeError(
            "No DSN found. Set FLY_REPORT_DIKONG_PG_WRITE_DSN or FLY_REPORT_DIKONG_PG_DSN"
        )
    return dsn


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed FlyReport mock data into PostgreSQL")
    parser.add_argument("--dsn", help="PostgreSQL DSN; defaults from env/deploy/.env")
    parser.add_argument("--db-user", help="Override DSN username")
    parser.add_argument("--db-password", help="Override DSN password")
    parser.add_argument("--apply", action="store_true", help="Actually write data (default is dry-run)")
    parser.add_argument("--days", type=int, default=14, help="How many recent days to spread logs")
    parser.add_argument("--flights-per-dept", default="10", help="MISSION logs per dept: N or MIN:MAX (e.g. 5:15)")
    parser.add_argument("--algo-per-dept", default="6", help="Algorithm records per dept: N or MIN:MAX (e.g. 3:10)")
    parser.add_argument("--media-per-job", default="3", help="Media files per job: N or MIN:MAX (e.g. 1:5)")
    parser.add_argument("--td-url", default=TD_BASE_URL, help="TDengine REST URL (empty to skip)")
    parser.add_argument("--td-user", default=TD_USER, help="TDengine username")
    parser.add_argument("--td-password", default=TD_PASSWORD, help="TDengine password")
    parser.add_argument("--no-tdengine", action="store_true", help="Skip TDengine OSD seeding")
    args = parser.parse_args()

    dsn = args.dsn or _resolve_default_dsn()
    dsn = _replace_user_pass(dsn, user=args.db_user, password=args.db_password)

    if "fly_report_ro" in dsn and args.db_user is None:
        raise RuntimeError(
            "Current DSN appears read-only (fly_report_ro). Please pass --db-user and --db-password "
            "for a writable role, for example --db-user dikong --db-password '***'."
        )

    seed(
        dsn=dsn,
        dry_run=not args.apply,
        days=args.days,
        flights_range=_parse_range(args.flights_per_dept),
        algo_range=_parse_range(args.algo_per_dept),
        media_range=_parse_range(args.media_per_job),
        td_url="" if args.no_tdengine else args.td_url,
        td_user=args.td_user,
        td_password=args.td_password,
    )


if __name__ == "__main__":
    main()
