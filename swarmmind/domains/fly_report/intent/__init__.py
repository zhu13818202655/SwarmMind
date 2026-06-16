"""FlyReport intent layer.

Wraps a lightweight :class:`OpenAICompatibleLMClient` with a thin business
class that:

- formats the user text plus optional ``preference`` / ``now`` metadata,
- calls the underlying LM client with a JSON-only response format,
- parses and validates the JSON reply into :class:`DraftFilterSpec`.

It does not run clarification, permission checks, or normalization — those
are owned by the FlyReport state machine (see ``DESIGN-2`` §3.1 / §7).
"""

from __future__ import annotations

from .classifier import IntentClassifier, IntentLabel
from .parser import IntentParser

__all__ = ["IntentParser", "IntentClassifier", "IntentLabel"]
