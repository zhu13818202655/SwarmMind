from __future__ import annotations

from datetime import datetime, timezone

from swarmmind.domains.fly_report.analyzer.aggregations import (
    analyze,
    build_algorithm_disposal_summary,
    build_algorithm_high_frequency_locations,
    build_algorithm_high_frequency_time_slots,
    build_algorithm_push_events,
    build_algorithm_recognition_distribution,
    build_algorithm_recognition_overall,
    build_flight_stat_day_trend,
    build_flight_stat_department_share,
    build_flight_stat_overall,
    build_media_collection_summary,
)
from swarmmind.domains.fly_report.schemas import (
    Dimension,
    NormalizedFilter,
    Period,
    RawDataset,
    ReportOptions,
)


def _filter(kind: str) -> NormalizedFilter:
    return NormalizedFilter(
        period=Period(
            kind=kind,
            start=datetime(2026, 4, 1, tzinfo=timezone.utc),
            end=datetime(2026, 4, 7, 23, 59, 59, tzinfo=timezone.utc),
        ),
        dimension=Dimension(scope="overall"),
        options=ReportOptions(),
        hash="h",
    )


def test_flight_stat_overall_uses_weekly_labels():
    table = build_flight_stat_overall(RawDataset(), _filter("weekly"))

    assert [column["label"] for column in table["columns"]] == [
        "统计指标",
        "本周数据",
        "上周数据",
        "环比变化",
    ]


def test_table_rows_keep_helper_values_in_meta():
    table = build_flight_stat_overall(RawDataset(), _filter("weekly"))
    column_keys = {column["key"] for column in table["columns"]}

    for row in table["rows"]:
        assert set(row) <= column_keys | {"key", "meta"}
        assert "current_value" in row["meta"]
        assert "unit" in row["meta"]


def test_flight_stat_overall_uses_monthly_labels():
    table = build_flight_stat_overall(RawDataset(), _filter("monthly"))

    assert [column["label"] for column in table["columns"]] == [
        "统计指标",
        "本月数据",
        "上月数据",
        "环比变化",
    ]


def test_flight_stat_overall_uses_period_labels_for_custom_time():
    table = build_flight_stat_overall(RawDataset(), _filter("custom"))

    assert [column["label"] for column in table["columns"]] == [
        "统计指标",
        "本期数据",
        "上期数据",
        "环比变化",
    ]


def test_flight_stat_overall_includes_longest_and_shortest_completed_duration():
    table = build_flight_stat_overall(
        RawDataset(
            current={
                "fly_job_logs": {
                    "records": [
                        {
                            "status": 2,
                            "begin_time": "2026-04-01 08:00:00",
                            "end_time": "2026-04-01 08:30:00",
                        },
                        {
                            "status": 2,
                            "begin_time": "2026-04-01 09:00:00",
                            "end_time": "2026-04-01 09:12:30",
                        },
                        {
                            "status": 4,
                            "begin_time": "2026-04-01 10:00:00",
                            "end_time": "2026-04-01 12:00:00",
                        },
                    ]
                }
            },
            previous={
                "fly_job_logs": {
                    "records": [
                        {
                            "status": 2,
                            "beginTime": "2026-03-25T08:00:00",
                            "endTime": "2026-03-25T08:20:00",
                        },
                    ]
                }
            },
        ),
        _filter("weekly"),
    )

    rows = {row["key"]: row for row in table["rows"]}
    assert rows["max_flight_duration"]["metric"] == "最长飞行时长"
    assert rows["max_flight_duration"]["meta"]["current_value"] == 30.0
    assert rows["max_flight_duration"]["meta"]["previous_value"] == 20.0
    assert rows["max_flight_duration"]["current"] == "30 分钟"
    assert rows["min_flight_duration"]["metric"] == "最短飞行时长"
    assert rows["min_flight_duration"]["meta"]["current_value"] == 12.5
    assert rows["min_flight_duration"]["current"] == "12.5 分钟"


