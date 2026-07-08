"""Aggregator for verbatim intent documentation.

Combines the per-category doc mappings (``_docs_*.py``) into the single
public :data:`INTENT_DOCS` mapping. This keeps the full original verbose
documentation (Scope/Input/Output/NOT) for every intent discoverable at
``narrare_core.llm.intents.INTENT_DOCS`` while the compact enum lives in
``_enums``.

Nothing is lost: every ``LLMIntent`` member's full original docstring text
is preserved word-for-word here. The split across category modules follows
RULE-04 (modularize, do not compress) and mirrors the section headers of
the former monolithic ``intents.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.llm.intents._docs_analysis import ANALYSIS_INTENT_DOCS
from narrare_core.llm.intents._docs_chat import CHAT_INTENT_DOCS
from narrare_core.llm.intents._docs_embed import EMBED_INTENT_DOCS
from narrare_core.llm.intents._docs_extraction import EXTRACTION_INTENT_DOCS
from narrare_core.llm.intents._docs_generation import GENERATION_INTENT_DOCS
from narrare_core.llm.intents._docs_kb import KB_INTENT_DOCS
from narrare_core.llm.intents._docs_planning import PLANNING_INTENT_DOCS
from narrare_core.llm.intents._docs_writing import WRITING_INTENT_DOCS

if TYPE_CHECKING:
    from narrare_core.llm.intents._enums import LLMIntent

#: Full verbose documentation (Scope/Input/Output/NOT) for every LLMIntent,
#: preserved verbatim from the original member docstrings. The compact
#: ``LLMIntent`` member docstrings (in ``_enums``) hold only a one-line scope
#: summary; this mapping holds the complete reference text.
INTENT_DOCS: dict[LLMIntent, str] = {
    **WRITING_INTENT_DOCS,
    **ANALYSIS_INTENT_DOCS,
    **KB_INTENT_DOCS,
    **PLANNING_INTENT_DOCS,
    **GENERATION_INTENT_DOCS,
    **EXTRACTION_INTENT_DOCS,
    **CHAT_INTENT_DOCS,
    **EMBED_INTENT_DOCS,
}
