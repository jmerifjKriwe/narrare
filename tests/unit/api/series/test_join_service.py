"""Unit tests for ``SeriesJoinService.preview_join`` — Policy alpha.

Exercises the adaptive scope-assignment preview logic without a database:

* Policy alpha — empty Series-Canon triggers Policy iii heuristics
  (system/concept/setting/location/object/timeline -> Canon;
  character/faction -> Novel-Overlay).
* Policy alpha — non-empty Series-Canon keeps every joining entry as a
  Novel-Overlay.
* C3 — every treatment carries a machine-stable ``reason_code``.
* C1 — ownership: a not-owned series/novel surfaces as ``ForbiddenError`` (403,
  anti-enumeration); a conflict (already in another series) → 409.

The ``apply_join`` execution path, atomicity, and T10 commit-time
``IntegrityError`` mapping live in ``test_join_apply.py`` (RULE-04 split); the
``remove_novel`` leave flow lives in ``test_join_remove.py``.

Domain dependencies are real in-memory fakes (ADR-030), not ``MagicMock``.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare.series.join_service import NovelAlreadyInSeriesError
from narrare.series.schemas import JoinEntryTreatment, JoinPreview
from narrare_core.shared.errors import ConflictError, ForbiddenError
from tests.factories import make_novel
from tests.fakes.fake_kb_join_repo import FakeJoinKBRepo
from tests.fakes.fake_novel_repo import FakeNovelRepository
from tests.fakes.fake_series_repo import FakeSeriesRepository

from ._join_helpers import (
    build_service,
    canon_entry,
    make_series,
    overlay_entry,
    seed_mixed_novel,
)

USER_ID = uuid4()

# Policy iii entity-type defaults (mirror the production constants).
CANON_TYPES = {"system", "concept", "setting", "location", "object", "timeline"}
OVERLAY_TYPES = {"character", "faction"}


# ---------------------------------------------------------------------------
# preview_join — Policy alpha
# ---------------------------------------------------------------------------


class TestPreviewJoinEmptyCanon:
    async def test_applies_policy_iii_heuristics(self) -> None:
        """Empty Canon -> canon-types promoted, overlay-types kept."""
        series = make_series(user_id=USER_ID)
        novel_id = uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=novel_id, user_id=USER_ID, series_id=None))
        kb_repo = FakeJoinKBRepo()
        seed_mixed_novel(novel_id, kb_repo)
        series_repo = FakeSeriesRepository()
        series_repo.seed(series)
        service, *_ = build_service(novel_repo=novel_repo, kb_repo=kb_repo, series_repo=series_repo)

        preview = await service.preview_join(series.id, novel_id, USER_ID)

        assert isinstance(preview, JoinPreview)
        assert preview.canon_empty is True
        by_type = {t.entity_type: t for t in preview.treatments}
        assert by_type["system"].target_scope == "series"
        assert by_type["character"].target_scope == "novel"
        assert all(t.current_scope == "novel" for t in preview.treatments)

    async def test_reason_codes_are_machine_stable(self) -> None:
        """C3: each treatment carries a stable reason_code the frontend i18n-resolves."""
        series = make_series(user_id=USER_ID)
        novel_id = uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=novel_id, user_id=USER_ID, series_id=None))
        kb_repo = FakeJoinKBRepo()
        seed_mixed_novel(novel_id, kb_repo)
        series_repo = FakeSeriesRepository()
        series_repo.seed(series)
        service, *_ = build_service(novel_repo=novel_repo, kb_repo=kb_repo, series_repo=series_repo)

        preview = await service.preview_join(series.id, novel_id, USER_ID)

        by_type = {t.entity_type: t for t in preview.treatments}
        assert by_type["system"].reason_code == "entity_default_canon"
        assert by_type["character"].reason_code == "entity_default_overlay"

    async def test_reason_strings_explain_decision(self) -> None:
        series = make_series(user_id=USER_ID)
        novel_id = uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=novel_id, user_id=USER_ID, series_id=None))
        kb_repo = FakeJoinKBRepo()
        seed_mixed_novel(novel_id, kb_repo)
        series_repo = FakeSeriesRepository()
        series_repo.seed(series)
        service, *_ = build_service(novel_repo=novel_repo, kb_repo=kb_repo, series_repo=series_repo)

        preview = await service.preview_join(series.id, novel_id, USER_ID)

        by_type = {t.entity_type: t for t in preview.treatments}
        assert "Canon" in by_type["system"].reason
        assert "Overlay" in by_type["character"].reason

    async def test_does_not_mutate_state(self) -> None:
        """preview_join must not promote anything (no side effects)."""
        series = make_series(user_id=USER_ID)
        novel_id = uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=novel_id, user_id=USER_ID, series_id=None))
        kb_repo = FakeJoinKBRepo()
        seed_mixed_novel(novel_id, kb_repo)
        series_repo = FakeSeriesRepository()
        series_repo.seed(series)
        service, *_ = build_service(novel_repo=novel_repo, kb_repo=kb_repo, series_repo=series_repo)

        await service.preview_join(series.id, novel_id, USER_ID)

        assert kb_repo.promoted == []
        assert all(c.method != "promote_to_canon" for c in kb_repo.calls)


class TestPreviewJoinPopulatedCanon:
    async def test_keeps_all_entries_as_overlay(self) -> None:
        """Non-empty Canon -> every entry stays a Novel-Overlay."""
        series = make_series(user_id=USER_ID)
        novel_id = uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=novel_id, user_id=USER_ID, series_id=None))
        kb_repo = FakeJoinKBRepo()
        kb_repo.seed_canon(series.id, [canon_entry(series.id)])  # non-empty
        seed_mixed_novel(novel_id, kb_repo)
        series_repo = FakeSeriesRepository()
        series_repo.seed(series)
        service, *_ = build_service(novel_repo=novel_repo, kb_repo=kb_repo, series_repo=series_repo)

        preview = await service.preview_join(series.id, novel_id, USER_ID)

        assert preview.canon_empty is False
        assert all(t.target_scope == "novel" for t in preview.treatments)
        assert all(t.reason_code == "canon_nonempty_overlay" for t in preview.treatments)
        assert all("non-empty" in t.reason for t in preview.treatments)

    async def test_promotes_nothing_even_for_canon_types(self) -> None:
        series = make_series(user_id=USER_ID)
        novel_id = uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=novel_id, user_id=USER_ID, series_id=None))
        kb_repo = FakeJoinKBRepo()
        kb_repo.seed_canon(series.id, [canon_entry(series.id, entity_type="concept")])
        kb_repo.seed_overlay(novel_id, [overlay_entry(novel_id, entity_type="system")])
        series_repo = FakeSeriesRepository()
        series_repo.seed(series)
        service, *_ = build_service(novel_repo=novel_repo, kb_repo=kb_repo, series_repo=series_repo)

        preview = await service.preview_join(series.id, novel_id, USER_ID)

        assert preview.treatments[0].target_scope == "novel"


class TestPreviewJoinOwnershipAndConflict:
    async def test_rejects_novel_already_in_other_series(self) -> None:
        other_series = uuid4()
        series = make_series(user_id=USER_ID)
        novel = make_novel(user_id=USER_ID, series_id=other_series)
        novel_repo = FakeNovelRepository()
        novel_repo.seed(novel)
        series_repo = FakeSeriesRepository()
        series_repo.seed(series)
        service, *_ = build_service(novel_repo=novel_repo, series_repo=series_repo)

        with pytest.raises(NovelAlreadyInSeriesError) as exc_info:
            await service.preview_join(series.id, novel.id, USER_ID)

        assert exc_info.value.novel_id == novel.id
        assert exc_info.value.existing_series_id == other_series

    async def test_allows_novel_already_in_same_series(self) -> None:
        """Re-previewing the same series is a no-op idempotent call."""
        series = make_series(user_id=USER_ID)
        novel = make_novel(user_id=USER_ID, series_id=series.id)
        novel_repo = FakeNovelRepository()
        novel_repo.seed(novel)
        kb_repo = FakeJoinKBRepo()
        kb_repo.seed_overlay(novel.id, [overlay_entry(novel.id, entity_type="system")])
        series_repo = FakeSeriesRepository()
        series_repo.seed(series)
        service, *_ = build_service(novel_repo=novel_repo, kb_repo=kb_repo, series_repo=series_repo)

        preview = await service.preview_join(series.id, novel.id, USER_ID)

        assert preview.series_id == series.id

    async def test_raises_forbidden_when_novel_missing(self) -> None:
        """Anti-enumeration: a missing novel surfaces as 403, not 404."""
        series = make_series(user_id=USER_ID)
        series_repo = FakeSeriesRepository()
        series_repo.seed(series)
        service, *_ = build_service(series_repo=series_repo)

        with pytest.raises(ForbiddenError):
            await service.preview_join(series.id, uuid4(), USER_ID)

    async def test_raises_forbidden_when_series_not_owned(self) -> None:
        """A series owned by another user surfaces as 403 (anti-enumeration)."""
        other_user = uuid4()
        series = make_series(user_id=other_user)  # not owned by USER_ID
        series_repo = FakeSeriesRepository()
        series_repo.seed(series)
        service, *_ = build_service(series_repo=series_repo)

        with pytest.raises(ForbiddenError):
            await service.preview_join(series.id, uuid4(), USER_ID)


# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------


class TestNovelAlreadyInSeriesError:
    def test_is_a_conflict_error_for_409_mapping(self) -> None:
        novel_id, series_id = uuid4(), uuid4()

        err = NovelAlreadyInSeriesError(novel_id, series_id)

        assert isinstance(err, ConflictError)
        assert err.novel_id == novel_id
        assert err.existing_series_id == series_id
        assert str(series_id) in str(err)


class TestTreatmentModel:
    def test_treatment_round_trips_through_schema(self) -> None:
        entry_id = uuid4()
        treatment = JoinEntryTreatment(
            entry_id=entry_id,
            slug="magic-system",
            entity_type="system",
            current_scope="novel",
            target_scope="series",
            reason_code="entity_default_canon",
            reason="x",
        )
        assert treatment.entry_id == entry_id
        assert treatment.target_scope == "series"
        assert treatment.reason_code == "entity_default_canon"
