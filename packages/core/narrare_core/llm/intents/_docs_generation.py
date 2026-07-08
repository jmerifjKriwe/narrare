"""Verbatim intent documentation — Generation operations category.

Full original docstring text (Scope/Input/Output/NOT) for structured
content generation intents. Aggregated into
:data:`narrare_core.llm.intents.INTENT_DOCS`.

Split out of the former monolithic ``intents.py`` per RULE-04. The text
here is preserved word-for-word from the original member docstrings.
"""

from __future__ import annotations

from narrare_core.llm.intents._enums import LLMIntent

GENERATION_INTENT_DOCS: dict[LLMIntent, str] = {
    LLMIntent.GENERATE: """\
General structured generation.

Scope: Generate structured content (not chapter prose) based on
parameters. Fallback intent for generation tasks without a specific
intent.
Input: Task-specific parameters and context.
Output: Structured data in requested format.
NOT: Name generation (use NAME_GENERATE).
NOT: Title generation (use TITLE_GENERATE).
""",
    LLMIntent.NAME_GENERATE: """\
Name generation for characters, places, etc.

Scope: Generate fiction-appropriate names matching specified type,
style, gender, and cultural context. Avoids duplicates with existing
project names.
Input: {{name_type}}, {{count}}, {{gender}}, {{writing_language}},
{{explanation_language}}, {{existing_names}}.
Output: JSON array of names with optional pronunciation and meaning.
NOT: Title generation (use TITLE_GENERATE).
NOT: General structured generation (use GENERATE).
""",
    LLMIntent.TITLE_GENERATE: """\
Title generation for chapters, novels, etc.

Scope: Generate compelling titles that match genre conventions
and story context. Avoids duplicates with existing titles.
Input: Story context, genre, existing titles.
Output: List of suggested titles with brief rationale.
NOT: Name generation (use NAME_GENERATE).
NOT: General structured generation (use GENERATE).
""",
}
