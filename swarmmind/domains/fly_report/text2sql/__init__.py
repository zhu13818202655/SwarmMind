"""FlyReport Text-to-SQL data-query subdomain.

Backed by a Vanna 2.0 multi-tool agent (see :mod:`agent`) that runs over a
hand-curated YAML knowledge base under
:attr:`swarmmind.config.schema.FlyReportText2SqlConfig.knowledge_path`.

Public surface:

* :class:`Text2SqlService` — high-level entrypoint. Returns
  :class:`Text2SqlAnswer`.
* :class:`Text2SqlAgent` — the Vanna 2.0 agent wrapper for scripts / CLI.
* :func:`build_text2sql_service_from_settings` — factory used by the
  FlyReport service layer.
"""

from swarmmind.domains.fly_report.text2sql.agent import (
    Text2SqlAgent,
    Text2SqlAgentResult,
)
from swarmmind.domains.fly_report.text2sql.errors import (
    Text2SqlConfigError,
    Text2SqlError,
    Text2SqlExecutionError,
    Text2SqlGenerationError,
)
from swarmmind.domains.fly_report.text2sql.knowledge import (
    Knowledge,
    load_knowledge,
)
from swarmmind.domains.fly_report.text2sql.service import (
    QueryResult,
    Text2SqlAnswer,
    Text2SqlService,
    build_text2sql_service_from_settings,
)

__all__ = [
    "Knowledge",
    "QueryResult",
    "Text2SqlAgent",
    "Text2SqlAgentResult",
    "Text2SqlAnswer",
    "Text2SqlConfigError",
    "Text2SqlError",
    "Text2SqlExecutionError",
    "Text2SqlGenerationError",
    "Text2SqlService",
    "build_text2sql_service_from_settings",
    "load_knowledge",
]
