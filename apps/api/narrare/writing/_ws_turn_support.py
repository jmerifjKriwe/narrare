"""WS turn runtime composition — lazy model resolution support (ADR-086 L39).

Owns the deferred runtime composition for WebSocket writing sessions: the
frozen handshake config (``temperature=0.7``, ``max_tokens=limits.output_limit``
— the eager ``resolve_ws_session_config`` freeze, reproduced exactly once at
first use), the ADR-082 context budgets, and the KB assembler construction.
Extracted from ``ws_factory``/``ws_turn_service`` for the RULE-04 size limits
the lazy seam crossed (family precedent: ``_writing_support``,
``_timeline_analysis_support``).

Timing contract (ADR-086): the WRITE-intent routing cascade is wired lazily
at the handshake and resolves at FIRST USE — the first turn or the first
interview draft. The token-limits cascade stays at WS bootstrap (accepted
residual: ``ws_timeout`` feeds the handler idle timeout before the message
loop starts); its outputs are captured by the closures below. Both closures
share one ``ModelResolution``, so the routing cascade runs at most once per
connection.

The prompt/invocation-context builders here are pure functions extracted
verbatim from ``WritingTurnService`` static helpers (RULE-06: the service
orchestrates; the support module assembles).
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from uuid import UUID

    from narrare._app.dependencies_services import ModelResolution
    from narrare.settings.token_limits.contracts import TokenLimitOverrides
    from narrare_core.ai_invocation.models import PromptInvocationContext
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.prompts.context import PromptContext
    from narrare_core.writing.context_assembler import WritingContextAssembler
    from narrare_core.writing.models import WritingContext


class WritingTurnRuntime:
    """Composed per-connection turn runtime (frozen config + assembler).

    Produced once per connection by :func:`build_turn_runtime_factory` and
    cached by ``WritingTurnService.ensure_resolved``.

    Attributes:
        config: The frozen handshake model configuration.
        context_assembler: The KB assembler for turns (``None`` when no
            handshake limits were wired — Core-default degradation).
    """

    def __init__(
        self,
        config: ResolvedModelConfig,
        context_assembler: WritingContextAssembler | None,
    ) -> None:
        self.config = config
        self.context_assembler = context_assembler


def freeze_handshake_config(
    resolved_config: ResolvedModelConfig,
    limits: TokenLimitOverrides | None,
) -> ResolvedModelConfig:
    """Freeze the eager handshake's effective config (timing-only move).

    The eager ``resolve_ws_session_config`` applied ``temperature=0.7`` and
    ``max_tokens=limits.output_limit`` on top of the routed config; with no
    handshake limits (tests / legacy call sites) only the temperature is
    applied.
    """
    if limits is None:
        return replace(resolved_config, temperature=0.7)
    return replace(resolved_config, temperature=0.7, max_tokens=limits.output_limit)


def build_config_provider(
    model_resolution: ModelResolution,
    limits: TokenLimitOverrides | None,
) -> Callable[[], Awaitable[ResolvedModelConfig]]:
    """Build the frozen-config provider shared by the WS consumers.

    Awaits the (cached) routing resolution and freezes the handshake
    config. Deterministic in the resolved model, so turn service and
    interview-draft path observe identical configs.
    """

    async def config_provider() -> ResolvedModelConfig:
        resolved = await model_resolution.resolve()
        return freeze_handshake_config(resolved.config, limits)

    return config_provider


def build_turn_runtime_factory(
    model_resolution: ModelResolution,
    limits: TokenLimitOverrides | None,
) -> Callable[[], Awaitable[WritingTurnRuntime]]:
    """Build the turn-runtime composition consumed by ``ensure_resolved``.

    Composes, at first use: the frozen config, the ADR-082 budgets
    (``resolve_context_budgets`` over the handshake limits and the frozen
    config's model window — WS never injects ``{{series_history}}`` →
    standalone tier-base semantics, ADR-082 Decision 6, mirroring
    ``deps_extend``), and the data-fetching assembler with the FIND-012
    tier overrides and the model-capped ``writing_tier_base``. With
    ``limits=None`` budgets are skipped and the assembler falls back to
    Core defaults (RULE-11) — the pre-item-E wiring.
    """

    async def compose_runtime() -> WritingTurnRuntime:
        from narrare.settings.token_limits.context_budgets import resolve_context_budgets
        from narrare.writing.ws_context_assembler import WsWritingContextAssembler

        config_provider = build_config_provider(model_resolution, limits)
        config = await config_provider()
        if limits is None:
            # Pre-item-E wiring preserved: bare fetching assembler with
            # Core-default budgets (RULE-11) — never KB-blind.
            return WritingTurnRuntime(
                config=config,
                context_assembler=WsWritingContextAssembler(),
            )
        budgets = resolve_context_budgets(
            limits=limits,
            config=config,
            series_in_scope=False,
        )
        assembler = WsWritingContextAssembler(
            tier_overrides=limits.tier_percentages,
            total_budget=budgets.writing_tier_base,
        )
        return WritingTurnRuntime(config=config, context_assembler=assembler)

    return compose_runtime


# ---------------------------------------------------------------------------
# Prompt / invocation context builders (extracted from WritingTurnService)
# ---------------------------------------------------------------------------


def resolve_turn_intent(session_mode: str) -> LLMIntent:
    """Map session mode to LLM intent."""
    if session_mode == "interview_assisted":
        return LLMIntent.CHAT
    return LLMIntent.WRITE


def resolve_prompt_mode(session_mode: str) -> str:
    """Map session mode to prompt mode."""
    if session_mode == "interview_assisted":
        return "interview"
    return "interactive_session"


def build_prompt_context(
    content: str,
    prompt_mode: str,
    writing_context: WritingContext | None,
) -> PromptContext:
    """Build the PromptContext from the user's direction + KB context.

    The direction becomes ``author_instructions`` (RULE-02a). The
    composition contract (build_and_validate_prompt) requires the caller
    to carry assembled KB context into the PromptContext: supplies the
    ``kb_context_extras`` SSOT spread, ``chapter_outline`` /
    ``timeline_position`` / ``recent_chapters`` (empty when KB-blind), and
    ``word_target_line`` for interactive_session only (slice-3:
    label-in-value).
    """
    from narrare_core.prompts.context import PromptContext
    from narrare_core.writing._helpers import kb_context_extras, word_target_line
    from narrare_core.writing.models import WritingContext

    kb_source = writing_context if writing_context is not None else WritingContext()
    extra: dict[str, str] = kb_context_extras(kb_source)
    extra["chapter_outline"] = kb_source.chapter_outline
    extra["timeline_position"] = kb_source.timeline_position
    extra["recent_chapters"] = kb_source.recent_chapters
    if prompt_mode == "interactive_session":
        extra["word_target_line"] = word_target_line(kb_source.word_target, label="Word target: ")
    return PromptContext(
        language="en",
        mode=prompt_mode,
        author_instructions=content,
        extra=extra,
    )


def build_invocation_context(
    *,
    intent: LLMIntent,
    prompt_ctx: PromptContext,
    session_mode: str,
    user_id: UUID,
    project_id: UUID,
    chapter_id: UUID,
    session_id: UUID,
    invocation_id: UUID,
) -> PromptInvocationContext:
    """Build the PromptInvocationContext with all identifiers.

    ADR-045 Decision 6: user and project IDs are mandatory in the
    invocation context. Chapter and session IDs are carried as dynamic
    inputs so enrichers and evidence can correlate them.
    """
    from narrare_core.ai_invocation.models import PromptInvocationContext

    return PromptInvocationContext(
        feature_id=f"writing_{intent.value}",
        intent=intent,
        mode=session_mode,
        invocation_id=invocation_id,
        user_id=user_id,
        project_id=project_id,
        language=prompt_ctx.language,
        streaming=True,
        dynamic_inputs={
            "chapter_id": str(chapter_id),
            "session_id": str(session_id),
        },
        prompt_context=prompt_ctx,
    )
