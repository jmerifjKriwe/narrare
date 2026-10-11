"""Scene-plan AI service — governed draft/refine generators (PLAN-001 T8).

Zero-DB-write AI surface (spec §5.2/§6): ``draft`` proposes N scenes for a
chapter, ``refine`` rewrites one carried scene under the author's
instruction. Proposals return to the client and are applied via the
aggregate PUT — the single write path. No scene repository is injected
at all (the unused seam was removed, FU-e: refine carries the scene in
the request, draft needs no scene read, and writes never happen by
design); the chapter/novel repos are read-only ownership-guard inputs.
Enforcement: behavioral (contract tests assert zero write calls) plus
the mechanical source scan (``test_scene_ai_zero_write_static.py``).

Ownership: uid-scoped novel guard FIRST, then chapter-must-belong-to-novel
(foreign ≡ unknown → NotFoundError → 404) — gate-before-resolution ordering
(the planning guard ruling, ADR-086).

Model routing is lazy (ADR-086 L34): the per-user PLAN cascade resolves on
first use; ``ConfigurationError`` (no AI provider) degrades gracefully —
logged ``no_ai_provider_configured``, HTTP 200 with ``ai_unavailable=True``
(AI-optional feature, spec §5.2).

Prompts (RULE-02/02a): task framing comes from the governed PLAN modes
(``scene_plan_draft`` / ``scene_plan_refine``, T7) resolved via
``PromptComposer``; chapter/scene data is category-3 runtime data,
XML-wrapped in ``_scene_ai_support`` per RULE-22 §6 (spec §6.3, the
``_outline_render`` precedent). Agent: ``ScenePlanAgent`` (RULE-01b) run
with the prepared triple from ``ModelRegistry.prepare`` (19009e17
convention, ``build_remap_agent`` pattern).

Pattern: Service → PromptComposer (RULE-02) → Core Agent (RULE-01b).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.planning._scene_ai_support import (
    build_draft_run_prompt,
    build_refine_run_prompt,
    proposal_to_schema,
)
from narrare.planning.schemas_scenes import SceneDraftResponse, SceneRefineResponse
from narrare_core.agents.scene_plan_types import SceneDraftOutput, SceneRefineOutput
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare._app.dependencies_services import ModelResolution
    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.novels.models import Novel
    from narrare.planning.schemas_scenes import SceneDraftRequest, SceneRefineRequest
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.model_routing import ResolvedModel
    from narrare_core.prompts.composer import ComposedPrompt, PromptComposer

logger = structlog.get_logger(__name__)

_DRAFT_MODE = "scene_plan_draft"
_REFINE_MODE = "scene_plan_refine"


class SceneAIService:
    """AI draft/refine generators for a chapter's scene plans (zero-write)."""

    def __init__(
        self,
        chapter_repo: ChapterRepositoryProtocol,
        novel_repo: NovelRepositoryProtocol,
        model_registry: ModelRegistry,
        *,
        model_resolution: ModelResolution,
        composer: PromptComposer | None = None,
        run_limit_resolver: DefaultRunLimitResolver | None = None,
    ) -> None:
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo
        self._registry = model_registry
        self._model_resolution = model_resolution
        self._composer = composer
        self._run_limit_resolver = run_limit_resolver or DefaultRunLimitResolver()
        self._resolved: ResolvedModel | None = None
        self._resolve_attempted = False

    async def draft(
        self,
        chapter_id: uuid.UUID,
        request: SceneDraftRequest,
        user_id: uuid.UUID,
        *,
        novel_id: uuid.UUID,
    ) -> SceneDraftResponse:
        """Propose scenes for a chapter from the carried context (zero-write)."""
        novel = await self._guard(chapter_id, novel_id=novel_id, user_id=user_id)
        if not await self._resolve_gracefully(novel_id):
            return SceneDraftResponse(ai_unavailable=True)
        composed = await self._compose_system_prompt(_DRAFT_MODE)
        output = await self._run_agent(
            novel, composed, build_draft_run_prompt(request), SceneDraftOutput
        )
        if not isinstance(output, SceneDraftOutput):  # pragma: no cover — bound output_type
            raise ConfigurationError(
                "Scene draft returned an unexpected output shape.", code="SCENE_OUTPUT_SHAPE"
            )
        return SceneDraftResponse(proposals=[proposal_to_schema(scene) for scene in output.scenes])

    async def refine(
        self,
        chapter_id: uuid.UUID,
        request: SceneRefineRequest,
        user_id: uuid.UUID,
        *,
        novel_id: uuid.UUID,
    ) -> SceneRefineResponse:
        """Rewrite the carried scene under the instruction (zero-write)."""
        novel = await self._guard(chapter_id, novel_id=novel_id, user_id=user_id)
        if not await self._resolve_gracefully(novel_id):
            return SceneRefineResponse(ai_unavailable=True)
        composed = await self._compose_system_prompt(_REFINE_MODE)
        output = await self._run_agent(
            novel, composed, build_refine_run_prompt(request), SceneRefineOutput
        )
        if not isinstance(output, SceneRefineOutput):  # pragma: no cover — bound output_type
            raise ConfigurationError(
                "Scene refine returned an unexpected output shape.", code="SCENE_OUTPUT_SHAPE"
            )
        return SceneRefineResponse(proposal=proposal_to_schema(output.scene))

    # ------------------------------------------------------------------
    # Guard + lazy resolution + run plumbing
    # ------------------------------------------------------------------

    async def _guard(
        self, chapter_id: uuid.UUID, *, novel_id: uuid.UUID, user_id: uuid.UUID
    ) -> Novel:
        """Uid-scoped novel guard, then chapter-must-belong-to-novel guard.

        Runs BEFORE the routing cascade (gate-before-resolution) so the
        resolver cannot auto-create ``project_settings`` for a foreign
        novel (foreign ≡ unknown, anti-enumeration → 404).
        """
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))
        chapter = await self._chapter_repo.get_by_id(chapter_id, novel_id)
        if chapter is None:
            raise NotFoundError("Chapter", identifier=str(chapter_id))
        return novel

    async def _resolve_gracefully(self, novel_id: uuid.UUID) -> bool:
        """First-use lazy PLAN resolve (ADR-086 L34); True when resolved.

        ``ConfigurationError`` (no AI provider) is entry-point policy
        here: logged with the house ``no_ai_provider_configured`` event,
        the outcome stays unset, and the caller degrades to
        ``ai_unavailable`` (AI-optional feature, RULE-11: loud via the
        log, deterministic via the outcome). At most one resolve attempt
        per instance.
        """
        if self._resolve_attempted:
            return self._resolved is not None
        self._resolve_attempted = True
        try:
            self._resolved = await self._model_resolution.resolve()
        except ConfigurationError:
            logger.info("no_ai_provider_configured", novel_id=str(novel_id))
        return self._resolved is not None

    async def _compose_system_prompt(self, mode: str) -> ComposedPrompt:
        """Resolve the governed PLAN-mode system prompt via the composer.

        Planning templates are EN-only (planning convention); project
        metadata rides the deps channel. Fail loudly (RULE-11) when the
        factory did not wire a composer — no inline fallback assembly.
        """
        if self._composer is None:
            raise ConfigurationError(
                "PromptComposer is not configured for scene-plan AI.",
                code="NO_COMPOSER",
            )
        from narrare_core.llm.intents import LLMIntent
        from narrare_core.prompts.context import PromptContext

        return await self._composer.build(LLMIntent.PLAN, PromptContext(language="en", mode=mode))

    async def _run_agent(
        self,
        novel: Novel,
        composed: ComposedPrompt,
        run_prompt: str,
        output_type: type[SceneDraftOutput] | type[SceneRefineOutput],
    ) -> SceneDraftOutput | SceneRefineOutput:
        """Prepare the run triple and execute ScenePlanAgent once.

        The composed system prompt binds at agent construction
        (pydantic-ai convention); the XML-wrapped category-3 data flows
        as the run prompt. The full prepared triple crosses the run
        boundary (``build_remap_agent`` pattern) — usage/cost events
        flow through the registry emission points (ADR-093/094).
        """
        from uuid import uuid4

        from narrare_core.agents.scene_plan_agent import ScenePlanAgent
        from narrare_core.agents.scene_plan_types import ScenePlanDeps
        from narrare_core.llm.intents import LLMIntent

        assert self._resolved is not None
        resolved_limits = self._run_limit_resolver.resolve(
            config=self._resolved.config, budget=None, invocation_id=uuid4()
        )
        prepared = await self._registry.prepare(
            self._resolved.config,
            intent=LLMIntent.PLAN,
            usage_limits=resolved_limits.usage_limits,
            api_key=self._resolved.api_key,
            base_url=self._resolved.base_url,
        )
        agent = ScenePlanAgent(
            model=prepared.model,
            output_type=output_type,
            system_prompt=composed.system,
        )
        deps = ScenePlanDeps(
            language=novel.writing_language or "en",
            genre=novel.genre or "",
            project_title=novel.title,
        )
        return await agent.run(
            prompt=run_prompt,
            deps=deps,
            model_settings=prepared.model_settings,
            usage_limits=prepared.usage_limits,
        )
