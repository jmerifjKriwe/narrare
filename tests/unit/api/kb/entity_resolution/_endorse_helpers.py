"""Shared fakes and app builders for the endorse/reject route tests.

Split from ``_router_helpers.py`` per RULE-04 (the P4 slice adds the
endorse/reject surface with its own repository seams). Mirrors the
established helper convention: module-level fakes + one app builder,
imported by the test module. The app builder runs the REAL analyzer,
analysis cache, and endorse-service factories — fakes sit only at the
repository/dismissal seams (same fidelity as ``build_production_app``).

A distinct novel id (``ENDORSE_NOVEL_ID``) isolates these tests from the
process-wide analysis-cache singleton the P3 production-wiring test uses
(T8 deferred minor: no reset seam — distinct keys are the hygiene).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from fastapi import FastAPI

from narrare._app.database import get_async_session
from narrare._app.dependencies_auth import get_current_user_id
from narrare.kb.dependencies_core import get_kb_repository, get_rel_repository
from narrare.kb.entity_resolution.dependencies import (
    get_novel_scope_repository,
    get_resolution_dismissal_store,
)
from narrare.kb.entity_resolution.router import router as resolution_router
from narrare.kb.entity_resolution.schemas_resolution import (
    BandStats,
    ResolutionAnalysisResponse,
    SuggestionResponse,
)

from ._router_helpers import (
    NOVEL_ID,
    USER_ID,
    FakeDismissedStore,
    _add_not_found_handler,
    mounted_paths,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from tests.fakes.fake_novel_repo import FakeNovelRepository

ENDORSE_NOVEL_ID = uuid4()

__all__ = [
    "ENDORSE_NOVEL_ID",
    "NOVEL_ID",
    "USER_ID",
    "FakeDismissedStore",
    "FakeEndorseEdge",
    "FakeEndorseEntry",
    "FakeEndorseKbRepo",
    "FakeEndorseRelRepo",
    "FakeEndorseSession",
    "build_endorse_app",
    "duplicate_endorse_entries",
    "fake_endorse_session",
    "low_band_entries",
    "mounted_paths",
    "suggestion_id_for",
]


# --- Fakes ----------------------------------------------------------------------


class FakeEndorseEntry:
    """Plain mutable entry exposing every column builder + executor touch.

    ``NovelKBEntry`` lacks ``created_at``/``embeddings_dirty``; a plain
    stand-in serves both the SnapshotBuilder read and the MergeExecutor
    read/write seam in one object.
    """

    def __init__(
        self,
        *,
        name: str,
        chapters: tuple[int, ...],
        novel_id: UUID = ENDORSE_NOVEL_ID,
        status: str = "active",
        created_at: datetime | None = None,
    ) -> None:
        self.id = uuid4()
        self.novel_id = novel_id
        self.entity_type = "character"
        self.name = name
        self.slug = f"slug-{name.lower().replace(' ', '-')}"
        self.status = status
        self.metadata_: dict[str, object] = {
            "provenance": {
                "chapters": list(chapters),
                "first_seen_chapter": chapters[0],
                "last_seen_chapter": chapters[-1],
                "name_variants": [],
            }
        }
        self.embeddings_dirty = False
        self.created_at = created_at or datetime.now(tz=UTC)


class FakeEndorseKbRepo:
    """Fake kb repository: overlay fetch + scoped get + recorded updates."""

    def __init__(self, entries: list[FakeEndorseEntry]) -> None:
        self._entries = entries
        self.updates: list[tuple[UUID, dict[str, object]]] = []

    async def find_overlay_for_novel(self, novel_id: UUID) -> list[FakeEndorseEntry]:
        return [e for e in self._entries if e.novel_id == novel_id]

    async def get_by_id(self, entry_id: UUID) -> FakeEndorseEntry | None:
        return next((e for e in self._entries if e.id == entry_id), None)

    def get_one(self, entry_id: UUID) -> FakeEndorseEntry:
        """Sync test accessor: fetch a seeded entry or fail the test."""
        entry = next((e for e in self._entries if e.id == entry_id), None)
        if entry is None:
            msg = f"entry {entry_id} not seeded"
            raise AssertionError(msg)
        return entry

    async def update(self, entry: FakeEndorseEntry, data: dict[str, object]) -> FakeEndorseEntry:
        for field, value in data.items():
            setattr(entry, field, value)
        self.updates.append((entry.id, dict(data)))
        return entry


class FakeEndorseEdge:
    """Minimal KBRelationship stand-in (uq shape: source/target/rel_type)."""

    def __init__(self, *, source_id: UUID, target_id: UUID, rel_type: str = "ally") -> None:
        self.id = uuid4()
        self.source_id = source_id
        self.target_id = target_id
        self.rel_type = rel_type


class FakeEndorseRelRepo:
    """Fake relationship repository at the endorse/executor wiring seam.

    Holds REAL edge objects: the executor's repoint loop reads and
    mutates ``source_id``/``target_id``, and ``exists`` mirrors the
    ``uq_kb_relationships_unique`` shape.
    """

    def __init__(self) -> None:
        self.edges: list[FakeEndorseEdge] = []

    def add_edge(self, source_id: UUID, target_id: UUID, rel_type: str = "ally") -> FakeEndorseEdge:
        edge = FakeEndorseEdge(source_id=source_id, target_id=target_id, rel_type=rel_type)
        self.edges.append(edge)
        return edge

    async def get_adjacency_map(
        self,
        novel_id: UUID,
        entity_ids: set[UUID] | None = None,
    ) -> dict[str, set[str]]:
        adjacency: dict[str, set[str]] = {}
        for e in self.edges:
            adjacency.setdefault(str(e.source_id), set()).add(str(e.target_id))
            adjacency.setdefault(str(e.target_id), set()).add(str(e.source_id))
        return adjacency

    async def list_for_entry(
        self, entry_id: UUID, direction: str | None = None
    ) -> list[FakeEndorseEdge]:
        return [e for e in self.edges if entry_id in (e.source_id, e.target_id)]

    async def exists(self, source_id: UUID, target_id: UUID, rel_type: str) -> bool:
        return any(
            e.source_id == source_id and e.target_id == target_id and e.rel_type == rel_type
            for e in self.edges
        )

    async def update(self, rel: FakeEndorseEdge, data: dict[str, object]) -> FakeEndorseEdge:
        for field, value in data.items():
            setattr(rel, field, value)
        return rel


class FakeEndorseSession:
    """AsyncSession stand-in exposing the ``begin_nested`` savepoint seam.

    The savepoint never suppresses exceptions — a failing merge still
    surfaces (mirrors the merge-executor test fake).
    """

    def begin_nested(self) -> _FakeSavepoint:
        return _FakeSavepoint()


class _FakeSavepoint:
    async def __aenter__(self) -> _FakeSavepoint:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> bool:
        return False


async def fake_endorse_session() -> AsyncIterator[FakeEndorseSession]:
    """Session dependency yielding the savepoint-capable fake."""
    yield FakeEndorseSession()


# --- Factory helpers --------------------------------------------------------------


async def stub_session_iter() -> AsyncIterator[object]:
    yield object()


def suggestion_id_for(a: UUID, b: UUID) -> str:
    """The stateless suggestion id: sha256(min ‖ max)[:16]."""
    import hashlib

    lo, hi = sorted((str(a), str(b)))
    return hashlib.sha256(f"{lo}{hi}".encode()).hexdigest()[:16]


def duplicate_endorse_entries() -> list[FakeEndorseEntry]:
    """§4 worked example pair: "Anna" (ch-01-03) vs "Anna Meyer" (ch-04+)."""
    return [
        FakeEndorseEntry(name="Anna", chapters=(1, 2, 3)),
        FakeEndorseEntry(name="Anna Meyer", chapters=(4, 5, 6)),
    ]


def low_band_entries() -> list[FakeEndorseEntry]:
    """Distractor pair ("Anna Meyer"/"Anna Meier", co-active) → SUPPRESSED."""
    return [
        FakeEndorseEntry(name="Anna Meyer", chapters=(8, 9, 10)),
        FakeEndorseEntry(name="Anna Meier", chapters=(9, 10, 11)),
    ]


def build_endorse_app(
    novel_repo: FakeNovelRepository,
    kb_repo: FakeEndorseKbRepo,
    rel_repo: FakeEndorseRelRepo,
    dismissed_store: FakeDismissedStore,
) -> FastAPI:
    """App with the REAL analyzer + endorse factories — fakes at the seams."""
    app = FastAPI()
    app.include_router(resolution_router, prefix="/api/v1")
    _add_not_found_handler(app)

    app.dependency_overrides[get_current_user_id] = lambda: str(USER_ID)
    app.dependency_overrides[get_novel_scope_repository] = lambda: novel_repo
    app.dependency_overrides[get_async_session] = fake_endorse_session
    app.dependency_overrides[get_kb_repository] = lambda: kb_repo
    app.dependency_overrides[get_rel_repository] = lambda: rel_repo
    app.dependency_overrides[get_resolution_dismissal_store] = lambda: dismissed_store
    return app


def analysis_response_for(
    entry_a: FakeEndorseEntry, entry_b: FakeEndorseEntry
) -> ResolutionAnalysisResponse:
    """Canned single-suggestion response for a concrete entry pair."""
    return ResolutionAnalysisResponse(
        suggestions=[
            SuggestionResponse(
                suggestion_id=suggestion_id_for(entry_a.id, entry_b.id),
                entry_a_id=min(entry_a.id, entry_b.id),
                entry_b_id=max(entry_a.id, entry_b.id),
                name_a=entry_a.name,
                name_b=entry_b.name,
                confidence=0.645,
                band="REVIEW",
                auto_merge_eligible=False,
                signals=[],
            )
        ],
        stats=BandStats(review=1, auto_eligible=0, suppressed=0),
        cache_hit=False,
    )
