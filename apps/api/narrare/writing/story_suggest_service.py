"""Story suggest service — calls StorySuggestAgent (Writer's Unblock).

Generates 3-5 distinct story suggestions (plot developments, character
moments, dialogue options, world details, stylistic alternatives) to
help writers who are stuck.  Each suggestion explains how it connects
to established plot threads.

Model routing is lazy (ADR-086 L34, Pattern M-graceful): the per-user
SUGGEST cascade resolves on first use — ``ensure_resolved`` — never at
construction. The eager factory's wiring-time ``except
ConfigurationError`` swallow is entry-point policy (``no_ai_provider_
configured`` log + the preserved ``no_model_config`` degraded outcome);
the eager wiring-time uid-scoped novel guard lives in the first-use
paths, immediately BEFORE the resolve (gate-before-resolution ordering,
planning guard ruling). The router calls the ``validate_suggest``
pre-stream seam so the novel gate's 404 stays a pre-header status.

Prompt resolution is Mode 1 (composer-driven) per ADR-054 D1/D7/D8: the
service resolves its system prompt via
``compose_invocation(composer=..., prompt_context=PromptContext(mode="story_suggest"),
intent=LLMIntent.SUGGEST)``
and passes the composed system prompt to the ``StorySuggestAgent``
constructor (pydantic-ai binds ``system_prompt`` at construction, not
at run-time). The previous inline f-string feature prompt pattern is
prohibited (RULE-02 / RULE-02a). Invocation-composition errors
propagate (RULE-11) instead of being silently swallowed.

Pattern: Service → PromptComposer (RULE-02) → Core Agent (RULE-01b).

See WRITE-009 (Writer's Unblock Tools).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.writing._story_suggest_support import (
    compose_story_suggest_prompt,
    run_story_suggest_agent,
)
from narrare.writing.schemas_story_suggest import (
    StorySuggestionResponse,
    StorySuggestStreamEvent,
)
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare._app.dependencies_services import ModelResolution
    from narrare.novels.models import Novel
    from narrare.novels.repository import NovelRepository
    from narrare.planning.contracts import (
        OutlineRepositoryProtocol,
        ScenePlanRepositoryProtocol,
    )
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
        model_resolution: Lazy per-user model resolution (ADR-086 L34) —
            the SUGGEST routing cascade resolves at first use, never at
            construction. A ``ConfigurationError`` (no AI provider) is
            graceful here: the entry-point policy logs
            ``no_ai_provider_configured`` and the preserved
            ``no_model_config`` outcome fires (AI-optional feature).
        composer: PromptComposer for resolving the governed
            story-suggest system prompt via the cascade (RULE-02b /
            ADR-054 D1).  Required for ``suggest``.
        outline_repo: For the targeted chapter's outline, rendered into the
            ``chapter_outline`` prompt slot when a ``chapter_id`` is set
            (§7 closed).  When ``None`` or no chapter is targeted the slot
            stays empty (legitimate RULE-11 — story-suggest is a
            project-level tool and a chapter need not be selected).
        scene_repo: For the targeted chapter's scene plans (PLAN-001 T15,
            spec §7 — rendered as numbered blocks into the
            ``chapter_outline`` slot).  When ``None`` the slot degrades to
            stage + notes (RULE-11).
        invocation_pipeline: Optional pipeline for invocation evidence
            (Mode 1 prepare/finalize).  Retained for DI-contract
            stability.
    """

    def __init__(
        self,
        novel_repo: NovelRepository,
        model_registry: ModelRegistry,
        model_resolution: ModelResolution,
        composer: PromptComposer | None = None,
        outline_repo: OutlineRepositoryProtocol | None = None,
        scene_repo: ScenePlanRepositoryProtocol | None = None,
        *,
        invocation_pipeline: InvocationPipeline | None = None,
        run_limit_resolver: DefaultRunLimitResolver | None = None,
    ) -> None:
        self._novel_repo = novel_repo
        self._registry = model_registry
        self._model_resolution = model_resolution
        self._config: ResolvedModelConfig | None = None
        self._resolve_attempted = False
        self._composer = composer
        self._outline_repo = outline_repo
        self._scene_repo = scene_repo
        self._invocation_pipeline = invocation_pipeline
        self._run_limit_resolver = run_limit_resolver or DefaultRunLimitResolver()

    async def ensure_resolved(self) -> None:
        """Resolve the per-user SUGGEST routing cascade once (ADR-086 L34).

        First call awaits the injected ``ModelResolution`` and caches the
        resolved config; repeat calls are idempotent — the cascade runs
        at most once per instance, success or failure (eager-world
        timing also resolved exactly once per request).
        ``ConfigurationError`` propagates UNCHANGED: the graceful
        swallow is entry-point policy (see :meth:`validate_suggest` and
        :meth:`suggest`), so this method stays honest about what
        happened (RULE-11).
        """
        if self._resolve_attempted:
            return
        self._resolve_attempted = True
        resolved = await self._model_resolution.resolve()
        self._config = resolved.config

    async def _get_novel_or_raise(self, novel_id: UUID, user_id: UUID) -> Novel:
        """Load the novel uid-scoped or raise the ownership ``NotFoundError``.

        The eager factory's wiring-time uid-scoped novel guard, relocated
        into the first-use paths (ADR-086 L34, planning guard ruling):
        foreign ≡ unknown (anti-enumeration) → 404, BEFORE the routing
        cascade can auto-create ``project_settings`` for a foreign novel.
        """
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))
        return novel

    async def validate_suggest(self, novel_id: UUID, user_id: UUID) -> None:
        """Pre-stream seam: gate the novel, then resolve gracefully.

        Called by the router BEFORE the ``StreamingResponse`` is
        constructed so the uid-scoped novel gate (``NotFoundError`` →
        404) stays a pre-header status and the first-use cascade runs
        post-validation (ADR-086 L34). Graceful (AI-optional feature):
        a missing AI provider never raises here — it logs
        ``no_ai_provider_configured`` and lets the preserved
        ``no_model_config`` degraded outcome fire in-band in
        :meth:`suggest`, exactly as the eager factory's wiring-time
        swallow did.

        Raises:
            NotFoundError: If the novel is unknown or owned by another
                user (foreign ≡ unknown, anti-enumeration).
        """
        await self._get_novel_or_raise(novel_id, user_id)
        try:
            await self.ensure_resolved()
        except ConfigurationError:
            logger.info("no_ai_provider_configured", novel_id=str(novel_id))

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
            NotFoundError: If the novel does not exist, or — the
                preserved degraded outcome — if no AI provider is
                configured (``no_model_config``; AI-optional feature,
                ADR-086 L34).
            ConfigurationError: If the PromptComposer is missing or
                prompt composition yields no system prompt (RULE-11).
        """
        novel = await self._get_novel_or_raise(novel_id, user_id)

        # ADR-086 L34: first-use lazy resolve — the uid-scoped novel guard
        # above stays ahead of the cascade (eager-world precedence; the
        # ADR-086 planning guard ruling). Degradation is service policy
        # (Pattern M-graceful): a missing AI provider is logged (the eager
        # factory's event, byte-identical) and leaves the config unset, so
        # the ``no_model_config`` outcome below fires exactly as it did
        # when the eager factory swallowed this error at wiring time —
        # timing only. The resolve is attempted at most once per instance.
        try:
            await self.ensure_resolved()
        except ConfigurationError:
            logger.info("no_ai_provider_configured", novel_id=str(novel_id))

        if self._config is None:
            # Sanctioned degraded state (AI-optional feature): the graceful
            # resolve found no provider configured (RULE-11 — loud about
            # it via the log, deterministic via this outcome).
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
        # PromptComposer (RULE-02 / ADR-054 D1) and run the agent with
        # the prepared triple — assembly split to
        # ``_story_suggest_support.py`` (RULE-04).
        composed_prompt = await compose_story_suggest_prompt(
            composer=self._composer,
            outline_repo=self._outline_repo,
            invocation_pipeline=self._invocation_pipeline,
            novel=novel,
            novel_id=novel_id,
            user_id=user_id,
            request=request,
            language=language,
            scene_repo=self._scene_repo,
        )
        result = await run_story_suggest_agent(
            registry=self._registry,
            config=self._config,
            run_limit_resolver=self._run_limit_resolver,
            composed_prompt=composed_prompt,
            novel=novel,
            request=request,
            language=language,
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
