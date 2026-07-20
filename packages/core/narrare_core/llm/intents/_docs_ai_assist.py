"""Verbatim intent documentation — AI-assist operations category.

Full original docstring text (Scope/Input/Output/NOT) for ASSIST-*
intents. Aggregated into :data:`narrare_core.llm.intents.INTENT_DOCS`.

Split into its own category module per RULE-04 (mirrors
``_docs_analysis.py``, ``_docs_writing.py``, etc.).
"""

from __future__ import annotations

from narrare_core.llm.intents._enums import LLMIntent

AI_ASSIST_INTENT_DOCS: dict[LLMIntent, str] = {
    LLMIntent.DIALOGUE_COACH: """\
Dialogue coaching — analyse and improve selected dialogue.

Scope: Dual-mode dialogue assistance. ``analyze`` mode identifies
issues (voice mismatch, subtext absence, exposition overload, tag
overuse, redundancy, unnatural cadence, inconsistency) with severity
and speaker attribution. ``improve`` mode additionally proposes one
or more ``DialogueAlternative`` rewrites per flagged issue. Consumes
``AdaptiveContext`` (PreferenceProfile + CharacterVoiceProfile +
derived style_constraints / avoidance_patterns + weights) as the
first pilot user of the adaptive-context vertical. Uses only the
descriptive ``speech_summary`` (never ``voice_metrics`` — ADR-055/057
boundary preserved).
Input: {{text_to_analyze}} (user-selected dialogue passage),
{{characters}} (system-attributed speaker list),
{{user_preferences}}, {{style_constraints}},
{{avoidance_patterns}}, {{character_voice_profiles}},
{{mode}} ("analyze" | "improve").
Output: Structured DialogueCoachOutput — issues with severity and
speaker; alternatives when mode="improve".
NOT: General analysis (use ANALYSE). NOT: Voice profiling (use
VOICE with character_voice mode). NOT: Voice checking/drift scoring
(use VOICE with voice_check mode). NOT: Full-chapter rewrite (use
REWRITE). NOT: Inline suggestions (use SUGGEST).
""",
}
