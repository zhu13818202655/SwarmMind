"""F2: endpoint registry consistency."""

from __future__ import annotations

from swarmmind.domains.fly_report.dikong import (
    ENDPOINTS,
    EndpointGroup,
    EndpointKey,
    HttpMethod,
    get_endpoint,
)

# §6 minimum coverage required by DESIGN-2.
_REQUIRED_KEYS: set[EndpointKey] = {
    EndpointKey.GET_FLY_STATIS,
    EndpointKey.GET_MISSION_STATIS,
    EndpointKey.GET_DEVICE_STATIS,
    EndpointKey.GET_MEDIA_STATIC,
    EndpointKey.GET_WARN_STATIC,
    EndpointKey.MISSION_QUERY_BY_PAGE,
    EndpointKey.CALENDAR_OVERVIEW,
    EndpointKey.CALENDAR_DETAIL,
    EndpointKey.JOB_LOG_LIST,
    EndpointKey.HMS_STATS,
    EndpointKey.HMS_PAGE,
    EndpointKey.ACHS_PICS,
    EndpointKey.ACHS_VIDEOS,
    EndpointKey.ACHS_STORAGE_STATS,
    EndpointKey.ALGORITHM_RECORD_QUERY,
    EndpointKey.ALGORITHM_RECORD_QUERY_WARN,
    EndpointKey.DEVICES_MANAGE_LIST_DEPT,
    EndpointKey.DEVICES_MANAGE_DRONE_BOUND,
    EndpointKey.DASHBOARD_TASK,
    EndpointKey.DASHBOARD_RUNNING,
    EndpointKey.DASHBOARD_RESOURCE,
    EndpointKey.DASHBOARD_ACHIEVEMENT,
    EndpointKey.WEATHER_STATS,
}


def test_every_required_key_is_registered() -> None:
    missing = _REQUIRED_KEYS - set(ENDPOINTS)
    assert not missing, f"missing endpoint registrations: {missing}"


def test_paths_are_unique() -> None:
    paths = [spec.path for spec in ENDPOINTS.values()]
    assert len(paths) == len(set(paths)), "duplicate dikong paths in registry"


def test_paths_start_with_slash() -> None:
    for spec in ENDPOINTS.values():
        assert spec.path.startswith("/"), spec


def test_method_is_known_http_verb() -> None:
    for spec in ENDPOINTS.values():
        assert spec.method in {HttpMethod.GET, HttpMethod.POST}


def test_groups_cover_each_indicator_family() -> None:
    used = {spec.group for spec in ENDPOINTS.values()}
    # The five indicator families described in §6 must each have a backing group.
    for required in (
        EndpointGroup.MISSION,
        EndpointGroup.DEVICE_HEALTH,
        EndpointGroup.MEDIA,
        EndpointGroup.ALGORITHM,
        EndpointGroup.JOB_LOG,
    ):
        assert required in used


def test_get_endpoint_returns_spec() -> None:
    spec = get_endpoint(EndpointKey.GET_FLY_STATIS)
    assert spec.path == "/api/device/missions/getFlyStatis"
    assert spec.method is HttpMethod.GET
