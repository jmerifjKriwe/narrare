"""Opt-in per-step dynamic model tier selection (ADR-089 pilot).

This module owns the *product policy* of the dynamic tier routing pilot:
*when* to escalate (``TieringPolicy`` / :func:`should_escalate`) and
*how* the two pre-built models are exposed per request step
(:func:`build_tiered_model`, wired through the upstream
``pydantic_ai.capabilities.SelectModel`` capability).

Boundary (ADR-089 Decision 1): both ``Model`` instances are built by the
caller through ``ModelRegistry.get_model`` (RULE-01b — the gateway stays
the only model factory) and handed in fully constructed. The selection
callback closes over those two instances and the policy — nothing else;
it never touches factories, environment variables, or the database
(credential safety, ADR-071/ADR-001).

The escalation policy v1 is deterministic: latest-user-prompt length or
conversation turn count. No LLM in the routing path (RULE-20).

See: docs/architecture/decisions/ADR-089-dynamic-tier-routing-selectmodel.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog
from pydantic_ai.capabilities import SelectModel
from pydantic_ai.messages import ModelRequest, TextContent, UserPromptPart

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pydantic_ai.messages import ModelMessage, UserContent
    from pydantic_ai.models import Model, ModelSelectionContext

logger = structlog.get_logger(__name__)

__all__ = [
    "TieringPolicy",
    "build_tiered_model",
    "latest_user_prompt",
    "should_escalate",
    "turn_count",
]


@dataclass(frozen=True, slots=True)
class TieringPolicy:
    """Deterministic escalation thresholds (ADR-089 Decision 3).

    Attributes:
        max_prompt_chars: Escalate when the latest user prompt is strictly
            longer than this (operator knob
            ``NARRARE_LLM_DYNAMIC_TIERING_MAX_PROMPT_CHARS``).
        min_turns: Escalate when the conversation has at least this many
            user turns (operator knob
            ``NARRARE_LLM_DYNAMIC_TIERING_MIN_TURNS``).
    """

    max_prompt_chars: int = 2000
    min_turns: int = 6


def should_escalate(
    *,
    latest_user_prompt: str | None,
    turn_count: int,
    policy: TieringPolicy,
) -> bool:
    """Return True when the request should run on the escalation tier.

    Pure function (ADR-089 Decision 1): no I/O, no logging — callers log.
    A ``None`` prompt disables the length trigger; only ``turn_count``
    can escalate then (Decision 3 clarification).
    """
    return _escalation_reason(latest_user_prompt, turn_count, policy) is not None


def _escalation_reason(
    latest_user_prompt: str | None,
    turn_count: int,
    policy: TieringPolicy,
) -> str | None:
    """Return the first matching trigger's name, or ``None``.

    Single source of truth for the escalation decision, shared by
    :func:`should_escalate` (pure boolean) and the selector's
    observability event (``reason`` field).
    """
    if latest_user_prompt is not None and len(latest_user_prompt) > policy.max_prompt_chars:
        return "prompt_chars"
    if turn_count >= policy.min_turns:
        return "min_turns"
    return None


def _text_fragments(content: str | Sequence[UserContent]) -> list[str]:
    """Extract text items from user content; non-text content contributes 0.

    Text-bearing items are plain strings and ``TextContent`` parts;
    multi-modal items (image/audio/video/document/binary) and cache
    points contribute nothing (ADR-089 Decision 3).
    """
    if isinstance(content, str):
        return [content]
    fragments: list[str] = []
    for item in content:
        if isinstance(item, str):
            fragments.append(item)
        elif isinstance(item, TextContent):
            fragments.append(item.content)
    return fragments


def latest_user_prompt(
    prompt: str | Sequence[UserContent] | None,
    messages: Sequence[ModelMessage],
) -> str:
    """Derive the effective latest user prompt (ADR-089 Decision 3).

    ``ModelSelectionContext.prompt`` semantics: a ``str`` prompt is used
    as-is; a ``Sequence[UserContent]`` prompt contributes its text items
    joined with a single space; ``None`` (history-only resume) falls back
    to the text parts of the last ``ModelRequest`` in ``messages``,
    joined the same way. When no prompt text exists at all the result is
    ``""`` — the length trigger is false (only ``turn_count`` escalates).
    """
    if isinstance(prompt, str):
        return prompt
    if prompt is not None:
        return " ".join(_text_fragments(prompt))
    for message in reversed(messages):
        if isinstance(message, ModelRequest):
            fragments: list[str] = []
            for part in message.parts:
                if isinstance(part, UserPromptPart):
                    fragments.extend(_text_fragments(part.content))
            return " ".join(fragments)
    return ""


def turn_count(messages: Sequence[ModelMessage]) -> int:
    """Count user turns: the ``ModelRequest`` entries in the history.

    In the tool-free chat path this equals the number of user turns
    including the one being routed (ADR-089 Decision 3).
    """
    return sum(1 for message in messages if isinstance(message, ModelRequest))


def build_tiered_model(
    base_model: Model,
    escalation_model: Model | None,
    *,
    policy: TieringPolicy,
) -> SelectModel[Any]:
    """Build the tiered-model ``SelectModel`` capability (ADR-089 Decision 1).

    The selector closes over the two eagerly-constructed ``Model``
    instances (built by the caller via ``ModelRegistry.get_model``) and
    the policy — nothing else. It picks ``escalation_model`` iff
    :func:`should_escalate` holds for the step's context, else
    ``base_model``. ``escalation_model=None`` (degraded mode, Decision 5)
    short-circuits to ``base_model`` so the call site stays branch-free.

    Observability (ADR-089 Decision 7): one structured
    ``dynamic_tier_escalation`` event per escalated turn (``reason``,
    ``prompt_chars``, ``turn_count``, both thresholds, base/escalation
    model ids); no message content is logged. Provider attribution is
    left to the wiring layer, which holds the ``ResolvedModelConfig``s —
    the ``Model`` ABC carries only ``model_name``.
    """

    def _select(context: ModelSelectionContext[Any]) -> Model:
        if escalation_model is None:
            return base_model
        prompt = latest_user_prompt(context.prompt, context.messages)
        turns = turn_count(context.messages)
        reason = _escalation_reason(prompt, turns, policy)
        if reason is None:
            return base_model
        logger.info(
            "dynamic_tier_escalation",
            reason=reason,
            prompt_chars=len(prompt),
            turn_count=turns,
            max_prompt_chars=policy.max_prompt_chars,
            min_turns=policy.min_turns,
            base_model_id=base_model.model_name,
            escalation_model_id=escalation_model.model_name,
        )
        return escalation_model

    return SelectModel(_select)
