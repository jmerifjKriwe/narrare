"""Mode-1 prompt resolution helper for dialogue_coach (ADR-054).

Extracted from ``service.py`` for RULE-04 compliance. Owns the single
responsibility of resolving the governed ``dialogue_coach`` system prompt
via :func:`compose_invocation` Mode 1 (``LLMIntent.DIALOGUE_COACH`` +
``context_mode="dialogue_coach"``).

Returns both the composed prompt AND the ``invocation_id`` threaded from
:func:`compose_invocation`'s result, so the caller (the service) can
correlate the adaptive evidence snapshot with the prompt fingerprint
(ADR-069 Decision 11). The previous placeholder approach (best-effort
``getattr(chapter, "id", chapter_id)``) is replaced by the real
pipeline-minted id.

See:
    ADR-069 Decision 5 (new intent + new category),
    ADR-069 Decision 11 (adaptive evidence correlation),
    ADR-054 (Mode 1 composer-driven resolution),
    RULE-04 (Modularise, never compress).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.shared.errors import ConfigurationError

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.prompts.composer import ComposedPrompt, PromptComposer


async def resolve_dialogue_coach_prompt(
    composer: PromptComposer,
    invocation_pipeline: InvocationPipeline | None,
    *,
    project_id: UUID,
    user_id: UUID,
    language: str,
    project_title: str,
    genre: str,
    selection_text: str,
    mode: str,
    characters: list[str],
    adaptive_extra: dict[str, str],
) -> tuple[ComposedPrompt, UUID | None]:
    """Resolve the governed dialogue_coach system prompt (Mode 1).

    Builds a :class:`PromptContext` with ``mode="dialogue_coach"`` and
    the project + runtime metadata, then composes the governed system
    prompt via :func:`compose_invocation` Mode 1.

    Args:
        composer: PromptComposer for the cascade.
        invocation_pipeline: Optional pipeline for evidence.
        project_id: The project id.
        user_id: The requesting user id.
        language: Writing language code.
        project_title: Novel title.
        genre: Novel genre.
        selection_text: The dialogue selection (category-3 runtime data).
        mode: "analyze" or "improve".
        characters: Canonical speaker roster.
        adaptive_extra: Adaptive variable values (populated by
            AdaptiveContextEnricher when the pipeline runs).

    Returns:
        A tuple ``(composed_prompt, invocation_id)``. The
        ``invocation_id`` comes from
        :attr:`ComposedInvocation.prepared.context.invocation_id` — the
        pipeline mints one in ``prepare()`` when the caller did not supply
        one, so the adaptive evidence row correlates with the prompt
        fingerprint. ``None`` only on the backward-compatible fallback
        path (``invocation_pipeline=None``) where ``prepare()`` is
        skipped; the service then falls back to ``chapter_id``.
    """
    from narrare._app.invocation_context import build_invocation_context
    from narrare_core.ai_invocation import compose_invocation
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.prompts.context import PromptContext

    ctx = PromptContext(
        language=language,
        writing_language=language,
        project_title=project_title,
        genre=genre or "",
        mode="dialogue_coach",
        extra={
            "mode": mode,
            "characters": ", ".join(characters),
            # text_to_analyze is USER_CONTENT_VARS — XML-wrapped by the
            # template (RULE-22 §6). Supplied here as runtime content.
            "text_to_analyze": selection_text,
            **adaptive_extra,
        },
    )

    invocation_context = build_invocation_context(
        feature_id="ai_assist_dialogue_coach",
        intent=LLMIntent.DIALOGUE_COACH,
        project_id=project_id,
        user_id=user_id,
        language=language,
    )
    invocation = await compose_invocation(
        invocation_pipeline=invocation_pipeline,
        invocation_context=invocation_context,
        composer=composer,
        prompt_context=ctx,
        intent=LLMIntent.DIALOGUE_COACH,
    )
    composed_prompt = invocation.composed_prompt
    if composed_prompt is None:  # pragma: no cover - Mode 1 invariant
        raise ConfigurationError(
            "Prompt composition produced no system prompt for dialogue_coach.",
            code="COMPOSITION_EMPTY",
        )
    # invocation_id: prepared.context always exists (the no-pipeline
    # fallback constructs a noop PreparedInvocation with the caller's
    # context). With a real pipeline, prepare() mints one if absent
    # (see _evidence.py: invocation_id = context.invocation_id or uuid4()).
    invocation_id = invocation.prepared.context.invocation_id
    return composed_prompt, invocation_id
