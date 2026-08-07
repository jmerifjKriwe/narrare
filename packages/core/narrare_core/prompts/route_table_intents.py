"""Intent → category/mode lookup tables for PromptComposer routing.

Extracted from ``route_table.py`` per RULE-04 — ``route_table.py`` reached the
400-line hard limit (see ADR-079 Consequences). The two mappings are
re-exported from ``route_table.py`` so the public import surface is unchanged
(``from narrare_core.prompts.route_table import INTENT_TO_CATEGORY`` keeps
working). This module is the authoritative source for the two dicts: the
architecture prompt-identity / prompt-surface / orphan-template checkers parse
it via ``scripts/architecture/_checkers/_ast_helpers.py``.
"""

from __future__ import annotations

from narrare_core.llm.intents import LLMIntent

__all__ = ["INTENT_TO_CATEGORY", "INTENT_TO_MODE"]

INTENT_TO_CATEGORY: dict[LLMIntent, str] = {
    LLMIntent.WRITE: "writing",
    LLMIntent.EXTEND: "writing",
    LLMIntent.REWRITE: "writing",
    LLMIntent.CO_AUTHOR: "writing",
    LLMIntent.KB_CREATE: "kb",
    LLMIntent.KB_IMPROVE: "kb",
    LLMIntent.KB_EXTRACT: "kb",
    LLMIntent.KB_INTERVIEW: "kb",
    LLMIntent.KB_SUGGEST: "kb",
    LLMIntent.KB_ENHANCE: "kb",
    LLMIntent.KB_WORLDBUILD: "kb",
    LLMIntent.KB_CONSISTENCY: "kb",
    LLMIntent.ANALYSE: "analysis",
    LLMIntent.CONSISTENCY: "analysis",
    LLMIntent.BETA_READ: "analysis",
    LLMIntent.PLAN: "planning",
    LLMIntent.SUMMARIZE: "analysis",
    LLMIntent.NAME_GENERATE: "generation",
    LLMIntent.EXTRACT: "analysis",
    LLMIntent.FACT_EXTRACT: "analysis",
    # ADR-055 D4: VOICE promoted from non-routeable to a multi-mode analysis
    # intent. Modes: character_voice (ANAL-008); voice_check (WRITE-010,
    # ADR-057 D3); voice_drift (ANAL-009 Phase 1, ADR-073 D3); author_voice
    # (ANAL-007, ADR-074); author_voice_drift (ANAL-009 Phase 2B — narrator
    # longitudinal trend classifier).
    LLMIntent.VOICE: "analysis",
    LLMIntent.SUGGEST: "writing",
    # ADR-024 / ADR-049: CHAT is a writing-craft assistant (category "writing",
    # mode "chat"). The earlier `category="chat", mode=""` drift was an
    # unauthorised deviation from ADR-024 §Decision 3 — see ADR-049 FIND-010.
    LLMIntent.CHAT: "writing",
    # ADR-069 Decision 5: DIALOGUE_COACH is the first ai_assist intent
    # (Phase 4 Task 7 — formal follow-through on the Phase 1 Task 5 stub).
    LLMIntent.DIALOGUE_COACH: "ai_assist",
}

INTENT_TO_MODE: dict[LLMIntent, str] = {
    LLMIntent.WRITE: "new_chapter",
    LLMIntent.EXTEND: "extend_chapter",
    LLMIntent.REWRITE: "rewrite_selection",
    LLMIntent.CO_AUTHOR: "co_author",
    LLMIntent.KB_IMPROVE: "improve",
    LLMIntent.KB_EXTRACT: "extract",
    LLMIntent.KB_INTERVIEW: "interview",
    LLMIntent.KB_SUGGEST: "suggest",
    LLMIntent.KB_ENHANCE: "enhance",
    LLMIntent.KB_WORLDBUILD: "worldbuilding/phase1",
    LLMIntent.KB_CONSISTENCY: "consistency",
    LLMIntent.ANALYSE: "review",
    LLMIntent.CONSISTENCY: "consistency",
    LLMIntent.BETA_READ: "beta_reader",
    LLMIntent.PLAN: "outline",
    LLMIntent.SUMMARIZE: "summarize",
    LLMIntent.NAME_GENERATE: "names",
    LLMIntent.FACT_EXTRACT: "fact_extraction",
    LLMIntent.SUGGEST: "inline_suggest",
    # ADR-055 D4: default mode for the VOICE intent. character_voice (ANAL-008)
    # is the first governed mode; voice_check (WRITE-010, ADR-057 D3) is an
    # opt-in non-default checker mode; voice_drift (ANAL-009 Phase 1, ADR-073
    # D3) is an opt-in non-default longitudinal trend-classifier mode;
    # author_voice (ANAL-007, ADR-074) is an opt-in non-default author-voice
    # profiler mode; author_voice_drift (ANAL-009 Phase 2B) is an opt-in
    # non-default narrator longitudinal trend-classifier mode.
    LLMIntent.VOICE: "character_voice",
    # ADR-024 / ADR-049: CHAT mode is "chat" (not root-mode ""). Root-mode is
    # forbidden for routeable intents per ADR-049 D3.
    LLMIntent.CHAT: "chat",
    LLMIntent.DIALOGUE_COACH: "dialogue_coach",
}
