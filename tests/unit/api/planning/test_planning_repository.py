"""Unit tests for the planning repository contract via FakeOutlineRepository.

The real OutlineRepository (apps/api/narrare/planning/repository.py) uses
SQLAlchemy and is tested in integration tests. This file verifies the
FakeOutlineRepository faithfully mirrors the real repository's contract,
which is critical because other unit tests depend on this fake.
"""

from __future__ import annotations

import uuid

import pytest

from narrare_core.shared.errors import NotFoundError
from tests.factories import make_chapter_outline
from tests.fakes import FakeOutlineRepository

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo() -> FakeOutlineRepository:
    return FakeOutlineRepository()


# ---------------------------------------------------------------------------
# get_by_chapter_id
# ---------------------------------------------------------------------------


class TestGetByChapterId:
    async def test_get_by_chapter_id_when_exists_returns_outline(
        self, repo: FakeOutlineRepository
    ) -> None:
        outline = make_chapter_outline()
        repo.seed(outline)

        result = await repo.get_by_chapter_id(outline.chapter_id)

        assert result is outline

    async def test_get_by_chapter_id_when_not_found_returns_none(
        self, repo: FakeOutlineRepository
    ) -> None:
        result = await repo.get_by_chapter_id(uuid.uuid4())

        assert result is None


# ---------------------------------------------------------------------------
# get_all_for_novel
# ---------------------------------------------------------------------------


class TestGetAllForNovel:
    async def test_get_all_for_novel_returns_all_seeded_outlines(
        self, repo: FakeOutlineRepository
    ) -> None:
        a = make_chapter_outline()
        b = make_chapter_outline()
        repo.seed(a, b)

        result = await repo.get_all_for_novel(uuid.uuid4())

        assert set(result) == {a, b}

    async def test_get_all_for_novel_when_empty_returns_empty_list(
        self, repo: FakeOutlineRepository
    ) -> None:
        result = await repo.get_all_for_novel(uuid.uuid4())

        assert result == []


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestCreate:
    async def test_create_with_all_fields_returns_outline(
        self, repo: FakeOutlineRepository
    ) -> None:
        chapter_id = uuid.uuid4()
        beats = [{"beat": "opening"}, {"beat": "climax"}]

        outline = await repo.create(
            chapter_id=chapter_id,
            stage_assignment="act-2",
            planned_beats=beats,
            outline_notes="Key reveals",
        )

        assert outline.chapter_id == chapter_id
        assert outline.stage_assignment == "act-2"
        assert outline.planned_beats == beats
        assert outline.outline_notes == "Key reveals"

    async def test_create_defaults_optional_fields(self, repo: FakeOutlineRepository) -> None:
        chapter_id = uuid.uuid4()

        outline = await repo.create(
            chapter_id=chapter_id,
            stage_assignment="act-1",
        )

        assert outline.planned_beats == []
        assert outline.outline_notes == ""

    async def test_create_stores_outline_retrievable_by_chapter_id(
        self, repo: FakeOutlineRepository
    ) -> None:
        chapter_id = uuid.uuid4()

        created = await repo.create(
            chapter_id=chapter_id,
            stage_assignment="act-1",
        )

        found = await repo.get_by_chapter_id(chapter_id)
        assert found is created


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


class TestUpdate:
    async def test_update_modifies_existing_fields(self, repo: FakeOutlineRepository) -> None:
        outline = make_chapter_outline(stage_assignment="act-1", outline_notes="draft")
        repo.seed(outline)

        updated = await repo.update(
            outline.chapter_id,
            stage_assignment="act-2",
            outline_notes="revised",
        )

        assert updated.stage_assignment == "act-2"
        assert updated.outline_notes == "revised"

    async def test_update_when_not_found_raises_not_found_error(
        self, repo: FakeOutlineRepository
    ) -> None:
        missing_id = uuid.uuid4()

        with pytest.raises(NotFoundError):
            await repo.update(missing_id, stage_assignment="act-3")


# ---------------------------------------------------------------------------
# Call tracking
# ---------------------------------------------------------------------------


class TestCallTracking:
    async def test_call_count_tracks_method_invocations(self, repo: FakeOutlineRepository) -> None:
        chapter_id = uuid.uuid4()

        await repo.get_by_chapter_id(chapter_id)
        await repo.get_by_chapter_id(chapter_id)

        assert repo.call_count("get_by_chapter_id") == 2

    async def test_assert_called_once_passes_for_single_call(
        self, repo: FakeOutlineRepository
    ) -> None:
        chapter_id = uuid.uuid4()
        await repo.get_by_chapter_id(chapter_id)

        repo.assert_called_once("get_by_chapter_id")

    async def test_assert_called_once_raises_for_wrong_count(
        self, repo: FakeOutlineRepository
    ) -> None:
        chapter_id = uuid.uuid4()
        await repo.get_by_chapter_id(chapter_id)
        await repo.get_by_chapter_id(chapter_id)

        with pytest.raises(AssertionError, match="Expected 1 call"):
            repo.assert_called_once("get_by_chapter_id")
