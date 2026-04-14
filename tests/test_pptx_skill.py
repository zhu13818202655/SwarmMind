from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


def test_create_presentation_script_generates_pptx(tmp_path: Path) -> None:
    pytest.importorskip("pptx")

    script_path = (
        Path(__file__).resolve().parents[1]
        / "swarmmind"
        / "skills"
        / "pptx"
        / "scripts"
        / "create_presentation.py"
    )
    output_path = tmp_path / "gold-investment.pptx"
    deck_spec = {
        "title": "Gold Investment Outlook",
        "subtitle": "Trend review and positioning",
        "slides": [
            {
                "title": "Recent price trends",
                "summary": "Gold remained elevated as safe-haven demand stayed strong.",
                "bullets": [
                    "Prices held near recent highs during the quarter.",
                    "Rate-cut expectations supported sentiment.",
                ],
                "highlight": "Momentum is positive, but short-term swings are wider.",
                "source": "Yahoo Finance; CNBC",
            }
        ],
    }

    result = subprocess.run(
        [sys.executable, str(script_path), json.dumps(deck_spec, ensure_ascii=False), str(output_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert output_path.exists()
    with zipfile.ZipFile(output_path) as archive:
        names = set(archive.namelist())

    assert "[Content_Types].xml" in names
    assert "ppt/presentation.xml" in names
    assert "ppt/slides/slide1.xml" in names
    assert "ppt/slides/slide2.xml" in names