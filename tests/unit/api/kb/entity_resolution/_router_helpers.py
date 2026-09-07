"""Shared fakes and app builders for the KB resolution router tests.

Extracted from ``test_router.py`` for RULE-04 (the route tests grew past
the 400-line hard limit when the production-wiring cache test landed).
Structure mirrors the sibling ``kb/_scope_service_helpers.py`` convention:
module-level fakes + factory helpers, imported by the test module. Fixtures
stay in the test module.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from narrare._app.database import get_async_session
from narrare._app.dependencies_auth import get_current_user_id
from narrare.kb.dependencies_core import get_kb_repository, get_rel_repository
from narrare.kb.entity_resolution.analysis_cache import ResolutionAnalysisCache
from narrare.kb.entity_resolution.analysis_service import ResolutionAnalysisService
from narrare.kb.entity_resolution.dependencies import (
    get_novel_scope_repository,
    get_resolution_analyzer,
    get_resolution_dismissal_store,
)
from narrare.kb.entity_resolution.router import router as resolution_router
from narrare.kb.entity_resolution.schemas_resolution import (
    BandStats,
    ResolutionAnalysisResponse,
    SignalEvidence,
    SuggestionResponse,
)
from narrare_core.kb.resolution.models import EntitySnapshot, EntryProvenance
from narrare_core.kb.resolution.scoring import ResolutionEngine
from narrare_core.kb.schemas.entry import NovelKBEntry
from narrare_core.shared.errors import NotFoundError
from tests.fakes.fake_novel_repo import FakeNovelRepository

if TYPE_CHECKING:
    from narrare.kb.entity_resolution.contracts import SnapshotBuilderProtocol
    from narrare_core.writing.session_manager import SessionCacheProtocol

USER_ID = uuid4()
NOVEL_ID = uuid4()

# Identical embeddings -> cosine 1.0 -> S5 = +1.0 (worked-example setup).
SAME_EMBEDDING: tuple[float, ...] = (1.0, 0.0)


# --- Fakes ----------------------------------------------------------------------


class FakeAnalyzer:
    """Fake ResolutionAnalysisService recording endpoint calls."""

    def __init__(self) -> None:
        self.analyze_calls: list[tuple[UUID, UUID, bool]] = []
        self.cached_calls: list[UUID] = []
        self.analyze_response: ResolutionAnalysisResponse = empty_analysis()
        self.cached_response: ResolutionAnalysisResponse = empty_analysis()

    async def analyze(
        self,
        novel_id: UUID,
        user_id: UUID,
        *,
        refresh: bool = False,
    ) -> ResolutionAnalysisResponse:
        self.analyze_calls.append((novel_id, user_id, refresh))
        return self.analyze_response

    async def get_cached(self, novel_id: UUID) -> ResolutionAnalysisResponse:
        self.cached_calls.append(novel_id)
        return self.cached_response


class FakeBuilder:
    """Fake SnapshotBuilderProtocol returning a canned snapshot tuple."""

    def __init__(self, snapshots: tuple[EntitySnapshot, ...]) -> None:
        self.snapshots = snapshots
        self.build_calls = 0

    async def build(self, novel_id: UUID) -> tuple[EntitySnapshot, ...]:
        self.build_calls += 1
        return self.snapshots


class FakeCacheBackend:
    """Dict-backed SessionCacheProtocol fake."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


class FakeResolutionKbRepo:
    """Fake kb repository at the wiring seam (overlay fetch only)."""

    def __init__(self, entries: list[NovelKBEntry]) -> None:
        self._entries = entries

    async def find_overlay_for_novel(self, novel_id: UUID) -> list[NovelKBEntry]:
        return [e for e in self._entries if e.novel_id == novel_id]


class FakeResolutionRelationshipRepo:
    """Fake relationship repository at the wiring seam (adjacency only)."""

    def __init__(self, adjacency: dict[str, set[str]] | None = None) -> None:
        self._adjacency: dict[str, set[str]] = adjacency or {}

    async def get_adjacency_map(
        self,
        novel_id: UUID,
        entity_ids: set[UUID] | None = None,
    ) -> dict[str, set[str]]:
        return dict(self._adjacency)


