"""Unit tests for ``SeriesJoinService.remove_novel`` (leave flow).

Covers the inverse of ``apply_join``: clearing a novel's series membership.
Uses the same in-memory fakes as ``test_join_service.py`` (ADR-030).

Cases:
* happy path — membership cleared + committed.
* novel missing — ``NotFoundError`` (404), no commit.
* idempotent — novel not in this series is a no-op (no clear, no commit).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare_core.shared.errors import NotFoundError
from tests.factories import make_novel
from tests.fakes.fake_novel_repo import FakeNovelRepository

from ._join_helpers import build_service


class TestRemoveNovel:
    async def test_clears_membership_and_commits(self) -> None:
        series_id, novel_id = uuid4(), uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=novel_id, series_id=series_id, series_position=1))
        service, session, _, _ = build_service(novel_repo=novel_repo)

        await service.remove_novel(series_id, novel_id)

        assert novel_repo.call_count("clear_series_membership") == 1
        assert session.commit_count == 1
        cleared = await novel_repo.get(novel_id)
        assert cleared is not None
        assert cleared.series_id is None

    async def test_unknown_novel_raises_not_found(self) -> None:
        service, session, _, _ = build_service()

        with pytest.raises(NotFoundError):
            await service.remove_novel(uuid4(), uuid4())

        assert session.commit_count == 0

    async def test_novel_in_other_series_is_noop(self) -> None:
        """A novel belonging to a different series is left untouched (idempotent)."""
        other_series, novel_id = uuid4(), uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=novel_id, series_id=other_series, series_position=2))
        service, session, _, _ = build_service(novel_repo=novel_repo)

        # Asking to remove from an unrelated series must not mutate or commit.
        await service.remove_novel(uuid4(), novel_id)

        assert novel_repo.call_count("clear_series_membership") == 0
        assert session.commit_count == 0
        unchanged = await novel_repo.get(novel_id)
        assert unchanged is not None
        assert unchanged.series_id == other_series
