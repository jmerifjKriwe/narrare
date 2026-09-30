"""Intent-to-profile mapping — suggests model capabilities per LLMIntent.

Each intent has a recommended output profile and model capability tier.
This is **advisory** — the actual model is resolved by
:class:`~narrare_core.llm.model_routing.ModelRoutingResolver` using
the user's settings cascade. This module does not change routing
behaviour; it provides guidance for model selection.

Usage::

    from narrare_core.llm.intent_profiles import get_intent_profile

    profile = get_intent_profile(LLMIntent.WRITE)
    # profile.capability_tier == "creative"
    # profile.output_profile == "long_texts"

See Also
--------
:mod:`narrare_core.llm.intent_categories`
    Category grouping and default token-limit profiles (authoritative for
    routing).
:mod:`narrare_core.llm.model_config`
    ``PROFILE_OUTPUT_LIMITS`` — concrete token counts per profile name.
"""

from __future__ import annotations

from dataclasses import dataclass

from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.token_profiles import TOKEN_PRESET_PROFILE_VALUES

# ------------------------------------------------------------------
# Valid value sets — used by tests to validate the mapping table.
# ------------------------------------------------------------------

VALID_OUTPUT_PROFILES: frozenset[str] = frozenset(TOKEN_PRESET_PROFILE_VALUES)
"""Output profile names recognised by the token-limit system."""

VALID_CAPABILITY_TIERS: frozenset[str] = frozenset({"fast", "balanced", "creative", "reasoning"})
"""Model capability tiers for intent→model suitability."""


@dataclass(frozen=True, slots=True)
class IntentProfile:
    """Recommended model profile for an LLM intent.

    Attributes
    ----------
    output_profile:
        Expected output size hint (``"quick"``, ``"balanced"``,
        ``"long_texts"``, ``"comprehensive"``).  Mirrors the profiles
        in :data:`~narrare_core.llm.intent_categories._INTENT_PROFILE_DEFAULTS`.
    capability_tier:
        Recommended model capability (``"fast"``, ``"balanced"``,
        ``"creative"``, ``"reasoning"``).  Guides the resolver toward
        models suited for the intent's nature.
    description:
        Human-readable summary of the intent's purpose.
    """

    output_profile: str
    capability_tier: str
    description: str


# ------------------------------------------------------------------
# Mapping table — one entry per LLMIntent member.
# ------------------------------------------------------------------

