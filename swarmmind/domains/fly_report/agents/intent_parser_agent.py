"""IntentParserAgent (alias / convenience accessor).

The actual agent is built by :func:`swarmmind.domains.fly_report.agents.factory.build_intent_agent`.
This module exists so future code (and tests) can import a stable symbol name
without depending on the factory layout.
"""

from swarmmind.domains.fly_report.agents.factory import build_intent_agent

__all__ = ["build_intent_agent"]
