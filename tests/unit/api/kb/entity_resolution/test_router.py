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
mirrors the production mapping in ``_app/main.py``. One test exercises the
REAL production wiring (analyzer factory not overridden, fakes only at the
repository seam) to pin the process-wide cache-backend lifetime: the
analysis cache must survive across requests.

Fakes, factories, and app builders live in ``_router_helpers.py``
(RULE-04 split); fixtures stay here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.factories import make_novel
from tests.fakes.fake_novel_repo import FakeNovelRepository

from ._router_helpers import (
    NOVEL_ID,
    USER_ID,
    FakeAnalyzer,
    FakeResolutionKbRepo,
    FakeResolutionRelationshipRepo,
    build_app,
    build_production_app,
    duplicate_entries,
    duplicate_pair,
    make_resolution_service,
    mounted_paths,
    one_suggestion_analysis,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


# --- Fixtures -------------------------------------------------------------------


@pytest.fixture
def novel_repo() -> FakeNovelRepository:
    repo = FakeNovelRepository()
    repo.seed(make_novel(id=NOVEL_ID, user_id=USER_ID))
    return repo


@pytest.fixture
def analyzer() -> FakeAnalyzer:
    return FakeAnalyzer()


@pytest.fixture
def client(analyzer: FakeAnalyzer, novel_repo: FakeNovelRepository) -> Iterator[TestClient]:
    with TestClient(build_app(analyzer, novel_repo)) as test_client:
        yield test_client


# --- Route table ------------------------------------------------------------------


class TestRouteTable:
    def test_create_app_mounts_resolution_endpoints(self) -> None:
        """The app factory mounts both spec §7 P3 endpoints."""
        from narrare._app.main import create_app

        paths = mounted_paths(create_app(test_mode=True))
        assert "/api/v1/novels/{novel_id}/kb/resolution/analyze" in paths
        assert "/api/v1/novels/{novel_id}/kb/resolution/suggestions" in paths


# --- Auth -----------------------------------------------------------------------


class TestAuth:
    def test_analyze_without_token_returns_401(self, novel_repo: FakeNovelRepository) -> None:
        """A request without a bearer token is rejected at the auth dep."""
        app = build_app(FakeAnalyzer(), novel_repo, override_auth=False)
        with TestClient(app) as bare_client:
            response = bare_client.post(
                f"/api/v1/novels/{NOVEL_ID}/kb/resolution/analyze",
                json={"refresh": False},
            )

        assert response.status_code == 401


# --- Novel scope ------------------------------------------------------------------


class TestNovelScope:
    def test_analyze_with_foreign_novel_returns_404(
        self, client: TestClient, analyzer: FakeAnalyzer
    ) -> None:
        """A novel not owned by the caller → 404 (anti-enumeration)."""
        response = client.post(
            f"/api/v1/novels/{uuid4()}/kb/resolution/analyze",
            json={"refresh": False},
        )

        assert response.status_code == 404
        assert response.json()["code"] == "NOT_FOUND"
        assert analyzer.analyze_calls == []  # scope failure short-circuits

    def test_suggestions_get_with_foreign_novel_returns_404(
        self, client: TestClient, analyzer: FakeAnalyzer
    ) -> None:
        """The router-level scope guard covers the GET endpoint too (Task 10 reach)."""
        response = client.get(f"/api/v1/novels/{uuid4()}/kb/resolution/suggestions")

        assert response.status_code == 404
        assert response.json()["code"] == "NOT_FOUND"
        assert analyzer.cached_calls == []  # scope failure short-circuits


# --- Analyze endpoint ---------------------------------------------------------------


class TestAnalyzeEndpoint:
    def test_analyze_with_valid_request_returns_suggestions_and_stats(
        self, client: TestClient, analyzer: FakeAnalyzer
    ) -> None:
        analyzer.analyze_response = one_suggestion_analysis()
        response = client.post(
            f"/api/v1/novels/{NOVEL_ID}/kb/resolution/analyze",
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
        assert analyzer.analyze_calls == [(NOVEL_ID, USER_ID, False)]

    def test_analyze_with_refresh_true_passes_flag_to_service(
        self, client: TestClient, analyzer: FakeAnalyzer
    ) -> None:
        response = client.post(
            f"/api/v1/novels/{NOVEL_ID}/kb/resolution/analyze",
            json={"refresh": True},
        )

        assert response.status_code == 200
        assert analyzer.analyze_calls == [(NOVEL_ID, USER_ID, True)]


# --- Suggestions GET endpoint ---------------------------------------------------------


class TestSuggestionsEndpoint:
    def test_suggestions_get_before_any_analyze_returns_200_empty_list(
        self, client: TestClient, analyzer: FakeAnalyzer
    ) -> None:
        """404-free: never-analyzed novels yield an empty list, not an error."""
        response = client.get(f"/api/v1/novels/{NOVEL_ID}/kb/resolution/suggestions")

        assert response.status_code == 200
        body = response.json()
        assert body["suggestions"] == []
        assert body["stats"] == {"review": 0, "auto_eligible": 0, "suppressed": 0}
        assert body["cache_hit"] is False
        assert analyzer.cached_calls == [NOVEL_ID]
        assert analyzer.analyze_calls == []  # GET never triggers a recompute

    def test_analyze_then_suggestions_get_returns_cached_pair(
        self, novel_repo: FakeNovelRepository
    ) -> None:
        """Real service + cache: GET serves the cached analysis, no recompute."""
        service = make_resolution_service(duplicate_pair())
        with TestClient(build_app(service, novel_repo)) as test_client:
            created = test_client.post(
                f"/api/v1/novels/{NOVEL_ID}/kb/resolution/analyze",
                json={"refresh": False},
            )
            fetched = test_client.get(f"/api/v1/novels/{NOVEL_ID}/kb/resolution/suggestions")

        assert created.status_code == 200
        assert created.json()["cache_hit"] is False
        pair = created.json()["suggestions"]
        assert len(pair) == 1
        assert pair[0]["confidence"] > 0

        assert fetched.status_code == 200
        # cache_hit=True proves the GET was served from cache, not recomputed.
        assert fetched.json()["cache_hit"] is True
        assert fetched.json()["suggestions"] == pair


# --- Production wiring (cache-backend lifetime) -----------------------------------


class TestProductionWiring:
    def test_real_dependency_chain_caches_analysis_across_requests(
        self, novel_repo: FakeNovelRepository
    ) -> None:
        """Regression (fix round 1): the cache backend outlives single requests.

        The analyzer factory is NOT overridden — only the repositories are
        faked. A per-request cache backend made analyze never hit and GET
        suggestions always serve the empty miss; the module-level singleton
        must make request 2 a cache hit and request 3 an analyze cache hit.
        """
        entries, adjacency = duplicate_entries()
        app = build_production_app(
            novel_repo,
            FakeResolutionKbRepo(entries),
            FakeResolutionRelationshipRepo(adjacency),
        )

        with TestClient(app) as client:
            first = client.post(
                f"/api/v1/novels/{NOVEL_ID}/kb/resolution/analyze",
                json={"refresh": False},
            )
            fetched = client.get(f"/api/v1/novels/{NOVEL_ID}/kb/resolution/suggestions")
            second = client.post(
                f"/api/v1/novels/{NOVEL_ID}/kb/resolution/analyze",
                json={"refresh": False},
            )

        assert first.status_code == 200
        assert first.json()["cache_hit"] is False

        assert fetched.status_code == 200
        assert fetched.json()["cache_hit"] is True
        assert fetched.json()["suggestions"] == first.json()["suggestions"]

        assert second.status_code == 200
        assert second.json()["cache_hit"] is True
        assert second.json()["suggestions"] == first.json()["suggestions"]
