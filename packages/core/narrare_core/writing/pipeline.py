"""Writing generation pipeline — orchestrates context → prompt → LLM → post-process.

MODES:
    - ``full_draft``          Generate a complete chapter via WritingGraph.
    - ``extend``              Seamless continuation from cursor position (direct LLM).
    - ``scene_by_scene``      Delegates to pipeline_scene module.
    - ``interview_assisted``  Delegates to pipeline_interview module.
    - ``interactive_session`` Handled via WebSocket (raises ValueError here).

RULE-01b: All LLM calls go through the injected registry.
RULE-02: All prompts built through the injected composer.

Stage contracts (AUFG-01-08):
    ``WritingPipeline.generate()`` is a thin orchestrator. Each stage has a
    single responsibility and a documented input→output contract, so new
    writing features can dock onto a named stage rather than onto the body of
    ``generate()`` itself:

    1. Voice-profile resolution — :func:`_stages.resolve_voice_profile_consumer`
       in:  ``kb_entities`` (list[KBEntity] | None)
       out: ``VoiceProfileConsumer | None``  (``None`` when no factory/entities)
    2. Context assembly — :func:`_stages.assemble_writing_context`
       in:  request + context inputs (chapter text, KB, recent chapters, …)
            + the Stage-1 consumer
       out: ``WritingContext``  (fully tiered; NO prompt built here — RULE-02)
    3. Metadata emission — inline in ``generate()``
       in:  assembled ``WritingContext``
       out: first ``StreamChunk`` carrying ``context_meta`` (CR-07 Context Inspector)
    4. Mode dispatch + invocation — :func:`_mode_dispatch.stream_for_mode`
       in:  pipeline, request, context, config, mode-specific params
       out: ``AsyncIterator[StreamChunk]``  (routes to the mode module; budget
            resolution, prompt build and the LLM call all happen INSIDE each
            mode module — never in ``generate()``)

    The ``finally`` block always discards the request's stop signal, so an
    interrupted generation cannot leak state into the next one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.llm.result import StreamChunk
from narrare_core.prompts.context import PromptContext
from narrare_core.writing._invocation_adapter import build_and_validate_prompt
from narrare_core.writing._mode_dispatch import stream_for_mode
from narrare_core.writing._stages import (
    assemble_writing_context,
    resolve_voice_profile_consumer,
)
from narrare_core.writing._tone_data import TONE_INSTRUCTIONS

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from uuid import UUID

    from narrare_core.agents.registry import AgentRegistry
    from narrare_core.ai_invocation.models import PromptInvocationContext
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.profiles.contracts import VoiceProfileConsumer
    from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
    from narrare_core.writing.context_assembler import WritingContextAssembler
    from narrare_core.writing.context_models import KBEntity, RecentChapter
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.models import GenerationRequest, WritingContext
    from narrare_core.writing.style_variants import StyleVariant

logger = structlog.get_logger(__name__)


class WritingPipeline:
    """Orchestrates the writing generation pipeline in four modes.

    Dependencies are injected via constructor (DI pattern).
    """

    def __init__(
        self,
        registry: ModelRegistry,
        composer: PromptComposer,
        context_assembler: WritingContextAssembler,
        draft_processor: DraftProcessor,
        agent_registry: AgentRegistry | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
        voice_profile_consumer_factory: Callable[[list[KBEntity]], VoiceProfileConsumer]
        | None = None,
    ) -> None:
        self._registry = registry
        self._composer = composer
        self._context_assembler = context_assembler
        self._draft_processor = draft_processor
        self._agent_registry = agent_registry
        self._invocation_pipeline = invocation_pipeline
        self._voice_profile_consumer_factory = voice_profile_consumer_factory
        self._stop_signals: set[UUID] = set()

    # -- Public API --

    async def generate(
        self,
        request: GenerationRequest,
        *,
        config: ResolvedModelConfig,
        api_key: str | None = None,
        base_url: str | None = None,
        chapter_content: str = "",
        chapter_frontmatter: str = "",
        chapter_outline: str = "",
        recent_chapters: list[RecentChapter] | None = None,
        kb_entities: list[KBEntity] | None = None,
        entity_connections: dict[str, set[str]] | None = None,
        kb_relationships: str = "",
        project_title: str = "",
        genre: str = "",
        user_preferences: str = "",
        avoidance_patterns: str = "",
        cross_session_context: str = "",
        series_history: str = "",
        custom_tone_instructions: str | None = None,
        selection_text: str = "",
        context_before: str = "",
        context_after: str = "",
        rewrite_mode: str = "tone",
        custom_instructions: str = "",
        rewrite_count: int = 1,
        co_author_focus: list[str] | None = None,
        style_variant: StyleVariant | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream generated text chunks for the given request.

        Args:
            request: The generation request with mode, tone, etc.
            config: Resolved model configuration for the LLM call.
            api_key: Optional API key override.
            base_url: Optional base URL override.
            chapter_content: Existing chapter text for continuation.
            chapter_frontmatter: Chapter metadata/frontmatter.
            chapter_outline: Chapter outline or structure notes.
            recent_chapters: List of recent chapters for context.
            kb_entities: Knowledge base entities for reference.
            entity_connections: Adjacency map of entity IDs to connected
                entity IDs, used for KB entity classification.
            kb_relationships: Pre-formatted relationship text for prompt
                injection (e.g. ``"Aria → [ally of] → Marcus"``).
                Produced by :func:`~narrare_core.writing._relationship_format.format_relationships`
                in the API layer.  Passed through to
                :class:`WritingContext` (FIND-009).
            project_title: Title of the project/novel.
            genre: Genre of the writing project.
            user_preferences: User's writing preference string.
            avoidance_patterns: Patterns the user wants to avoid.
            cross_session_context: Cross-session writing memories from mem0,
                formatted as a string of past writing-session observations.
                Empty when no memories exist (graceful degradation).
            series_history: Pre-assembled ``Previously in this series:`` block
                (Spec 2 / SERIES-002) produced by
                :class:`~narrare_core.context.series_history.SeriesHistoryTier`
                in the Backend. Threaded into ``{{series_history}}``. Empty for
                standalone novels (RULE-11 graceful — renders nothing).
            custom_tone_instructions: User-defined tone instructions
                to override bundled tones. When provided, used directly
                instead of looking up ``_TONE_INSTRUCTIONS``.
            selection_text: Text selection to rewrite (REWRITE mode).
            context_before: Text immediately before the selection.
            context_after: Text immediately after the selection.
            rewrite_mode: Rewrite strategy mode (tone/style/voice/
                fix/custom).
            custom_instructions: Author-defined rewrite instructions
                (required when ``rewrite_mode`` is ``"custom"``).
            rewrite_count: Number of alternatives to generate (1-3).
            co_author_focus: Focus areas for CO_AUTHOR mode (e.g.
                ``["dialogue", "description"]``).  ``None`` means no
                specific focus.
            style_variant: Optional creative-direction variant for
                style-variant regeneration (CR-AUFG-07-22).  When set, the
                variant's instruction text is injected into the rewrite
                prompt via ``{{style_variant_instructions}}``.  ``None``
                renders the variable as empty (backward compatible).
        """
        # Stage 1 — voice-profile consumer resolution
        voice_profile_consumer = resolve_voice_profile_consumer(self, kb_entities)

        # Stage 2 — context assembly
        context = await assemble_writing_context(
            self,
            request,
            voice_profile_consumer=voice_profile_consumer,
            chapter_content=chapter_content,
            chapter_frontmatter=chapter_frontmatter,
            chapter_outline=chapter_outline,
            recent_chapters=recent_chapters,
            kb_entities=kb_entities,
            entity_connections=entity_connections,
            kb_relationships=kb_relationships,
            project_title=project_title,
            genre=genre,
            user_preferences=user_preferences,
            avoidance_patterns=avoidance_patterns,
            cross_session_context=cross_session_context,
            series_history=series_history,
        )

        # Stage 3 — emit assembled context metadata (CR-07 Context Inspector)
        yield StreamChunk(text="", context_meta=context.to_metadata().to_dict())

        # Stage 4 — mode dispatch + invocation. Budget resolution, prompt
        # build and the LLM call all happen INSIDE the selected mode module;
        # see :func:`narrare_core.writing._mode_dispatch.stream_for_mode`.
        try:
            async for chunk in stream_for_mode(
                self,
                request,
                context,
                config,
                api_key=api_key,
                base_url=base_url,
                selection_text=selection_text,
                context_before=context_before,
                context_after=context_after,
                rewrite_mode=rewrite_mode,
                custom_instructions=custom_instructions,
                rewrite_count=rewrite_count,
                custom_tone_instructions=custom_tone_instructions,
                co_author_focus=co_author_focus,
                style_variant=style_variant,
            ):
                yield chunk
        finally:
            self._stop_signals.discard(request.id)

    async def stop(self, request_id: UUID) -> None:
        """Flag an in-progress generation for stopping."""
        self._stop_signals.add(request_id)
        logger.info("generation_stop_requested", request_id=str(request_id))

    def _is_stopped(self, request_id: UUID) -> bool:
        return request_id in self._stop_signals

    # -- Helpers (used by sub-modules via the pipeline instance) --

    def _build_prompt_context(
        self,
        request: GenerationRequest,
        context: WritingContext,
        *,
        mode: str = "new_chapter",
        author_instructions: str | None = None,
        extra_overrides: dict[str, str] | None = None,
        custom_tone_instructions: str | None = None,
    ) -> PromptContext:
        """Build a PromptContext from request + assembled writing context.

        Args:
            request: The generation request.
            context: Assembled writing context.
            mode: Prompt mode (e.g. "new_chapter", "continuation").
            author_instructions: Override for author instructions.
            extra_overrides: Additional extra variable overrides.
            custom_tone_instructions: User-defined tone instructions.
                When provided, used directly instead of bundled lookup.
        """
        tone_instr = (
            custom_tone_instructions
            if custom_tone_instructions is not None
            else self._tone_instructions(context.tone)
        )
        extra: dict[str, str] = {
            "user_id": str(request.user_id),
            "project_id": str(request.project_id),
            "chapter_outline": context.chapter_outline,
            "kb_characters": context.kb_characters,
            "kb_locations": context.kb_locations,
            "recent_chapters": context.recent_chapters,
            "character_voice_profiles": context.character_voice_profiles,
            "author_voice": context.author_voice,
            "series_history": context.series_history,
            "word_target": str(context.word_target) if context.word_target else "",
            "tone_instructions": tone_instr,
            "writing_language": context.writing_language,
        }
        if extra_overrides:
            extra.update(extra_overrides)

        return PromptContext(
            language=context.language,
            writing_language=context.writing_language,
            project_title=context.project_title,
            genre=context.genre,
            tone=context.tone,
            mode=mode,
            existing_content=context.chapter_content,
            author_instructions=author_instructions or request.prompt or request.outline or "",
            user_preferences=context.user_preferences,
            avoidance_patterns=context.avoidance_patterns,
            cross_session_context=context.cross_session_context,
            character_voice_profiles=context.character_voice_profiles,
            author_voice=context.author_voice,
            extra=extra,
        )

    async def _build_and_validate_prompt(
        self,
        intent: LLMIntent,
        prompt_ctx: PromptContext,
        invocation_context: PromptInvocationContext | None = None,
        *,
        user_id: object | None = None,
        project_id: object | None = None,
    ) -> ComposedPrompt:
        """Build prompt with optional invocation pipeline validation."""
        return await build_and_validate_prompt(
            self._composer,
            self._invocation_pipeline,
            intent,
            prompt_ctx,
            invocation_context,
            user_id=user_id,
            project_id=project_id,
        )

    @staticmethod
    def _tone_instructions(tone: str) -> str:
        """Return tone-specific writing instructions."""
        return TONE_INSTRUCTIONS.get(tone, "")
