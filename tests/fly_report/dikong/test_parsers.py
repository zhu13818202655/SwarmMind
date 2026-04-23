"""F3: envelope + typed payload parsing tests."""

from __future__ import annotations

from swarmmind.domains.fly_report.dikong.parsers import (
    DikongEnvelope,
    FlyStatisResp,
    HmsStatsResp,
    MissionQueryByPageResp,
    WarnStaticResp,
    parse_envelope,
)


def test_envelope_success_typed() -> None:
    payload = {
        "code": 0,
        "msg": "ok",
        "requestId": "r-1",
        "requestTime": "2026-04-01T10:00:00Z",
        "data": {"droneCount": 3, "numTotal": 10, "flyTimeTotal": 1234.5},
    }
    env = parse_envelope(payload, endpoint="/missions/getFlyStatis", data_model=FlyStatisResp)
    assert isinstance(env, DikongEnvelope)
    assert env.is_success
    assert env.request_id == "r-1"
    assert isinstance(env.data, FlyStatisResp)
    assert env.data.drone_count == 3
    assert env.data.num_total == 10
    assert env.data.fly_time_total == 1234.5


def test_envelope_success_untyped_falls_back_to_dict() -> None:
    env = parse_envelope({"code": 0, "data": {"x": 1}}, endpoint="/x")
    assert env.is_success
    assert env.data == {"x": 1}


def test_envelope_business_error_does_not_raise() -> None:
    env = parse_envelope(
        {"code": 4001, "msg": "permission denied", "data": None},
        endpoint="/missions/getFlyStatis",
    )
    assert not env.is_success
    assert env.code == 4001
    assert env.msg == "permission denied"


def test_loose_typed_responses_keep_unknown_keys() -> None:
    raw = {"warnNum": 7, "categories": {"a": 1, "b": 2}}
    env = parse_envelope({"code": 0, "data": raw}, endpoint="/missions/getWarnStatic", data_model=WarnStaticResp)
    assert env.data is not None
    assert env.data.raw == raw

    env2 = parse_envelope({"code": 0, "data": {"alarms": 9}}, endpoint="/devices/hms/stats", data_model=HmsStatsResp)
    assert env2.data is not None
    assert env2.data.raw == {"alarms": 9}


def test_mission_query_by_page_aliases_list_field() -> None:
    payload = {
        "code": 0,
        "data": {
            "total": 2,
            "pageNum": 1,
            "pageSize": 50,
            "list": [
                {"id": 1, "no": "M-1", "status": "OK", "deptId": 9},
                {"id": 2, "no": "M-2", "status": "FAIL", "deptId": 9},
            ],
        },
    }
    env = parse_envelope(payload, endpoint="/missions/queryByPage", data_model=MissionQueryByPageResp)
    assert env.data is not None
    assert env.data.total == 2
    assert env.data.page == 1
    assert env.data.page_size == 50
    assert len(env.data.rows) == 2
    assert env.data.rows[0].no == "M-1"
    assert env.data.rows[0].dept_id == 9
