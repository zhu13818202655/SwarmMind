from __future__ import annotations

import os

os.environ.setdefault("SWARMMIND_AGENT__MODEL__NAME", "test-model")
os.environ.setdefault("SWARMMIND_AGENT__MODEL__BASE_URL", "http://127.0.0.1")
os.environ.setdefault("SWARMMIND_AGENT__MODEL__API_KEY", "test-key")

from swarmmind.domains.fly_report.composer.simple_composer import (
    _clean_llm_markdown,
    _table_numeric_slices,
)


def test_clean_llm_markdown_removes_trailing_hard_break_spaces() -> None:
    value = "1. 第一条结论。  \n\n\n2. 第二条结论。 \n3. 第三条结论。\t\n"

    cleaned = _clean_llm_markdown(value)

    assert cleaned == "1. 第一条结论。\n2. 第二条结论。\n3. 第三条结论。"
    assert all(not line.endswith((" ", "\t")) for line in cleaned.splitlines())


def test_table_numeric_slices_can_aggregate_algorithm_rows_by_name() -> None:
    table = {
        "rows": [
            {"algorithm_name": "漂浮物识别", "recognized_count": 5, "department_name": "水务部"},
            {"algorithm_name": "漂浮物识别", "recognized_count": 4, "department_name": "交管局"},
            {"algorithm_name": "车牌识别", "recognized_count": 2, "department_name": "交管局"},
        ]
    }

    slices = _table_numeric_slices(
        table,
        "algorithm_name",
        "recognized_count_value",
        "recognized_count",
        aggregate_by_label=True,
    )

    assert slices == [("漂浮物识别", 9.0), ("车牌识别", 2.0)]
