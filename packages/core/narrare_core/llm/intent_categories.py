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
    LLMIntent.BETA_READ: "long_texts",
    LLMIntent.NAME_GENERATE: "quick",
}
"""Default token-limit profiles per intent.

When the model routing resolver builds a ``ResolvedModelConfig``, it
should consult this mapping to set ``token_limit_profile`` unless the
user/project already provides one.  Intents not listed here fall back
to the global default (``"balanced"``).
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
