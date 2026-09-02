"""SeriesConsistencyService — canon-contradiction detection (Spec 4 Task 2).

Business logic only (RULE-06): no SQL, no HTTP. Delegates the Canon fetch to
``KBRepository.find_canon_for_series`` (Spec 1), the chapter fetch to
``ChapterRepository.list_by_novel``, the governed system prompt to
:mod:`narrare.series.series_consistency_prompt`, the runtime-content formatting
to :mod:`narrare.series.series_consistency_runtime_content`, and the LLM call
to the :class:`~narrare_core.agents.series_consistency_agent.SeriesConsistencyAgent`
(Task 1) — agents are the primary LLM surface (RULE-01b). The Canon entries +
chapter texts flow as runtime content in the agent run prompt (user channel,
RULE-02a category 3 — mirroring how analysis agents receive the analysed
passage and how ``BandSummaryAgent`` receives chapter summaries).

This is the *novel-vs-series-Canon* check (cross-novel). It is distinct from
the per-novel :class:`~narrare.kb.consistency_service.KBConsistencyService`
(CONS-001, which checks *within* a novel).

RULE-11 graceful degradation: a series with no Canon entries OR a novel with no
chapter prose yields an empty-conflicts result **without an LLM call** (the
agent has nothing to check). A non-empty Canon + prose runs the agent exactly
once (``1 LLM call per check`` — Spec 4 design D1).

Testability (ADR-030 — Fake-based): the agent is injectable via
``agent_factory`` (default → real ``SeriesConsistencyAgent``) so unit tests
supply a fake agent whose ``.run()`` returns a controlled
``SeriesConsistencyOutput`` (mirrors ``BandSummaryService``).

Pattern: Service → PromptComposer (RULE-02) → Core Agent (RULE-01b)
         → Repositories (RULE-07, no raw column access).

See:
    :mod:`narrare.series.series_consistency_contracts` — the Protocol.
    :mod:`narrare.series.series_consistency_schemas` — request/response DTOs.
    :mod:`narrare.series.series_consistency_prompt` — governed prompt resolution.
    :mod:`narrare.series.series_consistency_runtime_content` — runtime formatting.
    ADR-075 — Series Foundation (Canon KB scope).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from narrare.series.series_consistency_prompt import resolve_series_consistency_prompt
from narrare.series.series_consistency_runtime_content import (
    format_canon_entries,
    format_run_prompt,
)
from narrare.series.series_consistency_schemas import SeriesConsistencyCheckResponse
from narrare_core.agents.series_consistency_agent import SeriesConsistencyAgent
from narrare_core.agents.series_consistency_types import SeriesConsistencyDeps
from narrare_core.shared.errors import (
    ConfigurationError,
    ForbiddenError,
    NotFoundError,
    WritingError,
)

if TYPE_CHECKING:
    import uuid
    from collections.abc import Callable

    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.series.contracts import SeriesRepositoryProtocol
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.series.schemas import Series

logger = structlog.get_logger(__name__)


def _default_agent_factory(model: Any, system_prompt: str | None = None) -> SeriesConsistencyAgent:
    """Production agent factory (overridable in tests for Fake injection)."""
    return SeriesConsistencyAgent(model=model, system_prompt=system_prompt)


class SeriesConsistencyService:
    """Detects canon contradictions between a band's chapters and the series Canon.

    One operation backs the Series Consistency API (Task 2):

    - ``check_novel`` — verify novel in series → fetch Canon entries + chapters
      → run :class:`SeriesConsistencyAgent` (1 LLM call) → return conflicts.

    All dependencies are injected (RULE-07). Ownership + novel-membership are
    verified inside the service (mirrors :class:`SeriesVoiceService`) so the
    contract is enforced even when called from non-request contexts.
    """

    def __init__(
        self,
        *,
        series_repo: SeriesRepositoryProtocol,
        novel_repo: NovelRepositoryProtocol,
        chapter_repo: ChapterRepositoryProtocol,
        kb_repo: KBRepositoryProtocol,
        registry: ModelRegistry,
        config: ResolvedModelConfig | None = None,
        composer: PromptComposer | None = None,
        agent_factory: Callable[..., SeriesConsistencyAgent] | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """Initialise the service with all dependencies injected (RULE-07).

        Args:
            series_repo: Series lookup (ownership verification).
            novel_repo: Novel lookup (verify membership + resolve metadata).
            chapter_repo: Chapter prose fetch (``list_by_novel``).
            kb_repo: Canon fetch (``find_canon_for_series`` — Spec 1).
            registry: Model registry for resolving the LLM model instance.
            config: Resolved analysis model config (None → NotFoundError at
                check time, mirroring the analysis siblings).
            composer: PromptComposer for the governed series_consistency system
                prompt (None → ConfigurationError at check time).
            agent_factory: Callable ``(model, system_prompt) -> Agent``.
                Defaults to the real constructor; tests inject a Fake.
            invocation_pipeline: Optional InvocationPipeline for evidence.
            api_key: Optional per-user provider API key override (model-routing
                cascade) — injected into ``ModelRegistry.get_model``.
            base_url: Optional per-user provider base URL override.
        """
        self._series_repo = series_repo
        self._novel_repo = novel_repo
        self._chapter_repo = chapter_repo
        self._kb_repo = kb_repo
        self._registry = registry
        self._config = config
        self._composer = composer
        self._agent_factory = agent_factory or _default_agent_factory
        self._invocation_pipeline = invocation_pipeline
        self._api_key = api_key
        self._base_url = base_url

    async def check_novel(
        self,
        series_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> SeriesConsistencyCheckResponse:
        """Check a band's chapter prose against the series Canon KB.

        Full contract on
        :meth:`SeriesConsistencyServiceProtocol.check_novel`.
        """
        # 1. Verify series ownership (anti-enumeration, C1).
        series = await self._verify_series_ownership(series_id, user_id)

        # 2. Verify the novel belongs to this series (anti-enumeration: a
        #    missing novel and a mismatched novel both surface as 403).
        novel = await self._novel_repo.get(novel_id)
        if novel is None or novel.series_id != series_id:
            raise ForbiddenError("You do not have access to this series")

        # 3. Fetch Canon entries (Spec 1 — novel_id IS NULL series rows).
        canon_entries = await self._kb_repo.find_canon_for_series(series_id)

        # 4. Fetch chapters; keep only those with non-empty prose (the agent
        #    compares chapter TEXT against Canon — empty prose carries no
        #    signal). Ordered by position (list_by_novel contract).
        chapters = await self._chapter_repo.list_by_novel(novel_id)
        chapter_texts = [c.content for c in chapters if (c.content or "").strip()]

        # 5. RULE-11 graceful degradation: no Canon OR no prose → empty result
        #    without an LLM call (the agent has nothing to check).
        if not canon_entries or not chapter_texts:
            logger.info(
                "series_consistency_skipped_no_input",
                feature_id="series_consistency",
                series_id=str(series_id),
                novel_id=str(novel_id),
                canon_count=len(canon_entries),
                chapter_count=len(chapter_texts),
            )
            return SeriesConsistencyCheckResponse(
                series_id=series_id,
                novel_id=novel_id,
                conflicts=[],
                summary="No check performed: missing Canon entries or chapter prose.",
                canon_entry_count=len(canon_entries),
                chapter_count=len(chapter_texts),
            )

        if self._config is None:
            raise NotFoundError("Model config", identifier="no_model_config")
        if self._composer is None:
            raise ConfigurationError(
                "PromptComposer is not configured for series-consistency analysis.",
                code="NO_COMPOSER",
            )

        language = novel.writing_language or series.writing_language or "en"

        try:
            # 6. Resolve the governed series_consistency system prompt (RULE-02b)
            #    + format the runtime content (Canon + chapters, user channel).
            system_prompt = await resolve_series_consistency_prompt(
                self._composer,
                self._invocation_pipeline,
                novel_title=novel.title,
                genre=novel.genre,
                language=language,
                novel_id=novel_id,
                user_id=user_id,
            )
            formatted_canon = format_canon_entries(canon_entries)

            # 7. Resolve model + instantiate agent (RULE-01b: agents-first).
            #    The per-user provider credentials (model-routing cascade)
            #    are injected into the resolution call.
            model = await self._registry.get_model(
                self._config,
                api_key=self._api_key,
                base_url=self._base_url,
            )
            agent = self._agent_factory(model, system_prompt)

            # 8. Run the agent. Canon entries + chapter texts flow as runtime
            #    content in the user-channel prompt (RULE-02a category 3);
            #    SeriesConsistencyDeps carries the same data for validators.
            deps = SeriesConsistencyDeps(
                canon_entries=formatted_canon,
                chapter_texts=chapter_texts,
                novel_title=novel.title,
            )
            result = await agent.run(
                prompt=format_run_prompt(formatted_canon, chapter_texts),
                deps=deps,
            )
            logger.info(
                "series_consistency_complete",
                feature_id="series_consistency",
                series_id=str(series_id),
                novel_id=str(novel_id),
                conflict_count=len(result.conflicts),
            )
            return SeriesConsistencyCheckResponse(
                series_id=series_id,
                novel_id=novel_id,
                conflicts=list(result.conflicts),
                summary=result.summary,
                canon_entry_count=len(canon_entries),
                chapter_count=len(chapter_texts),
            )
        except NotFoundError, ConfigurationError, ForbiddenError:
            raise
        except Exception as exc:
            logger.error(
                "series_consistency_failed",
                feature_id="series_consistency",
                series_id=str(series_id),
                novel_id=str(novel_id),
                error=str(exc),
                exc_info=True,
            )
            raise WritingError("Series-consistency check failed") from exc

    # ------------------------------------------------------------------
    # Ownership helper (mirrors SeriesVoiceService._verify_series_ownership)
    # ------------------------------------------------------------------

    async def _verify_series_ownership(self, series_id: uuid.UUID, user_id: uuid.UUID) -> Series:
        """Load a series and verify the caller owns it (anti-enumeration).

        A *missing* series and a *not-owned* series both surface as
        ``ForbiddenError`` (HTTP 403) — never ``NotFoundError`` (404) — so
        series ids are not enumerable (C1 / IDOR fix).
        """
        series = await self._series_repo.get(series_id)
        if series is None or series.user_id != user_id:
            raise ForbiddenError("You do not have access to this series")
        return series