class FakeDismissedStore:
    """In-memory DismissedSuggestionStore fake recording dismiss calls.

    Shared by the P3 production-wiring builder (which must not touch the
    DB-backed ledger) and the P4 endorse tests (which assert on the
    recorded dismiss calls) — defined here so the builders stay
    import-cycle-free (_endorse_helpers imports from this module).
    """

    def __init__(self) -> None:
        self._rejected: dict[UUID, set[str]] = {}
        self.dismiss_calls: list[tuple[UUID, str]] = []

    async def dismiss(self, novel_id: UUID, suggestion_id: str) -> None:
        self.dismiss_calls.append((novel_id, suggestion_id))
        self._rejected.setdefault(novel_id, set()).add(suggestion_id)

    async def rejected_ids(self, novel_id: UUID) -> frozenset[str]:
        return frozenset(self._rejected.get(novel_id, set()))


async def stub_session() -> AsyncIterator[object]:
    """Hermetic stand-in for the async DB session (no factory touches it)."""
    yield object()


# --- Factory helpers --------------------------------------------------------------


def empty_analysis() -> ResolutionAnalysisResponse:
    """Empty miss response (never analyzed)."""
    return ResolutionAnalysisResponse(
        suggestions=[],
        stats=BandStats(review=0, auto_eligible=0, suppressed=0),
        cache_hit=False,
    )


def one_suggestion_analysis() -> ResolutionAnalysisResponse:
    """Full-shape response with a single AUTO_ELIGIBLE suggestion."""
    return ResolutionAnalysisResponse(
        suggestions=[
            SuggestionResponse(
                suggestion_id="abcd1234abcd1234",
                entry_a_id=uuid4(),
                entry_b_id=uuid4(),
                name_a="Anna",
                name_b="Anna Meyer",
                confidence=0.895,
                band="AUTO_ELIGIBLE",
                auto_merge_eligible=True,
                signals=[
                    SignalEvidence(signal="name_tier", value=0.7, veto=False, detail="subset match")
                ],
            )
        ],
        stats=BandStats(review=0, auto_eligible=1, suppressed=0),
        cache_hit=False,
    )


def duplicate_pair() -> tuple[EntitySnapshot, ...]:
    """§4 worked example: "Anna" (ch-01-03) vs "Anna Meyer" (ch-04+) → 0.895."""
    shared = frozenset({uuid4(), uuid4()})
    anna = EntitySnapshot(
        entry_id=uuid4(),
        name="Anna",
        entity_type="character",
        status="active",
        metadata={},
        provenance=EntryProvenance(
            chapters=(1, 2, 3), first_seen_chapter=1, last_seen_chapter=3, name_variants=()
        ),
        neighbor_ids=shared | {uuid4()},
        embedding=SAME_EMBEDDING,
    )
    anna_meyer = EntitySnapshot(
        entry_id=uuid4(),
        name="Anna Meyer",
        entity_type="character",
        status="active",
        metadata={},
        provenance=EntryProvenance(
            chapters=(4, 5, 6), first_seen_chapter=4, last_seen_chapter=6, name_variants=()
        ),
        neighbor_ids=shared | {uuid4()},
        embedding=SAME_EMBEDDING,
    )
    return (anna, anna_meyer)


def duplicate_entries() -> tuple[list[NovelKBEntry], dict[str, set[str]]]:
    """Entry-level duplicate pair + adjacency for the real production chain."""
    anna_id, anna_meyer_id = uuid4(), uuid4()
    shared = {uuid4(), uuid4()}
    adjacency = {
        str(anna_id): {*(str(u) for u in shared), str(uuid4())},
        str(anna_meyer_id): {*(str(u) for u in shared), str(uuid4())},
    }
    entries = [
        NovelKBEntry(
            id=entry_id,
            entity_type="character",
            name=name,
            slug=f"slug-{name.lower().replace(' ', '-')}",
            status="active",
            metadata_={
                "provenance": {
                    "chapters": list(chapters),
                    "first_seen_chapter": chapters[0],
                    "last_seen_chapter": chapters[-1],
                    "name_variants": [],
                }
            },
            novel_id=NOVEL_ID,
        )
        for entry_id, name, chapters in (
            (anna_id, "Anna", (1, 2, 3)),
            (anna_meyer_id, "Anna Meyer", (4, 5, 6)),
        )
    ]
    return entries, adjacency


