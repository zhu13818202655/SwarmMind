#!/usr/bin/env python3
"""
Inspect the PostgreSQL/PostGIS database from docker-compose.yaml.

Install driver:
    python3 -m pip install "psycopg[binary]"

Run:
    python3 scripts/query_postgres_example.py

Connection defaults from docker-compose.yaml:
    host=127.0.0.1 port=51543 dbname=dikong user=dikong password=dikong123

Common overrides:
    PGHOST=127.0.0.1 PGPORT=51543 PGDATABASE=dikong PGUSER=dikong PGPASSWORD=dikong123 \
      python3 scripts/query_postgres_example.py

Target overrides used by functions in main():
    TARGET_DATABASE=dikong TARGET_SCHEMA=public TARGET_TABLE=your_table \
      python3 scripts/query_postgres_example.py
"""

from __future__ import annotations

import os
import sys
from typing import Any

try:
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
except ImportError as exc:
    raise SystemExit(
        'Missing dependency: psycopg. Install it with: python3 -m pip install "psycopg[binary]"'
    ) from exc


DEFAULT_DATABASE = os.getenv("PGDATABASE", "dikong")
TARGET_DATABASE = os.getenv("TARGET_DATABASE", DEFAULT_DATABASE)
TARGET_SCHEMA = os.getenv("TARGET_SCHEMA", "public")
TARGET_TABLE = os.getenv("TARGET_TABLE", "")


def get_connection_config(database_name: str | None = None) -> dict[str, Any]:
    return {
        "host": os.getenv("PGHOST", "127.0.0.1"),
        "port": int(os.getenv("PGPORT", "51543")),
        "dbname": database_name or DEFAULT_DATABASE,
        "user": os.getenv("PGUSER", "dikong"),
        "password": os.getenv("PGPASSWORD", "dikong123"),
        "connect_timeout": int(os.getenv("PGCONNECT_TIMEOUT", "5")),
    }


def fetch_rows(
    query: str | sql.SQL,
    params: tuple[Any, ...] | dict[str, Any] | None = None,
    database_name: str | None = None,
) -> list[dict[str, Any]]:
    config = get_connection_config(database_name)
    with psycopg.connect(**config, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            if cursor.description is None:
                return []
            return list(cursor.fetchall())


def print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def print_rows(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("No rows returned.")
        return

    for row in rows:
        print(row)


def show_database_count() -> list[dict[str, Any]]:
    """Step 1: show how many databases exist in this PostgreSQL instance."""
    print_section("1. 当前 PostgreSQL 实例中的数据库")
    rows = fetch_rows(
        """
        select
            datname as database_name,
            pg_catalog.pg_get_userbyid(datdba) as owner,
            pg_encoding_to_char(encoding) as encoding,
            datistemplate as is_template,
            datallowconn as allow_connections
        from pg_database
        order by datistemplate, datname
        """
    )

    print(f"数据库总数: {len(rows)}")
    print_rows(rows)
    return rows


def show_table_count(database_name: str = TARGET_DATABASE) -> list[dict[str, Any]]:
    """Step 2: connect to a database and show how many data tables it contains."""
    print_section(f"2. 数据库 {database_name!r} 中的数据表")
    rows = fetch_rows(
        """
        select
            table_schema,
            table_name,
            table_type
        from information_schema.tables
        where table_schema not in ('pg_catalog', 'information_schema')
        order by table_schema, table_name
        """,
        database_name=database_name,
    )

    print(f"数据表总数: {len(rows)}")
    print_rows(rows)
    return rows


def split_table_name(table_name: str, default_schema: str = TARGET_SCHEMA) -> tuple[str, str]:
    if "." not in table_name:
        return default_schema, table_name

    schema_name, bare_table_name = table_name.split(".", 1)
    return schema_name, bare_table_name


def get_first_table(database_name: str = TARGET_DATABASE) -> tuple[str, str] | None:
    rows = fetch_rows(
        """
        select table_schema, table_name
        from information_schema.tables
        where table_schema not in ('pg_catalog', 'information_schema')
          and table_type = 'BASE TABLE'
        order by table_schema, table_name
        limit 1
        """,
        database_name=database_name,
    )
    if not rows:
        return None
    return rows[0]["table_schema"], rows[0]["table_name"]


def show_table_columns(
    database_name: str,
    schema_name: str,
    table_name: str,
) -> list[dict[str, Any]]:
    rows = fetch_rows(
        """
        select
            ordinal_position,
            column_name,
            data_type,
            udt_name,
            is_nullable,
            column_default,
            character_maximum_length,
            numeric_precision,
            numeric_scale
        from information_schema.columns
        where table_schema = %s
          and table_name = %s
        order by ordinal_position
        """,
        (schema_name, table_name),
        database_name=database_name,
    )
    print("\n字段结构:")
    print_rows(rows)
    return rows


def show_table_constraints(
    database_name: str,
    schema_name: str,
    table_name: str,
) -> list[dict[str, Any]]:
    rows = fetch_rows(
        """
        select
            tc.constraint_name,
            tc.constraint_type,
            string_agg(kcu.column_name, ', ' order by kcu.ordinal_position) as columns
        from information_schema.table_constraints tc
        left join information_schema.key_column_usage kcu
          on tc.constraint_catalog = kcu.constraint_catalog
         and tc.constraint_schema = kcu.constraint_schema
         and tc.constraint_name = kcu.constraint_name
         and tc.table_schema = kcu.table_schema
         and tc.table_name = kcu.table_name
        where tc.table_schema = %s
          and tc.table_name = %s
        group by tc.constraint_name, tc.constraint_type
        order by tc.constraint_type, tc.constraint_name
        """,
        (schema_name, table_name),
        database_name=database_name,
    )
    print("\n约束:")
    print_rows(rows)
    return rows


def show_table_indexes(
    database_name: str,
    schema_name: str,
    table_name: str,
) -> list[dict[str, Any]]:
    rows = fetch_rows(
        """
        select
            indexname as index_name,
            indexdef as index_definition
        from pg_indexes
        where schemaname = %s
          and tablename = %s
        order by indexname
        """,
        (schema_name, table_name),
        database_name=database_name,
    )
    print("\n索引:")
    print_rows(rows)
    return rows


def show_table_structure(
    database_name: str = TARGET_DATABASE,
    schema_name: str = TARGET_SCHEMA,
    table_name: str = TARGET_TABLE,
) -> None:
    """Step 3: show the structure of one table: columns, constraints, and indexes."""
    if table_name:
        schema_name, table_name = split_table_name(table_name, schema_name)
    else:
        first_table = get_first_table(database_name)
        if first_table is None:
            print_section(f"3. 数据库 {database_name!r} 中没有可查看的数据表")
            return
        schema_name, table_name = first_table

    print_section(f"3. 表结构 {database_name}.{schema_name}.{table_name}")
    show_table_columns(database_name, schema_name, table_name)
    show_table_constraints(database_name, schema_name, table_name)
    show_table_indexes(database_name, schema_name, table_name)


def main() -> int:
    try:
        # show_database_count()

        # 想执行第 2 步时，取消下一行注释即可。
        # show_table_count(TARGET_DATABASE)

        # 想执行第 3 步时，取消下一行注释即可。
        # 如果没有设置 TARGET_TABLE，会自动选择目标数据库里的第一张普通表。
        show_table_structure(TARGET_DATABASE, TARGET_SCHEMA, table_name="sys_job_log")
    except Exception as exc:  # noqa: BLE001 - CLI should print a clear connection/query failure.
        print(f"Query failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())