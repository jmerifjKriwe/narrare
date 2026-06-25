"""Story suggest service — calls StorySuggestAgent (Writer's Unblock).

Generates 3-5 distinct story suggestions (plot developments, character
moments, dialogue options, world details, stylistic alternatives) to
help writers who are stuck.  Each suggestion explains how it connects
to established plot threads.

Prompt resolution is Mode 1 (composer-driven) per ADR-054 D1/D7/D8: the
service resolves its system prompt via
``compose_invocation(composer=..., prompt_context=PromptContext(mode="story_suggest"),
intent=LLMIntent.SUGGEST)``
and passes the composed system prompt to the ``StorySuggestAgent``
constructor (pydantic-ai binds ``system_prompt`` at construction, not
at run-time).

The previous inline f-string feature prompt pattern is prohibited
(RULE-02 / RULE-02a).  Invocation-composition errors propagate
(RULE-11) instead of being silently swallowed.

Pattern: Service → PromptComposer (RULE-02) → Core Agent (RULE-01b).

See WRITE-009 (Writer's Unblock Tools).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.writing.schemas_story_suggest import (
    StorySuggestionResponse,
    StorySuggestStreamEvent,
)
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.novels.repository import NovelRepository
    from narrare.writing.schemas_story_suggest import StorySuggestRequest
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


class StorySuggestService:
    """Service for generating story direction suggestions (Writer's Unblock).

    Takes a novel's project context and optional author instructions,
    then runs the :class:`StorySuggestAgent` to produce 3-5 distinct
    story suggestions.

    The story-suggest prompt is resolved through ``PromptComposer`` in
    Mode 1 (ADR-054 D1): the governed
    ``_bundled/writing/{locale}/story_suggest/system.md`` template
    carries the task framing and project metadata variables.  No inline
    f-string feature prompt is assembled in the service (RULE-02 /
    RULE-02a).

    Args:
        novel_repo: For novel existence + metadata (genre, language,
            story structure).
        model_registry: Shared LLM model registry.
        model_config: Resolved model config (provider + model ID).
        composer: PromptComposer for resolving the governed
            story-suggest system prompt via the cascade (RULE-02b /
            ADR-054 D1).  Required for ``suggest``.
        invocation_pipeline: Optional pipeline for invocation evidence
            (Mode 1 prepare/finalize).  Retained for DI-contract
            stability.
    """

    def __init__(
        self,
        novel_repo: NovelRepository,
        model_registry: ModelRegistry,
        model_config: ResolvedModelConfig | None = None,
        composer: PromptComposer | None = None,
        *,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._novel_repo = novel_repo
        self._registry = model_registry
        self._config = model_config
        self._composer = composer
        self._invocation_pipeline = invocation_pipeline

    async def suggest(
        self,
        novel_id: UUID,
        user_id: UUID,
        request: StorySuggestRequest,
    ) -> AsyncIterator[StorySuggestStreamEvent]:
        """Generate story direction suggestions for a novel.

        Runs the :class:`StorySuggestAgent` with project context and
        yields SSE events: a ``"suggestions"`` event with the full
        suggestion list, followed by a ``"done"`` event.

        Args:
            novel_id: Novel to generate suggestions for.
            user_id: Authenticated user identifier.
            request: Story suggest request with optional ``chapter_id``
                and ``author_instructions``.

        Yields:
            :class:`StorySuggestStreamEvent` instances.  The final
            event has ``is_final=True``.

        Raises:
            NotFoundError: If the novel does not exist.
            ConfigurationError: If no model config or PromptComposer
                is configured.
        """
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        if self._config is None:
            raise NotFoundError("Model config", identifier="no_model_config")

        if self._composer is None:
            # Defensive: the factory always wires a composer, but fail
            # loudly (RULE-11) rather than silently falling back to
            # inline assembly.
            raise ConfigurationError(
                "PromptComposer is not configured for story suggestions.",
                code="NO_COMPOSER",
            )

        language = novel.writing_language or "en"

        # Resolve the governed story-suggest system prompt via
        # PromptComposer (RULE-02 / ADR-054 D1).  The template
        # ``_bundled/writing/{locale}/story_suggest/system.md`` carries
        # the task framing and project metadata variables.
        from narrare._app.invocation_context import build_invocation_context
        from narrare_core.agents.story_suggest_agent import StorySuggestAgent
        from narrare_core.agents.story_suggest_types import StorySuggestDeps
        from narrare_core.ai_invocation import compose_invocation
        from narrare_core.llm.intents import LLMIntent
        from narrare_core.prompts.context import PromptContext

        ctx = PromptContext(
            language=language,
            writing_language=language,
            project_title=novel.title,
            genre=novel.genre or "",
            story_structure=novel.story_structure or "",
            mode="story_suggest",
            author_instructions=request.author_instructions or "",
            extra={
                "chapter_id": str(request.chapter_id) if request.chapter_id else "",
                # No chapter-outline assembler wired for this call path
                # yet; declared explicitly (not silently omitted) so the
                # template's variable substitution succeeds (precedent:
                # character_arc_service existing_plot_points).
                "chapter_outline": "",
                "culture_guidelines": "",
            },
        )

        invocation_context = build_invocation_context(
            feature_id="writing_story_suggest",
            intent=LLMIntent.SUGGEST,
            project_id=novel_id,
            user_id=user_id,
            language=language,
        )
        invocation = await compose_invocation(
            invocation_pipeline=self._invocation_pipeline,
            invocation_context=invocation_context,
            composer=self._composer,
            prompt_context=ctx,
            intent=LLMIntent.SUGGEST,
        )
        composed_prompt = invocation.composed_prompt
        # Mode 1 guarantees composed_prompt is set; the guard documents
        # the invariant and satisfies the type-checker (RULE-11: no
        # silent None).
        if composed_prompt is None:  # pragma: no cover - Mode 1 invariant
            raise ConfigurationError(
                "Prompt composition produced no system prompt for story suggestions.",
                code="COMPOSITION_EMPTY",
            )

        model = await self._registry.get_model(self._config)

        # Build agent dependencies — minimal runtime data per
        # StorySuggestDeps (project-level fields only).
        deps = StorySuggestDeps(
            project_title=novel.title,
            genre=novel.genre or "",
            writing_language=language,
        )

        # pydantic-ai binds ``system_prompt`` at agent construction, so
        # the composed system prompt is supplied to the constructor
        # (not to ``run()``).  The project data additionally flows as
        # the run prompt (runtime data, RULE-02a category 3) when the
        # template has no "## First Message".
        agent = StorySuggestAgent(model=model, system_prompt=composed_prompt.system)
        result = await agent.run(
            prompt=composed_prompt.user
            or (
                f"Project: {novel.title}\n"
                f"Genre: {novel.genre or ''}\n"
                f"Story structure: {novel.story_structure or ''}\n"
                f"Author instructions: {request.author_instructions or ''}"
            ),
            deps=deps,
        )

        # Map core output to API response schemas.
        suggestions = [
            StorySuggestionResponse(
                type=s.type.value,
                title=s.title,
                description=s.description,
                connection=s.connection,
            )
            for s in result.suggestions
        ]

        logger.info(
            "story_suggest_completed",
            feature_id="writing_story_suggest",
            novel_id=str(novel_id),
            suggestion_count=len(suggestions),
        )

        yield StorySuggestStreamEvent(
            event="suggestions",
            suggestions=suggestions,
        )
        yield StorySuggestStreamEvent(event="done", is_final=True)
