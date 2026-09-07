"""Unit tests for the KB resolution HTTP surface (ADR-085 P3, spec §7).

Route-level tests for the two P3 endpoints (``POST .../resolution/analyze``
and ``GET .../resolution/suggestions``): auth (401 without token), novel
scope enforcement (404 for foreign/unknown novels — anti-enumeration, the
same semantics the kb relationship surface has for foreign-novel
resources), the analyze response shape (suggestions + stats + cache_hit),
the 404-free suggestions GET (empty list when never analyzed), the cache
round-trip (analyze then GET serves the cached pair with ``cache_hit``
and no recompute), and the ``refresh`` flag reaching the service.

Service fakes are injected via FastAPI ``dependency_overrides`` (ADR-030:
fakes, not MagicMock); the scope guard runs as the real dependency against
a seeded fake novel repository. A minimal ``NotFoundError`` handler
mirrors the production mapping in ``_app/main.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from narrare._app.dependencies_auth import get_current_user_id
from narrare.kb.entity_resolution.analysis_service import (
    ResolutionAnalysisCache,
    ResolutionAnalysisService,
)
from narrare.kb.entity_resolution.dependencies import (
    get_novel_scope_repository,
    get_resolution_analyzer,
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
from narrare_core.shared.errors import NotFoundError
from tests.factories import make_novel
from tests.fakes.fake_novel_repo import FakeNovelRepository

if TYPE_CHECKING:
    from collections.abc import Iterator

    from narrare.kb.entity_resolution.contracts import SnapshotBuilderProtocol
    from narrare_core.writing.session_manager import SessionCacheProtocol

_USER_ID = uuid4()
_NOVEL_ID = uuid4()

# Identical embeddings -> cosine 1.0 -> S5 = +1.0 (worked-example setup).
_SAME_EMBEDDING: tuple[float, ...] = (1.0, 0.0)


# --- Fakes ----------------------------------------------------------------------


class _FakeAnalyzer:
    """Fake ResolutionAnalysisService recording endpoint calls."""

    def __init__(self) -> None:
        self.analyze_calls: list[tuple[UUID, UUID, bool]] = []
        self.cached_calls: list[UUID] = []
        self.analyze_response: ResolutionAnalysisResponse = _empty_analysis()
        self.cached_response: ResolutionAnalysisResponse = _empty_analysis()

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


class _FakeBuilder:
    """Fake SnapshotBuilderProtocol returning a canned snapshot tuple."""

    def __init__(self, snapshots: tuple[EntitySnapshot, ...]) -> None:
        self.snapshots = snapshots
        self.build_calls = 0

    async def build(self, novel_id: UUID) -> tuple[EntitySnapshot, ...]:
        self.build_calls += 1
        return self.snapshots


class _FakeCacheBackend:
    """Dict-backed SessionCacheProtocol fake."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


# --- Helpers --------------------------------------------------------------------


def _empty_analysis() -> ResolutionAnalysisResponse:
    return ResolutionAnalysisResponse(
        suggestions=[],
        stats=BandStats(review=0, auto_eligible=0, suppressed=0),
        cache_hit=False,
    )


def _one_suggestion_analysis() -> ResolutionAnalysisResponse:
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


def _provenance(first: int, last: int) -> EntryProvenance:
    return EntryProvenance(
        chapters=tuple(range(first, last + 1)),
        first_seen_chapter=first,
        last_seen_chapter=last,
        name_variants=(),
    )


def _snapshot(
    *,
    name: str,
    provenance: EntryProvenance,
    neighbor_ids: frozenset[UUID],
    embedding: tuple[float, ...],
) -> EntitySnapshot:
    return EntitySnapshot(
        entry_id=uuid4(),
        name=name,
        entity_type="character",
        status="active",
        metadata={},
        provenance=provenance,
        neighbor_ids=neighbor_ids,
        embedding=embedding,
    )


def _duplicate_pair() -> tuple[EntitySnapshot, ...]:
    """§4 worked example: "Anna" (ch-01-03) vs "Anna Meyer" (ch-04+) → 0.895."""
    shared = frozenset({uuid4(), uuid4()})
    anna = _snapshot(
        name="Anna",
        provenance=_provenance(1, 3),
        neighbor_ids=shared | {uuid4()},
        embedding=_SAME_EMBEDDING,
    )
    anna_meyer = _snapshot(
        name="Anna Meyer",
        provenance=_provenance(4, 6),
        neighbor_ids=shared | {uuid4()},
        embedding=_SAME_EMBEDDING,
    )
    return (anna, anna_meyer)


def _build_app(
    analyzer: _FakeAnalyzer | ResolutionAnalysisService,
    novel_repo: FakeNovelRepository,
    *,
    override_auth: bool = True,
) -> FastAPI:
    app = FastAPI()
    app.include_router(resolution_router, prefix="/api/v1")

    @app.exception_handler(NotFoundError)
    async def _not_found_handler(  # pyright: ignore[reportUnusedFunction]
        _: Request, exc: NotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc), "code": exc.code})

    if override_auth:
        app.dependency_overrides[get_current_user_id] = lambda: str(_USER_ID)
    app.dependency_overrides[get_novel_scope_repository] = lambda: novel_repo
    app.dependency_overrides[get_resolution_analyzer] = lambda: analyzer
    return app


@pytest.fixture
def novel_repo() -> FakeNovelRepository:
    repo = FakeNovelRepository()
    repo.seed(make_novel(id=_NOVEL_ID, user_id=_USER_ID))
    return repo


