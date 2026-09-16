"""Character arc generation service — calls CharacterArcAgent.

Prompt resolution is Mode 1 (composer-driven) per ADR-054 D1/D7/D8: the
service resolves its system prompt via
``compose_invocation(composer=..., prompt_context=PromptContext(mode="character_arc"),
intent=LLMIntent.PLAN)``
and passes the composed system prompt to the ``CharacterArcAgent`` constructor
(pydantic-ai binds ``system_prompt`` at construction, not at run-time).

The previous inline f-string feature prompt and the false ADR-048 Mode 2
``_CHARACTER_ARC_INJECTION`` declaration were removed. Invocation-composition
errors now propagate (RULE-11) instead of being silently swallowed.

Pattern: Service → PromptComposer (RULE-02) → Core Agent (RULE-01b).

Model acquisition (ADR-086 L20): the per-user PLAN routing cascade is
injected as a ``ModelResolution`` and resolved on first use inside
``generate_character_arc`` — after the uid-scoped novel guard, never at
construction (the eager factory resolved at wiring time). Graceful
degradation (AI-optional feature) is service policy: a missing provider
is logged and degrades to the preserved ``no_model_config`` outcome —
the eager factory's wiring-time swallow, moved past validation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

from narrare.planning._event_render import render_confirmed_events
from narrare.planning.schemas import ArcPhaseResponse, CharacterArcRequest, CharacterArcResponse
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare._app.dependencies_services import ModelResolution
    from narrare.novels.repository import NovelRepository
    from narrare.planning.timeline_repository import TimelineEventRepository
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


class CharacterArcService:
    """Service for generating character development arcs.

    Takes a character name, current state, and goal state, then runs
    the CharacterArcAgent to produce a multi-phase arc analysis.

    The arc prompt is resolved through ``PromptComposer`` in Mode 1
    (ADR-054 D1): the governed
    ``_bundled/planning/en/character_arc/system.md`` template carries the
    task framing, project metadata, and character state variables. No inline
    f-string feature prompt is assembled in the service (RULE-02 / RULE-02a).

    Args:
        novel_repo: For novel existence + metadata (genre, language).
        model_registry: Shared LLM model registry.
        model_resolution: Lazy per-user model resolution (ADR-086 L20) —
            the PLAN routing cascade resolves on first use, never at
            construction. A ``ConfigurationError`` (no AI provider)
            degrades gracefully (AI-optional feature) at the entry point.
        composer: PromptComposer for resolving the governed character-arc
            system prompt via the cascade (RULE-02b / ADR-054 D1). Required
            for ``generate_character_arc``.
        event_repo: For the novel's confirmed plot-point events, rendered
            into the ``existing_plot_points`` prompt slot (§7 closed). When
            ``None`` or the novel has no such events the slot degrades to an
            empty string (RULE-11).
        invocation_pipeline: Optional pipeline for invocation evidence
            (Mode 1 prepare/finalize). Retained for DI-contract stability.
    """

    def __init__(
        self,
        novel_repo: NovelRepository,
        model_registry: ModelRegistry,
        model_resolution: ModelResolution,
        composer: PromptComposer | None = None,
        event_repo: TimelineEventRepository | None = None,
        *,
        invocation_pipeline: InvocationPipeline | None = None,
        run_limit_resolver: DefaultRunLimitResolver | None = None,
    ) -> None:
        self._novel_repo = novel_repo
        self._registry = model_registry
        self._model_resolution = model_resolution
        # Resolved triple — unset until first use; a failed (graceful)
        # resolve leaves it unset for the instance's lifetime.
        self._config: ResolvedModelConfig | None = None
        self._api_key: str | None = None
        self._base_url: str | None = None
        self._resolve_attempted = False
        self._composer = composer
        self._event_repo = event_repo
        self._invocation_pipeline = invocation_pipeline
        self._run_limit_resolver = run_limit_resolver or DefaultRunLimitResolver()

    async def ensure_resolved(self) -> None:
        """Resolve the per-user PLAN routing cascade once (ADR-086 L20).

        First call awaits the injected ``ModelResolution`` and caches the
        resolved triple into ``_config``/``_api_key``/``_base_url``; repeat
        calls are idempotent — the cascade runs at most once per instance,
        success or failure (eager-world timing also resolved exactly once
        per request). ``ConfigurationError`` propagates UNCHANGED: the
        graceful swallow is entry-point policy (see
        :meth:`generate_character_arc`), so this method stays honest about
        what happened (RULE-11).
        """
        if self._resolve_attempted:
            return
        self._resolve_attempted = True
        resolved = await self._model_resolution.resolve()
        self._config = resolved.config
        self._api_key = resolved.api_key
        self._base_url = resolved.base_url

    async def generate_character_arc(
        self,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        request: CharacterArcRequest,
    ) -> CharacterArcResponse:
        """Generate a character arc for the given character.

        Args:
            novel_id: UUID of the novel.
            user_id: UUID of the requesting user.
            request: Character name, current state, and goal state.

        Returns:
            Full character arc analysis with phases and relationships.

        Raises:
            NotFoundError: If the novel does not exist, or — the preserved
                degraded outcome — if no AI provider is configured
                (``no_model_config``; AI-optional feature, ADR-086 L20).
            ConfigurationError: If the PromptComposer is missing or prompt
                composition yields no system prompt (RULE-11).
        """
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        # ADR-086 L20: first-use lazy resolve — the uid-scoped novel guard
        # above stays ahead of the cascade (eager-world precedence; the
        # ADR-086 planning guard ruling). Degradation is service policy
        # (Pattern M-graceful): a missing AI provider is logged (the eager
        # factory's event, byte-identical) and leaves the triple unset, so
        # the ``no_model_config`` outcome below fires exactly as it did when
        # the eager factory swallowed this error at wiring time — timing
        # only. The resolve is attempted at most once per instance.
        try:
            await self.ensure_resolved()
        except ConfigurationError:
            logger.info("no_ai_provider_configured", novel_id=str(novel_id))

        if self._config is None:
            # Sanctioned degraded state (AI-optional feature): the graceful
            # resolve above found no provider configured (RULE-11 — loud
            # about it via the log, deterministic via this outcome).
            raise NotFoundError("Model config", identifier="no_model_config")

        if self._composer is None:
            # Defensive: the factory always wires a composer, but fail loudly
            # (RULE-11) rather than silently falling back to inline assembly.
            raise ConfigurationError(
                "PromptComposer is not configured for character arc generation.",
                code="NO_COMPOSER",
            )

        language = novel.writing_language or "en"

        # Resolve the governed character-arc system prompt via PromptComposer
        # (RULE-02 / ADR-054 D1). The template
        # ``_bundled/planning/en/character_arc/system.md`` carries the task
        # framing, project metadata, and character state variables.
        from narrare._app.invocation_context import build_invocation_context
        from narrare_core.agents.character_arc_agent import CharacterArcAgent, CharacterArcDeps
        from narrare_core.ai_invocation import compose_invocation
        from narrare_core.llm.intents import LLMIntent
        from narrare_core.prompts.context import PromptContext

        # Confirmed plot-point events give the arc model the novel's
        # established plot beats (§7 closed; rendered from the event_repo).
        # Empty-but-valid when none exist or no repo is wired (RULE-11).
        existing_plot_points = await render_confirmed_events(
            self._event_repo, novel_id, event_type="plot_point"
        )

        ctx = PromptContext(
            language=language,
            writing_language=language,
            project_title=novel.title,
            genre=novel.genre or "",
            mode="character_arc",
            extra={
                "character_name": request.character_name,
                "character_current_state": request.character_current_state,
                "character_goal_state": request.character_goal_state,
                "existing_plot_points": existing_plot_points,
            },
        )

        invocation_context = build_invocation_context(
            feature_id="planning_character_arc",
            intent=LLMIntent.PLAN,
            project_id=novel_id,
        )
        invocation = await compose_invocation(
            invocation_pipeline=self._invocation_pipeline,
            invocation_context=invocation_context,
            composer=self._composer,
            prompt_context=ctx,
            intent=LLMIntent.PLAN,
        )
        composed_prompt = invocation.composed_prompt
        # Mode 1 guarantees composed_prompt is set; the guard documents the
        # invariant and satisfies the type-checker (RULE-11: no silent None).
        if composed_prompt is None:  # pragma: no cover - Mode 1 invariant
            raise ConfigurationError(
                "Prompt composition produced no system prompt for character arc.",
                code="COMPOSITION_EMPTY",
            )

        # Single assembly point (Task 6b — Task 4/5 pattern): model + intent-aware
        # runtime settings + usage limits as one coherent triple, so the thinking
        # policy actually reaches this call.
        resolved = self._run_limit_resolver.resolve(
            config=self._config, budget=None, invocation_id=uuid4()
        )
        prepared = await self._registry.prepare(
            self._config,
            intent=LLMIntent.PLAN,
            usage_limits=resolved.usage_limits,
            api_key=self._api_key,
            base_url=self._base_url,
        )

        # Build agent dependencies
        deps = CharacterArcDeps(
            character_name=request.character_name,
            character_current_state=request.character_current_state,
            character_goal_state=request.character_goal_state,
            genre=novel.genre or "",
            language=language,
        )

        # pydantic-ai binds ``system_prompt`` at agent construction, so the
        # composed system prompt is supplied to the constructor (not to
        # ``run()``). The character data additionally flows as the run prompt
        # (runtime data, RULE-02a category 3) when the template has no
        # "## First Message".
        agent = CharacterArcAgent(model=prepared.model, system_prompt=composed_prompt.system)
        result = await agent.run(
            prompt=composed_prompt.user
            or (
                f"Character: {request.character_name}\n"
                f"Current state: {request.character_current_state}\n"
                f"Goal state: {request.character_goal_state}"
            ),
            deps=deps,
            model_settings=prepared.model_settings,
            usage_limits=prepared.usage_limits,
        )

        # Map core output to API response
        return CharacterArcResponse(
            character_name=result.character_name,
            starting_state=result.starting_state,
            ending_state=result.ending_state,
            arc_type=result.arc_type,
            phases=[ArcPhaseResponse(**p.model_dump()) for p in result.phases],
            key_relationships=result.key_relationships,
            internal_conflict=result.internal_conflict,
            resolution=result.resolution,
        )
