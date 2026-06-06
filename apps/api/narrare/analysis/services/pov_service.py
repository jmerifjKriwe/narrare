"""POV analysis service — orchestrates POVDetectionAgent for POV detection.

Handles HTTP-layer concerns: fetching chapter content, resolving language,
access control, and character resolution from KB.  Delegates AI analysis to
``POVDetectionAgent`` via ``ModelRegistry``.

No DB queries — delegated to repositories (RULE-06).
LLM calls go through ``POVDetectionAgent`` via ``ModelRegistry`` (RULE-01).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.analysis.services.pov_mapper import build_deps, map_output_to_result
from narrare_core.analysis.types import POVResult
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
        invocation_pipeline: Optional pipeline for invocation evidence.
    """

    def __init__(
        self,
        *,
        chapter_repo: ChapterRepository,
        novel_repo: NovelRepository,
        kb_repo: KBRepository,
        model_registry: ModelRegistry,
        model_config: ResolvedModelConfig,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo
        self._kb_repo = kb_repo
        self._model_registry = model_registry
        self._model_config = model_config
        self._invocation_pipeline = invocation_pipeline

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

        # 4. Run POVDetectionAgent
        try:
            # 4a. Record invocation evidence (ADR-040)
            from narrare._app.invocation_context import safe_record_evidence
            from narrare_core.llm.intents import LLMIntent

            await safe_record_evidence(
                self._invocation_pipeline,
                feature_id="analysis_pov",
                intent=LLMIntent.ANALYSE,
                user_id=user_id,
                project_id=novel_id,
                language=effective_language,
            )

            agent = self._get_agent()
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

        # 5. Map POVDetectionOutput → POVResult
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

    def _get_agent(self) -> POVDetectionAgent:
        """Construct a ``POVDetectionAgent`` from the model registry.

        Returns a fresh agent per call — agents are lightweight wrappers
        around the model.
        """
        from narrare_core.agents.pov_agent import POVDetectionAgent

        model = self._model_registry.get_model(self._model_config)
        return POVDetectionAgent(model=model)
