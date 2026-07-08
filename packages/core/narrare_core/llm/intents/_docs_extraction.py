"""Verbatim intent documentation — Extraction operations category.

Full original docstring text (Scope/Input/Output/NOT) for pulling
structured data from text. Aggregated into
:data:`narrare_core.llm.intents.INTENT_DOCS`.

Split out of the former monolithic ``intents.py`` per RULE-04. The text
here is preserved word-for-word from the original member docstrings.
"""

from __future__ import annotations

from narrare_core.llm.intents._enums import LLMIntent

EXTRACTION_INTENT_DOCS: dict[LLMIntent, str] = {
    LLMIntent.EXTRACT: """\
General structured extraction from text.

Scope: Extract structured information from arbitrary text. Used
for tasks like extracting character traits, plot points, or
thematic elements.
Input: Source text + extraction schema/parameters.
Output: Structured data matching the schema.
NOT: KB extraction (KB_EXTRACT), analysis (ANALYSE),
structured fact extraction (FACT_EXTRACT).
""",
    LLMIntent.FACT_EXTRACT: """\
Structured fact extraction with provenance (ADR-044 Stage 1).

Extract facts from prose, KB, timeline with provenance+confidence.
Reusable for KB-007, ANAL-005. NOT: KB_EXTRACT, CONSISTENCY.
""",
    LLMIntent.SUGGEST: """\
Quick inline suggestions.

Scope: Generate short, targeted suggestions — inline text completion,
story development suggestions, KB value ideas. Fast, low-token
operations.
Input: Varies by mode: {{text_before/after}} for inline, story
context for story suggestions.
Output: Short continuation text or structured suggestion list.
NOT: Full chapter generation (use WRITE).
NOT: KB-specific field suggestion (use KB_SUGGEST).
""",
}
