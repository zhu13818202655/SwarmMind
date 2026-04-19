"""FlyReport domain package.

See ``docs/FlyReport/DESIGN-2.md`` for the end-to-end design.

Step 1 of the rollout intentionally ships only a skeleton: schemas, error
types, state-machine helpers, a service stub and the three minimal agents
(intent / clarifier / followup-router via the session hub). All external
side effects (dikong HTTP, PG, Redis, renderers) are deferred to later steps.
"""

from swarmmind.domains.fly_report.service import FlyReportService

__all__ = ["FlyReportService"]
