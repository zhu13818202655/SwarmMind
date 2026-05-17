#!/usr/bin/env python3
"""逐功能测试 dikong_sql 所有 SQL 查询，同步执行，打印中间结果。

用法:
    .venv/bin/python scripts/test_all_sql_queries.py
    # 可选覆盖时间窗口:
    START=2026-01-01 END=2026-05-15 .venv/bin/python scripts/test_all_sql_queries.py
"""

from __future__ import annotations

import base64
import json
import os
import sys
from typing import Any

# ---------------------------------------------------------------------------
# 确保项目根目录在 sys.path
# ---------------------------------------------------------------------------
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import psycopg
from psycopg.rows import dict_row
import httpx

# ---------------------------------------------------------------------------
# 连接参数
# ---------------------------------------------------------------------------
PG_DSN = os.getenv(
    "FLY_REPORT_DIKONG_PG_DSN",
    "postgresql://fly_report_ro:jundadt888report@127.0.0.1:51543/dikong",
)
TD_URL = os.getenv("TDENGINE_URL", "http://127.0.0.1:51741")
TD_USER = os.getenv("TDENGINE_USER", "root")
TD_PWD = os.getenv("TDENGINE_PASSWORD", "taosdata")
TD_DB = os.getenv("TDENGINE_DB", "dikong")

# ---------------------------------------------------------------------------
# 时间窗口 & 部门
# ---------------------------------------------------------------------------
START_TS = os.getenv("START", "2026-01-01") + " 00:00:00"
END_TS = os.getenv("END", "2026-04-30") + " 23:59:59"

DEPT_MAP: dict[int, str] = {
    380: "武义县资规局",
    375: "武义县公安局",
    382: "武义县交通运输局",
    381: "武义县建设局",
    395: "金华市生态环境局武义分局",
    394: "武义县综合行政执法局（城市管理局）",
    384: "武义县农业农村局",
    217: "县创建办",
}
DEPT_IDS = list(DEPT_MAP.keys())

# ---------------------------------------------------------------------------
# SQL 导入
# ---------------------------------------------------------------------------
from swarmmind.domains.fly_report.dikong_sql.queries_pg import (
    SQL_DEPT_NAMES,
    SQL_FLY_JOB_LOGS,
    SQL_FLY_PERIOD_DRONE_SNS,
    SQL_FLY_STATIS_COUNTS,
    SQL_MEDIA_STATIC,
    SQL_ROUTE_PLAN_COUNT,
    SQL_WARN_STATIC,
)
from swarmmind.domains.fly_report.dikong_sql.queries_td import (
    sql_flight_day_trend,
    sql_flight_overall,
    sql_flight_per_job,
)

# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

def _banner(title: str) -> None:
    print(f"\n{'=' * 72}")
    print(f"  {title}")
    print(f"{'=' * 72}")


def _trunc(v: Any, maxlen: int = 80) -> str:
    s = str(v)
    return s[:maxlen] + "…" if len(s) > maxlen else s


def _print_rows(rows: list[dict], limit: int = 10) -> None:
    print(f"  返回行数: {len(rows)}")
    for i, r in enumerate(rows[:limit]):
        print(f"  [{i}] {_trunc(r, 160)}")
    if len(rows) > limit:
        print(f"  ... 省略 {len(rows) - limit} 行")


# ---------------------------------------------------------------------------
# PG 查询函数（同步）
# ---------------------------------------------------------------------------

def _pg_conn() -> psycopg.Connection:
    return psycopg.connect(PG_DSN, row_factory=dict_row, autocommit=True)


def test_dept_names(conn: psycopg.Connection) -> list[dict]:
    """功能: 部门名称查询"""
    _banner("部门名称查询 (SQL_DEPT_NAMES)")
    print(f"  dept_ids = {DEPT_IDS}")
    cur = conn.execute(SQL_DEPT_NAMES, {"dept_ids": [str(d) for d in DEPT_IDS]})
    rows = cur.fetchall()
    _print_rows(rows)
    return rows


def test_route_plan_count(conn: psycopg.Connection) -> list[dict]:
    """功能: 航线总数"""
    _banner("航线总数 (SQL_ROUTE_PLAN_COUNT)")
    cur = conn.execute(SQL_ROUTE_PLAN_COUNT)
    rows = cur.fetchall()
    _print_rows(rows)
    return rows


def test_fly_statis_counts(conn: psycopg.Connection) -> list[dict]:
    """功能 1: 总体飞行统计 — PG 计数部分"""
    _banner("总体飞行统计 · PG 计数 (SQL_FLY_STATIS_COUNTS)")
    params = {"start_ts": START_TS, "end_ts": END_TS, "dept_ids": DEPT_IDS}
    print(f"  时间窗口: {START_TS} → {END_TS}")
    print(f"  dept_ids = {DEPT_IDS}")
    cur = conn.execute(SQL_FLY_STATIS_COUNTS, params)
    rows = cur.fetchall()
    _print_rows(rows)
    return rows


