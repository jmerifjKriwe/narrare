"""Writing generation pipeline — orchestrates context → prompt → LLM → post-process.

MODES:
    - ``full_draft``          Generate a complete chapter via WritingGraph.
    - ``scene_by_scene``      Delegates to pipeline_scene module.
    - ``interview_assisted``  Delegates to pipeline_interview module.
    - ``interactive_session`` Handled via WebSocket (raises ValueError here).

RULE-01: All LLM calls go through the injected registry.
RULE-02: All prompts built through the injected composer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.prompts.context import PromptContext
from narrare_core.shared.errors import WritingError
from narrare_core.writing.models import (
    GenerationMode,
    GenerationRequest,
    WritingContext,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.intents import ResolvedModelConfig
    from narrare_core.llm.result import StreamChunk
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
    "humorous": (
        "Use witty observations, lighthearted tone, playful language, "
        "comedic timing, and unexpected juxtapositions. Maintain levity."
    ),
    "contemplative": (
        "Use reflective prose, philosophical musings, measured pacing, "
        "internal monologue, and layered observations."
    ),
    "romantic": (
        "Use evocative sensory details, emotional language, intimate moments, "
        "lyrical prose, and heightened emotional resonance."
    ),
    "dark": (
        "Use grim imagery, foreboding atmosphere, visceral details, "
        "moral ambiguity, and unsettling tension."
    ),
    "adventurous": (
        "Use dynamic action sequences, energetic pacing, bold descriptive "
        "language, rising stakes, and momentum."
    ),
}


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
    ) -> None:
        self._registry = registry
        self._composer = composer
        self._context_assembler = context_assembler
        self._draft_processor = draft_processor
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
            language=request.writing_language,
            writing_language=request.writing_language,
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
    # Mode: Full Draft (always via WritingGraph)
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
        """Generate a complete chapter draft via WritingGraph."""
        from narrare_core.writing.pipeline_graph import stream_via_writing_graph

        async for chunk in stream_via_writing_graph(
            request,
            context,
            config,
            registry=self._registry,
            context_assembler=self._context_assembler,
            api_key=api_key,
            base_url=base_url,
        ):
            yield chunk

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
            extra=extra,
        )

    @staticmethod
    def _tone_instructions(tone: str) -> str:
        """Return tone-specific writing instructions."""
        # TODO(metadata-consistency): Add user override support via prompt cascade
        # Currently bundled instructions only. Future: user can override via
        # prompt cascade mechanism (see design.md Decision 6).
        return _TONE_INSTRUCTIONS.get(tone, "")
