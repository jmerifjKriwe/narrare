"""Builders and service factory for ``SeriesJoinService`` unit tests.

Kept out of ``test_join_service.py`` to respect the RULE-04 300-line test
file limit. The fakes themselves live in ``tests/fakes/`` (ADR-030); this
module holds the small test-data factories that wire those fakes together.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from narrare.series.join_service import SeriesJoinService
from narrare_core.kb.schemas.entry import NovelKBEntry, SeriesKBEntry
from narrare_core.series.schemas import Series
from tests.fakes.fake_db_session import FakeTxSession
from tests.fakes.fake_kb_join_repo import FakeJoinKBRepo
from tests.fakes.fake_novel_repo import FakeNovelRepository
from tests.fakes.fake_series_repo import FakeSeriesRepository


def overlay_entry(novel_id: UUID, *, entity_type: str, slug: str | None = None) -> NovelKBEntry:
    """Build a Novel-Overlay KB entry (Core type) with sensible defaults."""
    return NovelKBEntry(
        id=uuid4(),
        entity_type=entity_type,
        name=entity_type.title(),
        slug=slug or entity_type,
        novel_id=novel_id,
    )


def canon_entry(series_id: UUID, *, entity_type: str = "system") -> SeriesKBEntry:
    """Build a Series-Canon KB entry (Core type) with sensible defaults."""
    return SeriesKBEntry(
        id=uuid4(),
        entity_type=entity_type,
        name=entity_type.title(),
        slug=f"{entity_type}-canon",
        series_id=series_id,
    )


def make_series(*, user_id: UUID, series_id: UUID | None = None, **overrides: object) -> Series:
    """Build a Core ``Series`` owned by ``user_id`` (C1 ownership seeding)."""
    defaults: dict[str, object] = {
        "id": series_id or uuid4(),
        "user_id": user_id,
        "title": "Test Series",
        "subtitle": None,
        "description": None,
        "genre": None,
        "writing_language": None,
        "status": "draft",
        "planned_novel_count": None,
    }
    defaults.update(overrides)
    return Series(**defaults)  # type: ignore[arg-type]


def seed_mixed_novel(novel_id: UUID, kb_repo: FakeJoinKBRepo) -> list[NovelKBEntry]:
    """Seed one Canon-type + one Overlay-type entry on the novel."""
    entries = [
        overlay_entry(novel_id, entity_type="system"),
        overlay_entry(novel_id, entity_type="character"),
    ]
    kb_repo.seed_overlay(novel_id, entries)
    return entries


def build_owned(
    *,
    user_id: UUID,
    series: Series | None = None,
    novel_id: UUID | None = None,
    novel_series_id: UUID | None = None,
    canon: list[SeriesKBEntry] | None = None,
    overlays: list[NovelKBEntry] | None = None,
    session: FakeTxSession | None = None,
) -> tuple[
    SeriesJoinService,
    FakeTxSession,
    FakeNovelRepository,
    FakeJoinKBRepo,
    FakeSeriesRepository,
    Series,
    UUID,
]:
    """Build a join service with series + novel owned by ``user_id`` (C1 seeding).

    Collapses the repeated ownership seeding the join tests need: a Series owned
    by ``user_id`` and a Novel owned by ``user_id`` (``series_id`` configurable
    via ``novel_series_id``), plus optional Canon/Overlay KB seeding. Returns
    ``(service, session, novel_repo, kb_repo, series_repo, series, novel_id)``.

    ``session`` may be injected to simulate transaction-control behaviour
    (e.g. a commit-time ``IntegrityError``); defaults to a fresh
    :class:`FakeTxSession`. Mirrors :func:`build_service`.
    """
    series = series or make_series(user_id=user_id)
    novel_id = novel_id or uuid4()
    novel_repo = FakeNovelRepository()
    from tests.factories import make_novel

    novel_repo.seed(make_novel(id=novel_id, user_id=user_id, series_id=novel_series_id))
    kb_repo = FakeJoinKBRepo()
    if canon is not None:
        kb_repo.seed_canon(series.id, canon)
    if overlays is not None:
        kb_repo.seed_overlay(novel_id, overlays)
    series_repo = FakeSeriesRepository()
    series_repo.seed(series)
    # Local (not parameter reassignment): pyright-tests basic-mode keeps a
    # parameter's declared ``FakeTxSession | None`` even after ``if … is None``
    # narrowing, so a fresh local is required to surface a non-Optional type.
    tx_session = session if session is not None else FakeTxSession()
    service = SeriesJoinService(tx_session, series_repo, novel_repo, kb_repo)
    return service, tx_session, novel_repo, kb_repo, series_repo, series, novel_id


def build_service(
    *,
    session: FakeTxSession | None = None,
    novel_repo: FakeNovelRepository | None = None,
    kb_repo: FakeJoinKBRepo | None = None,
    series_repo: FakeSeriesRepository | None = None,
) -> tuple[
    SeriesJoinService,
    FakeTxSession,
    FakeNovelRepository,
    FakeJoinKBRepo,
    FakeSeriesRepository,
]:
    """Assemble a ``SeriesJoinService`` wired to fresh fakes by default.

    ``series_repo`` is now exercised (series ownership + leave-time KB detach),
    so a real ``FakeSeriesRepository`` is wired in — tests seed an owned series
    onto it (see :func:`make_series`).
    """
    # Locals (not parameter reassignment): pyright-tests basic-mode keeps a
    # parameter's declared ``T | None`` even after ``if … is None`` narrowing,
    # so fresh locals are required to surface non-Optional types. See
    # ``build_owned`` for the same pattern on the session parameter.
    tx_session = session if session is not None else FakeTxSession()
    novel_repository = novel_repo if novel_repo is not None else FakeNovelRepository()
    kb_repository = kb_repo if kb_repo is not None else FakeJoinKBRepo()
    series_repository = series_repo if series_repo is not None else FakeSeriesRepository()
    service = SeriesJoinService(tx_session, series_repository, novel_repository, kb_repository)
    return service, tx_session, novel_repository, kb_repository, series_repository
