"""PromptComposer route governance.

This module is the single routeability contract for mapping ``LLMIntent`` values
to bundled prompt template targets. Routeable defaults must resolve to a bundled
EN prompt. Aggregate/default-less intents are explicit context-mode routes, and
model-routing-only intents are explicitly non-routeable (INFRA-012).
"""

from __future__ import annotations

from dataclasses import dataclass

from narrare_core.llm.intents import LLMIntent
from narrare_core.shared.errors import PromptRouteNotConfiguredError


@dataclass(frozen=True, slots=True)
class PromptRoute:
    """Resolved PromptComposer route."""

    category: str
    mode: str


_INTENT_TO_CATEGORY: dict[LLMIntent, str] = {
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
    LLMIntent.SUGGEST: "writing",
    LLMIntent.CHAT: "chat",
}

_INTENT_TO_MODE: dict[LLMIntent, str] = {
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
    LLMIntent.SUGGEST: "inline_suggest",
    LLMIntent.CHAT: "",
}

_CONTEXT_MODE_REQUIRED_INTENTS: dict[LLMIntent, str] = {
    LLMIntent.KB_CREATE: (
        "KB creation is an aggregate assisted flow; callers must choose an "
        "existing KB mode such as interview, suggest, or enhance."
    ),
    LLMIntent.EXTRACT: (
        "General extraction has no canonical bundled template; production "
        "callers must provide a governed feature mode such as preferences."
    ),
}

_NON_ROUTEABLE_INTENTS: dict[LLMIntent, str] = {
    LLMIntent.SENTIMENT: ("Sentiment analysis is handled by deterministic NLP analyzers."),
    LLMIntent.VOICE: ("Voice analysis has no dedicated bundled PromptComposer template yet."),
    LLMIntent.GENERATE: ("Generic generation must use a specific routed intent or feature mode."),
    LLMIntent.TITLE_GENERATE: "No title-generation feature prompt is bundled yet.",
    LLMIntent.RESEARCH: "Research synthesis has no bundled PromptComposer route yet.",
}


def resolve_prompt_route(intent: LLMIntent, context_mode: str = "") -> PromptRoute:
    """Resolve a governed PromptComposer route for an intent."""
    if intent in _NON_ROUTEABLE_INTENTS:
        raise PromptRouteNotConfiguredError(intent.value, _NON_ROUTEABLE_INTENTS[intent])

    category = _INTENT_TO_CATEGORY.get(intent)
    if category is None:
        raise PromptRouteNotConfiguredError(
            intent.value,
            "No PromptComposer category mapping is registered.",
        )

    if context_mode:
        return PromptRoute(category=category, mode=context_mode)

    if intent in _CONTEXT_MODE_REQUIRED_INTENTS:
        raise PromptRouteNotConfiguredError(
            intent.value,
            _CONTEXT_MODE_REQUIRED_INTENTS[intent],
        )

    mode = _INTENT_TO_MODE.get(intent)
    if mode is None:
        raise PromptRouteNotConfiguredError(
            intent.value,
            "No PromptComposer mode mapping is registered.",
        )
    return PromptRoute(category=category, mode=mode)