def test_fly_statis_counts_no_dept(conn: psycopg.Connection) -> list[dict]:
    """功能 1: 总体飞行统计 · PG 计数（不过滤部门）"""
    _banner("总体飞行统计 · PG 计数 · 无部门过滤 (SQL_FLY_STATIS_COUNTS)")
    params = {"start_ts": START_TS, "end_ts": END_TS, "dept_ids": None}
    cur = conn.execute(SQL_FLY_STATIS_COUNTS, params)
    rows = cur.fetchall()
    _print_rows(rows)
    return rows


def test_fly_period_drone_sns(conn: psycopg.Connection) -> list[str]:
    """功能 1: 获取参与飞行的无人机 SN 列表"""
    _banner("参与飞行的无人机 SN (SQL_FLY_PERIOD_DRONE_SNS)")
    params = {"start_ts": START_TS, "end_ts": END_TS, "dept_ids": DEPT_IDS}
    cur = conn.execute(SQL_FLY_PERIOD_DRONE_SNS, params)
    rows = cur.fetchall()
    sns = sorted({r["device_sn"] for r in rows if r.get("device_sn")})
    print(f"  drone_sn 数量: {len(sns)}")
    for sn in sns:
        print(f"    {sn}")
    return sns


def test_fly_period_drone_sns_no_dept(conn: psycopg.Connection) -> list[str]:
    """功能 1: 获取参与飞行的无人机 SN（不过滤部门）"""
    _banner("参与飞行的无人机 SN · 无部门过滤 (SQL_FLY_PERIOD_DRONE_SNS)")
    params = {"start_ts": START_TS, "end_ts": END_TS, "dept_ids": None}
    cur = conn.execute(SQL_FLY_PERIOD_DRONE_SNS, params)
    rows = cur.fetchall()
    sns = sorted({r["device_sn"] for r in rows if r.get("device_sn")})
    print(f"  drone_sn 数量: {len(sns)}")
    for sn in sns:
        print(f"    {sn}")
    return sns


def test_fly_job_logs(conn: psycopg.Connection) -> list[dict]:
    """功能 1+2+3: 飞行日志（用于总体统计、日趋势、部门占比）"""
    _banner("飞行日志 (SQL_FLY_JOB_LOGS) · 有部门过滤")
    params = {
        "start_ts": START_TS,
        "end_ts": END_TS,
        "dept_ids": DEPT_IDS,
        "row_cap": 20,
    }
    cur = conn.execute(SQL_FLY_JOB_LOGS, params)
    rows = cur.fetchall()
    _print_rows(rows)
    return rows


def test_fly_job_logs_no_dept(conn: psycopg.Connection) -> list[dict]:
    """功能 1+2+3: 飞行日志（不过滤部门）"""
    _banner("飞行日志 (SQL_FLY_JOB_LOGS) · 无部门过滤")
    params = {
        "start_ts": START_TS,
        "end_ts": END_TS,
        "dept_ids": None,
        "row_cap": 20,
    }
    cur = conn.execute(SQL_FLY_JOB_LOGS, params)
    rows = cur.fetchall()
    _print_rows(rows)
    return rows


def test_warn_static(conn: psycopg.Connection) -> list[dict]:
    """功能 5-10: 算法识别记录（有部门过滤）"""
    _banner("算法识别记录 (SQL_WARN_STATIC) · 有部门过滤")
    params = {"start_ts": START_TS, "end_ts": END_TS, "dept_ids": DEPT_IDS}
    cur = conn.execute(SQL_WARN_STATIC, params)
    rows = cur.fetchall()
    _print_rows(rows)
    return rows


def test_warn_static_no_dept(conn: psycopg.Connection) -> list[dict]:
    """功能 5-10: 算法识别记录（不过滤部门）"""
    _banner("算法识别记录 (SQL_WARN_STATIC) · 无部门过滤")
    params = {"start_ts": START_TS, "end_ts": END_TS, "dept_ids": None}
    cur = conn.execute(SQL_WARN_STATIC, params)
    rows = cur.fetchall()
    _print_rows(rows)
    return rows


def test_media_static(conn: psycopg.Connection) -> list[dict]:
    """功能 4: 图片视频采集统计（有部门过滤）"""
    _banner("图片视频采集统计 (SQL_MEDIA_STATIC) · 有部门过滤")
    params = {"start_ts": START_TS, "end_ts": END_TS, "dept_ids": DEPT_IDS}
    cur = conn.execute(SQL_MEDIA_STATIC, params)
    rows = cur.fetchall()
    _print_rows(rows)
    return rows


