"""LLM-free :class:`DraftFilterSpec` extractor for local debugging.

Mirrors :class:`IntentParser` so the FlyReport service can run end-to-end
without an LLM/agent. Real production deployments swap this for the
LLM-driven :class:`IntentParser` via the service constructor.

Recognises:
- 周期: 本周/上周/周报 → weekly; 本月/上月/月报 → monthly; default = 本周
- 部门: "部门 10,20" / "dept:10" / "dept_id=10"
- 飞手: "飞手 P001"
- 指标关键字: 飞行/算法/告警/图片/视频/HMS/健康
"""

from __future__ import annotations

import calendar
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from swarmmind.domains.fly_report.errors import FilterParseError
from swarmmind.domains.fly_report.schemas import (
    Dimension,
    DraftFilterSpec,
    Indicator,
    Period,
    ReportOptions,
)

_DEPT_RE = re.compile(
    r"(?:部门|dept(?:_id)?)\s*[:：=]?\s*([\w,，\s]+?)(?=$|[，,。；;\s]|部门|飞手|指标)"
)
_PILOT_RE = re.compile(r"(?:飞手|pilot)\s*[:：]?\s*([\w,，\s]+)")

_INDICATOR_KEYWORDS: tuple[tuple[Indicator, tuple[str, ...]], ...] = (
    ("flight", ("飞行", "航迹", "里程", "架次")),
    ("algorithm", ("算法", "告警", "alert", "warn")),
    ("media_image", ("图片", "图像", "照片", "image")),
    ("media_video", ("视频", "录像", "video")),
    ("device_health", ("健康", "hms", "设备状态", "故障")),
)


def _now() -> datetime:
    return datetime.now(UTC)


def _week_period(anchor: datetime, *, offset_weeks: int = 0) -> Period:
    anchor = anchor + timedelta(weeks=offset_weeks)
    monday = (anchor - timedelta(days=anchor.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
    iso_year, iso_week, _ = monday.isocalendar()
    return Period(
        kind="weekly",
        start=monday,
        end=sunday,
        label=f"{iso_year}年第{iso_week}周",
    )


def _month_period(anchor: datetime, *, offset_months: int = 0) -> Period:
    year, month = anchor.year, anchor.month + offset_months
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    last_day = calendar.monthrange(year, month)[1]
    return Period(
        kind="monthly",
        start=datetime(year, month, 1, tzinfo=UTC),
        end=datetime(year, month, last_day, 23, 59, 59, tzinfo=UTC),
        label=f"{year}年{month:02d}月",
    )


def _detect_period(text: str) -> Period:
    t = text.lower()
    if any(k in text for k in ("上月", "上个月", "上一个月")):
        return _month_period(_now(), offset_months=-1)
    if any(k in text for k in ("本月", "这个月", "当月", "月报")):
        return _month_period(_now())
    if any(k in text for k in ("上周", "上一周")):
        return _week_period(_now(), offset_weeks=-1)
    # default: 本周 (also matches 周报/本周/这周/empty)
    return _week_period(_now())


def _detect_dimension(text: str) -> Dimension:
    dept_match = _DEPT_RE.search(text)
    if dept_match:
        ids = [t for t in re.split(r"[,，\s]+", dept_match.group(1).strip()) if t]
        ids = [i for i in ids if i and not _looks_like_period(i)]
        if ids:
            return Dimension(scope="department", department_ids=ids)

    pilot_match = _PILOT_RE.search(text)
    if pilot_match:
        ids = [t for t in re.split(r"[,，\s]+", pilot_match.group(1).strip()) if t]
        ids = [i for i in ids if i and not _looks_like_period(i)]
        if ids:
            return Dimension(scope="pilot", pilot_ids=ids)

    return Dimension(scope="overall")


def _looks_like_period(token: str) -> bool:
    return token in {"周报", "月报", "本周", "上周", "本月", "上月"}


def _detect_indicators(text: str) -> list[Indicator]:
    found: list[Indicator] = []
    for indicator, words in _INDICATOR_KEYWORDS:
        if any(w in text or w in text.lower() for w in words):
            found.append(indicator)
    if not found:
        # sensible default for "生成 XX 周报" without explicit indicator
        found = ["flight", "algorithm", "media_image", "device_health"]
    return found


class RuleBasedIntentParser:
    """LLM-free :class:`DraftFilterSpec` extractor.

    Implements the same ``parse(user_text, ...)`` coroutine signature as
    :class:`swarmmind.domains.fly_report.intent.parser.IntentParser` so
    callers can swap implementations without changes.
    """

    async def parse(
        self,
        user_text: str,
        *,
        preference: dict[str, Any] | None = None,
        now: datetime | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> DraftFilterSpec:
        if not user_text or not user_text.strip():
            raise FilterParseError("empty user text")

        text = user_text.strip()
        return DraftFilterSpec(
            period=_detect_period(text),
            dimension=_detect_dimension(text),
            indicators=_detect_indicators(text),
            options=ReportOptions(),
        )


__all__ = ["RuleBasedIntentParser"]