def test_flight_stat_day_trend_returns_table_with_zero_filled_dates():
    table = build_flight_stat_day_trend(
        RawDataset(
            current={
                "fly_job_logs": {
                    "records": [
                        {
                            "status": 2,
                            "begin_time": "2026-04-01 08:00:00",
                            "end_time": "2026-04-01 08:30:00",
                        },
                        {
                            "status": 4,
                            "beginTime": "2026-04-02T09:00:00",
                            "endTime": "2026-04-02T11:00:00",
                        },
                    ]
                }
            }
        ),
        _filter("weekly"),
    )

    assert table["title"] == "每日飞行趋势"
    assert [column["label"] for column in table["columns"]] == [
        "日期",
        "飞行次数",
        "飞行时长（小时）",
        "异常次数",
    ]
    rows = {row["key"]: row for row in table["rows"]}
    assert list(rows) == [
        "2026-04-01",
        "2026-04-02",
        "2026-04-03",
        "2026-04-04",
        "2026-04-05",
        "2026-04-06",
        "2026-04-07",
    ]
    assert rows["2026-04-01"]["meta"]["flight_count_value"] == 1
    assert rows["2026-04-01"]["meta"]["flight_hours_value"] == 0.5
    assert rows["2026-04-01"]["date"] == "04-01"
    assert rows["2026-04-01"]["flight_count"] == 1
    assert rows["2026-04-01"]["flight_hours"] == 0.5
    assert rows["2026-04-02"]["meta"]["flight_count_value"] == 0
    assert rows["2026-04-02"]["meta"]["exception_count_value"] == 1
    assert rows["2026-04-03"]["flight_count"] == 0
    assert rows["2026-04-03"]["flight_hours"] == 0


def test_analyze_includes_overall_and_day_trend_tables():
    result = analyze(RawDataset(), _filter("weekly"))

    assert result.flight_stat_overall["title"] == "总体飞行统计概览"
    assert result.flight_stat_day_trend["title"] == "每日飞行趋势"
    assert result.flight_stat_department_share["title"] == "部门飞行时长占比"
    assert result.media_collection_summary["title"] == "图片视频采集统计"
    assert result.algorithm_recognition_overall["title"] == "总的算法识别数据汇总"
    assert result.algorithm_recognition_distribution["title"] == "算法识别统计"
    assert result.algorithm_disposal_summary["title"] == "算法处置统计"
    assert result.algorithm_high_frequency_locations["title"] == "高频案发点统计"
    assert result.algorithm_high_frequency_time_slots["title"] == "高频案时间段统计"
    assert result.algorithm_push_events["title"] == "算法推送事件"


def test_flight_stat_department_share_returns_ranked_table_without_other_bucket():
    table = build_flight_stat_department_share(
        RawDataset(
            current={
                "fly_job_logs": {
                    "records": [
                        {
                            "status": 2,
                            "deptidsTagName": "农业农村局",
                            "begin_time": "2026-04-01 08:00:00",
                            "end_time": "2026-04-01 10:00:00",
                        },
                        {
                            "status": 2,
                            "deptidsTagName": "自然资源和规划局",
                            "beginTime": "2026-04-01T08:00:00",
                            "endTime": "2026-04-01T09:30:00",
                        },
                        {
                            "status": 2,
                            "deptidsTagName": "应急管理局",
                            "begin_time": "2026-04-01 08:00:00",
                            "end_time": "2026-04-01 09:00:00",
                        },
                        {
                            "status": 2,
                            "deptidsTagName": "交通运输局",
                            "begin_time": "2026-04-01 08:00:00",
                            "end_time": "2026-04-01 08:30:00",
                        },
                        {
                            "status": 2,
                            "deptidsTagName": "水务局",
                            "begin_time": "2026-04-01 08:00:00",
                            "end_time": "2026-04-01 08:15:00",
                        },
                        {
                            "status": 2,
                            "deptidsTagName": "建设局",
                            "begin_time": "2026-04-01 08:00:00",
                            "end_time": "2026-04-01 08:15:00",
                        },
                        {
                            "status": 2,
                            "begin_time": "2026-04-01 08:00:00",
                            "end_time": "2026-04-01 18:00:00",
                        },
                        {
                            "status": 4,
                            "deptidsTagName": "农业农村局",
                            "begin_time": "2026-04-01 08:00:00",
                            "end_time": "2026-04-01 18:00:00",
                        },
                    ]
                }
            }
        ),
        _filter("weekly"),
    )

    assert table["title"] == "部门飞行时长占比"
    assert [column["label"] for column in table["columns"]] == [
        "部门名称",
        "飞行时长（小时）",
        "占比",
    ]
    rows = table["rows"]
    assert [row["department_name"] for row in rows] == [
        "农业农村局",
        "自然资源和规划局",
        "应急管理局",
        "交通运输局",
        "水务局",
        "建设局",
    ]
    assert rows[0]["flight_hours"] == 2.0
    assert rows[0]["share"] == "36.4%"
    assert rows[-1]["department_name"] == "建设局"
    assert rows[-1]["flight_hours"] == 0.2
    assert rows[-1]["share"] == "4.5%"
    assert "其他部门" not in {row["department_name"] for row in rows}


