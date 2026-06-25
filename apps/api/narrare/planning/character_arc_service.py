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
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.planning.schemas import ArcPhaseResponse, CharacterArcRequest, CharacterArcResponse
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare.novels.repository import NovelRepository
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
        model_config: Resolved model config (provider + model ID).
        composer: PromptComposer for resolving the governed character-arc
            system prompt via the cascade (RULE-02b / ADR-054 D1). Required
            for ``generate_character_arc``.
        api_key: Optional API key override.
        base_url: Optional base URL override.
        invocation_pipeline: Optional pipeline for invocation evidence
            (Mode 1 prepare/finalize). Retained for DI-contract stability.
    """

    def __init__(
        self,
        novel_repo: NovelRepository,
        model_registry: ModelRegistry,
        model_config: ResolvedModelConfig | None = None,
        composer: PromptComposer | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._novel_repo = novel_repo
        self._registry = model_registry
        self._config = model_config
        self._composer = composer
        self._api_key = api_key
        self._base_url = base_url
        self._invocation_pipeline = invocation_pipeline

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
            NotFoundError: If the novel does not exist.
            ConfigurationError: If no AI provider or PromptComposer is configured.
        """
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        if self._config is None:
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
                # No plot-point assembler wired for this call path yet;
                # declared explicitly (not silently omitted) so the template's
                # variable substitution succeeds (precedent: timeline_analysis).
                "existing_plot_points": "",
                "culture_guidelines": "",
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

        model = await self._registry.get_model(self._config)

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
        agent = CharacterArcAgent(model=model, system_prompt=composed_prompt.system)
        result = await agent.run(
            prompt=composed_prompt.user
            or (
                f"Character: {request.character_name}\n"
                f"Current state: {request.character_current_state}\n"
                f"Goal state: {request.character_goal_state}"
            ),
            deps=deps,
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
