"""Composer subpackage for FlyReport.

Step 6 ships a *minimal* composer that turns an :class:`AnalysisResult`
into a renderable :class:`ReportContext` so the end-to-end pipeline
(fetch → analyze → compose → render) can run without depending on the
LLM-driven SectionSummarizerAgent. Richer composers (LLM summaries,
narrative generation, multi-section breakdowns) land in M2+.
"""

from swarmmind.domains.fly_report.composer.simple_composer import (
    SimpleComposer,
    compose_report_context,
)

__all__ = ["SimpleComposer", "compose_report_context"]
