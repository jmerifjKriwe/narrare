"""Writing generation pipeline — orchestrates context → prompt → LLM → post-process.

MODES:
    - ``full_draft``          Generate a complete chapter in one pass.
    - ``scene_by_scene``      Delegates to pipeline_scene module.
    - ``interview_assisted``  Delegates to pipeline_interview module.
    - ``interactive_session`` Handled via WebSocket (raises ValueError here).

RULE-01: All LLM calls go through the injected gateway.
RULE-02: All prompts built through the injected composer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.llm.intents import LLMIntent, ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.prompts.context import PromptContext
from narrare_core.shared.errors import LLMGatewayError, WritingError
from narrare_core.writing.models import (
    GenerationMode,
    GenerationRequest,
    WritingContext,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare_core.llm.gateway import LLMGateway, ModelRegistry
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.writing.context_assembler import WritingContextAssembler
    from narrare_core.writing.context_models import KBEntity, RecentChapter
    from narrare_core.writing.draft_processor import DraftProcessor

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Tone instructions — injected into prompt extra variables
# ---------------------------------------------------------------------------

_TONE_INSTRUCTIONS: dict[str, str] = {
    "dramatic": (
        "Use vivid imagery, heightened emotional stakes, powerful verbs, "
        "and dramatic pacing. Build tension through escalating sentences."
    ),
    "quiet": (
        "Use understated prose, sensory details, internal reflection, "
        "and gentle pacing. Let subtext carry the emotional weight."
    ),
    "suspenseful": (
        "Use short punchy sentences, cliffhangers, sensory details, "
        "and withheld information. Create urgency and uncertainty."
    ),
    "balanced": "",
}


class WritingPipeline:
    """Orchestrates the writing generation pipeline in four modes.

    Dependencies are injected via constructor (DI pattern).
    """

    def __init__(
        self,
        gateway: LLMGateway,
        composer: PromptComposer,
        context_assembler: WritingContextAssembler,
        draft_processor: DraftProcessor,
        registry: ModelRegistry | None = None,
        use_draft_agent: bool = False,
    ) -> None:
        self._gateway = gateway
        self._composer = composer
        self._context_assembler = context_assembler
        self._draft_processor = draft_processor
        self._registry = registry
        self._use_draft_agent = use_draft_agent
        self._stop_signals: set[UUID] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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
        project_title: str = "",
        genre: str = "",
        user_preferences: str = "",
        avoidance_patterns: str = "",
    ) -> AsyncIterator[StreamChunk]:
        """Stream generated text chunks for the given request."""
        context = await self._context_assembler.assemble(
            chapter_content=chapter_content,
            chapter_frontmatter=chapter_frontmatter,
            chapter_outline=chapter_outline,
            recent_chapters=recent_chapters,
            kb_entities=kb_entities,
            project_title=project_title,
            genre=genre,
            language=request.language,
            tone=request.tone,
            word_target=request.word_target,
            user_preferences=user_preferences,
            avoidance_patterns=avoidance_patterns,
        )

        try:
            if request.mode == GenerationMode.FULL_DRAFT:
                async for chunk in self._full_draft(
                    request,
                    context,
                    config,
                    api_key=api_key,
                    base_url=base_url,
                ):
                    yield chunk

            elif request.mode == GenerationMode.SCENE_BY_SCENE:
                from narrare_core.writing.pipeline_scene import stream_scene_by_scene

                async for chunk in stream_scene_by_scene(
                    self,
                    request,
                    context,
                    config,
                    api_key=api_key,
                    base_url=base_url,
                ):
                    yield chunk

            elif request.mode == GenerationMode.INTERVIEW_ASSISTED:
                from narrare_core.writing.pipeline_interview import stream_interview_assisted

                async for chunk in stream_interview_assisted(
                    self,
                    request,
                    context,
                    config,
                    api_key=api_key,
                    base_url=base_url,
                ):
                    yield chunk

            elif request.mode == GenerationMode.INTERACTIVE_SESSION:
                raise ValueError("Interactive session uses WebSocket, not pipeline.generate()")
            else:
                raise WritingError(
                    f"Unsupported generation mode: {request.mode}",
                    code="UNSUPPORTED_MODE",
                )
        finally:
            self._stop_signals.discard(request.id)

    async def stop(self, request_id: UUID) -> None:
        """Flag an in-progress generation for stopping."""
        self._stop_signals.add(request_id)
        logger.info("generation_stop_requested", request_id=str(request_id))

    def _is_stopped(self, request_id: UUID) -> bool:
        return request_id in self._stop_signals

    # ------------------------------------------------------------------
    # Mode: Full Draft
    # ------------------------------------------------------------------

    async def _full_draft(
        self,
        request: GenerationRequest,
        context: WritingContext,
        config: ResolvedModelConfig,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Generate a complete chapter draft in one pass."""
        if self._use_draft_agent and self._registry is not None:
            async for chunk in self._stream_via_draft_agent(
                request,
                context,
                config,
                api_key=api_key,
                base_url=base_url,
            ):
                yield chunk
        else:
            async for chunk in self._legacy_full_draft(
                request,
                context,
                config,
                api_key=api_key,
                base_url=base_url,
            ):
                yield chunk

    async def _legacy_full_draft(
        self,
        request: GenerationRequest,
        context: WritingContext,
        config: ResolvedModelConfig,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Legacy full-draft path via LLMGateway (original implementation)."""
        prompt_context = self._build_prompt_context(request, context)
        prompt = await self._composer.build(LLMIntent.WRITE, prompt_context)

        accumulated: list[str] = []
        final_usage: TokenUsage | None = None

        try:
            async for chunk in self._gateway.stream(
                intent=LLMIntent.WRITE,
                system_prompt=prompt.system,
                user_prompt=prompt.user,
                config=config,
                api_key=api_key,
                base_url=base_url,
            ):
                if self._is_stopped(request.id):
                    logger.info(
                        "generation_stopped",
                        request_id=str(request.id),
                        chunks=len(accumulated),
                    )
                    break
                if chunk.is_final:
                    final_usage = chunk.usage
                    continue
                accumulated.append(chunk.text)
                yield chunk

        except LLMGatewayError as e:
            logger.error(
                "generation_failed",
                error=str(e),
                request_id=str(request.id),
                chunks=len(accumulated),
            )
            raise WritingError(
                f"Draft generation failed after {len(accumulated)} chunks: {e}",
                code="GENERATION_FAILED",
            ) from e

        raw_text = "".join(accumulated)
        cleaned = self._draft_processor.process(
            raw_text,
            word_target=request.word_target,
        )
        yield StreamChunk(text=cleaned, is_final=True, usage=final_usage)

    async def _stream_via_draft_agent(
        self,
        request: GenerationRequest,
        context: WritingContext,
        config: ResolvedModelConfig,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Generate a draft via DraftAgent (pydantic-ai based).

        Uses the DraftAgent's Output Function for post-processing
        and quality validation instead of the legacy gateway path.
        """
        # Lazy import to avoid circular dependencies
        from narrare_core.agents.draft_agent import DraftAgent, DraftDeps

        # Nur aufgerufen wenn self._registry gesetzt ist (siehe _full_draft Guard)
        registry = self._registry
        assert registry is not None

        prompt_context = self._build_prompt_context(request, context)
        prompt = await self._composer.build(LLMIntent.WRITE, prompt_context)

        model = await registry.get_model(
            config,
            api_key=api_key,
            base_url=base_url,
        )

        agent = DraftAgent(model=model, word_target=request.word_target)
        deps = DraftDeps(context_assembler=self._context_assembler)

        # Der DraftAgent hat bereits einen eigenen system_prompt.
        # Wir übergeben den user_prompt mit dem assemblierten Kontext.
        # narrare: allow-agent reason="DraftAgent is called from pipeline compat layer (Phase 2.3)"
        result = await agent.run(prompt=prompt.user, deps=deps)

        # DraftOutput → StreamChunk Konvertierung
        # TokenUsage ist aktuell nicht verfügbar (Phase 3: Agent-Usage-Reporting)
        yield StreamChunk(
            text=result.text,
            is_final=True,
            usage=None,
        )

    # ------------------------------------------------------------------
    # Helpers (used by sub-modules via the pipeline instance)
    # ------------------------------------------------------------------

    def _build_prompt_context(
        self,
        request: GenerationRequest,
        context: WritingContext,
        *,
        mode: str = "new_chapter",
        author_instructions: str | None = None,
        extra_overrides: dict[str, str] | None = None,
    ) -> PromptContext:
        """Build a PromptContext from request + assembled writing context."""
        extra: dict[str, str] = {
            "user_id": str(request.user_id),
            "project_id": str(request.project_id),
            "chapter_outline": context.chapter_outline,
            "kb_characters": context.kb_characters,
            "kb_locations": context.kb_locations,
            "recent_chapters": context.recent_chapters,
            "word_target": str(context.word_target) if context.word_target else "",
            "tone_instructions": self._tone_instructions(context.tone),
        }
        if extra_overrides:
            extra.update(extra_overrides)

        return PromptContext(
            language=context.language,
            project_title=context.project_title,
            genre=context.genre,
            tone=context.tone,
            mode=mode,
            existing_content=context.chapter_content,
            author_instructions=author_instructions or request.prompt or request.outline or "",
            user_preferences=context.user_preferences,
            avoidance_patterns=context.avoidance_patterns,
            extra=extra,
        )

    @staticmethod
    def _tone_instructions(tone: str) -> str:
        """Return tone-specific writing instructions."""
        return _TONE_INSTRUCTIONS.get(tone, "")
