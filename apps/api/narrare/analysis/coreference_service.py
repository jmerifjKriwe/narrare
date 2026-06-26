"""Coreference analysis service — calls CoreferenceAgent (ANAL-005).

Resolves pronoun references to character names, flags ambiguous pronouns,
tracks character mentions, and scores overall referential clarity. Results
are streamed as :class:`CoreferenceStreamEvent` objects so the frontend can
render progressively.

Prompt resolution is Mode 1 (composer-driven) per ADR-054 D1/D7/D8: the
service resolves its system prompt via
``compose_invocation(composer=..., prompt_context=PromptContext(mode="coreference"),
intent=LLMIntent.ANALYSE)``
and passes the composed system prompt to the ``CoreferenceAgent`` constructor
(pydantic-ai binds ``system_prompt`` at construction, not at run-time).

The chapter text flows as runtime data in the agent run prompt (user
channel, RULE-02a category 3). No inline f-string feature prompt is
assembled in the service (RULE-02 / RULE-02a). Invocation-composition
errors propagate (RULE-11) instead of being silently swallowed.

Pattern: Service → PromptComposer (RULE-02) → Core Agent (RULE-01b).

See:
    :mod:`narrare.analysis.contracts_coreference` — the Protocol.
    :mod:`narrare.analysis.schemas_coreference` — SSE event + response models.
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.analysis.schemas_coreference import (
    CharacterMentionResponse,
    CoreferenceResponse,
    CoreferenceStreamEvent,
    PronounResolutionResponse,
)
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


class CoreferenceService:
    """Service for coreference resolution analysis (ANAL-005).

    Takes a chapter, resolves the project context (novel metadata +
    language), then runs the :class:`CoreferenceAgent` to resolve
    pronouns, flag ambiguity, track mentions, and score clarity.

    The coreference prompt is resolved through ``PromptComposer`` in
    Mode 1 (ADR-054 D1): the governed
    ``_bundled/analysis/{locale}/coreference/system.md`` template carries
    the task framing and project metadata variables. No inline f-string
    feature prompt is assembled in the service (RULE-02 / RULE-02a).

    Args:
        novel_repo: For novel existence + metadata (genre, language)
            and access control.
        chapter_repo: For fetching the chapter content.
        model_registry: Shared LLM model registry.
        model_config: Resolved model config (provider + model ID).
        composer: PromptComposer for resolving the governed
            coreference system prompt via the cascade (RULE-02b /
            ADR-054 D1). Required for ``analyze``.
        invocation_pipeline: Optional pipeline for invocation evidence
            (Mode 1 prepare/finalize). Retained for DI-contract
            stability.
    """

    def __init__(
        self,
        novel_repo: NovelRepository,
        chapter_repo: ChapterRepository,
        model_registry: ModelRegistry,
        model_config: ResolvedModelConfig | None = None,
        composer: PromptComposer | None = None,
        *,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._novel_repo = novel_repo
        self._chapter_repo = chapter_repo
        self._registry = model_registry
        self._config = model_config
        self._composer = composer
        self._invocation_pipeline = invocation_pipeline

    async def analyze(
        self,
        chapter_id: UUID,
        user_id: UUID,
    ) -> AsyncIterator[CoreferenceStreamEvent]:
        """Analyse coreference for a chapter, streaming SSE events.

        Runs the :class:`CoreferenceAgent` with the chapter text and
        project context, then yields a ``"result"`` event with the full
        analysis followed by a terminal ``"done"`` event.

        Args:
            chapter_id: The chapter to analyse.
            user_id: Authenticated user identifier (resolved against the
                chapter's novel for access control).

        Yields:
            :class:`CoreferenceStreamEvent` instances. The final event
            has ``is_final=True``.

        Raises:
            NotFoundError: If the chapter or its novel does not exist or
                is not accessible, or no model config is configured.
            ConfigurationError: If no ``PromptComposer`` is configured.
        """
        # 1. Fetch chapter (novel_id-free lookup) then resolve novel
        #    metadata + access control.
        chapter = await self._chapter_repo.get(chapter_id)
        if chapter is None:
            raise NotFoundError("Chapter", identifier=str(chapter_id))

        novel = await self._novel_repo.get_by_id(chapter.novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(chapter.novel_id))

        if self._config is None:
            raise NotFoundError("Model config", identifier="no_model_config")

        if self._composer is None:
            # Defensive: the factory always wires a composer, but fail
            # loudly (RULE-11) rather than silently falling back to
            # inline assembly.
            raise ConfigurationError(
                "PromptComposer is not configured for coreference analysis.",
                code="NO_COMPOSER",
            )

        language = novel.writing_language or "en"
        chapter_text = chapter.content or ""

        # 2. Resolve the governed coreference system prompt via
        #    PromptComposer (RULE-02 / ADR-054 D1). The template
        #    ``_bundled/analysis/{locale}/coreference/system.md`` carries
        #    the task framing, project metadata, and KB-context
        #    variables.
        from narrare._app.invocation_context import build_invocation_context
        from narrare_core.agents.coreference_agent import CoreferenceAgent
        from narrare_core.agents.coreference_types import CoreferenceDeps
        from narrare_core.ai_invocation import compose_invocation
        from narrare_core.llm.intents import LLMIntent
        from narrare_core.prompts.context import PromptContext

        ctx = PromptContext(
            language=language,
            writing_language=language,
            project_title=novel.title,
            genre=novel.genre or "",
            chapter_title=chapter.title or "",
            mode="coreference",
            extra={
                # No KB repository is wired for this call path (the
                # service constructor intentionally omits it); declared
                # explicitly (not silently omitted) so the template's
                # variable substitution succeeds (precedent:
                # character_arc_service existing_plot_points).
                "kb_characters": "",
                "kb_locations": "",
                "kb_factions": "",
                "kb_relationships": "",
            },
        )

        invocation_context = build_invocation_context(
            feature_id="analysis_coreference",
            intent=LLMIntent.ANALYSE,
            project_id=chapter.novel_id,
            user_id=user_id,
            language=language,
        )
        invocation = await compose_invocation(
            invocation_pipeline=self._invocation_pipeline,
            invocation_context=invocation_context,
            composer=self._composer,
            prompt_context=ctx,
            intent=LLMIntent.ANALYSE,
        )
        composed_prompt = invocation.composed_prompt
        # Mode 1 guarantees composed_prompt is set; the guard documents
        # the invariant and satisfies the type-checker (RULE-11: no
        # silent None).
        if composed_prompt is None:  # pragma: no cover - Mode 1 invariant
            raise ConfigurationError(
                "Prompt composition produced no system prompt for coreference analysis.",
                code="COMPOSITION_EMPTY",
            )

        model = await self._registry.get_model(self._config)

        # 3. Build agent dependencies — structured project/chapter context.
        #    The chapter text additionally flows as the run prompt (runtime
        #    data, RULE-02a category 3) in the user channel below.
        deps = CoreferenceDeps(
            text=chapter_text,
            project_title=novel.title,
            genre=novel.genre or "",
            writing_language=language,
            chapter_title=chapter.title or "",
        )

        # pydantic-ai binds ``system_prompt`` at agent construction, so
        # the composed system prompt is supplied to the constructor (not
        # to ``run()``). The chapter text is runtime data and flows as
        # the run prompt (user channel) when the template has no
        # "## First Message".
        try:
            agent = CoreferenceAgent(model=model, system_prompt=composed_prompt.system)
            result = await agent.run(
                prompt=composed_prompt.user or chapter_text,
                deps=deps,
            )
        except Exception as exc:
            logger.error(
                "coreference_agent_failed",
                chapter_id=str(chapter_id),
                error=str(exc),
                exc_info=True,
            )
            raise

        # 4. Map core output to API response schemas.
        response = CoreferenceResponse(
            chapter_id=str(chapter_id),
            clarity_score=result.clarity_score,
            summary=result.summary,
            resolutions=[
                PronounResolutionResponse(
                    pronoun=r.pronoun,
                    position=r.position,
                    referent=r.referent,
                    confidence=r.confidence,
                    is_ambiguous=r.is_ambiguous,
                )
                for r in result.resolutions
            ],
            character_mentions=[
                CharacterMentionResponse(
                    character_name=m.character_name,
                    mentions=list(m.mentions),
                    is_pov=m.is_pov,
                )
                for m in result.character_mentions
            ],
        )

        logger.info(
            "coreference_analysis_complete",
            feature_id="analysis_coreference",
            chapter_id=str(chapter_id),
            resolution_count=len(response.resolutions),
            character_count=len(response.character_mentions),
            clarity_score=response.clarity_score,
        )

        yield CoreferenceStreamEvent(event="result", result=response)
        yield CoreferenceStreamEvent(event="done", is_final=True)