def test_media_collection_summary_aggregates_media_static_counts_and_duration():
    table = build_media_collection_summary(
        RawDataset(
            current={
                "media_static": {
                    "375": {
                        "raw": {
                            "picCount": 2800,
                            "picLableCount": 500,
                            "videoCount": 40,
                            "videoDurationMinute": 300,
                        }
                    },
                    "376": {
                        "raw": {
                            "picCount": 60,
                            "picLableCount": 20,
                            "videoCount": 8,
                            "videoDurationMinute": 25,
                        }
                    },
                }
            },
            previous={
                "media_static": {
                    "raw": {
                        "picCount": 2413,
                        "picLableCount": 420,
                        "videoCount": 42,
                    }
                }
            },
        ),
        _filter("weekly"),
    )

    assert [column["label"] for column in table["columns"]] == ["统计类别", "数量", "总时长", "平均时长", "环比变化"]
    rows = {row["key"]: row for row in table["rows"]}
    assert rows["image_collection_count"]["statistic_category"] == "图片采集总张数"
    assert rows["image_collection_count"]["count"] == "2860 张"
    assert rows["image_collection_count"]["total_duration"] == "—"
    assert rows["image_collection_count"]["average_duration"] == "—"
    assert rows["image_collection_count"]["change"] == "↑ 18.5%"
    assert rows["labeled_image_count"]["count"] == "520 张"
    assert rows["labeled_image_count"]["change"] == "↑ 23.8%"
    assert rows["video_collection_count"]["count"] == "48 条"
    assert rows["video_collection_count"]["total_duration"] == "325 分钟"
    assert rows["video_collection_count"]["average_duration"] == "6.8 分钟"
    assert rows["video_collection_count"]["change"] == "↑ 14.3%"


def test_algorithm_recognition_overall_uses_records_and_extra_result_values():
    table = build_algorithm_recognition_overall(
        RawDataset(
            current={
                "warn_static": {
                    "records": [
                        {"extraResult": '{"personCount": 1, "crowdMinCount": 2}'},
                        {"extra_result": {"plateCount": 4}},
                        {"extraResult": '{"plateNumbers": ["浙A12345", "浙A67890"]}'},
                    ]
                }
            },
            previous={"warn_static": {"records": [{"extraResult": '{"personCount": 2}'}]}},
        ),
        _filter("weekly"),
    )

    rows = {row["key"]: row for row in table["rows"]}
    assert [column["label"] for column in table["columns"]] == ["统计指标", "本周数据", "上周数据", "环比变化"]
    assert rows["recognition_count"]["current"] == "3 次"
    assert rows["recognition_count"]["previous"] == "1 次"
    assert rows["recognized_target_count"]["current"] == "9 个"
    assert rows["recognized_target_count"]["previous"] == "2 个"


