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

See: ADR-045, CONSTRAINTS.md RULE-02/RULE-03/RULE-06/RULE-12/RULE-13.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

from narrare_core.writing._invocation_adapter import build_and_validate_prompt

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare_core.ai_invocation.models import PromptInvocationContext
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.llm.result import StreamChunk
    from narrare_core.llm.run_limits import DefaultRunLimitResolver
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.prompts.context import PromptContext
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
        config: Fully resolved model configuration.
        run_limit_resolver: Resolves output budgets into pydantic-ai
            runtime limits (ADR-045 Decision 4).
        context_assembler: Optional WritingContextAssembler for KB-enriched
            supply; ``None`` or failure → KB-blind turn (RULE-11, ac55a094).
    """

    def __init__(
        self,
        composer: PromptComposer,
        invocation_pipeline: InvocationPipeline | None,
        registry: ModelRegistry,
        config: ResolvedModelConfig,
        run_limit_resolver: DefaultRunLimitResolver,
        context_assembler: WritingContextAssembler | None = None,
    ) -> None:
        self._composer = composer
        self._invocation_pipeline = invocation_pipeline
        self._registry = registry
        self._config = config
        self._run_limit_resolver = run_limit_resolver
        self._context_assembler = context_assembler

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
            1. Build :class:`PromptContext` from the user's direction.
            2. Build :class:`PromptInvocationContext` with identifiers.
            3. ``build_and_validate_prompt`` — prepare → merge → compose
               → finalize (enrichment, budget, validation, evidence).
            4. Resolve run limits with the same ``invocation_id``.
            5. Stream via :meth:`ModelRegistry.stream` with enforced
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
        intent = self._resolve_intent(session_mode)
        prompt_mode = self._resolve_prompt_mode(session_mode)

        # KB assembly graceful-None — see _assemble_writing_context (RULE-11).
        writing_context = await self._assemble_writing_context(
            project_id=project_id,
            chapter_id=chapter_id,
            prompt_mode=prompt_mode,
        )
        prompt_ctx = self._build_prompt_context(content, prompt_mode, writing_context)
        invocation_id = uuid4()
        invocation_ctx = self._build_invocation_context(
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

        resolved_limits = self._run_limit_resolver.resolve(
            config=self._config,
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
            config=self._config,
            usage_limits=resolved_limits.usage_limits,
            api_key=api_key,
            base_url=base_url,
        ):
            yield chunk

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_intent(session_mode: str) -> LLMIntent:
        """Map session mode to LLM intent."""
        from narrare_core.llm.intents import LLMIntent

        if session_mode == "interview_assisted":
            return LLMIntent.CHAT
        return LLMIntent.WRITE

    @staticmethod
    def _resolve_prompt_mode(session_mode: str) -> str:
        """Map session mode to prompt mode."""
        if session_mode == "interview_assisted":
            return "interview"
        return "interactive_session"

    async def _assemble_writing_context(
        self,
        *,
        project_id: UUID,
        chapter_id: UUID,
        prompt_mode: str,
    ) -> WritingContext | None:
        """Assemble the WritingContext graceful-None (RULE-11).

        Mirrors the writing-graph helper (ac55a094): ``None`` assembler or
        assembly failure → KB-blind turn (kb_* render empty); never silent.
        """
        if self._context_assembler is None:
            return None
        try:
            return await self._context_assembler.assemble(
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

    @staticmethod
    def _build_prompt_context(
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
        ``word_target_line`` for interactive_session only (slice-3: label-in-value).
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
            extra["word_target_line"] = word_target_line(
                kb_source.word_target, label="Word target: "
            )
        return PromptContext(
            language="en",
            mode=prompt_mode,
            author_instructions=content,
            extra=extra,
        )

    @staticmethod
    def _build_invocation_context(
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
        invocation context. Chapter and session IDs are carried as
        dynamic inputs so enrichers and evidence can correlate them.
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
