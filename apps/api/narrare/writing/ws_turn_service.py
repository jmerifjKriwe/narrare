"""WebSocket writing turn service — invocation-contract turn orchestration.

Owns one interactive writing turn: building the invocation context with
user/project/chapter/session identifiers, running the invocation pipeline
(prepare → merge → compose → finalize), resolving run limits, and
streaming with enforced budgets.

Transport-agnostic — yields :class:`~narrare_core.llm.result.StreamChunk`
instances so any transport adapter (WebSocket, SSE, MCP) can consume the
same service (RULE-12/RULE-13).

ADR-045 Decision 6: WebSocket writing sessions are writing invocations
and must use the same runtime adoption contract as other writing modes.

ADR-086 (L39): the model config resolves at FIRST USE — the constructor
wires a ``runtime_factory`` (the deferred composition from
``_ws_turn_support``) and :meth:`ensure_resolved` composes the runtime
idempotently at the top of :meth:`stream_turn`; an unconfigured provider
surfaces as a loud in-band error frame at turn time instead of an
abnormal handshake close (RULE-11). Prompt/invocation-context assembly
lives in ``_ws_turn_support`` (RULE-04 size limit the lazy seam crossed).

See: ADR-045, CONSTRAINTS.md RULE-02/RULE-03/RULE-06/RULE-12/RULE-13.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

from narrare.writing._ws_turn_support import (
    build_invocation_context,
    build_prompt_context,
    resolve_prompt_mode,
    resolve_turn_intent,
)
from narrare_core.writing._invocation_adapter import build_and_validate_prompt

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable
    from uuid import UUID

    from narrare.writing._ws_turn_support import WritingTurnRuntime
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.result import StreamChunk
    from narrare_core.llm.run_limits import DefaultRunLimitResolver
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.writing.context_assembler import WritingContextAssembler
    from narrare_core.writing.models import WritingContext

logger = structlog.get_logger(__name__)


class WritingTurnService:
    """Orchestrates a single WebSocket writing turn.

    Builds the invocation context, runs the writing invocation adapter
    (prepare/compose/finalize with evidence), resolves run limits for the
    same ``invocation_id``, and streams via :meth:`ModelRegistry.stream`.

    Dependencies are injected via constructor (DI pattern). This service
    has no FastAPI or WebSocket imports — it is transport-agnostic.

    Args:
        composer: PromptComposer for building prompts (RULE-02).
        invocation_pipeline: Optional InvocationPipeline for enrichment,
            validation, budget resolution, and evidence recording.
        registry: ModelRegistry for streaming LLM calls (RULE-01b).
        runtime_factory: Deferred runtime composition (ADR-086 L39) —
            resolves the model config, freezes the handshake overrides,
            and builds the KB assembler at first use.
        run_limit_resolver: Resolves output budgets into pydantic-ai
            runtime limits (ADR-045 Decision 4).
    """

    def __init__(
        self,
        composer: PromptComposer,
        invocation_pipeline: InvocationPipeline | None,
        registry: ModelRegistry,
        runtime_factory: Callable[[], Awaitable[WritingTurnRuntime]],
        run_limit_resolver: DefaultRunLimitResolver,
    ) -> None:
        self._composer = composer
        self._invocation_pipeline = invocation_pipeline
        self._registry = registry
        self._runtime_factory = runtime_factory
        self._run_limit_resolver = run_limit_resolver
        self._runtime: WritingTurnRuntime | None = None

    async def ensure_resolved(self) -> WritingTurnRuntime:
        """Compose and cache the turn runtime (idempotent, ADR-086 L39).

        The first call runs the deferred composition (routing cascade +
        config freeze + budgets + assembler); subsequent calls return the
        cached runtime. Composition errors propagate uncached — the next
        call retries (RULE-11 loud, never swallowed).
        """
        if self._runtime is None:
            self._runtime = await self._runtime_factory()
        return self._runtime

    async def stream_turn(
        self,
        *,
        content: str,
        session_mode: str,
        user_id: UUID,
        project_id: UUID,
        chapter_id: UUID,
        session_id: UUID,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream one writing turn as :class:`StreamChunk` instances.

        Runs the full invocation contract:
            1. Resolve the runtime at first use (ADR-086 L39 — the lazy
               model resolution happens here, before any other work).
            2. Build :class:`PromptContext` from the user's direction.
            3. Build :class:`PromptInvocationContext` with identifiers.
            4. ``build_and_validate_prompt`` — prepare → merge → compose
               → finalize (enrichment, budget, validation, evidence).
            5. Resolve run limits with the same ``invocation_id``.
            6. Stream via :meth:`ModelRegistry.stream` with enforced
               limits.

        Args:
            content: The user's direction/instruction text.
            session_mode: ``"interactive_session"`` or
                ``"interview_assisted"``.
            user_id: The authenticated user's identifier.
            project_id: The project identifier for enrichment.
            chapter_id: The chapter being written.
            session_id: The WebSocket session identifier.
            api_key: Optional provider API key override.
            base_url: Optional provider base URL override.

        Yields:
            :class:`StreamChunk` instances. The final chunk has
            ``is_final=True`` with populated ``usage``.

        Raises:
            WritingError: If pre-composition or final validation fails.
        """
        runtime = await self.ensure_resolved()
        intent = resolve_turn_intent(session_mode)
        prompt_mode = resolve_prompt_mode(session_mode)

        # KB assembly graceful-None — see _assemble_writing_context (RULE-11).
        writing_context = await self._assemble_writing_context(
            context_assembler=runtime.context_assembler,
            project_id=project_id,
            chapter_id=chapter_id,
            prompt_mode=prompt_mode,
        )
        prompt_ctx = build_prompt_context(content, prompt_mode, writing_context)
        invocation_id = uuid4()
        invocation_ctx = build_invocation_context(
            intent=intent,
            prompt_ctx=prompt_ctx,
            session_mode=prompt_mode,
            user_id=user_id,
            project_id=project_id,
            chapter_id=chapter_id,
            session_id=session_id,
            invocation_id=invocation_id,
        )

        prompt = await build_and_validate_prompt(
            self._composer,
            self._invocation_pipeline,
            intent,
            prompt_ctx,
            invocation_ctx,
            user_id=user_id,
            project_id=project_id,
        )

        config: ResolvedModelConfig = runtime.config
        resolved_limits = self._run_limit_resolver.resolve(
            config=config,
            budget=None,
            invocation_id=invocation_id,
        )

        logger.info(
            "ws_turn_stream_start",
            invocation_id=str(invocation_id),
            session_id=str(session_id),
            intent=intent.value,
            streaming=True,
        )

        async for chunk in self._registry.stream(
            intent=intent,
            system_prompt=prompt.system,
            user_prompt=prompt.user,
            config=config,
            usage_limits=resolved_limits.usage_limits,
            api_key=api_key,
            base_url=base_url,
        ):
            yield chunk

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _assemble_writing_context(
        self,
        *,
        context_assembler: WritingContextAssembler | None,
        project_id: UUID,
        chapter_id: UUID,
        prompt_mode: str,
    ) -> WritingContext | None:
        """Assemble the WritingContext graceful-None (RULE-11).

        Mirrors the writing-graph helper (ac55a094): ``None`` assembler or
        assembly failure → KB-blind turn (kb_* render empty); never silent.
        """
        if context_assembler is None:
            return None
        try:
            return await context_assembler.assemble(
                chapter_id=chapter_id,
                project_id=project_id,
                mode=prompt_mode,
            )
        except Exception as exc:
            logger.warning(
                "ws_turn_context_assembly_failed",
                error=str(exc),
                chapter_id=str(chapter_id),
                session_mode=prompt_mode,
            )
            return None
