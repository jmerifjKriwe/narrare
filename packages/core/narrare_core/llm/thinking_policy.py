"""Intent-aware thinking policy — universal, provider-agnostic.

Maps every :class:`~narrare_core.llm.intent_categories.IntentCategory` to a
pydantic-ai ``ThinkingLevel`` (or ``None`` to omit the setting entirely).
:func:`build_runtime_model_settings
<narrare_core.llm._model_settings.build_runtime_model_settings>` consults
the table via :func:`resolve_thinking_level`.

Root cause this fixes: thinking effort is a property of the **task**, not
the provider. The former ``provider_name == "zai"`` branch in
``_model_settings.py`` was a provider patch; the declarative table below
expresses the same latency/quality trade-off universally per intent
category (GLM extraction stalls: ~50k reasoning tokens / ~7 min with
default thinking vs ~22s with ``"low"`` — verified via direct API probe).

Providers that cannot think are handled downstream: pydantic-ai resolves
``ModelSettings['thinking']`` only when the model profile declares
``supports_thinking`` (or ``thinking_always_enabled``) and silently drops
it otherwise — so the policy is safe to apply for every provider.

See Also
--------
:mod:`narrare_core.llm.intent_categories`
    ``INTENT_CATEGORY_MAP`` — intent → category (authoritative grouping).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from narrare_core.llm.intent_categories import INTENT_CATEGORY_MAP, IntentCategory

if TYPE_CHECKING:
    from pydantic_ai.settings import ThinkingLevel

    from narrare_core.llm.intents import LLMIntent

INTENT_CATEGORY_THINKING_LEVELS: Final[dict[str, ThinkingLevel | None]] = {
    # ------------------------------------------------------------------
    # Structured extraction — schemas steer the output; deep reasoning
    # only adds latency. Cap at "low".
    # ------------------------------------------------------------------
    IntentCategory.EXTRACTION.value: "low",
    IntentCategory.KB.value: "low",
    # ------------------------------------------------------------------
    # Judgment work — some thinking measurably improves quality.
    # ------------------------------------------------------------------
    IntentCategory.ANALYSIS.value: "medium",
    IntentCategory.RESEARCH.value: "medium",
    IntentCategory.PLANNING.value: "medium",
    # ADR-069 Decision 5: ASSIST features analyse + improve selected text
    # ("reasoning" tier) — qualitative judgment benefits from thinking.
    IntentCategory.AI_ASSIST.value: "medium",
    # ------------------------------------------------------------------
    # Creative generation / conversation — omit the key: the model (or
    # user-side settings) decides; a forced level degrades prose.
    # ------------------------------------------------------------------
    IntentCategory.WRITING.value: None,
    IntentCategory.GENERATION.value: None,
    IntentCategory.CHAT.value: None,
}
"""Declarative ``IntentCategory.value`` → ``ThinkingLevel`` table.

``None`` means "omit the ``thinking`` key" — the model/provider default
applies. The table must cover **every** ``IntentCategory`` member (guarded
by ``TestTableCompleteness``); direct indexing in
:func:`resolve_thinking_level` makes drift fail loudly instead of
silently disabling the policy.
"""


def resolve_thinking_level(intent: LLMIntent) -> ThinkingLevel | None:
    """Return the thinking level for *intent*, or ``None`` to omit.

    Parameters
    ----------
    intent:
        The :class:`~narrare_core.llm.intents.LLMIntent` of the call.

    Returns
    -------
    ThinkingLevel | None
        The category's thinking level, or ``None`` when the intent has no
        category (e.g. ``LLMIntent.EMBED``, which is not routed through
        the model cascade) or its category omits thinking.
    """
    category = INTENT_CATEGORY_MAP.get(intent)
    if category is None:
        return None
    return INTENT_CATEGORY_THINKING_LEVELS[category.value]
