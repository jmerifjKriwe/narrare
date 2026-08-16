"""SeriesDriftPersistenceService — store-on-run + stale-aware snapshot read
(SERIES-004 Slice 6, C2 — design §5).

Business logic only (RULE-06): no SQL, no HTTP. This service WRAPS the two
UNCHANGED run services (``SeriesConsistencyService`` /
``SeriesVoiceDriftService`` — both at their RULE-04 file-size ceilings and
kept byte-identical for zero regression, the ADR-079 Decision-4 wrapper
pattern): each ``check_and_store_*`` runs the check, then persists the
result as its section of the composite ``series_drift_results`` document,
then returns the result verbatim.

Staleness (design §5): ``get_snapshot`` recomputes the chapter-texts
fingerprint with the SAME helper + read path used at save time
(``list_by_novel`` position order, non-empty-prose filter — identical to
``SeriesConsistencyService.check_novel`` step 4) and compares it with the
stored digest: ``stale=True`` means the band's texts changed after the last
completed write.

RULE-11 persistence degradation (documented ruling): the check's LLM cost is
already paid when the store runs, so a store failure logs a
``series_drift_persist_failed`` warning and the computed result is still
returned — mirroring ``SeriesVoiceDriftService._load_series_voice``'s
malformed-JSONB degradation. The GET path propagates errors normally.

Ownership (anti-enumeration, mirrors the run services): ``get_snapshot``
verifies series ownership + novel membership itself; the ``check_and_store_*``
methods inherit verification from the wrapped services (a 403 raises BEFORE
any store).

Pattern: router → this service → run services + repositories (RULE-07).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.analysis.schemas_author_voice_drift import AuthorVoiceDriftResponse
from narrare.series.series_consistency_schemas import SeriesConsistencyCheckResponse
from narrare.series.series_drift_schemas import SeriesDriftSnapshotResponse
from narrare_core.ai_invocation.correlation import fingerprint_chapter_texts
from narrare_core.shared.errors import ForbiddenError

if TYPE_CHECKING:
    import uuid

    from narrare.analysis.schemas_author_voice_drift import AuthorVoiceDriftRequest
    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.series.contracts import SeriesRepositoryProtocol
    from narrare.series.series_consistency_service import SeriesConsistencyService
    from narrare.series.series_drift_contracts import (
        DriftSection,
        SeriesDriftRepositoryProtocol,
    )
    from narrare.series.series_voice_drift_service import SeriesVoiceDriftService
    from narrare_core.series.schemas import Series

logger = structlog.get_logger(__name__)

_CONSISTENCY_SECTION: DriftSection = "consistency"
_VOICE_DRIFT_SECTION: DriftSection = "voice_drift"


class SeriesDriftPersistenceService:
    """Run-then-persist orchestration + stale-aware snapshot read (C2)."""

    def __init__(
        self,
        *,
        consistency_service: SeriesConsistencyService,
        voice_drift_service: SeriesVoiceDriftService,
        series_repo: SeriesRepositoryProtocol,
        novel_repo: NovelRepositoryProtocol,
        chapter_repo: ChapterRepositoryProtocol,
        drift_repo: SeriesDriftRepositoryProtocol,
    ) -> None:
        """Initialise with all dependencies injected (RULE-07).

        Args:
            consistency_service: The UNCHANGED canon-contradiction run service.
            voice_drift_service: The UNCHANGED series-voice-drift run service.
            series_repo: Series lookup (snapshot ownership verification).
            novel_repo: Novel lookup (membership verification).
            chapter_repo: Chapter prose fetch for the fingerprint.
            drift_repo: ``series_drift_results`` persistence (Task 4).
        """
        self._consistency_service = consistency_service
        self._voice_drift_service = voice_drift_service
        self._series_repo = series_repo
        self._novel_repo = novel_repo
        self._chapter_repo = chapter_repo
        self._drift_repo = drift_repo

    async def check_and_store_consistency(
        self, series_id: uuid.UUID, novel_id: uuid.UUID, user_id: uuid.UUID
    ) -> SeriesConsistencyCheckResponse:
        """Run the canon check, persist its section, return the result.

        Full contract on
        :meth:`SeriesDriftPersistenceServiceProtocol.check_and_store_consistency`.
        """
        result = await self._consistency_service.check_novel(series_id, novel_id, user_id)
        await self._store_section(
            series_id, novel_id, _CONSISTENCY_SECTION, result.model_dump(mode="json")
        )
        return result

    async def check_and_store_voice_drift(
        self,
        series_id: uuid.UUID,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        request: AuthorVoiceDriftRequest,
    ) -> AuthorVoiceDriftResponse:
        """Run the voice-drift check, persist its section, return the result.

        Full contract on
        :meth:`SeriesDriftPersistenceServiceProtocol.check_and_store_voice_drift`.
        """
        result = await self._voice_drift_service.check(series_id, novel_id, user_id, request)
        await self._store_section(
            series_id, novel_id, _VOICE_DRIFT_SECTION, result.model_dump(mode="json")
        )
        return result

    async def get_snapshot(
        self, series_id: uuid.UUID, novel_id: uuid.UUID, user_id: uuid.UUID
    ) -> SeriesDriftSnapshotResponse:
        """Read the persisted snapshot with the staleness flag.

        Full contract on
        :meth:`SeriesDriftPersistenceServiceProtocol.get_snapshot`.
        """
        # 1-2. Verify series ownership + novel membership (anti-enumeration).
        await self._verify_series_ownership(series_id, user_id)
        novel = await self._novel_repo.get(novel_id)
        if novel is None or novel.series_id != series_id:
            raise ForbiddenError("You do not have access to this series")

        # 3. No record -> the honest all-null snapshot (never an error).
        row = await self._drift_repo.get(novel_id)
        if row is None:
            return SeriesDriftSnapshotResponse(
                series_id=series_id,
                novel_id=novel_id,
                generated_at=None,
                stale=False,
                consistency=None,
                voice_drift=None,
            )

        # 4. Deserialize the stored sections back into the run-result models
        #    (RULE-22 — the document serializes THOSE models) + the stale
        #    verdict from ONE fingerprint computation path.
        document = row.result or {}
        consistency_doc = document.get(_CONSISTENCY_SECTION)
        voice_doc = document.get(_VOICE_DRIFT_SECTION)
        current_fingerprint = await self._compute_fingerprint(novel_id)
        return SeriesDriftSnapshotResponse(
            series_id=series_id,
            novel_id=novel_id,
            generated_at=row.generated_at,
            stale=row.input_fingerprint != current_fingerprint,
            consistency=(
                SeriesConsistencyCheckResponse.model_validate(consistency_doc)
                if consistency_doc is not None
                else None
            ),
            voice_drift=(
                AuthorVoiceDriftResponse.model_validate(voice_doc)
                if voice_doc is not None
                else None
            ),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _store_section(
        self,
        series_id: uuid.UUID,
        novel_id: uuid.UUID,
        section: DriftSection,
        document: dict[str, object],
    ) -> None:
        """Persist one run's section (RULE-11: degrade, never fail the check).

        The wrapped service already verified ownership + membership before
        this runs (a 403 raises before any store), and the LLM cost of the
        result is paid — a persistence failure logs a warning and the caller
        still returns the computed result to the author.
        """
        try:
            fingerprint = await self._compute_fingerprint(novel_id)
            await self._drift_repo.store_section(
                novel_id, section=section, document=document, fingerprint=fingerprint
            )
        except Exception as exc:  # documented degradation ruling (RULE-11)
            logger.warning(
                "series_drift_persist_failed",
                feature_id="series_drift_persistence",
                series_id=str(series_id),
                novel_id=str(novel_id),
                section=section,
                error=str(exc),
            )

    async def _compute_fingerprint(self, novel_id: uuid.UUID) -> str:
        """Fingerprint the band's chapter texts (ONE path for save + GET).

        Same read path and filter as ``SeriesConsistencyService.check_novel``
        step 4: ``list_by_novel`` (position-ordered per its contract), keeping
        only chapters with non-empty prose. Deterministic by construction.
        """
        chapters = await self._chapter_repo.list_by_novel(novel_id)
        texts = [c.content for c in chapters if (c.content or "").strip()]
        return fingerprint_chapter_texts(texts)

    async def _verify_series_ownership(self, series_id: uuid.UUID, user_id: uuid.UUID) -> Series:
        """Load a series and verify the caller owns it (anti-enumeration).

        Mirrors ``SeriesConsistencyService._verify_series_ownership``: a
        *missing* series and a *not-owned* series both surface as
        ``ForbiddenError`` (HTTP 403) — never 404.
        """
        series = await self._series_repo.get(series_id)
        if series is None or series.user_id != user_id:
            raise ForbiddenError("You do not have access to this series")
        return series
