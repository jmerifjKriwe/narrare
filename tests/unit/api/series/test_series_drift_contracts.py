"""Contract tests for the C2 drift-persistence surface (RULE-03).

Pins the repository + persistence-service Protocols and the snapshot
response schema BEFORE the implementations (the contract files are
untouchable for the remainder of the slice).
"""

from __future__ import annotations

import typing
import uuid
from datetime import UTC, datetime

from narrare.series.series_drift_contracts import (
    DriftSection,
    SeriesDriftPersistenceServiceProtocol,
    SeriesDriftRepositoryProtocol,
)
from narrare.series.series_drift_schemas import SeriesDriftSnapshotResponse


class TestDriftSection:
    def test_literal_members(self) -> None:
        # Typing-time contract; the runtime set mirrors the JSONB keys.
        args = typing.get_args(DriftSection)
        assert set(args) == {"consistency", "voice_drift"}


class TestSnapshotSchema:
    def test_holds_both_sections_plus_staleness(self) -> None:
        response = SeriesDriftSnapshotResponse(
            series_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            novel_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
            generated_at=datetime(2026, 8, 16, 12, 0, tzinfo=UTC),
            stale=True,
            consistency=None,
            voice_drift=None,
        )
        assert response.stale is True
        assert response.consistency is None
        assert response.voice_drift is None

    def test_empty_snapshot_shape(self) -> None:
        response = SeriesDriftSnapshotResponse(
            series_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            novel_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
            generated_at=None,
            stale=False,
            consistency=None,
            voice_drift=None,
        )
        assert response.generated_at is None

    def test_sections_carry_the_run_result_models(self) -> None:
        from narrare.analysis.schemas_author_voice_drift import (
            AuthorVoiceDriftResponse,
        )
        from narrare.series.series_consistency_schemas import (
            SeriesConsistencyCheckResponse,
        )

        consistency = SeriesConsistencyCheckResponse(
            series_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            novel_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        )
        voice = AuthorVoiceDriftResponse(novel_id="00000000-0000-0000-0000-000000000002")
        response = SeriesDriftSnapshotResponse(
            series_id=consistency.series_id,
            novel_id=consistency.novel_id,
            generated_at=None,
            stale=False,
            consistency=consistency,
            voice_drift=voice,
        )
        assert response.consistency is consistency
        assert response.voice_drift is voice


class TestProtocols:
    def test_repository_protocol_surface(self) -> None:
        for method in ("get", "store_section"):
            assert hasattr(SeriesDriftRepositoryProtocol, method)

    def test_service_protocol_surface(self) -> None:
        for method in (
            "check_and_store_consistency",
            "check_and_store_voice_drift",
            "get_snapshot",
        ):
            assert hasattr(SeriesDriftPersistenceServiceProtocol, method)
