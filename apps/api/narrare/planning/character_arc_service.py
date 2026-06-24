"""Character arc generation service — calls CharacterArcAgent.

Pattern: Service → Core Agent (RULE-01b). Model comes from ModelRegistry,
deps are built from the request + novel context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.planning.schemas import ArcPhaseResponse, CharacterArcRequest, CharacterArcResponse
from narrare_core.ai_invocation import ManualInjectionDeclaration
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare.novels.repository import NovelRepository
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry

logger = structlog.get_logger(__name__)

# ADR-048 Mode 2 declaration: CharacterArcAgent composes its prompt internally
# from CharacterArcDeps (character state, goal, genre, language).
_CHARACTER_ARC_INJECTION = ManualInjectionDeclaration(
    reason=(
        "CharacterArcAgent composes its prompt internally from CharacterArcDeps "
        "(character name, current/goal state, genre, language)."
    ),
    variables=(
        "character_name",
        "character_current_state",
        "character_goal_state",
        "genre",
        "language",
    ),
    injection_mechanism="agent_deps",
)


class CharacterArcService:
    """Service for generating character development arcs.

    Takes a character name, current state, and goal state, then runs
    the CharacterArcAgent to produce a multi-phase arc analysis.

    Args:
        novel_repo: For novel existence + metadata (genre, language).
        model_registry: Shared LLM model registry.
        model_config: Resolved model config (provider + model ID).
        api_key: Optional API key override.
        base_url: Optional base URL override.
    """

    def __init__(
        self,
        novel_repo: NovelRepository,
        model_registry: ModelRegistry,
        model_config: ResolvedModelConfig | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._novel_repo = novel_repo
        self._registry = model_registry
        self._config = model_config
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
        """
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        # Get model from registry — None config falls back to default
        from narrare_core.agents.character_arc_agent import CharacterArcAgent, CharacterArcDeps

        if self._config is None:
            raise NotFoundError("Model config", identifier="no_model_config")

        model = await self._registry.get_model(self._config)

        # Build agent dependencies
        deps = CharacterArcDeps(
            character_name=request.character_name,
            character_current_state=request.character_current_state,
            character_goal_state=request.character_goal_state,
            genre=novel.genre or "",
            language=novel.writing_language or "en",
        )

        # Run agent
        agent = CharacterArcAgent(model=model)
        from narrare._app.invocation_context import build_invocation_context
        from narrare_core.ai_invocation import compose_invocation
        from narrare_core.llm.intents import LLMIntent

        invocation_context = build_invocation_context(
            feature_id="planning_character_arc",
            intent=LLMIntent.PLAN,
            project_id=novel_id,
        )
        try:
            await compose_invocation(
                invocation_pipeline=self._invocation_pipeline,
                invocation_context=invocation_context,
                manual_injection=_CHARACTER_ARC_INJECTION,
            )
        except Exception:
            logger.warning(
                "invocation_composition_failed",
                feature_id="planning_character_arc",
                exc_info=True,
            )
        result = await agent.run(
            prompt=f"Generate a character arc for {request.character_name} in {novel.title}",
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
