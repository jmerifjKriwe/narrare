"""Shared helpers for KBScopeService and scope-endpoint unit tests.

Series Foundation Spec 1, Slice 3 Task 3.7.

Provides builders for Core ``SeriesKBEntry`` / ``NovelKBEntry`` value objects
and a fake of the ``KBRepositoryProtocol`` scope surface used by
:class:`KBScopeService`. Extracted so both ``test_scope_service.py`` (service
logic) and ``test_scope_endpoints.py`` (HTTP status codes) can share the same
fakes without duplication (RULE-04 split). These functions are the module's
public test API (no leading underscore) so cross-module imports don't trip
pyright's ``reportPrivateUsage``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from narrare.kb.scope_service import KBScopeService
from narrare_core.kb.schemas.entry import NovelKBEntry, SeriesKBEntry
from narrare_core.series.schemas import Series
from tests.fakes.fake_novel_repo import FakeNovelRepository
from tests.fakes.fake_series_repo import FakeSeriesRepository


@dataclass
class ScopeFixture:
    """Bundle of a wired ``KBScopeService`` + its fakes and seeded ownership ids."""

    service: KBScopeService
    kb_repo: FakeKBRepo
    novel_repo: FakeNovelRepository
    series_repo: FakeSeriesRepository
    user_id: uuid.UUID
    novel_id: uuid.UUID
    target_novel_id: uuid.UUID
    series_id: uuid.UUID


def make_series_entry(**overrides: object) -> SeriesKBEntry:
    """Build a SeriesKBEntry with sane defaults (canon scope)."""
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "entity_type": "system",
        "name": "Magic System",
        "slug": "magic-system",
        "status": "canon",
        "body": "Hard magic.",
        "series_id": uuid.uuid4(),
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return SeriesKBEntry(**defaults)  # type: ignore[arg-type]


def make_novel_entry(**overrides: object) -> NovelKBEntry:
    """Build a NovelKBEntry with sane defaults (overlay scope)."""
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "entity_type": "character",
        "name": "Anna",
        "slug": "anna",
        "status": "draft",
        "body": "A protagonist.",
        "novel_id": uuid.uuid4(),
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return NovelKBEntry(**defaults)  # type: ignore[arg-type]


class FakeKBRepo:
    """Fake of the KBRepositoryProtocol surface used by KBScopeService.

    Records calls and returns configurable results or raises configured
    errors, so we can assert delegation, return pass-through, and the
    ValueError→ConflictError translation without a database.
    """

    def __init__(self) -> None:
        self.promote_calls: list[tuple[uuid.UUID, uuid.UUID]] = []
        self.demote_calls: list[tuple[uuid.UUID, uuid.UUID, uuid.UUID]] = []
        self._promote_result: SeriesKBEntry | None = None
        self._demote_result: NovelKBEntry | None = None
        self._promote_error: Exception | None = None
        self._demote_error: Exception | None = None

    def set_promote_result(self, result: SeriesKBEntry) -> None:
        self._promote_result = result

    def set_demote_result(self, result: NovelKBEntry) -> None:
        self._demote_result = result

    def set_promote_error(self, exc: Exception) -> None:
        self._promote_error = exc

    def set_demote_error(self, exc: Exception) -> None:
        self._demote_error = exc

    async def promote_to_canon(self, novel_id: uuid.UUID, entry_id: uuid.UUID) -> SeriesKBEntry:
        self.promote_calls.append((novel_id, entry_id))
        if self._promote_error is not None:
            raise self._promote_error
        assert self._promote_result is not None
        return self._promote_result

    async def demote_to_overlay(
        self,
        series_id: uuid.UUID,
        entry_id: uuid.UUID,
        target_novel_id: uuid.UUID,
    ) -> NovelKBEntry:
        self.demote_calls.append((series_id, entry_id, target_novel_id))
        if self._demote_error is not None:
            raise self._demote_error
        assert self._demote_result is not None
        return self._demote_result


def build_scope_service(
    *,
    user_id: uuid.UUID | None = None,
    novel_id: uuid.UUID | None = None,
    series_id: uuid.UUID | None = None,
    target_novel_id: uuid.UUID | None = None,
) -> ScopeFixture:
    """Wire a ``KBScopeService`` with ownership-seeded Novel + Series fakes.

    The Novel + Series fakes are seeded so the caller owns the novel(s)/series
    (C1 ownership happy path); the KB fake records promote/demote calls. All
    seeded ids are exposed on the returned :class:`ScopeFixture`.
    """
    user_id = user_id or uuid.uuid4()
    novel_id = novel_id or uuid.uuid4()
    series_id = series_id or uuid.uuid4()
    target_novel_id = target_novel_id or uuid.uuid4()
    kb_repo = FakeKBRepo()
    novel_repo = FakeNovelRepository()
    from tests.factories import make_novel

    novel_repo.seed(make_novel(id=novel_id, user_id=user_id))
    novel_repo.seed(make_novel(id=target_novel_id, user_id=user_id))
    series_repo = FakeSeriesRepository()
    series_repo.seed(Series(id=series_id, user_id=user_id, title="Test Series"))
    service = KBScopeService(kb_repo, novel_repo, series_repo)
    return ScopeFixture(
        service=service,
        kb_repo=kb_repo,
        novel_repo=novel_repo,
        series_repo=series_repo,
        user_id=user_id,
        novel_id=novel_id,
        target_novel_id=target_novel_id,
        series_id=series_id,
    )
