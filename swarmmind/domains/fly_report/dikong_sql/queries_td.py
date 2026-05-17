"""TDengine REST SQL builders for the FlyReport SQL data fetcher.

TDengine's REST endpoint does not support parameter binding, so all
identifiers and literals are quoted via :mod:`td_client` helpers
(:func:`quote_drone_sn` / :func:`quote_ts`). Every public helper here is
a pure function returning the final SQL string.
"""

from __future__ import annotations

from swarmmind.domains.fly_report.dikong_sql.td_client import (
    quote_drone_sn,
    quote_ts,
)


def _sn_in_list(drone_sns: list[str]) -> str:
    if not drone_sns:
        # ``IN ()`` is invalid; substitute an unsatisfiable predicate.
        return "''"
    return ", ".join(quote_drone_sn(sn) for sn in drone_sns)


def sql_flight_overall(
    start_ts: str,
    end_ts: str,
    drone_sns: list[str],
) -> str:
    """Aggregate (sum across drones) flight time / distance / sorties.

    Returns one row with ``total_flight_time_sec``,
    ``total_flight_distance_m`` and ``total_flight_sorties``.
    """

    s, e = quote_ts(start_ts), quote_ts(end_ts)
    sn_list = _sn_in_list(drone_sns)
    return (
        "SELECT "
        "  SUM(last_t - first_t) AS total_flight_time_sec, "
        "  SUM(last_d - first_d) AS total_flight_distance_m, "
        "  SUM(last_s - first_s) AS total_flight_sorties "
        "FROM ("
        "  SELECT drone_sn, "
        "         FIRST(total_flight_time)     AS first_t, "
        "         LAST(total_flight_time)      AS last_t, "
        "         FIRST(total_flight_distance) AS first_d, "
        "         LAST(total_flight_distance)  AS last_d, "
        "         FIRST(total_flight_sorties)  AS first_s, "
        "         LAST(total_flight_sorties)   AS last_s "
        "    FROM st_drone_osd "
        f"   WHERE ts >= {s} AND ts <= {e} "
        f"     AND drone_sn IN ({sn_list}) "
        "   GROUP BY drone_sn"
        ") t"
    )


def sql_flight_day_trend(
    start_ts: str,
    end_ts: str,
    drone_sns: list[str],
) -> str:
    """Per-day per-drone flight duration (seconds) over the period."""

    s, e = quote_ts(start_ts), quote_ts(end_ts)
    sn_list = _sn_in_list(drone_sns)
    return (
        "SELECT drone_sn, "
        "       _wstart AS day_start, "
        "       LAST(total_flight_time) - FIRST(total_flight_time) "
        "         AS day_duration_sec "
        "  FROM st_drone_osd "
        f" WHERE ts >= {s} AND ts <= {e} "
        f"   AND drone_sn IN ({sn_list}) "
        " PARTITION BY drone_sn "
        " INTERVAL(1d)"
    )


def sql_flight_per_job(
    drone_sn: str,
    start_ts: str,
    stop_ts: str,
) -> str:
    """Single-job flight duration / distance for one ``[start, stop]`` window.

    Returns one row: ``{"duration_sec": float, "distance_m": float}``.
    """

    sn = quote_drone_sn(drone_sn)
    s, e = quote_ts(start_ts), quote_ts(stop_ts)
    return (
        "SELECT "
        "  LAST(total_flight_time)     - FIRST(total_flight_time)     AS duration_sec, "
        "  LAST(total_flight_distance) - FIRST(total_flight_distance) AS distance_m "
        "FROM st_drone_osd "
        f"WHERE drone_sn = {sn} "
        f"  AND ts >= {s} AND ts <= {e}"
    )


__all__ = [
    "sql_flight_overall",
    "sql_flight_day_trend",
    "sql_flight_per_job",
]
