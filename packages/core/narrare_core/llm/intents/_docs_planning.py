"""Verbatim intent documentation — Planning operations category.

Full original docstring text (Scope/Input/Output/NOT) for story
structure and scene planning intents. Aggregated into
:data:`narrare_core.llm.intents.INTENT_DOCS`.

Split out of the former monolithic ``intents.py`` per RULE-04. The text
here is preserved word-for-word from the original member docstrings.
"""

from __future__ import annotations

from narrare_core.llm.intents._enums import LLMIntent

PLANNING_INTENT_DOCS: dict[LLMIntent, str] = {
    LLMIntent.PLAN: """\
Scene/structure planning.

Scope: Generate chapter outlines, scene breakdowns, and story
structure plans. Can produce multiple variant outlines.
Input: {{project_title}}, {{genre}}, {{tone}}, {{kb_characters/locations}},
{{variant_count}}.
Output: Structured outline with scenes, chapter titles, narrative flow.
NOT: Character arc planning (no dedicated intent — uses PLAN).
NOT: Timeline analysis (no dedicated intent — uses PLAN).
""",
    LLMIntent.SUMMARIZE: """\
Chapter/section summarization.

Scope: Condense chapter content into concise plot-relevant summary
with key narrative beats. Present tense, no editorializing.
Input: Chapter text, {{chapter_title}}, {{genre}}, KB context.
Output: 2-4 sentence summary + 2-5 key points.
NOT: Reader-perspective analysis (use BETA_READ).
NOT: Consistency checking (use CONSISTENCY).
""",
}
