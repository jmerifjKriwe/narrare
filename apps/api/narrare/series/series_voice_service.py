"""Series Voice service — profiles a band's voice as the series voice (Spec 3 Task 2).

Business logic only (RULE-06): no SQL, no HTTP. Reuses the EXISTING
``AuthorVoiceAgent`` pipeline (ANAL-007 / ADR-074) — the same helpers
``AuthorVoiceService`` uses at novel level — and stores the result as
``SeriesSettings.author_voice`` (the Delta-model foundation, ADR-078) instead
of ``ProjectSettings.author_voice``. No new agent is created (RULE-01b: agents
are the LLM surface; this service orchestrates the existing one).

Model acquisition is LAZY (ADR-086): the factory wires a
``LazyModelResolution`` (VOICE cascade, ``project_id=None``); the service
resolves it on first use — :meth:`ensure_resolved` at the top of
:meth:`profile_from_novel`, after the ownership gates and BEFORE the chapter
fetch / graceful no-chapters exit, so an unconfigured provider stays a loud
400 on every path.

Invocation assembly (metrics → governed prompt → one agent call → profile)
lives in :mod:`narrare.series._series_voice_invocation` (RULE-04/RULE-06;
extracted for the size limit the ``ensure_resolved`` addition crossed).

The chapter-prose + precomputed metrics flow as runtime content in the agent
run prompt (user channel, RULE-02a category 3). No inline f-string feature
prompt is assembled here (RULE-02).

RULE-11 graceful degradation: a novel with no chapters → ``ValidationError``
(fail fast; the agent has nothing to profile — mirrors
``BandSummaryService.generate``).

Pattern: Service → PromptComposer (RULE-02) → Core Agent (RULE-01b)
         → SeriesRepository (RULE-07, no raw column access).

See:
    :mod:`narrare.series.series_voice_contracts` — the Protocol.
    :mod:`narrare.series._series_voice_invocation` — the invocation assembly.
    :mod:`narrare.analysis.author_voice_service` — the novel-level parallel.
    ADR-086 — lazy model resolution (this slice: L28).
    ADR-078 — Series Voice Hierarchy (Delta model).
    ADR-074 — Author Voice Storage Contract (the pipeline reused).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.series._series_voice_invocation import run_series_voice_invocation
from narrare_core.profiles.author_voice import AuthorVoiceProfile
from narrare_core.shared.errors import (
    ConfigurationError,
    ForbiddenError,
    ValidationError,
)

if TYPE_CHECKING:
    from uuid import UUID

    from narrare._app.dependencies_services import ModelResolution
    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.series.contracts import SeriesRepositoryProtocol
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.model_routing import ResolvedModel
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.series.schemas import Series

#: Minimum chapter count for a meaningful series-voice profile (mirrors
#: ``AuthorVoiceService.MIN_CHAPTERS_FOR_PROFILE``). Below this the service
#: surfaces a soft log warning but does NOT block (the user explicitly chose
#: this band; a thin profile is still useful as the Delta foundation).
MIN_CHAPTERS_FOR_SERIES_PROFILE: int = 3

logger = structlog.get_logger(__name__)


class SeriesVoiceService:
    """Series-voice profiling + management (Spec 3 Task 2).

    Takes a series + a member novel (the band), runs the ADR-074 hybrid
    pipeline over the novel's full chapter prose, assembles an
    :class:`AuthorVoiceProfile`, and persists it to
    ``SeriesSettings.author_voice`` via :meth:`SeriesRepository.update_settings`
    (no raw column access — RULE-07). Also supports manual override (set /
    clear) on the same single column.

    Constructor args are documented on :meth:`__init__`; the full method
    contracts live on
    :class:`narrare.series.series_voice_contracts.SeriesVoiceServiceProtocol`
    (RULE-03 SSOT).
    """

    def __init__(
        self,
        series_repo: SeriesRepositoryProtocol,
        novel_repo: NovelRepositoryProtocol,
        chapter_repo: ChapterRepositoryProtocol,
        model_registry: ModelRegistry,
        model_resolution: ModelResolution,
        composer: PromptComposer | None = None,
        *,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        """Initialise the service with all dependencies injected (RULE-07).

        Args:
            series_repo: Series + SeriesSettings persistence (ownership +
                ``author_voice`` read/write).
            novel_repo: Novel lookup (verify membership + resolve metadata).
            chapter_repo: Chapter prose fetch (``list_by_novel``).
            model_registry: Model registry for the AuthorVoiceAgent.
            model_resolution: Lazy per-user model resolution (ADR-086) —
                the routing cascade (VOICE, ``project_id=None``) resolves
                on first use, never at construction.
            composer: PromptComposer for the governed author_voice prompt
                (None → ConfigurationError at profile time).
            invocation_pipeline: Optional InvocationPipeline for evidence.
        """
        self._series_repo = series_repo
        self._novel_repo = novel_repo
        self._chapter_repo = chapter_repo
        self._registry = model_registry
        self._model_resolution = model_resolution
        self._resolved: ResolvedModel | None = None
        self._composer = composer
        self._invocation_pipeline = invocation_pipeline

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

    async def profile_from_novel(
        self,
        series_id: UUID,
        novel_id: UUID,
        user_id: UUID,
    ) -> AuthorVoiceProfile:
        """Profile a novel's voice → store as ``SeriesSettings.author_voice``.

        Full contract on
        :meth:`SeriesVoiceServiceProtocol.profile_from_novel`.
        """
        # 1. Verify series ownership (anti-enumeration, C1).
        series = await self._verify_series_ownership(series_id, user_id)

        # 2. Verify the novel belongs to this series (anti-enumeration: a
        #    missing novel and a mismatched novel both surface as 403).
        novel = await self._novel_repo.get(novel_id)
        if novel is None or novel.series_id != series_id:
            raise ForbiddenError("You do not have access to this series")

        # ADR-086 L28: first-use lazy resolve — the ownership gates above
        # stay ahead of resolution, and resolution precedes the chapter
        # fetch and the graceful no-chapters early exit, so an unconfigured
        # provider stays a loud 400 even when the profile would fail fast
        # below. The resolved triple flows into the invocation assembly
        # exactly as the eager factory passed it (timing-only migration:
        # WHAT unchanged — the eager resolve applied no sampling overrides
        # — only WHEN). The eager world's dead ``config=None →
        # NotFoundError`` branch is gone with the ctor swap: the required
        # ``ModelResolution`` makes an unresolvable cascade a loud
        # ``ConfigurationError`` at this line instead.
        resolved_model = await self.ensure_resolved()

        if self._composer is None:
            raise ConfigurationError(
                "PromptComposer is not configured for series-voice analysis.",
                code="NO_COMPOSER",
            )

        language = novel.writing_language or series.writing_language or "en"

        # 3. Fetch ALL chapter prose (series voice profiles the whole band).
        chapters = await self._chapter_repo.list_by_novel(novel_id)
        if not chapters:
            logger.info(
                "series_voice_no_chapters",
                feature_id="series_voice",
                series_id=str(series_id),
                novel_id=str(novel_id),
            )
            raise ValidationError(
                "Cannot profile series voice: the novel has no chapters to analyse"
            )

        # Soft warning below the recommended minimum (does NOT block).
        if len(chapters) < MIN_CHAPTERS_FOR_SERIES_PROFILE:
            logger.warning(
                "series_voice_below_chapter_minimum",
                feature_id="series_voice",
                chapter_count=len(chapters),
                minimum=MIN_CHAPTERS_FOR_SERIES_PROFILE,
            )

        # 4-8. Metrics → governed prompt → one agent call → profile
        #    assembly (the reused ADR-074 pipeline, verbatim order). The
        #    invocation assembly lives in the dedicated module (RULE-04/
        #    RULE-06; moved for the size limit the ADR-086 ensure_resolved
        #    addition crossed).
        profile = await run_series_voice_invocation(
            registry=self._registry,
            composer=self._composer,
            invocation_pipeline=self._invocation_pipeline,
            resolved_model=resolved_model,
            novel=novel,
            chapters=chapters,
            language=language,
            novel_id=novel_id,
            user_id=user_id,
        )

        # Persist the profile (RULE-07: via the repository).
        await self._series_repo.update_settings(
            series_id, {"author_voice": profile.model_dump(mode="json")}
        )
        logger.info(
            "series_voice_profiled",
            feature_id="series_voice",
            series_id=str(series_id),
            novel_id=str(novel_id),
            chapter_count=len(chapters),
        )
        return profile

    async def get(self, series_id: UUID, user_id: UUID) -> AuthorVoiceProfile | None:
        """Load the stored series voice profile (None when empty)."""
        await self._verify_series_ownership(series_id, user_id)
        settings = await self._series_repo.get_settings(series_id)
        if settings is None or settings.author_voice is None:
            return None
        try:
            return AuthorVoiceProfile.model_validate(settings.author_voice)
        except Exception as exc:  # malformed JSONB — graceful (RULE-11)
            logger.warning(
                "series_voice_malformed_json",
                series_id=str(series_id),
                error=str(exc),
            )
            return None

    async def update_override(
        self,
        series_id: UUID,
        user_id: UUID,
        override: dict[str, object],
    ) -> AuthorVoiceProfile:
        """Store a user-supplied voice profile (validated, then persisted)."""
        await self._verify_series_ownership(series_id, user_id)
        try:
            profile = AuthorVoiceProfile.model_validate(override)
        except Exception as exc:
            raise ValidationError("Override is not a valid author-voice profile") from exc
        await self._series_repo.update_settings(
            series_id, {"author_voice": profile.model_dump(mode="json")}
        )
        logger.info(
            "series_voice_override_set",
            feature_id="series_voice",
            series_id=str(series_id),
        )
        return profile

    async def clear_override(self, series_id: UUID, user_id: UUID) -> None:
        """Null ``SeriesSettings.author_voice``."""
        await self._verify_series_ownership(series_id, user_id)
        await self._series_repo.update_settings(series_id, {"author_voice": None})
        logger.info(
            "series_voice_override_cleared",
            feature_id="series_voice",
            series_id=str(series_id),
        )

    # ------------------------------------------------------------------
    # Ownership helper (mirrors SeriesService._verify_series_ownership)
    # ------------------------------------------------------------------

    async def _verify_series_ownership(self, series_id: UUID, user_id: UUID) -> Series:
        """Load a series and verify the caller owns it (anti-enumeration).

        A *missing* series and a *not-owned* series both surface as
        ``ForbiddenError`` (HTTP 403) — never ``NotFoundError`` (404) — so
        series ids are not enumerable (C1 / IDOR fix).
        """
        series = await self._series_repo.get(series_id)
        if series is None or series.user_id != user_id:
            raise ForbiddenError("You do not have access to this series")
        return series
