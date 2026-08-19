"""Store-on-run tests for SeriesDriftPersistenceService (C2 — design §5).

RULE-04 split (gate-forced): the snapshot-read tests live in
``test_series_drift_persistence_snapshot.py``; the shared builders/seam live
in ``_series_drift_persistence_test_helpers.py``. Test bodies are the
brief's, verbatim.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from structlog.testing import capture_logs

from narrare.analysis.schemas_author_voice_drift import (
    AuthorVoiceDriftRequest,
    AuthorVoiceDriftResponse,
)
from narrare.series.series_drift_contracts import (
    SeriesDriftPersistenceServiceProtocol,
)
from narrare.series.series_drift_persistence_service import (
    SeriesDriftPersistenceService,
)
from narrare_core.ai_invocation.correlation import fingerprint_chapter_texts
from narrare_core.shared.errors import ForbiddenError
from tests.fakes.fake_chapter_repo import FakeChapterRepository
from tests.fakes.fake_novel_repo import FakeNovelRepository
from tests.fakes.fake_series_drift_repo import FakeSeriesDriftRepository
from tests.fakes.fake_series_repo import FakeSeriesRepository
from tests.unit.api.series._series_drift_persistence_test_helpers import (
    make_chapter,
    make_consistency_response,
    make_persistence_service,
    seeded_drift_fakes,
)


class TestCheckAndStoreConsistency:
    async def test_runs_then_stores_its_section(self) -> None:
        owner = uuid.uuid4()
        series_repo, novel_repo, chapter_repo, drift_repo, series, novel = seeded_drift_fakes(owner)
        chapter_repo.seed(make_chapter(novel.id, "Prose one.", 1))
        response = make_consistency_response(series.id, novel.id)
        service = make_persistence_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            drift_repo=drift_repo,
            consistency_return=response,
        )

        result = await service.check_and_store_consistency(series.id, novel.id, owner)

        assert result is response  # returned verbatim
        drift_repo.assert_called(
            "store_section",
            novel_id=novel.id,
            section="consistency",
            document=response.model_dump(mode="json"),
        )

    async def test_store_fingerprint_uses_position_ordered_nonempty_texts(
        self,
    ) -> None:
        """Task-1 determinism contract, asserted caller-side: the fingerprint
        inputs are ``list_by_novel`` position order filtered to non-empty
        prose. Seeded deliberately out of position order with a whitespace-
        only chapter — the stored digest must equal the digest over exactly
        ``["First prose.", "Second prose."]``."""
        owner = uuid.uuid4()
        series_repo, novel_repo, chapter_repo, drift_repo, series, novel = seeded_drift_fakes(owner)
        # Insertion order (2, whitespace, 1) differs from position order on
        # purpose: only the list_by_novel contract may define the order.
        chapter_repo.seed(
            make_chapter(novel.id, "Second prose.", 2),
            make_chapter(novel.id, "   ", 3),
            make_chapter(novel.id, "First prose.", 1),
        )
        service = make_persistence_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            drift_repo=drift_repo,
            consistency_return=make_consistency_response(series.id, novel.id),
        )

        await service.check_and_store_consistency(series.id, novel.id, owner)

        chapter_repo.assert_called("list_by_novel", novel_id=novel.id)
        drift_repo.assert_called(
            "store_section",
            novel_id=novel.id,
            section="consistency",
            fingerprint=fingerprint_chapter_texts(["First prose.", "Second prose."]),
        )

    async def test_forbidden_before_check_propagates_without_store(self) -> None:
        drift_repo = FakeSeriesDriftRepository()
        consistency = AsyncMock()
        consistency.check_novel.side_effect = ForbiddenError("no access")
        service = SeriesDriftPersistenceService(
            consistency_service=consistency,
            voice_drift_service=AsyncMock(),
            series_repo=FakeSeriesRepository(),
            novel_repo=FakeNovelRepository(),
            chapter_repo=FakeChapterRepository(),
            drift_repo=drift_repo,
        )

        with pytest.raises(ForbiddenError):
            await service.check_and_store_consistency(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        drift_repo.assert_not_called("store_section")

    async def test_store_failure_degrades_gracefully_result_still_returned(
        self,
    ) -> None:
        """RULE-11 ruling: the LLM cost is paid; a store failure must not
        destroy the check result — log + return. The degradation must also
        BE logged: exactly one ``series_drift_persist_failed`` warning with
        the section context (not a silent swallow)."""
        owner = uuid.uuid4()
        series_repo, novel_repo, chapter_repo, drift_repo, series, novel = seeded_drift_fakes(owner)
        chapter_repo.seed(make_chapter(novel.id, "Prose one.", 1))
        drift_repo.raise_on_store = RuntimeError("db down")
        response = make_consistency_response(series.id, novel.id)
        service = make_persistence_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            drift_repo=drift_repo,
            consistency_return=response,
        )

        with capture_logs() as logs:
            result = await service.check_and_store_consistency(series.id, novel.id, owner)

        assert result is response
        warnings = [r for r in logs if r.get("event") == "series_drift_persist_failed"]
        assert len(warnings) == 1, f"expected one series_drift_persist_failed warning, got {logs}"
        assert warnings[0]["log_level"] == "warning"
        assert warnings[0]["section"] == "consistency"
        assert "db down" in warnings[0]["error"]


class TestCheckAndStoreVoiceDrift:
    async def test_runs_then_stores_its_section(self) -> None:
        owner = uuid.uuid4()
        series_repo, novel_repo, chapter_repo, drift_repo, series, novel = seeded_drift_fakes(owner)
        chapter_repo.seed(make_chapter(novel.id, "Prose one.", 1))
        voice_response = AuthorVoiceDriftResponse(novel_id=str(novel.id))
        service = make_persistence_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            drift_repo=drift_repo,
            voice_return=voice_response,
        )

        result = await service.check_and_store_voice_drift(
            series.id, novel.id, owner, AuthorVoiceDriftRequest()
        )

        assert result is voice_response
        drift_repo.assert_called(
            "store_section",
            novel_id=novel.id,
            section="voice_drift",
            document=voice_response.model_dump(mode="json"),
        )

    async def test_graceful_no_profile_result_is_stored(self) -> None:
        """Ruling: graceful-skip outcomes are valid analysis results."""
        owner = uuid.uuid4()
        series_repo, novel_repo, chapter_repo, drift_repo, series, novel = seeded_drift_fakes(owner)
        voice_response = AuthorVoiceDriftResponse.model_validate(
            {"novel_id": str(novel.id), "no_profile": {"reason": "no_stored_series_voice"}}
        )
        service = make_persistence_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            drift_repo=drift_repo,
            voice_return=voice_response,
        )

        await service.check_and_store_voice_drift(
            series.id, novel.id, owner, AuthorVoiceDriftRequest()
        )

        drift_repo.assert_called("store_section", section="voice_drift")


def test_service_satisfies_protocol() -> None:
    service = make_persistence_service(
        series_repo=FakeSeriesRepository(),
        novel_repo=FakeNovelRepository(),
        chapter_repo=FakeChapterRepository(),
        drift_repo=FakeSeriesDriftRepository(),
    )
    assert isinstance(service, SeriesDriftPersistenceServiceProtocol)
