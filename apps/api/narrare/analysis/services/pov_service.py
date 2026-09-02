"""POV analysis service — orchestrates POVDetectionAgent for POV detection.

Handles HTTP-layer concerns: fetching chapter content, resolving language,
access control, and character resolution from KB.  Delegates AI analysis to
``POVDetectionAgent`` via ``ModelRegistry``.

No DB queries — delegated to repositories (RULE-06).
LLM calls go through ``POVDetectionAgent`` via ``ModelRegistry`` (RULE-01b).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.analysis._invocation_compose import compose_analysis_invocation_prompt
from narrare.analysis.services.pov_mapper import build_deps, map_output_to_result
from narrare_core.analysis.types import POVResult
from narrare_core.llm.intents import LLMIntent
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.agents.pov_agent import POVDetectionAgent
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ModelRegistry
    from narrare_core.llm.model_config import ResolvedModelConfig
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
        model_config: Resolved model configuration (provider, model_id,
            temperature, max_tokens).
        composer: PromptComposer for Mode 1 (composer-driven) system prompt
            assembly (ADR-048). Builds the feature-specific POV system prompt
            from the bundled ``analysis/{lang}/pov`` template.
        invocation_pipeline: Optional pipeline for invocation evidence.
        api_key: Optional per-user provider API key override (model-routing
            cascade) — injected into ``ModelRegistry.get_model``.
        base_url: Optional per-user provider base URL override.
    """

    def __init__(
        self,
        *,
        chapter_repo: ChapterRepository,
        novel_repo: NovelRepository,
        kb_repo: KBRepository,
        model_registry: ModelRegistry,
        model_config: ResolvedModelConfig,
        composer: PromptComposer,
        invocation_pipeline: InvocationPipeline | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo
        self._kb_repo = kb_repo
        self._model_registry = model_registry
        self._model_config = model_config
        self._composer = composer
        self._invocation_pipeline = invocation_pipeline
        self._api_key = api_key
        self._base_url = base_url

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
            agent = await self._get_agent(system_prompt=composed.system)
            deps = build_deps(
                text=combined_text,
                language=effective_language,
                known_characters=known_characters,
                pov_type_hint=pov_type,
            )
            output = await agent.run(
                prompt="Analyze POV consistency in this text.",
                deps=deps,
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

    async def _get_agent(self, system_prompt: str | None = None) -> POVDetectionAgent:
        """Construct a ``POVDetectionAgent`` from the model registry.

        Args:
            system_prompt: Composed feature-specific system prompt (Mode 1,
                ADR-048). When ``None`` the agent falls back to Capabilities only.

        Returns:
            A fresh agent per call — agents are lightweight wrappers
            around the model.
        """
        from narrare_core.agents.pov_agent import POVDetectionAgent

        model = await self._model_registry.get_model(
            self._model_config,
            api_key=self._api_key,
            base_url=self._base_url,
        )
        return POVDetectionAgent(model=model, system_prompt=system_prompt)