def test_algorithm_recognition_distribution_groups_by_algorithm_and_department():
    filt = _filter("weekly").model_copy(update={"dept_ids": [101, 102], "dept_names": ["水务部", "交管局"]})
    table = build_algorithm_recognition_distribution(
        RawDataset(
            current={
                "warn_static": {
                    "101": {
                        "records": [
                            {"algorithmName": "漂浮物识别", "extraResult": '{"count": 3}'},
                            {"algorithmName": "漂浮物识别", "extraResult": '{"count": 2}'},
                        ]
                    },
                    "102": {
                        "records": [
                            {"algorithmName": "车牌识别", "extraResult": '{"plate": 4}'},
                            {"algorithmName": "漂浮物识别", "extraResult": '{"count": 1}'},
                        ]
                    },
                }
            }
        ),
        filt,
    )

    rows = table["rows"]
    assert [column["label"] for column in table["columns"]] == ["算法名称", "识别数量", "占比", "使用部门"]
    rows_by_key = {row["key"]: row for row in rows}
    assert rows_by_key["漂浮物识别:水务部"]["recognized_count"] == 5
    assert rows_by_key["漂浮物识别:水务部"]["share"] == "50.0%"
    assert rows_by_key["漂浮物识别:水务部"]["department_name"] == "水务部"
    assert rows_by_key["车牌识别:交管局"]["recognized_count"] == 4
    assert rows_by_key["车牌识别:交管局"]["share"] == "40.0%"
    assert rows_by_key["车牌识别:交管局"]["department_name"] == "交管局"
    assert rows_by_key["漂浮物识别:交管局"]["recognized_count"] == 1
    assert rows_by_key["漂浮物识别:交管局"]["share"] == "10.0%"
    assert rows_by_key["漂浮物识别:交管局"]["department_name"] == "交管局"


def test_algorithm_disposal_summary_counts_status_2_by_scene_and_department():
    filt = _filter("weekly").model_copy(update={"dept_ids": [101], "dept_names": ["部门一"]})
    table = build_algorithm_disposal_summary(
        RawDataset(
            current={
                "warn_static": {
                    "101": {
                        "records": [
                            {"algorithmName": "漂浮物识别", "status": 2},
                            {"algorithmName": "漂浮物识别", "status": 0},
                            {"algorithmName": "漂浮物识别", "status": 2},
                            {"algorithmName": "车牌识别", "status": 0},
                        ]
                    }
                }
            }
        ),
        filt,
    )

    rows = table["rows"]
    assert [column["label"] for column in table["columns"]] == ["场景名称", "使用部门", "发生次数", "处置次数", "处置占比"]
    assert rows[0]["scene_name"] == "漂浮物识别"
    assert rows[0]["department_name"] == "部门一"
    assert rows[0]["occurrence_count"] == 3
    assert rows[0]["disposal_count"] == 2
    assert rows[0]["disposal_share"] == "66.7%"
    assert rows[1]["disposal_share"] == "0%"


def test_algorithm_high_frequency_locations_groups_by_scene_department_and_blank_location():
    filt = _filter("weekly").model_copy(update={"dept_ids": [101, 102], "dept_names": ["部门一", "部门二"]})
    table = build_algorithm_high_frequency_locations(
        RawDataset(
            current={
                "warn_static": {
                    "101": {
                        "records": [
                            {"algorithmName": "占道经营识别", "createTime": "2026-04-21 19:34:08"},
                            {"algorithmName": "占道经营识别", "createTime": "2026-04-21 19:36:08"},
                            {"algorithmName": "占道经营识别", "createTime": "2026-04-21 19:38:08"},
                            {"algorithmName": "占道经营识别", "createTime": "2026-04-21 19:40:08"},
                            {"algorithmName": "零星违停识别", "address": "支路 A"},
                        ]
                    },
                    "102": {
                        "records": [
                            {"algorithmName": "交通拥堵识别", "address": "XXX 街道 XX 路"},
                            {"algorithmName": "交通拥堵识别", "address": "XXX 街道 XX 路"},
                            {"algorithmName": "交通拥堵识别", "address": "XXX 街道 XX 路"},
                        ]
                    },
                }
            }
        ),
        filt,
    )

    rows = table["rows"]
    assert [column["label"] for column in table["columns"]] == ["场景名称", "使用部门", "地点", "发生次数"]
    assert rows[0]["scene_name"] == "占道经营识别"
    assert rows[0]["department_name"] == "部门一"
    assert rows[0]["location"] == ""
    assert rows[0]["occurrence_count"] == 4
    assert rows[1]["scene_name"] == "交通拥堵识别"
    assert rows[1]["location"] == "XXX 街道 XX 路"
    assert rows[1]["occurrence_count"] == 3
    assert len(rows) == 2


