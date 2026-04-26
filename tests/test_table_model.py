from __future__ import annotations

import json

from swarmmind.models.table import DataTable, TableColumn


def test_data_table_serializes_and_extracts_summary():
    table = DataTable(
        title="总体飞行统计概览",
        columns=[
            TableColumn(key="metric", label="统计指标"),
            TableColumn(key="current", label="本周数据"),
        ],
    )
    table.add_row({"metric": "飞行总次数", "current": "12 次"}, key="flight_count")

    assert table.row_by_key("flight_count") is not None
    assert table.values_for("current") == ["12 次"]
    assert table.display_rows() == [{"metric": "飞行总次数", "current": "12 次"}]
    assert table.extract_summary() == {
        "title": "总体飞行统计概览",
        "column_count": 2,
        "row_count": 1,
        "columns": ["统计指标", "本周数据"],
        "row_keys": ["flight_count"],
    }

    payload = table.to_dict()
    assert payload["rows"][0]["key"] == "flight_count"
    assert json.loads(table.to_json())["title"] == "总体飞行统计概览"