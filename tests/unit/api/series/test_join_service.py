"""Unit tests for ``SeriesJoinService`` — Policy alpha (preview + apply).

Exercises the adaptive scope-assignment logic without a database:

* Policy alpha — empty Series-Canon triggers Policy iii heuristics
  (system/concept/setting/location/object/timeline -> Canon;
  character/faction -> Novel-Overlay).
* Policy alpha — non-empty Series-Canon keeps every joining entry as a
  Novel-Overlay.
* Conflict guard — a novel already in another series is rejected.
* ``apply_join`` — executes the previewed treatments atomically (commit on
  success; rollback + re-raise on failure), assigning series membership.

Domain dependencies are real in-memory fakes (ADR-030), not ``MagicMock``.
The KB fake returns the Core Pydantic types (``NovelKBEntry`` /
``SeriesKBEntry``) that the real ``KBRepository`` scope methods return.
True DB-level transaction rollback is verified by integration tests; here we
assert the service's transaction *contract* (rollback invoked, commit
withheld on error).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare.series.join_service import NovelAlreadyInSeriesError
from narrare.series.schemas import JoinEntryTreatment, JoinPreview, JoinResult
from narrare_core.shared.errors import ConflictError, NotFoundError
from tests.factories import make_novel
from tests.fakes.fake_kb_join_repo import FakeJoinKBRepo
from tests.fakes.fake_novel_repo import FakeNovelRepository

from ._join_helpers import build_service, canon_entry, overlay_entry, seed_mixed_novel

# Policy iii entity-type defaults (mirror the production constants).
CANON_TYPES = {"system", "concept", "setting", "location", "object", "timeline"}
OVERLAY_TYPES = {"character", "faction"}


# ---------------------------------------------------------------------------
# preview_join — Policy alpha
# ---------------------------------------------------------------------------


class TestPreviewJoinEmptyCanon:
    async def test_applies_policy_iii_heuristics(self) -> None:
        """Empty Canon -> canon-types promoted, overlay-types kept."""
        series_id, novel_id = uuid4(), uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=novel_id, series_id=None))
        kb_repo = FakeJoinKBRepo()
        seed_mixed_novel(novel_id, kb_repo)
        service, *_ = build_service(novel_repo=novel_repo, kb_repo=kb_repo)

        preview = await service.preview_join(series_id, novel_id)

        assert isinstance(preview, JoinPreview)
        assert preview.canon_empty is True
        by_type = {t.entity_type: t for t in preview.treatments}
        assert by_type["system"].target_scope == "series"
        assert by_type["character"].target_scope == "novel"
        # current_scope is always "novel" before join.
        assert all(t.current_scope == "novel" for t in preview.treatments)

    async def test_reason_strings_explain_decision(self) -> None:
        series_id, novel_id = uuid4(), uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=novel_id, series_id=None))
        kb_repo = FakeJoinKBRepo()
        seed_mixed_novel(novel_id, kb_repo)
        service, *_ = build_service(novel_repo=novel_repo, kb_repo=kb_repo)

        preview = await service.preview_join(series_id, novel_id)

        by_type = {t.entity_type: t for t in preview.treatments}
        assert "Canon" in by_type["system"].reason
        assert "Overlay" in by_type["character"].reason

    async def test_does_not_mutate_state(self) -> None:
        """preview_join must not promote anything (no side effects)."""
        novel_id = uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=novel_id, series_id=None))
        kb_repo = FakeJoinKBRepo()
        seed_mixed_novel(novel_id, kb_repo)
        service, *_ = build_service(novel_repo=novel_repo, kb_repo=kb_repo)

        await service.preview_join(uuid4(), novel_id)

        assert kb_repo.promoted == []
        assert all(c.method != "promote_to_canon" for c in kb_repo.calls)


class TestPreviewJoinPopulatedCanon:
    async def test_keeps_all_entries_as_overlay(self) -> None:
        """Non-empty Canon -> every entry stays a Novel-Overlay."""
        series_id, novel_id = uuid4(), uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=novel_id, series_id=None))
        kb_repo = FakeJoinKBRepo()
        kb_repo.seed_canon(series_id, [canon_entry(series_id)])  # non-empty
        seed_mixed_novel(novel_id, kb_repo)
        service, *_ = build_service(novel_repo=novel_repo, kb_repo=kb_repo)

        preview = await service.preview_join(series_id, novel_id)

        assert preview.canon_empty is False
        assert all(t.target_scope == "novel" for t in preview.treatments)
        assert all("non-empty" in t.reason for t in preview.treatments)

    async def test_promotes_nothing_even_for_canon_types(self) -> None:
        series_id, novel_id = uuid4(), uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=novel_id, series_id=None))
        kb_repo = FakeJoinKBRepo()
        kb_repo.seed_canon(series_id, [canon_entry(series_id, entity_type="concept")])
        kb_repo.seed_overlay(novel_id, [overlay_entry(novel_id, entity_type="system")])
        service, *_ = build_service(novel_repo=novel_repo, kb_repo=kb_repo)

        preview = await service.preview_join(series_id, novel_id)

        assert preview.treatments[0].target_scope == "novel"


class TestPreviewJoinConflictGuard:
    async def test_rejects_novel_already_in_other_series(self) -> None:
        other_series = uuid4()
        novel = make_novel(series_id=other_series)
        novel_repo = FakeNovelRepository()
        novel_repo.seed(novel)
        service, *_ = build_service(novel_repo=novel_repo)

        with pytest.raises(NovelAlreadyInSeriesError) as exc_info:
            await service.preview_join(uuid4(), novel.id)

        assert exc_info.value.novel_id == novel.id
        assert exc_info.value.existing_series_id == other_series

    async def test_allows_novel_already_in_same_series(self) -> None:
        """Re-previewing the same series is a no-op idempotent call."""
        series_id = uuid4()
        novel = make_novel(series_id=series_id)
        novel_repo = FakeNovelRepository()
        novel_repo.seed(novel)
        kb_repo = FakeJoinKBRepo()
        kb_repo.seed_overlay(novel.id, [overlay_entry(novel.id, entity_type="system")])
        service, *_ = build_service(novel_repo=novel_repo, kb_repo=kb_repo)

        preview = await service.preview_join(series_id, novel.id)

        assert preview.series_id == series_id

    async def test_raises_not_found_when_novel_missing(self) -> None:
        service, *_ = build_service()

        with pytest.raises(NotFoundError):
            await service.preview_join(uuid4(), uuid4())


# ---------------------------------------------------------------------------
# apply_join
# ---------------------------------------------------------------------------


class TestApplyJoin:
    async def test_promotes_canon_types_and_assigns_membership(self) -> None:
        series_id, novel_id = uuid4(), uuid4()
        novel = make_novel(id=novel_id, series_id=None)
        novel_repo = FakeNovelRepository()
        novel_repo.seed(novel)
        kb_repo = FakeJoinKBRepo()
        entries = seed_mixed_novel(novel_id, kb_repo)
        service, session, *_ = build_service(novel_repo=novel_repo, kb_repo=kb_repo)

        result = await service.apply_join(series_id, novel_id, position=1)

        assert isinstance(result, JoinResult)
        assert result.series_id == series_id
        assert result.novel_id == novel_id
        assert result.position == 1
        # one canon-type ("system") promoted, one overlay-type ("character") kept
        assert result.promoted_to_canon == 1
        assert result.kept_as_overlay == 1
        # only the canon-type entry was promoted
        system_entry = next(e for e in entries if e.entity_type == "system")
        assert kb_repo.promoted == [(novel_id, system_entry.id)]
        # series membership was assigned to the novel
        updated = await novel_repo.get(novel_id)
        assert updated is not None
        assert updated.series_id == series_id
        assert updated.series_position == 1
        # committed exactly once, no rollback
        assert session.commit_count == 1
        assert session.rollback_count == 0

    async def test_non_empty_canon_promotes_nothing(self) -> None:
        series_id, novel_id = uuid4(), uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=novel_id, series_id=None))
        kb_repo = FakeJoinKBRepo()
        kb_repo.seed_canon(series_id, [canon_entry(series_id)])
        seed_mixed_novel(novel_id, kb_repo)
        service, session, *_ = build_service(novel_repo=novel_repo, kb_repo=kb_repo)

        result = await service.apply_join(series_id, novel_id, position=3)

        assert result.promoted_to_canon == 0
        assert result.kept_as_overlay == 2
        assert kb_repo.promoted == []
        assert session.commit_count == 1


class TestApplyJoinAtomicity:
    async def test_rolls_back_and_reraises_on_promote_failure(self) -> None:
        """A failing promote triggers rollback + re-raise (RULE-11)."""
        series_id, novel_id = uuid4(), uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=novel_id, series_id=None))
        kb_repo = FakeJoinKBRepo()
        seed_mixed_novel(novel_id, kb_repo)
        kb_repo.fail_on_promote(1)  # first promote explodes
        service, session, *_ = build_service(novel_repo=novel_repo, kb_repo=kb_repo)

        with pytest.raises(RuntimeError):
            await service.apply_join(series_id, novel_id, position=1)

        # Transaction contract: rolled back, never committed.
        assert session.rollback_count == 1
        assert session.commit_count == 0

    async def test_conflict_during_repreview_does_not_touch_transaction(self) -> None:
        """If re-preview raises NovelAlreadyInSeriesError, no commit/rollback."""
        other_series = uuid4()
        novel = make_novel(series_id=other_series)
        novel_repo = FakeNovelRepository()
        novel_repo.seed(novel)
        service, session, *_ = build_service(novel_repo=novel_repo)

        with pytest.raises(NovelAlreadyInSeriesError):
            await service.apply_join(uuid4(), novel.id, position=1)

        # preview_join raised before the try/except block: neither commit nor
        # rollback should have been invoked.
        assert session.commit_count == 0
        assert session.rollback_count == 0


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
            reason="x",
        )
        assert treatment.entry_id == entry_id
        assert treatment.target_scope == "series"
