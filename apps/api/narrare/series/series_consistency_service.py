"""SeriesConsistencyService — canon-contradiction detection (Spec 4 Task 2).

Business logic only (RULE-06): no SQL, no HTTP. Delegates the Canon fetch to
``KBRepository.find_canon_for_series`` (Spec 1), the chapter fetch to
``ChapterRepository.list_by_novel``, and the compose-prepare-run invocation
assembly to
:mod:`narrare.series._series_consistency_invocation` (governed prompt via
:mod:`narrare.series.series_consistency_prompt`, runtime-content formatting
via :mod:`narrare.series.series_consistency_runtime_content`, LLM call via
the :class:`~narrare_core.agents.series_consistency_agent.SeriesConsistencyAgent`
— Task 1; agents are the primary LLM surface, RULE-01b). The Canon entries +
chapter texts flow as runtime content in the agent run prompt (user channel,
RULE-02a category 3 — mirroring how analysis agents receive the analysed
passage and how ``BandSummaryAgent`` receives chapter summaries).

Model acquisition (ADR-086 L26): the per-user routing cascade is injected
as a ``ModelResolution`` and resolved on first use inside :meth:`check_novel`
— after the ownership gates, before the graceful early exit — never at
construction (422-before-400 ordering for invalid request bodies).

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
    :mod:`narrare.series._series_consistency_invocation` — invocation assembly.
    ADR-075 — Series Foundation (Canon KB scope).
    ADR-086 — lazy model resolution (L26).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from narrare.series._series_consistency_invocation import run_series_consistency_invocation
from narrare.series.series_consistency_schemas import SeriesConsistencyCheckResponse
from narrare_core.agents.series_consistency_agent import SeriesConsistencyAgent
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.shared.errors import (
    ConfigurationError,
    ForbiddenError,
    NotFoundError,
    WritingError,
)

if TYPE_CHECKING:
    import uuid
    from collections.abc import Callable

    from narrare._app.dependencies_services import ModelResolution
    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.series.contracts import SeriesRepositoryProtocol
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.model_routing import ResolvedModel
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
        model_resolution: ModelResolution,
        composer: PromptComposer | None = None,
        agent_factory: Callable[..., SeriesConsistencyAgent] | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
        run_limit_resolver: DefaultRunLimitResolver | None = None,
    ) -> None:
        """Initialise the service with all dependencies injected (RULE-07).

        Args:
            series_repo: Series lookup (ownership verification).
            novel_repo: Novel lookup (verify membership + resolve metadata).
            chapter_repo: Chapter prose fetch (``list_by_novel``).
            kb_repo: Canon fetch (``find_canon_for_series`` — Spec 1).
            registry: Model registry for resolving the LLM model instance.
            model_resolution: Lazy per-user model resolution (ADR-086) —
                the routing cascade (ANALYSE, ``project_id=None``) resolves
                on first use, never at construction.
            composer: PromptComposer for the governed series_consistency system
                prompt (None → ConfigurationError at check time).
            agent_factory: Callable ``(model, system_prompt) -> Agent``.
                Defaults to the real constructor; tests inject a Fake.
            invocation_pipeline: Optional InvocationPipeline for evidence.
            run_limit_resolver: Optional ADR-045 run-limit resolver; defaults to
                ``DefaultRunLimitResolver`` (Task 3 wiring).
        """
        self._series_repo = series_repo
        self._novel_repo = novel_repo
        self._chapter_repo = chapter_repo
        self._kb_repo = kb_repo
        self._registry = registry
        self._model_resolution = model_resolution
        self._resolved: ResolvedModel | None = None
        self._composer = composer
        self._agent_factory = agent_factory or _default_agent_factory
        self._invocation_pipeline = invocation_pipeline
        self._run_limit_resolver = run_limit_resolver or DefaultRunLimitResolver()

    async def ensure_resolved(self) -> ResolvedModel:
        """Resolve the per-user model routing once; idempotent (ADR-086).

        First call resolves via the injected ``ModelResolution`` and
        caches the triple; repeat calls return the cached value without
        re-running the cascade. Errors propagate loudly and are never
        cached (RULE-11): ``ConfigurationError`` (``NO_AI_PROVIDER``)
        surfaces as a 400 on this AI-mandatory endpoint.
        """
        if self._resolved is None:
            self._resolved = await self._model_resolution.resolve()
        return self._resolved

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

        # ADR-086 L26: first-use lazy resolve — the ownership gates above
        # stay ahead of resolution (eager-world precedence), and resolution
        # precedes the Canon/chapter fetches and the graceful no-input early
        # exit, so an unconfigured provider stays a loud 400 even when the
        # check would degrade to an empty result. The resolved triple flows
        # into the invocation assembly exactly as the eager factory passed
        # it (timing-only migration: WHAT unchanged — the eager resolve
        # applied no sampling overrides — only WHEN).
        resolved_model = await self.ensure_resolved()

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

        if self._composer is None:
            raise ConfigurationError(
                "PromptComposer is not configured for series-consistency analysis.",
                code="NO_COMPOSER",
            )

        language = novel.writing_language or series.writing_language or "en"

        try:
            # 6-8. Compose the governed prompt (Mode 1), prepare the
            # coherent model triple, and run the agent exactly once —
            # the invocation assembly lives in the dedicated module
            # (RULE-04/RULE-06; moved for the size limit the ADR-086
            # ensure_resolved addition crossed).
            result = await run_series_consistency_invocation(
                registry=self._registry,
                agent_factory=self._agent_factory,
                composer=self._composer,
                invocation_pipeline=self._invocation_pipeline,
                run_limit_resolver=self._run_limit_resolver,
                resolved_model=resolved_model,
                novel_title=novel.title,
                genre=novel.genre,
                language=language,
                novel_id=novel_id,
                user_id=user_id,
                canon_entries=canon_entries,
                chapter_texts=chapter_texts,
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
