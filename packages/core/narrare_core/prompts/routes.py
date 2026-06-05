"""PromptComposer route governance.

This module is the single routeability contract for mapping ``LLMIntent`` values
to bundled prompt template targets. Routeable defaults must resolve to a bundled
EN prompt. Aggregate/default-less intents are explicit context-mode routes, and
model-routing-only intents are explicitly non-routeable (INFRA-012).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.prompts.route_table import (
    CONTEXT_MODE_REQUIRED_INTENTS,
    INTENT_TO_CATEGORY,
    INTENT_TO_MODE,
    NON_ROUTEABLE_INTENTS,
    ROUTE_CONFIGS,
)

if TYPE_CHECKING:
    from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.route_types import PromptRoute, PromptRouteConfig
from narrare_core.shared.errors import PromptRouteNotConfiguredError

__all__ = [
    "_CONTEXT_MODE_REQUIRED_INTENTS",
    "_INTENT_TO_CATEGORY",
    "_INTENT_TO_MODE",
    "_NON_ROUTEABLE_INTENTS",
    "PromptRoute",
    "PromptRouteConfig",
    "resolve_prompt_route",
]

_CONTEXT_MODE_REQUIRED_INTENTS = CONTEXT_MODE_REQUIRED_INTENTS
_INTENT_TO_CATEGORY = INTENT_TO_CATEGORY
_INTENT_TO_MODE = INTENT_TO_MODE
_NON_ROUTEABLE_INTENTS = NON_ROUTEABLE_INTENTS


def resolve_prompt_route(intent: LLMIntent, context_mode: str = "") -> PromptRoute:
    """Resolve a governed PromptComposer route for an intent."""
    if intent in NON_ROUTEABLE_INTENTS:
        raise PromptRouteNotConfiguredError(intent.value, NON_ROUTEABLE_INTENTS[intent])

    config = ROUTE_CONFIGS.get(intent)
    if config is None:
        raise PromptRouteNotConfiguredError(
            intent.value,
            "No PromptComposer category mapping is registered.",
        )

    if context_mode:
        return _resolve_context_mode_route(intent, config, context_mode)

    if intent in CONTEXT_MODE_REQUIRED_INTENTS:
        raise PromptRouteNotConfiguredError(
            intent.value,
            CONTEXT_MODE_REQUIRED_INTENTS[intent],
        )

    if config.default_mode is None:
        raise PromptRouteNotConfiguredError(
            intent.value,
            "No PromptComposer mode mapping is registered.",
        )
    return PromptRoute(
        category=config.category,
        mode=config.default_mode,
        required_variables=config.required_variables,
        optional_variables=config.optional_variables,
    )


def _resolve_context_mode_route(
    intent: LLMIntent,
    config: PromptRouteConfig,
    context_mode: str,
) -> PromptRoute:
    """Resolve an explicitly allowed context-mode route."""
    allowed = config.allowed_context_modes
    if allowed and context_mode not in allowed:
        raise PromptRouteNotConfiguredError(
            intent.value,
            f"Context mode '{context_mode}' is not a governed route for this intent.",
        )

    return PromptRoute(
        category=config.category,
        mode=context_mode,
        required_variables=config.required_variables,
        optional_variables=config.optional_variables,
    )
