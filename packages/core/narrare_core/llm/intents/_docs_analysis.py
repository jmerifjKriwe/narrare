"""Verbatim intent documentation — Analysis operations category.

Full original docstring text (Scope/Input/Output/NOT) for reading,
evaluating, and checking intents. Aggregated into
:data:`narrare_core.llm.intents.INTENT_DOCS`.

Split out of the former monolithic ``intents.py`` per RULE-04. The text
here is preserved word-for-word from the original member docstrings.
"""

from __future__ import annotations

from narrare_core.llm.intents._enums import LLMIntent

ANALYSIS_INTENT_DOCS: dict[LLMIntent, str] = {
    LLMIntent.ANALYSE: """\
General-purpose text analysis.

Scope: Multi-dimension analysis covering readability, sentence
structure, POV consistency, pacing, dialogue quality, description
effectiveness. Used for the "review" and general analysis prompts.
Input: Chapter text + KB context + analysis focus parameters.
Output: Structured feedback with issues and suggestions.
NOT: Genre-specific beta reading (use BETA_READ). NOT: Sentiment
analysis (use SENTIMENT). NOT: Consistency checking (use CONSISTENCY).
""",
    LLMIntent.SENTIMENT: """\
Sentiment and emotional tone analysis.

Scope: Analyze emotional arc and sentiment progression across a
chapter or section. Identifies emotional beats, mood shifts, and
tonal patterns.
Input: Chapter text.
Output: Sentiment scores and emotional arc description.
NOT: General analysis (use ANALYSE). NOT: Consistency checking
(use CONSISTENCY).
""",
    LLMIntent.CONSISTENCY: """\
Cross-chapter consistency checking.

Scope: CHAPTER-level consistency. Compares chapter prose against
KB entity data and across chapters. Checks character, timeline,
world, and plot consistency.
Input: {{chapter_texts}} (multiple chapters), {{kb_entities}},
{{check_types}} (character/timeline/world/plot).
Output: JSON with issues (error/warning/info).
NOT: KB entry-internal consistency (use KB_CONSISTENCY).
NOT: Worldbuilding cross-entity consistency (use KB_WORLDBUILD phase2).
""",
    LLMIntent.BETA_READ: """\
Beta reader simulation — reader-perspective feedback.

Scope: Evaluates chapter from a reader's perspective across 5
dimensions: plot, character, prose, pacing, reader experience.
Genre-sensitive assessment with specific text references.
Input: {{chapter_text}}, {{chapter_titles}}, KB context,
{{focus_categories}}, {{genre}}.
Output: JSON with strengths, feedback items, reader questions,
and dimension scores (1-10).
NOT: Line-level editing (use ANALYSE). NOT: Consistency checking
(use CONSISTENCY).
""",
    LLMIntent.VOICE: """\
Voice and style analysis.

Scope: Analyze author's voice, narrative distance, stylistic
patterns, and character dialogue distinctiveness.
Input: Chapter text.
Output: Voice profile with stylistic markers and patterns.
NOT: General analysis (use ANALYSE). NOT: Beta reading (use BETA_READ).
""",
}
