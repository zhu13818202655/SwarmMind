"""FlyReport analyzer package.

Entry point: :func:`analyze` takes a :class:`RawDataset` and a
:class:`NormalizedFilter` and returns an :class:`AnalysisResult`.
"""

from __future__ import annotations

from swarmmind.domains.fly_report.analyzer.aggregations import analyze

__all__ = ["analyze"]
