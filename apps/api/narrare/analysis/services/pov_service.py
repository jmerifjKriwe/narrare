"""POV analysis service — orchestrates POVDetectionAgent for POV detection.

Handles HTTP-layer concerns: fetching chapter content, resolving language,
access control, and character resolution from KB.  Delegates AI analysis to
``POVDetectionAgent`` via ``ModelRegistry``.

No DB queries — delegated to repositories (RULE-06).
LLM calls go through ``POVDetectionAgent`` via ``ModelRegistry`` (RULE-01b).
Model routing resolves lazily at first use, after body validation (ADR-086).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

from narrare.analysis._invocation_compose import compose_analysis_invocation_prompt
from narrare.analysis.services.pov_mapper import build_deps, map_output_to_result
from narrare_core.analysis.types import POVResult
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from uuid import UUID

    from narrare._app.dependencies_services import ModelResolution
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.agents.pov_agent import POVDetectionAgent
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ModelRegistry
    from narrare_core.llm._prepared_call import PreparedModelCall
    from narrare_core.llm.model_routing import ResolvedModel
    from narrare_core.prompts import PromptComposer

logger = structlog.get_logger(__name__)


class POVService:
    """Implements ``POVServiceProtocol`` (see ``analysis/contracts.py``).

    Orchestrates: validate access → fetch chapters → resolve characters
    from KB → concatenate texts → run POVDetectionAgent → map output
    → return ``POVResult``.

    Args:
        chapter_repo: For fetching chapter content.
        novel_repo: For resolving novel language and access control.
        kb_repo: For resolving known character names from KB entries.
        model_registry: LLM model registry for constructing the
            ``POVDetectionAgent``.
        model_resolution: Lazy model-routing source (ADR-086): the
            per-user cascade (config + credentials) resolves at first
            use — after body validation — and is cached by the
            implementation; tests/overrides wire ``StaticModelResolution``.
        composer: PromptComposer for Mode 1 (composer-driven) system prompt
            assembly (ADR-048). Builds the feature-specific POV system prompt
            from the bundled ``analysis/{lang}/pov`` template.
        invocation_pipeline: Optional pipeline for invocation evidence.
    """

    def __init__(
        self,
        *,
        chapter_repo: ChapterRepository,
        novel_repo: NovelRepository,
        kb_repo: KBRepository,
        model_registry: ModelRegistry,
        model_resolution: ModelResolution,
        composer: PromptComposer,
        invocation_pipeline: InvocationPipeline | None = None,
        run_limit_resolver: DefaultRunLimitResolver | None = None,
    ) -> None:
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo
        self._kb_repo = kb_repo
        self._model_registry = model_registry
        self._model_resolution = model_resolution
        self._composer = composer
        self._invocation_pipeline = invocation_pipeline
        self._run_limit_resolver = run_limit_resolver or DefaultRunLimitResolver()

    # -------------------------------------------------------------------
    # Public API — matches POVServiceProtocol
    # -------------------------------------------------------------------

    async def analyze(
        self,
        *,
        novel_id: UUID,
        chapter_ids: list[UUID],
        user_id: UUID,
        language: str = "en",
        pov_type: str | None = None,
    ) -> POVResult:
        """Analyze POV consistency for one or more chapters.

        Steps:
        1. Validate novel access (user owns it).
        2. Resolve effective language (override → novel default → ``"en"``).
        3. Fetch chapter contents (404 if any is missing).
        4. Fetch known character names from KB.
        5. Concatenate chapter texts.
        6. Run POVDetectionAgent with known characters + POV hint.
        7. Map ``POVDetectionOutput`` → ``POVResult``.

        Args:
            novel_id: The project containing the chapters.
            chapter_ids: Chapters to analyse (concatenated before analysis).
            user_id: The user requesting analysis (for access control).
            language: Language override. Defaults to ``"en"``.
            pov_type: Optional POV type hint. If ``None``, auto-detect.

        Returns:
            A ``POVResult`` with per-scene assignments, flagged violations,
            and distribution statistics.

        Raises:
            NotFoundError: If the novel or any chapter does not exist
                or is not accessible.
        """
        # ADR-086: first use — resolve the routing cascade after request-
        # body validation; ConfigurationError propagates loudly (RULE-11).
        resolved_model = await self._model_resolution.resolve()

        # 1. Novel access check + language resolution
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        effective_language = language if language != "auto" else (novel.writing_language or "en")

        # 2. Fetch chapters and concatenate content
        contents: list[str] = []
        for chapter_id in chapter_ids:
            chapter = await self._chapter_repo.get_by_id(chapter_id, novel_id)
            if chapter is None:
                raise NotFoundError("Chapter", identifier=str(chapter_id))
            contents.append(chapter.content or "")

        combined_text = "\n\n".join(contents)

        if not combined_text.strip():
            logger.info(
                "pov_analysis_skipped_empty",
                novel_id=str(novel_id),
                chapter_count=len(chapter_ids),
            )
            return POVResult(
                scenes=[],
                issues=[],
                pov_distribution={},
                switch_count=0,
                analysis_type="",
            )

        # 3. Fetch known character names from KB
        known_characters = await self._resolve_characters(novel_id)

        # 4. Compose prompt via Mode 1 (composer-driven, ADR-048) with
        # correlated evidence + enrichment. Falls back to direct composition
        # on pipeline failure so analysis proceeds regardless of
        # evidence/enrichment issues.
        composed = await compose_analysis_invocation_prompt(
            composer=self._composer,
            invocation_pipeline=self._invocation_pipeline,
            feature_id="analysis_pov",
            intent=LLMIntent.ANALYSE,
            novel_id=novel_id,
            user_id=user_id,
            language=effective_language,
            mode="pov",
        )

        # 5. Run POVDetectionAgent with the composed feature-specific prompt
        try:
            agent, prepared = await self._prepare_agent(
                system_prompt=composed.system, resolved_model=resolved_model
            )
            deps = build_deps(
                text=combined_text,
                language=effective_language,
                known_characters=known_characters,
                pov_type_hint=pov_type,
            )
            output = await agent.run(
                prompt="Analyze POV consistency in this text.",
                deps=deps,
                model_settings=prepared.model_settings,
                usage_limits=prepared.usage_limits,
            )
        except Exception as exc:
            logger.error(
                "pov_agent_failed",
                novel_id=str(novel_id),
                chapter_count=len(chapter_ids),
                error=str(exc),
                exc_info=True,
            )
            raise

        # 6. Map POVDetectionOutput → POVResult
        result = map_output_to_result(output)

        logger.info(
            "pov_analysis_complete",
            novel_id=str(novel_id),
            chapter_count=len(chapter_ids),
            language=effective_language,
            scene_count=len(result.scenes),
            issue_count=len(result.issues),
            analysis_type=result.analysis_type,
        )

        return result

    # -------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------

    async def _resolve_characters(self, novel_id: UUID) -> list[str]:
        """Fetch character names from KB entries.

        Args:
            novel_id: The novel to look up characters for.

        Returns:
            List of character names, or empty list if none found.
        """
        entries, _ = await self._kb_repo.list_entries(
            novel_id=novel_id,
            entity_type="character",
        )
        return [e.name for e in entries]

    async def _prepare_agent(
        self,
        system_prompt: str | None,
        resolved_model: ResolvedModel,
    ) -> tuple[POVDetectionAgent, PreparedModelCall]:
        """Prepare the model call and construct a ``POVDetectionAgent``.

        Args:
            system_prompt: Composed feature-specific system prompt (Mode 1,
                ADR-048). When ``None`` the agent falls back to Capabilities only.
            resolved_model: Routing-cascade resolution (ADR-086) threaded
                from first use in ``analyze``.

        Returns:
            A fresh agent per call — agents are lightweight wrappers
            around the model — plus the coherent ``PreparedModelCall``
            triple (Task 6a-2 single assembly point): the agent's
            ``run`` must receive ``prepared.model_settings`` and
            ``prepared.usage_limits``.
        """
        from narrare_core.agents.pov_agent import POVDetectionAgent

        resolved = self._run_limit_resolver.resolve(
            config=resolved_model.config, budget=None, invocation_id=uuid4()
        )
        prepared = await self._model_registry.prepare(
            resolved_model.config,
            intent=LLMIntent.ANALYSE,
            usage_limits=resolved.usage_limits,
            api_key=resolved_model.api_key,
            base_url=resolved_model.base_url,
        )
        return POVDetectionAgent(model=prepared.model, system_prompt=system_prompt), prepared