INTENT_PROFILES: dict[LLMIntent, IntentProfile] = {
    # ------------------------------------------------------------------
    # Writing — creative models for prose generation
    # ------------------------------------------------------------------
    LLMIntent.WRITE: IntentProfile("long_texts", "creative", "Full chapter generation"),
    LLMIntent.EXTEND: IntentProfile("long_texts", "creative", "Seamless continuation"),
    LLMIntent.REWRITE: IntentProfile("balanced", "creative", "Multiple alternatives"),
    LLMIntent.CO_AUTHOR: IntentProfile("balanced", "creative", "Targeted improvement"),
    # ------------------------------------------------------------------
    # Analysis — reasoning-oriented models
    # ------------------------------------------------------------------
    LLMIntent.ANALYSE: IntentProfile("balanced", "reasoning", "Multi-dimension analysis"),
    LLMIntent.SENTIMENT: IntentProfile("quick", "fast", "Emotional tone analysis"),
    LLMIntent.CONSISTENCY: IntentProfile("comprehensive", "reasoning", "Cross-chapter consistency"),
    LLMIntent.BETA_READ: IntentProfile("long_texts", "reasoning", "Reader-perspective feedback"),
    LLMIntent.VOICE: IntentProfile("balanced", "reasoning", "Voice/style analysis"),
    # Phase 5 F4 (Weg A decision-pattern pilot): cheap-model rubric triage
    # of already-detected consistency issues. "fast" tier + "quick" output
    # (per-issue rubric assessments, no long prose).
    LLMIntent.CONSISTENCY_TRIAGE: IntentProfile(
        "quick", "fast", "Rubric-based consistency triage (cheap model)"
    ),
    # ADR-069 Decision 5: Dialogue Coach — analyze + improve modes over
    # selected dialogue. "reasoning" tier (qualitative judgment + voice
    # matching); "long_texts" profile (structured output + alternatives).
    LLMIntent.DIALOGUE_COACH: IntentProfile(
        "long_texts", "reasoning", "Dialogue analysis and improvement (ASSIST-004)"
    ),
    # ------------------------------------------------------------------
    # KB — balanced / reasoning for structured work
    # ------------------------------------------------------------------
    LLMIntent.KB_CREATE: IntentProfile("balanced", "balanced", "Interactive entity creation"),
    LLMIntent.KB_IMPROVE: IntentProfile("balanced", "reasoning", "Improvement analysis"),
    LLMIntent.KB_EXTRACT: IntentProfile("balanced", "reasoning", "Entity extraction"),
    LLMIntent.KB_INTERVIEW: IntentProfile("quick", "balanced", "Single focused question"),
    LLMIntent.KB_SUGGEST: IntentProfile("quick", "balanced", "Single-field suggestion"),
    LLMIntent.KB_ENHANCE: IntentProfile("balanced", "creative", "Bulk entity generation"),
    LLMIntent.KB_WORLDBUILD: IntentProfile("balanced", "reasoning", "Gap/connection analysis"),
    LLMIntent.KB_CONSISTENCY: IntentProfile("balanced", "reasoning", "Entry-internal consistency"),
    # ------------------------------------------------------------------
    # Planning — creative models for structure
    # ------------------------------------------------------------------
    LLMIntent.PLAN: IntentProfile("balanced", "creative", "Story structure planning"),
    LLMIntent.SUMMARIZE: IntentProfile("quick", "fast", "Chapter summarization"),
    # ------------------------------------------------------------------
    # Generation — fast / creative for short output
    # ------------------------------------------------------------------
    LLMIntent.GENERATE: IntentProfile("balanced", "balanced", "General generation"),
    LLMIntent.NAME_GENERATE: IntentProfile("quick", "creative", "Name generation"),
    LLMIntent.TITLE_GENERATE: IntentProfile("quick", "creative", "Title generation"),
    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------
    LLMIntent.EXTRACT: IntentProfile("balanced", "reasoning", "Structured extraction"),
    LLMIntent.FACT_EXTRACT: IntentProfile(
        "balanced", "reasoning", "Structured fact extraction with provenance"
    ),
    LLMIntent.SUGGEST: IntentProfile("quick", "fast", "Inline suggestions"),
    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------
    LLMIntent.CHAT: IntentProfile("balanced", "balanced", "Conversational assistant"),
    LLMIntent.RESEARCH: IntentProfile("balanced", "reasoning", "Web research synthesis"),
    # ------------------------------------------------------------------
    # Embeddings (not routed through model cascade)
    # ------------------------------------------------------------------
    LLMIntent.EMBED: IntentProfile("quick", "fast", "Text embedding (not routed)"),
}
"""Advisory mapping from :class:`LLMIntent` to recommended model profile.

This table is **not** consumed by the routing resolver directly. It
provides guidance for:

* UI: show users which model capability is recommended per intent
* Resolver: an optional hint layer when no user preference exists
* Documentation: developer reference for intent suitability
"""


def get_intent_profile(intent: LLMIntent) -> IntentProfile:
    """Return the recommended profile for *intent*.

    Falls back to ``balanced/balanced`` for intents not present in the
    mapping table (defensive — should not happen if the table is
    complete).

    Parameters
    ----------
    intent:
        The :class:`LLMIntent` to look up.

    Returns
    -------
    IntentProfile
        The recommended output profile, capability tier, and description.
    """
    return INTENT_PROFILES.get(
        intent,
        IntentProfile("balanced", "balanced", "Unknown intent"),
    )
