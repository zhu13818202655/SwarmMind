"""PostgreSQL SQL strings used by :class:`DikongSqlClient`.

Each constant is the ONLY string that needs to be reviewed by the dikong
backend team. ``%(name)s`` parameter binding is mandatory – never inline
user input via f-strings.

Department filtering uses the ``route_dept`` CTE which explodes
``t_route_planning.deptids_tag`` (comma-separated department IDs) into
individual rows. This replaces the previous ``t_missions.dept_id``-based
filtering and is consistent with the dikong backend convention.

References:
- ``.github/story/#27/case/02_sql_fetcher_plan.md``
- ``.github/story/#27/case/飞行报告-修订2.md``
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Common CTE: route → department fan-out
# ---------------------------------------------------------------------------
# Explodes ``t_route_planning.deptids_tag`` (comma-separated int8 IDs) and
# ``deptids_tag_name`` into individual (route_id, dept_id, dept_name) rows.
# Used by all sub-table queries for unified department filtering.
_ROUTE_DEPT_CTE = """
route_dept AS (
  SELECT  rp.id AS route_id,
          NULLIF(trim(d.id_str), '')::int8                AS dept_id,
          COALESCE(NULLIF(trim(n.name_str), ''), '未分类') AS dept_name
    FROM  t_route_planning rp
    LEFT JOIN LATERAL unnest(string_to_array(
              COALESCE(rp.deptids_tag, ''), ','))
              WITH ORDINALITY AS d(id_str, ord1) ON TRUE
    LEFT JOIN LATERAL unnest(string_to_array(
              COALESCE(rp.deptids_tag_name, ''), ','))
              WITH ORDINALITY AS n(name_str, ord2) ON ord1 = ord2
   WHERE  rp.del_flag = false
)
"""

# ---------------------------------------------------------------------------
# fly_job_logs — replaces dikong ``GET /job/log/list``
# ---------------------------------------------------------------------------
# Returns one row per ``sys_job_log`` entry within the period.
# Department filtering via ``EXISTS (route_dept)`` avoids fan-out; the
# analyzer handles department share allocation in Python by splitting
# ``deptids_tag_name``.
SQL_FLY_JOB_LOGS = f"""
WITH {_ROUTE_DEPT_CTE}
SELECT
    jl.job_log_id                                                 AS job_log_id,
    jl.mission_id                                                 AS mission_id,
    m.dept_id                                                     AS dept_id,
    m.device_sn                                                   AS device_sn,
    m.route_id                                                    AS route_id,
    rp.deptids_tag                                                AS deptids_tag,
    rp.deptids_tag_name                                           AS deptids_tag_name,
    to_char(CAST(jl.start_time AS timestamp),
            'YYYY-MM-DD HH24:MI:SS')                              AS start_time,
    to_char(CAST(NULLIF(jl.stop_time, '') AS timestamp),
            'YYYY-MM-DD HH24:MI:SS')                              AS stop_time,
    jl.status::text                                               AS status,
    jl.create_time                                                AS create_time
  FROM sys_job_log jl
  LEFT JOIN t_missions       m  ON jl.mission_id = m.id
  LEFT JOIN t_route_planning rp ON m.route_id    = rp.id
 WHERE jl.job_group = 'MISSION'
   AND jl.start_time IS NOT NULL AND jl.start_time != ''
   AND CAST(jl.start_time AS timestamp) BETWEEN %(start_ts)s AND %(end_ts)s
   AND (
        %(dept_ids)s::int8[] IS NULL
        OR EXISTS (
            SELECT 1 FROM route_dept rd
             WHERE rd.route_id = m.route_id
               AND rd.dept_id = ANY(%(dept_ids)s::int8[])
        )
   )
 ORDER BY jl.start_time DESC
 LIMIT %(row_cap)s
"""


# ---------------------------------------------------------------------------
# fly_statis (PG side) — replaces the PG-derivable parts of
# ``GET /missions/getFlyStatis``.  The TDengine side (cumulative time /
# distance / sorties) is computed separately and merged in
# :meth:`DikongSqlClient.get_fly_statis`.
# ---------------------------------------------------------------------------
# Counts: total flights / abnormal / completed / distinct drones.
# Aligned with SQL-1.1 from 飞行报告-修订2.md.
SQL_FLY_STATIS_COUNTS = f"""
WITH {_ROUTE_DEPT_CTE},
base AS (
    SELECT  jl.job_log_id,
            m.device_sn,
            m.route_id,
            jl.status::int AS status
      FROM sys_job_log jl
      LEFT JOIN t_missions m ON jl.mission_id = m.id
     WHERE jl.job_group = 'MISSION'
       AND jl.start_time IS NOT NULL AND jl.start_time != ''
       AND CAST(jl.start_time AS timestamp) BETWEEN %(start_ts)s AND %(end_ts)s
       AND (
           %(dept_ids)s::int8[] IS NULL
           OR EXISTS (
               SELECT 1 FROM route_dept rd
                WHERE rd.route_id = m.route_id
                  AND rd.dept_id = ANY(%(dept_ids)s::int8[])
           )
       )
)
SELECT
    COUNT(*)                                            AS num_total,
    COUNT(*) FILTER (WHERE status = 4)                  AS abnormal_total,
    COUNT(*) FILTER (WHERE status = 2)                  AS drone_job_count,
    COUNT(DISTINCT device_sn) FILTER (WHERE status = 2) AS drone_count,
    COUNT(DISTINCT route_id)                            AS distinct_route_count
  FROM base
"""


SQL_ROUTE_PLAN_COUNT = """
SELECT COUNT(*) AS route_plan_count
  FROM t_route_planning
 WHERE del_flag = false