def test_algorithm_high_frequency_time_slots_groups_by_custom_periods():
    filt = _filter("weekly").model_copy(update={"dept_ids": [101, 102], "dept_names": ["部门一", "部门二"]})
    table = build_algorithm_high_frequency_time_slots(
        RawDataset(
            current={
                "warn_static": {
                    "101": {
                        "records": [
                            {"algorithmName": "占道经营识别", "createTime": "2026-04-20 18:00:00"},
                            {"algorithmName": "占道经营识别", "createTime": "2026-04-20 19:00:00"},
                            {"algorithmName": "占道经营识别", "createTime": "2026-04-21 20:59:59"},
                            {"algorithmName": "人群聚集识别", "createTime": "2026-04-25 15:00:00"},
                        ]
                    },
                    "102": {
                        "records": [
                            {"algorithmName": "交通拥堵识别", "createTime": "2026-04-21 06:00:00"},
                            {"algorithmName": "交通拥堵识别", "createTime": "2026-04-21 08:59:59"},
                        ]
                    },
                }
            }
        ),
        filt,
    )

    rows = table["rows"]
    assert [column["label"] for column in table["columns"]] == ["场景名称", "使用部门", "时间段", "发生次数"]
    assert rows[0]["scene_name"] == "占道经营识别"
    assert rows[0]["department_name"] == "部门一"
    assert rows[0]["time_slot"] == "工作日晚高峰"
    assert rows[0]["occurrence_count"] == 3
    assert rows[1]["scene_name"] == "交通拥堵识别"
    assert rows[1]["time_slot"] == "工作日早高峰"
    assert rows[1]["occurrence_count"] == 2
    assert len(rows) == 2


def test_algorithm_high_frequency_locations_keeps_only_top_five_repeated_items():
    filt = _filter("weekly").model_copy(update={"dept_ids": [101], "dept_names": ["部门一"]})
    records = []
    for index, occurrence_count in enumerate([7, 6, 5, 4, 3, 2, 1], start=1):
        records.extend(
            {
                "algorithmName": f"算法 {index}",
                "address": f"点位 {index}",
            }
            for _ in range(occurrence_count)
        )

    table = build_algorithm_high_frequency_locations(
        RawDataset(current={"warn_static": {"101": {"records": records}}}),
        filt,
    )

    rows = table["rows"]
    assert [row["occurrence_count"] for row in rows] == [7, 6, 5, 4, 3]
    assert [row["location"] for row in rows] == ["点位 1", "点位 2", "点位 3", "点位 4", "点位 5"]


def test_algorithm_push_events_keeps_only_pushed_records():
    filt = _filter("weekly").model_copy(update={"dept_ids": [101], "dept_names": ["部门二"]})
    table = build_algorithm_push_events(
        RawDataset(
            current={
                "warn_static": {
                    "101": {
                        "records": [
                            {
                                "id": 1,
                                "algorithmName": "漂浮物识别",
                                "pushStatus": 1,
                                "createTime": "2026-04-21 09:34:08",
                                "pushTime": "2026-04-21 09:35:08",
                            },
                            {
                                "id": 2,
                                "algorithmName": "车牌识别",
                                "pushStatus": 0,
                                "createTime": "2026-04-21 09:36:08",
                            },
                        ]
                    }
                }
            }
        ),
        filt,
    )

    assert [column["label"] for column in table["columns"]] == ["场景名称", "使用部门", "发生时间", "推送时间"]
    assert len(table["rows"]) == 1
    assert table["rows"][0]["scene_name"] == "漂浮物识别"
    assert table["rows"][0]["department_name"] == "部门二"
    assert table["rows"][0]["occurrence_time"] == "2026-04-21 09:34:08"
    assert table["rows"][0]["push_time"] == "2026-04-21 09:35:08"
