"""Unit tests for ``SeriesJoinService.apply_join`` + error mapping.

Split from ``test_join_service.py`` to respect the RULE-04 limit (the file name
``test_join_service.py`` matches the 300-line ``*_service.py`` rule). Covers the
apply execution path: authoritative re-preview, atomic commit/rollback, and the
T10 commit-time ``IntegrityError`` → typed domain-error translation
(``map_join_integrity_error``).

Domain dependencies are real in-memory fakes (ADR-030).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from narrare.series._join_errors import map_join_integrity_error
from narrare.series.join_service import NovelAlreadyInSeriesError
from narrare.series.schemas import JoinResult
from narrare_core.shared.errors import ConflictError, NotFoundError
from tests.fakes.fake_db_session import FakeTxSession

from ._join_helpers import build_owned, canon_entry, seed_mixed_novel

USER_ID = uuid4()


class _FakeOrig(Exception):
    """asyncpg-like DBAPI orig exposing ``constraint_name`` for IntegrityError tests."""

    def __init__(self, constraint_name: str | None) -> None:
        super().__init__("simulated dbapi error")
        self.constraint_name = constraint_name


def _integrity(constraint_name: str | None) -> IntegrityError:
    """Build an IntegrityError whose orig carries the given constraint name."""
    return IntegrityError("INSERT ...", {}, _FakeOrig(constraint_name))


# ---------------------------------------------------------------------------
# apply_join — happy path
# ---------------------------------------------------------------------------


class TestApplyJoin:
    async def test_promotes_canon_types_and_assigns_membership(self) -> None:
        service, session, novel_repo, kb_repo, _, series, novel_id = build_owned(user_id=USER_ID)
        entries = seed_mixed_novel(novel_id, kb_repo)

        result = await service.apply_join(series.id, novel_id, position=1, user_id=USER_ID)

        assert isinstance(result, JoinResult)
        assert result.series_id == series.id
        assert result.position == 1
        assert result.promoted_to_canon == 1
        assert result.kept_as_overlay == 1
        system_entry = next(e for e in entries if e.entity_type == "system")
        assert kb_repo.promoted == [(novel_id, system_entry.id)]
        updated = await novel_repo.get(novel_id)
        assert updated is not None
        assert updated.series_id == series.id
        assert updated.series_position == 1
        assert session.commit_count == 1
        assert session.rollback_count == 0

    async def test_non_empty_canon_promotes_nothing(self) -> None:
        service, session, _, kb_repo, _, series, novel_id = build_owned(
            user_id=USER_ID, canon=[canon_entry(series_id=uuid4())]
        )
        seed_mixed_novel(novel_id, kb_repo)

        result = await service.apply_join(series.id, novel_id, position=3, user_id=USER_ID)

        assert result.promoted_to_canon == 0
        assert result.kept_as_overlay == 2
        assert kb_repo.promoted == []
        assert session.commit_count == 1


# ---------------------------------------------------------------------------
# apply_join — atomicity
# ---------------------------------------------------------------------------


class TestApplyJoinAtomicity:
    async def test_rolls_back_and_reraises_on_promote_failure(self) -> None:
        """A failing promote triggers rollback + re-raise (RULE-11)."""
        service, session, _, kb_repo, _, series, novel_id = build_owned(user_id=USER_ID)
        seed_mixed_novel(novel_id, kb_repo)
        kb_repo.fail_on_promote(1)  # first promote explodes

        with pytest.raises(RuntimeError):
            await service.apply_join(series.id, novel_id, position=1, user_id=USER_ID)

        assert session.rollback_count == 1
        assert session.commit_count == 0

    async def test_conflict_during_repreview_does_not_touch_transaction(self) -> None:
        """If re-preview raises NovelAlreadyInSeriesError, no commit/rollback."""
        other_series = uuid4()
        service, session, _, _, _, series, novel_id = build_owned(
            user_id=USER_ID, novel_series_id=other_series
        )

        with pytest.raises(NovelAlreadyInSeriesError):
            await service.apply_join(series.id, novel_id, position=1, user_id=USER_ID)

        assert session.commit_count == 0
        assert session.rollback_count == 0


# ---------------------------------------------------------------------------
# apply_join — commit-time IntegrityError mapping (T10)
# ---------------------------------------------------------------------------


class TestApplyJoinIntegrityMapping:
    """T10: commit-time IntegrityError → typed domain error + rollback."""

    async def test_position_conflict_maps_to_conflict(self) -> None:
        service, session, _, kb_repo, _, series, novel_id = build_owned(
            user_id=USER_ID,
            session=FakeTxSession(commit_error=_integrity("uq_novels_series_position")),
        )
        seed_mixed_novel(novel_id, kb_repo)

        with pytest.raises(ConflictError, match="Position occupied"):
            await service.apply_join(series.id, novel_id, position=1, user_id=USER_ID)

        assert session.rollback_count == 1
        assert session.commit_count == 0

    async def test_slug_conflict_maps_to_conflict(self) -> None:
        service, session, _, kb_repo, _, series, novel_id = build_owned(
            user_id=USER_ID,
            session=FakeTxSession(commit_error=_integrity("uq_kb_canon_per_series")),
        )
        seed_mixed_novel(novel_id, kb_repo)

        with pytest.raises(ConflictError, match="Slug conflict"):
            await service.apply_join(series.id, novel_id, position=1, user_id=USER_ID)

        assert session.rollback_count == 1

    async def test_unknown_violation_maps_to_not_found(self) -> None:
        """An unrecognised violation (e.g. a membership FK race) → NotFoundError("Series")."""
        service, session, _, kb_repo, _, series, novel_id = build_owned(
            user_id=USER_ID, session=FakeTxSession(commit_error=_integrity(None))
        )
        seed_mixed_novel(novel_id, kb_repo)

        with pytest.raises(NotFoundError, match="Series"):
            await service.apply_join(series.id, novel_id, position=1, user_id=USER_ID)

        assert session.rollback_count == 1
        assert session.commit_count == 0


class TestMapJoinIntegrityError:
    """Direct unit tests for the extracted IntegrityError mapper (T10)."""

    def test_position_constraint_maps_to_conflict(self) -> None:
        result = map_join_integrity_error(_integrity("uq_novels_series_position"), uuid4())
        assert isinstance(result, ConflictError)
        assert "Position occupied" in str(result)

    def test_canon_slug_constraint_maps_to_conflict(self) -> None:
        result = map_join_integrity_error(_integrity("uq_kb_canon_per_series"), uuid4())
        assert isinstance(result, ConflictError)
        assert "Slug conflict" in str(result)

    def test_overlay_slug_constraint_maps_to_conflict(self) -> None:
        """``uq_kb_overlay_per_novel`` → ConflictError (not a misleading 404).

        Without this case a demote/scope collision falls through to the catch-all
        ``NotFoundError("Series")`` (404) — the misleading mapping the canon case
        already avoids. Mirrors the canon-case structure.
        """
        result = map_join_integrity_error(_integrity("uq_kb_overlay_per_novel"), uuid4())
        assert isinstance(result, ConflictError)
        assert "Slug conflict" in str(result)

    def test_unknown_constraint_maps_to_not_found(self) -> None:
        series_id = uuid4()
        result = map_join_integrity_error(_integrity("some_other_fk"), series_id)
        assert isinstance(result, NotFoundError)
