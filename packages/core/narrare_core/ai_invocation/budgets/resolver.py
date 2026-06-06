"""Production IntentOutputBudgetResolver implementation.

Bridges the existing intent→category→profile→tokens SSOT chain into a typed
:class:`~narrare_core.ai_invocation.budgets.OutputBudgetDecision` with
provenance metadata.

This resolver is the ONLY consumer of the profile lookup chain for budget
decisions. It does NOT define profiles or limits — it reads from:

- :func:`~narrare_core.llm.intent_categories.get_default_profile_for_intent`
- :meth:`~narrare_core.llm.model_config.ResolvedModelConfig.resolve_output_limit`

The resolver is stateless and safe to call concurrently.

See:
    ADR-038, INFRA-013, CONSTRAINTS.md RULE-03/RULE-06/RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.ai_invocation.budgets._types import OutputBudget, OutputBudgetDecision
from narrare_core.llm.intent_categories import get_default_profile_for_intent
from narrare_core.llm.model_config import ResolvedModelConfig

if TYPE_CHECKING:
    from narrare_core.ai_invocation.models import PromptInvocationContext

logger = structlog.get_logger(__name__)

#: Default source tag when a profile is found via intent mapping.
_SOURCE_INTENT_PROFILE: str = "intent_profile"

#: Default source tag when no profile mapping exists and the fallback is used.
_SOURCE_DEFAULT_CONFIG: str = "default_config"


class IntentOutputBudgetResolverImpl:
    """Resolves output-token budgets by bridging intent → profile → limit.

    Implements the :class:`~narrare_core.ai_invocation.contracts.IntentOutputBudgetResolver`
    Protocol. For each invocation, it:

    1. Reads ``context.intent`` (required, :class:`~narrare_core.llm.intents.LLMIntent`).
    2. Calls :func:`~narrare_core.llm.intent_categories.get_default_profile_for_intent`
       to get the profile name.
    3. If a profile is found, resolves the token limit through
       :meth:`~narrare_core.llm.model_config.ResolvedModelConfig.resolve_output_limit`.
    4. If no profile exists, falls back to ``default_max_tokens``.

    **Never raises** — always returns a valid
    :class:`~narrare_core.ai_invocation.budgets.OutputBudgetDecision`.

    Args:
        default_max_tokens: Fallback token limit when no intent-specific
            profile is found. Defaults to 4096.

    Implements:
        IntentOutputBudgetResolver Protocol.
    """

    def __init__(self, *, default_max_tokens: int = 4096) -> None:
        if default_max_tokens <= 0:
            raise ValueError(f"default_max_tokens must be positive, got {default_max_tokens}")
        self._default_max_tokens = default_max_tokens

    async def resolve(self, context: PromptInvocationContext) -> OutputBudgetDecision:
        """Resolve the output budget for the given invocation context.

        Args:
            context: The invocation context carrying the intent and
                optional mode.

        Returns:
            An :class:`OutputBudgetDecision` with the resolved budget
            and provenance metadata. Never raises.
        """
        intent = context.intent
        mode = context.mode

        profile_name = get_default_profile_for_intent(intent)

        if profile_name is not None:
            token_limit = ResolvedModelConfig(
                provider_name="invocation-budget-resolver",
                model_id="invocation-budget-resolver",
                max_tokens=self._default_max_tokens,
                token_limit_profile=profile_name,
            ).resolve_output_limit()
            reason_parts = [
                f"Intent {intent.value!r} mapped to profile {profile_name!r}",
                f"(limit={token_limit})",
            ]
            if mode is not None:
                reason_parts.append(f"mode={mode!r}")
            reason = ", ".join(reason_parts)

            logger.debug(
                "budget_resolved_from_profile",
                intent=intent.value,
                profile=profile_name,
                max_tokens=token_limit,
                mode=mode,
                feature_id=context.feature_id,
            )

            return OutputBudgetDecision(
                budget=OutputBudget(max_tokens=token_limit, profile=profile_name),
                source=_SOURCE_INTENT_PROFILE,
                reason=reason,
            )

        # No profile mapping — use the constructor-configured default.
        reason_parts = [
            (
                f"No profile for intent {intent.value!r}; "
                f"using default max_tokens={self._default_max_tokens}"
            ),
        ]
        if mode is not None:
            reason_parts.append(f"mode={mode!r}")
        reason = ", ".join(reason_parts)

        logger.debug(
            "budget_resolved_from_default",
            intent=intent.value,
            max_tokens=self._default_max_tokens,
            mode=mode,
            feature_id=context.feature_id,
        )

        return OutputBudgetDecision(
            budget=OutputBudget(max_tokens=self._default_max_tokens, profile=None),
            source=_SOURCE_DEFAULT_CONFIG,
            reason=reason,
        )