@pytest.fixture
def analyzer() -> _FakeAnalyzer:
    return _FakeAnalyzer()


@pytest.fixture
def client(analyzer: _FakeAnalyzer, novel_repo: FakeNovelRepository) -> Iterator[TestClient]:
    with TestClient(_build_app(analyzer, novel_repo)) as test_client:
        yield test_client


# --- Route table ------------------------------------------------------------------


def _mounted_paths(app: FastAPI) -> set[str]:
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


class TestRouteTable:
    def test_create_app_mounts_resolution_endpoints(self) -> None:
        """The app factory mounts both spec §7 P3 endpoints."""
        from narrare._app.main import create_app

        paths = _mounted_paths(create_app(test_mode=True))
        assert "/api/v1/novels/{novel_id}/kb/resolution/analyze" in paths
        assert "/api/v1/novels/{novel_id}/kb/resolution/suggestions" in paths


# --- Auth -----------------------------------------------------------------------


class TestAuth:
    def test_analyze_without_token_returns_401(self, novel_repo: FakeNovelRepository) -> None:
        """A request without a bearer token is rejected at the auth dep."""
        app = _build_app(_FakeAnalyzer(), novel_repo, override_auth=False)
        with TestClient(app) as bare_client:
            response = bare_client.post(
                f"/api/v1/novels/{_NOVEL_ID}/kb/resolution/analyze",
                json={"refresh": False},
            )

        assert response.status_code == 401


# --- Novel scope ------------------------------------------------------------------


class TestNovelScope:
    def test_analyze_with_foreign_novel_returns_404(
        self, client: TestClient, analyzer: _FakeAnalyzer
    ) -> None:
        """A novel not owned by the caller → 404 (anti-enumeration)."""
        response = client.post(
            f"/api/v1/novels/{uuid4()}/kb/resolution/analyze",
            json={"refresh": False},
        )

        assert response.status_code == 404
        assert response.json()["code"] == "NOT_FOUND"
        assert analyzer.analyze_calls == []  # scope failure short-circuits


# --- Analyze endpoint ---------------------------------------------------------------


class TestAnalyzeEndpoint:
    def test_analyze_with_valid_request_returns_suggestions_and_stats(
        self, client: TestClient, analyzer: _FakeAnalyzer
    ) -> None:
        analyzer.analyze_response = _one_suggestion_analysis()
        response = client.post(
            f"/api/v1/novels/{_NOVEL_ID}/kb/resolution/analyze",
            json={"refresh": False},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["cache_hit"] is False
        assert body["stats"] == {"review": 0, "auto_eligible": 1, "suppressed": 0}
        (suggestion,) = body["suggestions"]
        assert suggestion["suggestion_id"] == "abcd1234abcd1234"
        assert suggestion["band"] == "AUTO_ELIGIBLE"
        assert suggestion["auto_merge_eligible"] is True
        assert suggestion["confidence"] == pytest.approx(0.895)
        assert suggestion["signals"][0]["signal"] == "name_tier"
        # The route delegated the authenticated scope, not a fabricated one.
        assert analyzer.analyze_calls == [(_NOVEL_ID, _USER_ID, False)]

    def test_analyze_with_refresh_true_passes_flag_to_service(
        self, client: TestClient, analyzer: _FakeAnalyzer
    ) -> None:
        response = client.post(
            f"/api/v1/novels/{_NOVEL_ID}/kb/resolution/analyze",
            json={"refresh": True},
        )

        assert response.status_code == 200
        assert analyzer.analyze_calls == [(_NOVEL_ID, _USER_ID, True)]


# --- Suggestions GET endpoint ---------------------------------------------------------


class TestSuggestionsEndpoint:
    def test_suggestions_get_before_any_analyze_returns_200_empty_list(
        self, client: TestClient, analyzer: _FakeAnalyzer
    ) -> None:
        """404-free: never-analyzed novels yield an empty list, not an error."""
        response = client.get(f"/api/v1/novels/{_NOVEL_ID}/kb/resolution/suggestions")

        assert response.status_code == 200
        body = response.json()
        assert body["suggestions"] == []
        assert body["stats"] == {"review": 0, "auto_eligible": 0, "suppressed": 0}
        assert body["cache_hit"] is False
        assert analyzer.cached_calls == [_NOVEL_ID]
        assert analyzer.analyze_calls == []  # GET never triggers a recompute

    def test_analyze_then_suggestions_get_returns_cached_pair(
        self, novel_repo: FakeNovelRepository
    ) -> None:
        """Real service + cache: GET serves the cached analysis, no recompute."""
        service = ResolutionAnalysisService(
            builder=cast("SnapshotBuilderProtocol", _FakeBuilder(_duplicate_pair())),
            engine=ResolutionEngine(),
            cache=ResolutionAnalysisCache(cast("SessionCacheProtocol", _FakeCacheBackend())),
        )
        with TestClient(_build_app(service, novel_repo)) as test_client:
            created = test_client.post(
                f"/api/v1/novels/{_NOVEL_ID}/kb/resolution/analyze",
                json={"refresh": False},
            )
            fetched = test_client.get(f"/api/v1/novels/{_NOVEL_ID}/kb/resolution/suggestions")

        assert created.status_code == 200
        assert created.json()["cache_hit"] is False
        pair = created.json()["suggestions"]
        assert len(pair) == 1
        assert pair[0]["confidence"] > 0

        assert fetched.status_code == 200
        # cache_hit=True proves the GET was served from cache, not recomputed.
        assert fetched.json()["cache_hit"] is True
        assert fetched.json()["suggestions"] == pair
