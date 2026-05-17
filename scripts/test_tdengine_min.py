"""TDengine REST 最小连通性脚本.

用途：在不引入 SwarmMind 任何业务依赖的前提下，验证我们能通过
HTTP REST (taosAdapter, 默认 6041 端口、本环境宿主机 51741) 连上
低空后台的 TDengine，并执行简单查询。

依赖：仅 `httpx`（项目已有）。

环境变量（**全部可选**，不传则用脚本里的本地默认值）：
    TDENGINE_URL      默认 http://127.0.0.1:51741
    TDENGINE_USER     默认 fly_report_ro
    TDENGINE_PASSWORD 默认 Dikong@2026
    TDENGINE_DB       默认 dikong
    TDENGINE_SQL      可选；若不传则跑一组默认探测 SQL

用法：
    # 直接跑（用本地默认值，对接 dikong 容器）
    python scripts/test_tdengine_min.py

    # 跑自定义 SQL：
    TDENGINE_SQL="SELECT LAST(ts), drone_sn FROM st_drone_osd GROUP BY drone_sn LIMIT 5" \\
        python scripts/test_tdengine_min.py

    # 切回 root（管理员）账号：
    TDENGINE_USER=root TDENGINE_PASSWORD=taosdata python scripts/test_tdengine_min.py
"""

from __future__ import annotations

import asyncio
import base64
import os
import sys
from typing import Any

import httpx


# ---- 本地默认值（dikong 部署环境实测） -----------------------------------
DEFAULT_URL = "http://127.0.0.1:51741"   # taosAdapter 6041 -> 宿主机 51741
DEFAULT_USER = "fly_report_ro"           # 只读账号，见 docs/FlyReport/text2sql/DIKONG_TDENGINE_READONLY_ROLE_SETUP.md
DEFAULT_PASSWORD = "Dikong@2026"         # 强密码（满足 TDengine 3.3.5+ 强密码策略）
DEFAULT_DB = "dikong"
# --------------------------------------------------------------------------


def _build_client(base_url: str, user: str, password: str, *, timeout: float = 30.0) -> httpx.AsyncClient:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout),
        limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
        headers={"Authorization": f"Basic {token}", "Content-Type": "text/plain"},
    )


async def run_sql(client: httpx.AsyncClient, base_url: str, db: str, sql: str) -> dict[str, Any]:
    """执行单条 SQL，返回 {columns, rows, raw}."""
    url = f"{base_url.rstrip('/')}/rest/sql/{db}" if db else f"{base_url.rstrip('/')}/rest/sql"
    resp = await client.post(url, content=sql.encode("utf-8"))
    resp.raise_for_status()
    body = resp.json()
    if body.get("code", 0) != 0:
        raise RuntimeError(
            f"TDengine error: code={body.get('code')} desc={body.get('desc')!r} sql={sql!r}"
        )
    columns = [c[0] for c in body.get("column_meta", [])]
    rows = body.get("data", []) or []
    return {"columns": columns, "rows": rows, "raw": body}


def _print_table(title: str, columns: list[str], rows: list[list[Any]], *, limit: int = 10) -> None:
    print(f"\n>>> {title}")
    print(f"    columns: {columns}")
    if not rows:
        print("    (no rows)")
        return
    for r in rows[:limit]:
        print(f"    {r}")
    if len(rows) > limit:
        print(f"    ... ({len(rows) - limit} more rows)")


async def main() -> int:
    base_url = os.environ.get("TDENGINE_URL", DEFAULT_URL)
    user = os.environ.get("TDENGINE_USER", DEFAULT_USER)
    password = os.environ.get("TDENGINE_PASSWORD", DEFAULT_PASSWORD)
    db = os.environ.get("TDENGINE_DB", DEFAULT_DB)
    custom_sql = os.environ.get("TDENGINE_SQL")

    print(f"[config] base_url={base_url}  user={user}  db={db}  password={'*' * len(password)}")

    async with _build_client(base_url, user, password) as client:
        # 1) 最简单的一条：SHOW DATABASES（不要求指定 db，用 /rest/sql 根路径）
        try:
            r = await run_sql(client, base_url, db="", sql="SHOW DATABASES")
        except httpx.HTTPError as exc:
            print(f"FAIL  连接/HTTP 错误: {exc!r}", file=sys.stderr)
            return 1
        except RuntimeError as exc:
            print(f"FAIL  TDengine 鉴权或语法错误: {exc}", file=sys.stderr)
            return 1
        _print_table("SHOW DATABASES", r["columns"], r["rows"])

        if custom_sql:
            r = await run_sql(client, base_url, db=db, sql=custom_sql)
            _print_table(f"CUSTOM SQL ({db})", r["columns"], r["rows"])
            return 0

        # 2) 列出当前 db 下的 super tables（验证是否能访问业务库）
        try:
            r = await run_sql(client, base_url, db=db, sql="SHOW STABLES")
            _print_table(f"SHOW STABLES ({db})", r["columns"], r["rows"])
        except RuntimeError as exc:
            print(f"WARN  无法 SHOW STABLES，可能 db={db!r} 不存在或无权限: {exc}", file=sys.stderr)

        # 3) 探测飞行报告会用到的超级表 st_drone_osd 是否存在
        try:
            r = await run_sql(
                client,
                base_url,
                db=db,
                sql="SELECT COUNT(*) AS cnt FROM st_drone_osd",
            )
            _print_table("COUNT(*) FROM st_drone_osd", r["columns"], r["rows"])
        except RuntimeError as exc:
            print(f"WARN  st_drone_osd 不可用（可能表名/库名不同）: {exc}", file=sys.stderr)
            return 0

        # 4) 抽样最近的 5 个 drone_sn 看看有没有数据
        try:
            r = await run_sql(
                client,
                base_url,
                db=db,
                sql=(
                    "SELECT LAST(ts) AS last_ts, drone_sn, "
                    "LAST(total_flight_time) AS last_flight_time "
                    "FROM st_drone_osd GROUP BY drone_sn LIMIT 5"
                ),
            )
            _print_table("sample drones", r["columns"], r["rows"])
        except RuntimeError as exc:
            print(f"WARN  样例查询失败: {exc}", file=sys.stderr)

    print("\nOK  TDengine REST 连通性验证完成。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
