"""Dikong endpoint registry.

Stable identifiers for the dikong endpoints used by the FlyReport domain.
Mirrors the matrix in ``docs/FlyReport/DESIGN-2.md`` §6.

Adding a new upstream endpoint is a 3-step change:
1. add an :class:`EndpointKey` enum value;
2. add an :class:`EndpointSpec` to ``ENDPOINTS``;
3. (optional) wire a typed method on :class:`DikongClient`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"


class EndpointGroup(str, Enum):
    """Logical groups used by ``DataFetcher`` to route ``Indicator`` values."""

    AUTH = "auth"                  # 登录 / token
    MISSION = "mission"            # 飞行 / 任务统计
    DEVICE_HEALTH = "device_health"  # HMS
    MEDIA = "media"                # 成果中心
    ALGORITHM = "algorithm"        # AI 算法事件
    CALENDAR = "calendar"          # 飞行任务日历
    JOB_LOG = "job_log"            # 飞手归属落点
    DASHBOARD = "dashboard"        # Dashboard 兜底
    DEPARTMENT = "department"      # 部门字典 / 设备-部门
    WEATHER = "weather"            # 天气预警


class EndpointKey(str, Enum):
    """Stable identifier for a single dikong endpoint."""

    # auth
    LOGIN = "login"

    # department
    GET_DEPT_LIST = "get_dept_list"

    # mission stats
    GET_FLY_STATIS = "get_fly_statis"
    GET_MISSION_STATIS = "get_mission_statis"
    GET_DEVICE_STATIS = "get_device_statis"
    GET_MEDIA_STATIC = "get_media_static"
    GET_WARN_STATIC = "get_warn_static"
    MISSION_QUERY_BY_PAGE = "mission_query_by_page"

    # calendar
    CALENDAR_OVERVIEW = "calendar_overview"
    CALENDAR_DETAIL = "calendar_detail"

    # job log (pilot attribution)
    JOB_LOG_LIST = "job_log_list"
    JOB_LOG_DETAIL = "job_log_detail"

    # device health
    HMS_STATS = "hms_stats"
    HMS_PAGE = "hms_page"

    # media (achievements)
    ACHS_PICS = "achs_pics"
    ACHS_VIDEOS = "achs_videos"
    ACHS_STORAGE_STATS = "achs_storage_stats"

    # algorithm
    ALGORITHM_RECORD_QUERY = "algorithm_record_query"
    ALGORITHM_RECORD_QUERY_WARN = "algorithm_record_query_warn"

    # department / device-dept mapping
    DEVICES_MANAGE_LIST_DEPT = "devices_manage_list_dept"
    DEVICES_MANAGE_DRONE_BOUND = "devices_manage_drone_bound"

    # dashboard fallbacks
    DASHBOARD_TASK = "dashboard_task"
    DASHBOARD_RUNNING = "dashboard_running"
    DASHBOARD_RESOURCE = "dashboard_resource"
    DASHBOARD_ACHIEVEMENT = "dashboard_achievement"

    # weather (optional)
    WEATHER_STATS = "weather_stats"


@dataclass(frozen=True)
class EndpointSpec:
    """Static metadata for one dikong endpoint."""

    key: EndpointKey
    method: HttpMethod
    path: str
    group: EndpointGroup
    description: str = ""


_SPECS: tuple[EndpointSpec, ...] = (
    EndpointSpec(EndpointKey.LOGIN, HttpMethod.POST, "/system/user/login", EndpointGroup.AUTH, "账号密码登录，返回 accessToken"),
    EndpointSpec(EndpointKey.GET_DEPT_LIST, HttpMethod.GET, "/system/dept/list", EndpointGroup.DEPARTMENT, "部门列表"),
    EndpointSpec(EndpointKey.GET_FLY_STATIS, HttpMethod.GET, "/api/device/missions/getFlyStatis", EndpointGroup.MISSION, "飞行统计数据"),
    EndpointSpec(EndpointKey.GET_MISSION_STATIS, HttpMethod.GET, "/api/device/missions/getMissionStatis", EndpointGroup.MISSION, "查询任务统计数据"),
    EndpointSpec(EndpointKey.GET_DEVICE_STATIS, HttpMethod.GET, "/api/device/missions/getDeviceStatis", EndpointGroup.MISSION, "设备运行统计数据"),
    EndpointSpec(EndpointKey.GET_MEDIA_STATIC, HttpMethod.GET, "/api/device/missions/getMediaStatic", EndpointGroup.MEDIA, "媒体（图片/视频）统计"),
    EndpointSpec(EndpointKey.GET_WARN_STATIC, HttpMethod.GET, "/api/device/missions/getWarnStatic", EndpointGroup.ALGORITHM, "算法告警统计"),
    EndpointSpec(EndpointKey.MISSION_QUERY_BY_PAGE, HttpMethod.GET, "/api/device/missions/queryByPage", EndpointGroup.MISSION, "任务列表（分页明细）"),
    EndpointSpec(EndpointKey.CALENDAR_OVERVIEW, HttpMethod.GET, "/api/device/flight-task/calendar/overview", EndpointGroup.CALENDAR, "月度任务总览"),
    EndpointSpec(EndpointKey.CALENDAR_DETAIL, HttpMethod.GET, "/api/device/flight-task/calendar/detail", EndpointGroup.CALENDAR, "单日任务详情"),
    EndpointSpec(EndpointKey.JOB_LOG_LIST, HttpMethod.GET, "/api/device/job/log/list", EndpointGroup.JOB_LOG, "飞行历史 / 飞手归属"),
    EndpointSpec(EndpointKey.JOB_LOG_DETAIL, HttpMethod.GET, "/api/device/job/log/{jobLogId}", EndpointGroup.JOB_LOG, "飞行历史详情"),
    EndpointSpec(EndpointKey.HMS_STATS, HttpMethod.GET, "/api/device/devices/hms/stats", EndpointGroup.DEVICE_HEALTH, "HMS 概览"),
    EndpointSpec(EndpointKey.HMS_PAGE, HttpMethod.GET, "/api/device/devices/hms/page", EndpointGroup.DEVICE_HEALTH, "HMS 明细"),
    EndpointSpec(EndpointKey.ACHS_PICS, HttpMethod.GET, "/api/device/achs/pics", EndpointGroup.MEDIA, "成果中心｜图片列表"),
    EndpointSpec(EndpointKey.ACHS_VIDEOS, HttpMethod.GET, "/api/device/achs/videos", EndpointGroup.MEDIA, "成果中心｜视频列表"),
    EndpointSpec(EndpointKey.ACHS_STORAGE_STATS, HttpMethod.GET, "/api/device/achs/storage/stats", EndpointGroup.MEDIA, "成果中心｜存储统计"),
    EndpointSpec(EndpointKey.ALGORITHM_RECORD_QUERY, HttpMethod.GET, "/api/device/algorithmRecord/queryByPage", EndpointGroup.ALGORITHM, "AI 复核事件"),
    EndpointSpec(EndpointKey.ALGORITHM_RECORD_QUERY_WARN, HttpMethod.GET, "/api/device/algorithmRecord/queryByPageWarn", EndpointGroup.ALGORITHM, "AI 算法事件"),
    EndpointSpec(EndpointKey.DEVICES_MANAGE_LIST_DEPT, HttpMethod.GET, "/api/device/devices/manage/listDept", EndpointGroup.DEPARTMENT, "部门字典"),
    EndpointSpec(EndpointKey.DEVICES_MANAGE_DRONE_BOUND, HttpMethod.GET, "/api/device/devices/manage/drone/bound", EndpointGroup.DEPARTMENT, "设备-部门绑定"),
    EndpointSpec(EndpointKey.DASHBOARD_TASK, HttpMethod.GET, "/api/device/dashboard/stats/task", EndpointGroup.DASHBOARD, "Dashboard 任务统计"),
    EndpointSpec(EndpointKey.DASHBOARD_RUNNING, HttpMethod.GET, "/api/device/dashboard/stats/running", EndpointGroup.DASHBOARD, "Dashboard 运行统计"),
    EndpointSpec(EndpointKey.DASHBOARD_RESOURCE, HttpMethod.GET, "/api/device/dashboard/stats/resource", EndpointGroup.DASHBOARD, "Dashboard 资源统计"),
    EndpointSpec(EndpointKey.DASHBOARD_ACHIEVEMENT, HttpMethod.GET, "/api/device/dashboard/stats/achievement", EndpointGroup.DASHBOARD, "Dashboard 成果统计"),
    EndpointSpec(EndpointKey.WEATHER_STATS, HttpMethod.GET, "/api/device/weatherwarn/getWeatherStats", EndpointGroup.WEATHER, "天气预警统计"),
)


ENDPOINTS: dict[EndpointKey, EndpointSpec] = {spec.key: spec for spec in _SPECS}


def get_endpoint(key: EndpointKey) -> EndpointSpec:
    """Look up an :class:`EndpointSpec` by its :class:`EndpointKey`."""

    return ENDPOINTS[key]


__all__ = [
    "ENDPOINTS",
    "EndpointGroup",
    "EndpointKey",
    "EndpointSpec",
    "HttpMethod",
    "get_endpoint",
]
