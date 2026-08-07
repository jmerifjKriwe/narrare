"""Unit tests for ``SeriesJoinService.remove_novel`` (leave flow).

Covers the inverse of ``apply_join``: clearing a novel's series membership and
detaching its overlay KB ``series_id`` (T7/D6). Uses the same in-memory fakes
as ``test_join_service.py`` (ADR-030).

Cases:
* happy path — membership cleared, KB detached, committed.
* series not owned — ``ForbiddenError`` (403, anti-enumeration), no commit.
* novel missing/not owned — ``ForbiddenError`` (403), no commit.
* idempotent — novel not in this series is a no-op (no clear, no commit).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare_core.shared.errors import ForbiddenError
from tests.factories import make_novel
from tests.fakes.fake_novel_repo import FakeNovelRepository
from tests.fakes.fake_series_repo import FakeSeriesRepository

from ._join_helpers import build_service, make_series

USER_ID = uuid4()


class TestRemoveNovel:
    async def test_clears_membership_detaches_kb_and_commits(self) -> None:
        """Leave clears novel membership AND detaches overlay KB series_id (T7)."""
        series = make_series(user_id=USER_ID)
        novel_id = uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(
            make_novel(id=novel_id, user_id=USER_ID, series_id=series.id, series_position=1)
        )
        series_repo = FakeSeriesRepository()
        series_repo.seed(series)
        service, session, _, _, s_repo = build_service(
            novel_repo=novel_repo, series_repo=series_repo
        )

        await service.remove_novel(series.id, novel_id, USER_ID)

        assert novel_repo.call_count("clear_series_membership") == 1
        # T7: the leave flow detaches the novel's overlay KB series_id.
        assert s_repo.call_count("detach_overlay_series_id") == 1
        assert session.commit_count == 1
        cleared = await novel_repo.get(novel_id)
        assert cleared is not None
        assert cleared.series_id is None

    async def test_series_not_owned_raises_forbidden(self) -> None:
        """A series owned by another user → 403 (anti-enumeration), no commit."""
        other_user = uuid4()
        series = make_series(user_id=other_user)
        series_repo = FakeSeriesRepository()
        series_repo.seed(series)
        service, session, *_ = build_service(series_repo=series_repo)

        with pytest.raises(ForbiddenError):
            await service.remove_novel(series.id, uuid4(), USER_ID)

        assert session.commit_count == 0

    async def test_unknown_novel_raises_forbidden(self) -> None:
        """Anti-enumeration: a missing novel → 403 (not 404), no commit."""
        series = make_series(user_id=USER_ID)
        series_repo = FakeSeriesRepository()
        series_repo.seed(series)
        service, session, *_ = build_service(series_repo=series_repo)

        with pytest.raises(ForbiddenError):
            await service.remove_novel(series.id, uuid4(), USER_ID)

        assert session.commit_count == 0

    async def test_novel_in_other_series_is_noop(self) -> None:
        """A novel belonging to a different series is left untouched (idempotent)."""
        series = make_series(user_id=USER_ID)
        other_series = uuid4()
        novel_id = uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(
            make_novel(id=novel_id, user_id=USER_ID, series_id=other_series, series_position=2)
        )
        series_repo = FakeSeriesRepository()
        series_repo.seed(series)
        service, session, _, _, s_repo = build_service(
            novel_repo=novel_repo, series_repo=series_repo
        )

        # Asking to remove from an unrelated series must not mutate or commit.
        await service.remove_novel(series.id, novel_id, USER_ID)

        assert novel_repo.call_count("clear_series_membership") == 0
        assert s_repo.call_count("detach_overlay_series_id") == 0
        assert session.commit_count == 0
        unchanged = await novel_repo.get(novel_id)
        assert unchanged is not None
        assert unchanged.series_id == other_series
