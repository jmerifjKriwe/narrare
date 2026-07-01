"""Unit tests for ``WikiSystemAccessors`` (system-mode mixin).

The mixin delegates to ``self._wiki_repo`` without ownership checks. These
tests cover the three accessor methods with a fake repository, including the
``None`` short-circuit when no summary exists.
"""

from __future__ import annotations

from uuid import uuid4

from narrare.wiki._system_accessors import WikiSystemAccessors


class _FakeWikiRepo:
    def __init__(
        self,
        *,
        summary: object = None,
        chapter_summary: object = None,
        stale_count: int = 0,
    ) -> None:
        self._summary = summary
        self._chapter_summary = chapter_summary
        self._stale_count = stale_count

    async def get_summary(self, entity_id: object, novel_id: object) -> object:
        del entity_id, novel_id
        return self._summary

    async def get_chapter_summary(self, chapter_id: object) -> object:
        del chapter_id
        return self._chapter_summary

    async def mark_related_stale(self, entity_id: object) -> int:
        del entity_id
        return self._stale_count


class _Accessor(WikiSystemAccessors):
    """Concrete host so the mixin's ``self._wiki_repo`` can be set."""

    def __init__(self, repo: _FakeWikiRepo) -> None:
        self._wiki_repo = repo  # type: ignore[assignment]


class TestGetSummaryRaw:
    async def test_returns_none_when_no_summary_exists(self) -> None:
        accessor = _Accessor(_FakeWikiRepo(summary=None))
        assert await accessor.get_summary_raw(uuid4(), uuid4()) is None

    async def test_returns_none_when_repo_returns_falsy(self) -> None:
        accessor = _Accessor(_FakeWikiRepo(summary=0))
        assert await accessor.get_summary_raw(uuid4(), uuid4()) is None


class TestGetChapterSummaryRaw:
    async def test_returns_none_when_no_chapter_summary_exists(self) -> None:
        accessor = _Accessor(_FakeWikiRepo(chapter_summary=None))
        assert await accessor.get_chapter_summary_raw(uuid4()) is None


class TestMarkRelatedStale:
    async def test_returns_repo_stale_count(self) -> None:
        accessor = _Accessor(_FakeWikiRepo(stale_count=7))
        assert await accessor.mark_related_stale(uuid4()) == 7

    async def test_returns_zero_when_nothing_stale(self) -> None:
        accessor = _Accessor(_FakeWikiRepo(stale_count=0))
        assert await accessor.mark_related_stale(uuid4()) == 0