def test_media_static_no_dept(conn: psycopg.Connection) -> list[dict]:
    """功能 4: 图片视频采集统计（不过滤部门）"""
    _banner("图片视频采集统计 (SQL_MEDIA_STATIC) · 无部门过滤")
    params = {"start_ts": START_TS, "end_ts": END_TS, "dept_ids": None}
    cur = conn.execute(SQL_MEDIA_STATIC, params)
    rows = cur.fetchall()
    _print_rows(rows)
    return rows


# ---------------------------------------------------------------------------
# TDengine 查询函数（同步 httpx）
# ---------------------------------------------------------------------------

def _td_query(sql: str) -> list[dict]:
    token = base64.b64encode(f"{TD_USER}:{TD_PWD}".encode()).decode()
    url = f"{TD_URL.rstrip('/')}/rest/sql/{TD_DB}"
    resp = httpx.post(
        url,
        content=sql.encode("utf-8"),
        headers={"Authorization": f"Basic {token}", "Content-Type": "text/plain"},
        timeout=30.0,
    )
    body = resp.json()
    if body.get("code", 0) != 0:
        print(f"  ❌ ERROR: code={body.get('code')}, desc={body.get('desc')}")
        return []
    cols = [c[0] for c in body.get("column_meta", [])]
    return [dict(zip(cols, row)) for row in body.get("data", [])]


def test_td_flight_overall(drone_sns: list[str]) -> list[dict]:
    """功能 1: 总体飞行统计 — TDengine 累计时长/里程/架次"""
    _banner("TDengine · 总体飞行统计 (sql_flight_overall)")
    if not drone_sns:
        print("  ⚠ 无可用 drone_sn，跳过")
        return []
    sql = sql_flight_overall(START_TS, END_TS, drone_sns)
    print(f"  drone_sns ({len(drone_sns)}): {drone_sns[:5]}{'…' if len(drone_sns) > 5 else ''}")
    print(f"  SQL: {_trunc(sql, 120)}")
    rows = _td_query(sql)
    _print_rows(rows)
    return rows


def test_td_flight_day_trend(drone_sns: list[str]) -> list[dict]:
    """功能 2: 每日飞行趋势 — TDengine 每天每架时长"""
    _banner("TDengine · 每日飞行趋势 (sql_flight_day_trend)")
    if not drone_sns:
        print("  ⚠ 无可用 drone_sn，跳过")
        return []
    sql = sql_flight_day_trend(START_TS, END_TS, drone_sns)
    print(f"  SQL: {_trunc(sql, 120)}")
    rows = _td_query(sql)
    _print_rows(rows)
    return rows


def test_td_flight_per_job(drone_sns: list[str], job_logs: list[dict]) -> list[dict]:
    """功能 1: 单次任务实际时长 — TDengine (sql_flight_per_job)"""
    _banner("TDengine · 单次任务时长 (sql_flight_per_job)")
    # 找一条有 device_sn + start/stop 的已完成日志
    target = None
    for log in job_logs:
        sn = log.get("device_sn")
        if sn and sn in drone_sns and log.get("start_time") and log.get("stop_time") and str(log.get("status")) == "2":
            target = log
            break
    if target is None:
        print("  ⚠ 无可用的已完成飞行日志，跳过")
        return []
    sn = target["device_sn"]
    start = target["start_time"]
    stop = target["stop_time"]
    print(f"  drone_sn={sn}  start={start}  stop={stop}")
    sql = sql_flight_per_job(sn, start, stop)
    print(f"  SQL: {_trunc(sql, 120)}")
    rows = _td_query(sql)
    _print_rows(rows)
    return rows


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"时间窗口: {START_TS} → {END_TS}")
    print(f"部门列表 ({len(DEPT_IDS)}):")
    for did, dname in DEPT_MAP.items():
        print(f"  {did} - {dname}")

    conn = _pg_conn()
    try:
        # ---- PG 查询 ----
        test_dept_names(conn)
        test_route_plan_count(conn)
        test_fly_statis_counts(conn)
        test_fly_statis_counts_no_dept(conn)
        drone_sns = test_fly_period_drone_sns(conn)
        drone_sns_all = test_fly_period_drone_sns_no_dept(conn)
        job_logs = test_fly_job_logs(conn)
        test_fly_job_logs_no_dept(conn)
        test_warn_static(conn)
        test_warn_static_no_dept(conn)
        test_media_static(conn)
        test_media_static_no_dept(conn)

        # ---- TDengine 查询 ----
        # 优先用部门过滤后的 sn，若为空则用全量 sn
        td_sns = drone_sns if drone_sns else drone_sns_all
        test_td_flight_overall(td_sns)
        test_td_flight_day_trend(td_sns)
        # 用全量 sn 的日志做 per_job 测试（更可能有匹配数据）
        all_logs = test_fly_job_logs_no_dept(conn) if not job_logs else job_logs
        test_td_flight_per_job(td_sns if td_sns else drone_sns_all, all_logs)
    finally:
        conn.close()

    _banner("全部完成 ✓")


if __name__ == "__main__":
    main()