"""


# Per-period drone_sn list — feeds TDengine OSD aggregation (SQL-1.3).
SQL_FLY_PERIOD_DRONE_SNS = f"""
WITH {_ROUTE_DEPT_CTE}
SELECT DISTINCT m.device_sn AS device_sn
  FROM sys_job_log jl
  JOIN t_missions m ON jl.mission_id = m.id
 WHERE jl.job_group = 'MISSION'
   AND jl.status::int = 2
   AND m.device_sn IS NOT NULL
   AND m.device_sn <> ''
   AND jl.start_time IS NOT NULL AND jl.start_time != ''
   AND CAST(jl.start_time AS timestamp) BETWEEN %(start_ts)s AND %(end_ts)s
   AND (
        %(dept_ids)s::int8[] IS NULL
        OR EXISTS (
            SELECT 1 FROM route_dept rd
             WHERE rd.route_id = m.route_id
               AND rd.dept_id = ANY(%(dept_ids)s::int8[])
        )
   )
"""


# ---------------------------------------------------------------------------
# warn_static — replaces dikong ``GET /missions/getWarnStatic``.
# Returns one row per algorithm record. When dept_ids is provided, the
# LEFT JOIN on route_dept yields the specific ``dept_name`` for the matched
# department; when dept_ids is NULL (no dept filter), dept_name is NULL and
# the analyzer falls back to ``deptids_tag_name``.
#
# Department filtering: route_dept CTE + LEFT JOIN pattern — see
# 飞行报告-修订2.md §5–10.
# ---------------------------------------------------------------------------
SQL_WARN_STATIC = f"""
WITH {_ROUTE_DEPT_CTE}
SELECT
    r.id                                                          AS id,
    r.mission_id                                                  AS mission_id,
    r.algorithm_name                                              AS algorithm_name,
    r.algorithm_id                                                AS algorithm_id,
    r.algorithm_result                                            AS algorithm_result,
    r.extra_result                                                AS extra_result,
    r.status::text                                                AS status,
    r.push_status::text                                           AS push_status,
    r.push_result                                                 AS push_result,
    r.address                                                     AS address,
    r.longitude                                                   AS longitude,
    r.latitude                                                    AS latitude,
    to_char(r.create_time, 'YYYY-MM-DD HH24:MI:SS')               AS create_time,
    rp.deptids_tag                                                AS deptids_tag,
    rp.deptids_tag_name                                           AS deptids_tag_name,
    rd.dept_name                                                  AS dept_name
  FROM t_algorithm_record r
  JOIN t_missions          m  ON r.mission_id = m.id
  LEFT JOIN t_route_planning rp ON m.route_id  = rp.id
  LEFT JOIN route_dept     rd  ON rd.route_id  = m.route_id
                               AND rd.dept_id  = ANY(%(dept_ids)s::int8[])
 WHERE r.create_time >= %(start_ts)s
   AND r.create_time <= %(end_ts)s
   AND (
        %(dept_ids)s::int8[] IS NULL
        OR rd.route_id IS NOT NULL
   )
 ORDER BY r.create_time DESC
"""


# ---------------------------------------------------------------------------
# media_static — replaces dikong ``GET /missions/getMediaStatic``.
# Returns a single row of aggregated counters.
#
# Joins through ``sys_job_log`` (``biz_id = job_log_id``) → ``t_missions``
# → route_dept to apply department filtering, per SQL-4.1 in
# 飞行报告-修订2.md.
# ---------------------------------------------------------------------------
SQL_MEDIA_STATIC = f"""
WITH {_ROUTE_DEPT_CTE}
SELECT
    COUNT(DISTINCT mf.id) FILTER (WHERE mf.file_type = 3)
        AS "picCount",
    COUNT(DISTINCT mf.id) FILTER (WHERE mf.file_type = 3 AND mf.lable IS NOT NULL)
        AS "picLableCount",
    COUNT(DISTINCT mf.id) FILTER (WHERE mf.file_type = 4)
        AS "videoCount",
    COALESCE(SUM(
        CASE
            WHEN mf.file_type = 4
            THEN COALESCE(NULLIF(mf.metadata->>'durationSec', '')::float, 0)
            ELSE 0
        END
    ), 0) / 60.0
        AS "videoDurationMinute"
  FROM t_media_file  mf
  JOIN sys_job_log   jl ON mf.biz_id::text = jl.job_log_id::text
  JOIN t_missions     m ON jl.mission_id   = m.id
 WHERE mf.deleted = false
   AND jl.job_group = 'MISSION'
   AND mf.created_at > %(start_ts)s
   AND mf.created_at < %(end_ts)s
   AND (
        %(dept_ids)s::int8[] IS NULL
        OR EXISTS (
            SELECT 1 FROM route_dept rd
             WHERE rd.route_id = m.route_id
               AND rd.dept_id = ANY(%(dept_ids)s::int8[])
        )
   )
"""


# ---------------------------------------------------------------------------
# sys_dept lookup
# ---------------------------------------------------------------------------
SQL_DEPT_NAMES = """
SELECT dept_id::text AS dept_id, dept_name AS dept_name
  FROM sys_dept
 WHERE dept_id::text = ANY(%(dept_ids)s::text[])
"""


__all__ = [
    "SQL_FLY_JOB_LOGS",
    "SQL_FLY_STATIS_COUNTS",
    "SQL_ROUTE_PLAN_COUNT",
    "SQL_FLY_PERIOD_DRONE_SNS",
    "SQL_WARN_STATIC",
    "SQL_MEDIA_STATIC",
    "SQL_DEPT_NAMES",
]