def make_resolution_service(
    snapshots: tuple[EntitySnapshot, ...],
) -> ResolutionAnalysisService:
    """Real analysis service over a fake builder + fake cache backend."""
    return ResolutionAnalysisService(
        builder=cast("SnapshotBuilderProtocol", FakeBuilder(snapshots)),
        engine=ResolutionEngine(),
        cache=ResolutionAnalysisCache(cast("SessionCacheProtocol", FakeCacheBackend())),
    )


# --- App builders -------------------------------------------------------------------


def _add_not_found_handler(app: FastAPI) -> None:
    """Mirror the production NarrareError mappings these routes rely on.

    ``_app/main.py`` maps NotFoundError → 404, ConflictError → 409 and
    ValidationError → 422; the endorse/reject surface asserts against all
    three, so the test app mirrors them (404 handler unchanged).
    """
    from narrare_core.shared.errors import ConflictError, ValidationError

    @app.exception_handler(NotFoundError)
    async def _not_found_handler(  # pyright: ignore[reportUnusedFunction]
        _: Request, exc: NotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc), "code": exc.code})

    @app.exception_handler(ConflictError)
    async def _conflict_handler(  # pyright: ignore[reportUnusedFunction]
        _: Request, exc: ConflictError
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc), "code": exc.code})

    @app.exception_handler(ValidationError)
    async def _validation_handler(  # pyright: ignore[reportUnusedFunction]
        _: Request, exc: ValidationError
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": exc.code})


def build_app(
    analyzer: FakeAnalyzer | ResolutionAnalysisService,
    novel_repo: FakeNovelRepository,
    *,
    override_auth: bool = True,
) -> FastAPI:
    """App with the analyzer SEAM overridden (fakes at the service seam)."""
    app = FastAPI()
    app.include_router(resolution_router, prefix="/api/v1")
    _add_not_found_handler(app)

    if override_auth:
        app.dependency_overrides[get_current_user_id] = lambda: str(USER_ID)
    app.dependency_overrides[get_novel_scope_repository] = lambda: novel_repo
    app.dependency_overrides[get_resolution_analyzer] = lambda: analyzer
    return app


def build_production_app(
    novel_repo: FakeNovelRepository,
    kb_repo: FakeResolutionKbRepo,
    rel_repo: FakeResolutionRelationshipRepo,
) -> FastAPI:
    """App with the REAL analyzer factory — fakes only at the repository seam."""
    app = FastAPI()
    app.include_router(resolution_router, prefix="/api/v1")
    _add_not_found_handler(app)

    app.dependency_overrides[get_current_user_id] = lambda: str(USER_ID)
    app.dependency_overrides[get_novel_scope_repository] = lambda: novel_repo
    app.dependency_overrides[get_async_session] = stub_session
    app.dependency_overrides[get_kb_repository] = lambda: kb_repo
    app.dependency_overrides[get_rel_repository] = lambda: rel_repo
    app.dependency_overrides[get_resolution_dismissal_store] = lambda: FakeDismissedStore()
    return app


def mounted_paths(app: FastAPI) -> set[str]:
    """Collect concrete route paths, traversing FastAPI 0.116+ ``_IncludedRouter`` wrappers."""
    paths: set[str] = set()
    for route in app.routes:
        original = getattr(route, "original_router", None)
        context = getattr(route, "include_context", None)
        if original is None or context is None:
            path: str | None = getattr(route, "path", None)
            if path is not None:
                paths.add(path)
            continue
        prefix: str = context.prefix
        for sub in original.routes:
            sub_path: str | None = getattr(sub, "path", None)
            if sub_path is not None:
                paths.add(prefix + sub_path)
    return paths
