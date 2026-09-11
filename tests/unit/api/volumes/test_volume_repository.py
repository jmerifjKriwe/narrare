"""Unit tests for ``VolumeRepository`` query wiring (fake session).

Exercises every repository method including the multi-query ``get_stats``
(aggregate row + target lookup) and the ``reorder`` bulk-update loop, plus
the ``max_position`` explicit-None empty-set fallback. No real database.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from tests.factories import make_novel, make_volume
from tests.fakes import FakeNovelService
from tests.fakes.fake_db_session import FakeDbSession, FakeResult

from narrare.volumes.repository import VolumeRepository
from narrare.volumes.schemas import CreateVolumeRequest, UpdateVolumeRequest
from narrare.volumes.service import VolumeService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.volumes.models import Volume


class TestVolumeRepositoryReads:
    async def test_get_by_id_returns_volume(self) -> None:
        volume = make_volume()
        session = FakeDbSession([FakeResult(value=volume)])
        repo = VolumeRepository(cast("object", session))  # type: ignore[arg-type]

        result = await repo.get_by_id(volume.id, volume.novel_id)

        assert result is volume

    async def test_list_by_novel_returns_ordered_scalars(self) -> None:
        volumes = [make_volume(), make_volume()]
        session = FakeDbSession([FakeResult(scalars=volumes)])
        repo = VolumeRepository(cast("object", session))  # type: ignore[arg-type]

        result = await repo.list_by_novel(uuid4())

        assert result == volumes

    async def test_max_position_returns_max_value(self) -> None:
        session = FakeDbSession([FakeResult(value=3)])
        repo = VolumeRepository(cast("object", session))  # type: ignore[arg-type]

        result = await repo.max_position(uuid4())

        assert result == 3

    async def test_max_position_returns_minus_one_when_empty(self) -> None:
        """An empty aggregate (None) resolves to -1 via the explicit None check."""
        session = FakeDbSession([FakeResult(value=None)])
        repo = VolumeRepository(cast("object", session))  # type: ignore[arg-type]

        result = await repo.max_position(uuid4())

        assert result == -1

    async def test_get_default_volume_returns_match(self) -> None:
        default = make_volume(is_default=True)
        session = FakeDbSession([FakeResult(value=default)])
        repo = VolumeRepository(cast("object", session))  # type: ignore[arg-type]

        result = await repo.get_default_volume(default.novel_id)

        assert result is default


class TestVolumeRepositoryWrite:
    async def test_create_adds_and_flushes_with_position(self) -> None:
        session = FakeDbSession()
        repo = VolumeRepository(cast("object", session))  # type: ignore[arg-type]

        result = await repo.create(uuid4(), "Act One", 0, is_default=True)

        assert result.title == "Act One"
        assert result.is_default is True
        assert len(session.added) == 1
        assert session.flush_count == 1

    async def test_update_applies_non_none_fields(self) -> None:
        volume: Volume = make_volume(title="Old")
        session = FakeDbSession()
        repo = VolumeRepository(cast("object", session))  # type: ignore[arg-type]

        result = await repo.update(volume, UpdateVolumeRequest(title="New"))

        assert result.title == "New"
        assert session.flush_count == 1

    async def test_delete_delegates_and_flushes(self) -> None:
        volume = make_volume()
        session = FakeDbSession()
        repo = VolumeRepository(cast("object", session))  # type: ignore[arg-type]

        await repo.delete(volume)

        assert session.deleted == [volume]
        assert session.flush_count == 1


class TestVolumeRepositoryGetStats:
    async def test_get_stats_assembles_dict_from_two_queries(self) -> None:
        """get_stats runs an aggregate query then a target lookup."""
        row = SimpleNamespace(word_count=1200, chapter_count=4)
        session = FakeDbSession([FakeResult(value=row), FakeResult(value=50000)])
        repo = VolumeRepository(cast("object", session))  # type: ignore[arg-type]

        result = await repo.get_stats(uuid4())

        assert result == {
            "word_count": 1200,
            "chapter_count": 4,
            "word_count_target": 50000,
        }

    async def test_get_stats_target_none_when_volume_missing(self) -> None:
        """When the target lookup returns None, word_count_target is None."""
        row = SimpleNamespace(word_count=0, chapter_count=0)
        session = FakeDbSession([FakeResult(value=row), FakeResult(value=None)])
        repo = VolumeRepository(cast("object", session))  # type: ignore[arg-type]

        result = await repo.get_stats(uuid4())

        assert result["word_count_target"] is None
        assert result["chapter_count"] == 0


class TestVolumeRepositoryReorder:
    async def test_reorder_issues_update_per_volume_then_lists(self) -> None:
        """reorder() executes once per id, flushes, then re-lists."""
        volumes = [make_volume(), make_volume(), make_volume()]
        novel_id = volumes[0].novel_id
        # 3 ignored update-executes + 1 final list query returning the volumes.
        session = FakeDbSession(
            [FakeResult(), FakeResult(), FakeResult(), FakeResult(scalars=volumes)]
        )
        repo = VolumeRepository(cast("object", session))  # type: ignore[arg-type]

        result = await repo.reorder(novel_id, [v.id for v in volumes])

        assert result == volumes
        assert session.flush_count == 1


# ---------------------------------------------------------------------------
# Regression — max_position falsy-zero (same class as chapters fix)
# ---------------------------------------------------------------------------


class TestSequentialCreatePositions:
    """Sequential creates without explicit position must assign 0, 1, 2, …

    Regression guard for the falsy-zero bug in ``VolumeRepository.
    max_position``: ``scalar_one_or_none() or -1`` mapped a legitimate
    max position of 0 (the first volume) to -1, so every subsequent
    volume was also created with position 0.
    """

    async def test_create_without_position_assigns_sequential_0_1(self) -> None:
        """DB max values None → 0 must produce volume positions 0, 1."""
        session = FakeDbSession(
            [
                FakeResult(value=None),  # empty novel
                FakeResult(value=0),  # max = volume 1
            ]
        )
        repo = VolumeRepository(cast("AsyncSession", session))
        novel_service = FakeNovelService()
        novel_id, user_id = uuid.uuid4(), uuid.uuid4()
        novel_service.seed(make_novel(id=novel_id, user_id=user_id))
        service = VolumeService(repo=repo, novel_service=novel_service)

        volume_1 = await service.create(novel_id, user_id, CreateVolumeRequest(title="Volume 1"))
        volume_2 = await service.create(novel_id, user_id, CreateVolumeRequest(title="Volume 2"))

        assert volume_1.position == 0
        assert volume_2.position == 1  # RED before fix: falsy `0 or -1` → both 0
