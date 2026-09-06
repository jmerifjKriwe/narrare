"""
Intent category grouping and default profile mapping.

Extracted from ``intents.py`` per RULE-04 (file size limit).
See :mod:`narrare_core.llm.intents` for :class:`LLMIntent`.
"""

from __future__ import annotations

from enum import StrEnum

from narrare_core.llm.intents import LLMIntent


class IntentCategory(StrEnum):
    """Categories grouping related LLM intents for manageable UX.

    Users configure model overrides per category. Intent-level overrides
    are optional (expand-on-demand in the UI).

    See: design.md D4
    """

    WRITING = "writing"
    ANALYSIS = "analysis"
    KB = "kb"
    PLANNING = "planning"
    GENERATION = "generation"
    EXTRACTION = "extraction"
    CHAT = "chat"
    RESEARCH = "research"
    # ADR-069 Decision 5: writer-facing assistance (ASSIST-* features).
    # Distinct from ANALYSIS (evaluative) and WRITING (prose generation).
    AI_ASSIST = "ai_assist"


INTENT_CATEGORY_MAP: dict[LLMIntent, IntentCategory] = {
    # Writing
    LLMIntent.WRITE: IntentCategory.WRITING,
    LLMIntent.EXTEND: IntentCategory.WRITING,
    LLMIntent.REWRITE: IntentCategory.WRITING,
    LLMIntent.CO_AUTHOR: IntentCategory.WRITING,
    # Analysis
    LLMIntent.ANALYSE: IntentCategory.ANALYSIS,
    LLMIntent.SENTIMENT: IntentCategory.ANALYSIS,
    LLMIntent.CONSISTENCY: IntentCategory.ANALYSIS,
    LLMIntent.BETA_READ: IntentCategory.ANALYSIS,
    LLMIntent.VOICE: IntentCategory.ANALYSIS,
    # ADR-069 Decision 5: DIALOGUE_COACH is the first AI_ASSIST intent.
    # Phase 1 Task 5 added this as an ANALYSIS stub; Phase 4 Task 7
    # replaces it with the real AI_ASSIST category (this commit).
    LLMIntent.DIALOGUE_COACH: IntentCategory.AI_ASSIST,
    # Knowledge base
    LLMIntent.KB_CREATE: IntentCategory.KB,
    LLMIntent.KB_IMPROVE: IntentCategory.KB,
    LLMIntent.KB_EXTRACT: IntentCategory.KB,
    LLMIntent.KB_INTERVIEW: IntentCategory.KB,
    LLMIntent.KB_SUGGEST: IntentCategory.KB,
    LLMIntent.KB_ENHANCE: IntentCategory.KB,
    LLMIntent.KB_WORLDBUILD: IntentCategory.KB,
    LLMIntent.KB_CONSISTENCY: IntentCategory.KB,
    # Planning
    LLMIntent.PLAN: IntentCategory.PLANNING,
    LLMIntent.SUMMARIZE: IntentCategory.PLANNING,
    # Generation
    LLMIntent.GENERATE: IntentCategory.GENERATION,
    LLMIntent.NAME_GENERATE: IntentCategory.GENERATION,
    LLMIntent.TITLE_GENERATE: IntentCategory.GENERATION,
    # Extraction
    LLMIntent.EXTRACT: IntentCategory.EXTRACTION,
    LLMIntent.FACT_EXTRACT: IntentCategory.EXTRACTION,
    LLMIntent.SUGGEST: IntentCategory.EXTRACTION,
    # Chat
    LLMIntent.CHAT: IntentCategory.CHAT,
    # Research
    LLMIntent.RESEARCH: IntentCategory.RESEARCH,
}
"""Maps every routeable ``LLMIntent`` to its ``IntentCategory``.

Note: ``LLMIntent.EMBED`` is intentionally excluded — embeddings are
handled separately via ``core/embeddings/`` and do not go through the
model routing cascade.
"""


_INTENT_PROFILE_DEFAULTS: dict[LLMIntent, str] = {
    # Writing — long-form output needs generous limits
    LLMIntent.WRITE: "long_texts",
    LLMIntent.EXTEND: "long_texts",
    LLMIntent.REWRITE: "long_texts",
    LLMIntent.CO_AUTHOR: "balanced",
    # Analysis
    LLMIntent.ANALYSE: "long_texts",
    LLMIntent.SENTIMENT: "quick",
    LLMIntent.CONSISTENCY: "comprehensive",
    LLMIntent.BETA_READ: "long_texts",
    LLMIntent.VOICE: "balanced",
    # ADR-069 Decision 5: Dialogue Coach output is a structured issues list
    # + alternatives (improve mode). "long_texts" (32000 tokens) fits the
    # structured-output-with-rewrites shape. Tunable via Eval (Phase 6).
    LLMIntent.DIALOGUE_COACH: "long_texts",
    # Knowledge Base
    LLMIntent.KB_CREATE: "balanced",
    LLMIntent.KB_IMPROVE: "balanced",
    LLMIntent.KB_EXTRACT: "long_texts",
    LLMIntent.KB_INTERVIEW: "quick",
    LLMIntent.KB_SUGGEST: "quick",
    LLMIntent.KB_ENHANCE: "balanced",
    LLMIntent.KB_WORLDBUILD: "long_texts",
    LLMIntent.KB_CONSISTENCY: "long_texts",
    # Planning
    LLMIntent.PLAN: "long_texts",
    LLMIntent.SUMMARIZE: "balanced",
    # Generation
    LLMIntent.GENERATE: "balanced",
    LLMIntent.NAME_GENERATE: "quick",
    LLMIntent.TITLE_GENERATE: "quick",
    # Extraction
    LLMIntent.EXTRACT: "balanced",
    LLMIntent.FACT_EXTRACT: "balanced",
    LLMIntent.SUGGEST: "quick",
    # Chat
    LLMIntent.CHAT: "balanced",
    # Research
    LLMIntent.RESEARCH: "long_texts",
}
"""Default token-limit profiles per intent.

Every routeable intent (all intents except ``EMBED``) has an explicit
profile assignment. This prevents silent fallback to ``max_tokens``
defaults and ensures writing intents receive sufficient output capacity.

Profile tiers (see ``PROFILE_OUTPUT_LIMITS`` in ``model_config.py``):

- ``quick`` (500) — lightweight operations: names, sentiment, suggestions.
- ``balanced`` (2000) — moderate output: chat, summaries, KB creation.
- ``long_texts`` (32000) — prose and analysis: writing, extraction, planning.
- ``comprehensive`` (32000) — exhaustive output: cross-chapter consistency.
"""


def get_default_profile_for_intent(intent: LLMIntent) -> str | None:
    """Return the default token-limit profile for *intent*, or ``None``.

    Callers (typically the model routing resolver) use this to seed
    ``ResolvedModelConfig.token_limit_profile`` when no user/project
    override exists.

    Parameters
    ----------
    intent:
        The LLM intent to look up.

    Returns
    -------
    str | None
        Profile name (e.g. ``"long_texts"``) if a default is defined,
        otherwise ``None``.
    """
    return _INTENT_PROFILE_DEFAULTS.get(intent)
