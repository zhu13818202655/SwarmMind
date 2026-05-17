"""SQL-backed data layer for the FlyReport domain.

This package replaces the dikong HTTP client (see
:mod:`swarmmind.domains.fly_report.dikong`) with direct reads against:

- **PostgreSQL** – the dikong business main DB (``sys_job_log`` /
  ``t_missions`` / ``t_route_planning`` / ``t_algorithm_record`` /
  ``t_media_file`` / ``sys_dept``)
- **TDengine** – the time-series DB ``dikong.st_drone_osd`` (per-drone OSD
  with cumulative ``total_flight_time/distance/sorties`` columns)

Activated by setting ``fly_report.source: sql`` in the config.
See ``.github/story/#27/case/02_sql_fetcher_plan.md`` for the design notes.
"""

from swarmmind.domains.fly_report.dikong_sql.client import DikongSqlClient
from swarmmind.domains.fly_report.dikong_sql.data_fetcher import SqlDataFetcher
from swarmmind.domains.fly_report.dikong_sql.pg_pool import (
    close_pg_pool,
    get_pg_pool,
)
from swarmmind.domains.fly_report.dikong_sql.td_client import (
    TDengineRestClient,
    close_td_client,
    get_td_client,
)

__all__ = [
    "DikongSqlClient",
    "SqlDataFetcher",
    "TDengineRestClient",
    "get_pg_pool",
    "close_pg_pool",
    "get_td_client",
    "close_td_client",
]
