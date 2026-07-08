"""Verbatim intent documentation — Writing operations category.

Full original docstring text (Scope/Input/Output/NOT) for chapter-level
prose generation intents. Aggregated into :data:`narrare_core.llm.intents.INTENT_DOCS`.

Split out of the former monolithic ``intents.py`` per RULE-04. The text
here is preserved word-for-word from the original member docstrings.
"""

from __future__ import annotations

from narrare_core.llm.intents._enums import LLMIntent

WRITING_INTENT_DOCS: dict[LLMIntent, str] = {
    LLMIntent.WRITE: """\
Generate new chapter content from outline.

Scope: Full chapter prose generation from scratch. Uses outline + KB
context to produce a complete chapter draft in a single generation.
Input: {{chapter_outline}}, {{kb_characters/locations/factions}}, {{recent_chapters}},
{{novel_synopsis}}, {{style_profile}}, {{chapter_voice_profiles}}.
Output: Chapter prose in target language.
NOT: Continue/extend existing text (use EXTEND). NOT: Overwrite a
selection (use REWRITE). NOT: Scene-by-scene incremental (same intent,
different mode).
""",
    LLMIntent.EXTEND: """\
Extend existing chapter content from a continuation point.

Scope: Seamlessly continue existing text from a [CONTINUE FROM HERE]
marker. Matches style, voice, and pacing of the surrounding text.
Input: {{existing_content}}, surrounding KB context, {{extend_length}}.
Output: Continuation prose only — no meta-commentary.
NOT: Full chapter from outline (use WRITE). NOT: Rewrite existing
text (use REWRITE).
""",
    LLMIntent.REWRITE: """\
Rewrite a specific text selection with author direction.

Scope: Targeted rewrite of a selected passage. Surrounding context
(before/after) provided for style matching. Produces N alternatives.
Input: {{selection_text}}, {{context_before/after}}, {{rewrite_mode_instructions}},
{{count}} (number of alternatives).
Output: N alternatives wrapped in <alternative> tags.
NOT: Free-form continuation (use EXTEND). NOT: Full chapter generation
(use WRITE). NOT: Minor improvement without rewrite mode (use CO_AUTHOR).
""",
    LLMIntent.CO_AUTHOR: """\
Collaborative writing — targeted improvement of existing text.

Scope: Focused improvement of a passage within selected categories
(word choice, pacing, dialogue quality, description, etc.). Preserves
author's voice and structure.
Input: {{selection_text}}, {{context_before/after}}, {{co_author_focus_instructions}}.
Output: Complete revised passage (single version).
NOT: Multiple rewrite alternatives (use REWRITE). NOT: Free-form
continuation (use EXTEND).
""",
}
