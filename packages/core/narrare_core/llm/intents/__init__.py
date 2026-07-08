"""LLM Intent definitions and documentation.

Every LLM call carries an intent. Intents are grouped into categories
for user-configurable model routing. The actual model resolution is
handled by ``ModelRoutingResolver`` implementations — this package
defines the types and their documentation only.

Package layout (split from the former monolithic ``intents.py`` per
RULE-04 — modularize, do not compress):

- :data:`LLMIntent` — the compact ``StrEnum`` (one-line scope docstrings),
  defined in ``_enums``.
- :data:`INTENT_DOCS` — the **full verbose documentation** (Scope/Input/
  Output/NOT) for every intent, preserved verbatim from the original
  member docstrings, split across ``_docs_*.py`` category modules and
  aggregated in ``_docs``.

Public API is unchanged: ``from narrare_core.llm.intents import LLMIntent``
resolves identically to before.
"""

from __future__ import annotations

from narrare_core.llm.intents._docs import INTENT_DOCS
from narrare_core.llm.intents._enums import LLMIntent

__all__ = [
    "INTENT_DOCS",
    "LLMIntent",
]
