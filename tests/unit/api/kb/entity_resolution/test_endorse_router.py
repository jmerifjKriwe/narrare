"""Endorse/reject route tests for the KB resolution surface (ADR-085 P4).

Split from ``test_router.py`` per RULE-04 (the P4 adjudication surface
grew the P3 route file past the 400-line hard limit). Route-level tests
against the REAL analyzer + endorse-service factories with fakes only at
the repository/dismissal/session seams:

- endorse happy path: re-scores, merges (loser deprecated, survivor
  renamed/re-embed-flagged), invalidates the analysis cache, returns the
  ``MergeExecutionResult`` shape;
- 409 for unknown ids (stale) and for SUPPRESSED (below-review) pairs;
- ``survivor_id`` override honored; deterministic auto-pick without a body;
- reject: 204, dismissal persisted via the ledger seam, analysis cache
  STAYS (``cache_hit=True``) while the rejected pair disappears from the
  served list with recounted stats.

The ``EndorseWorld`` builder isolates each test behind fresh entry ids so
the process-wide analysis-cache singleton never leaks state between the
production-wiring tests (T8 deferred minor: no reset seam — distinct
keys are the hygiene). A distinct novel id (``ENDORSE_NOVEL_ID``) keeps
these tests disjoint from the P3 cache test.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from tests.factories import make_novel
from tests.fakes.fake_novel_repo import FakeNovelRepository

from ._endorse_helpers import (
    ENDORSE_NOVEL_ID,
    FakeDismissedStore,
    FakeEndorseKbRepo,
    FakeEndorseRelRepo,
    build_endorse_app,
    duplicate_endorse_entries,
    low_band_entries,
    suggestion_id_for,
)
from ._router_helpers import USER_ID, mounted_paths


class EndorseWorld:
    """Seeded endorse app: real analyzer + endorse service, fakes at the seams."""

    def __init__(self) -> None:
        self.novel_repo = FakeNovelRepository()
        self.novel_repo.seed(make_novel(id=ENDORSE_NOVEL_ID, user_id=USER_ID))
        self.entries = duplicate_endorse_entries()
        # Stable object references: the merge renames the survivor, so
        # name-based lookups after endorse are unreliable.
        self.anna = next(e for e in self.entries if e.name == "Anna")
        self.meyer = next(e for e in self.entries if e.name == "Anna Meyer")
        self.kb_repo = FakeEndorseKbRepo(self.entries)
        # Shared third-party neighbor via two edges (identical-degree
        # neighborhoods → S4 corroboration); the loser→X edge repoints to
        # the survivor on merge without colliding (X→survivor differs).
        self.x_id = uuid4()
        self.rel_repo = FakeEndorseRelRepo()
        self.rel_repo.add_edge(self.anna.id, self.x_id)
        self.rel_repo.add_edge(self.x_id, self.meyer.id)
        self.store = FakeDismissedStore()
        self.app = build_endorse_app(self.novel_repo, self.kb_repo, self.rel_repo, self.store)


# --- Route table ------------------------------------------------------------------


class TestEndorseRouteTable:
    def test_create_app_mounts_endorse_and_reject(self) -> None:
        """The app factory mounts both spec §7 P4 adjudication endpoints."""
        from narrare._app.main import create_app

        paths = mounted_paths(create_app(test_mode=True))
        assert (
            "/api/v1/novels/{novel_id}/kb/resolution/suggestions/{suggestion_id}/endorse" in paths
        )
        assert "/api/v1/novels/{novel_id}/kb/resolution/suggestions/{suggestion_id}/reject" in paths


# --- Endorse endpoint ---------------------------------------------------------------


class TestEndorseEndpoint:
    def test_endorse_happy_path_executes_merge_invalidates_cache_and_returns_result(
        self,
    ) -> None:
        """Endorse re-scores, merges, invalidates the cache, returns the result."""
        world = EndorseWorld()
        with TestClient(world.app) as client:
            analyzed = client.post(
                f"/api/v1/novels/{ENDORSE_NOVEL_ID}/kb/resolution/analyze",
                json={"refresh": False},
            )
            suggestion_id = analyzed.json()["suggestions"][0]["suggestion_id"]

            endorsed = client.post(
                f"/api/v1/novels/{ENDORSE_NOVEL_ID}/kb/resolution/suggestions/"
                f"{suggestion_id}/endorse",
                json={},
            )
            after = client.get(f"/api/v1/novels/{ENDORSE_NOVEL_ID}/kb/resolution/suggestions")

        assert analyzed.status_code == 200
        assert endorsed.status_code == 200
        result = endorsed.json()
        assert result["survivor_id"] == str(world.meyer.id)
        assert result["loser_id"] == str(world.anna.id)
        assert isinstance(result["merged_fact_keys"], list)
        assert isinstance(result["repointed_relationships"], int)
        assert isinstance(result["skipped_relationships"], int)
        assert result["conflicts"] == []
        # Loser deprecated, never deleted (§6.4); survivor flagged for re-embed.
        loser_after = world.kb_repo.get_one(world.anna.id)
        assert loser_after.status == "deprecated"
        resolution_block = loser_after.metadata_["resolution"]
        assert isinstance(resolution_block, dict)
        assert resolution_block["merged_into"] == str(world.meyer.id)
        assert world.kb_repo.get_one(world.meyer.id).embeddings_dirty is True
        # Merge mutated the KB → the cached analysis must be gone.
        assert after.json()["cache_hit"] is False
        assert after.json()["suggestions"] == []

    def test_endorse_with_unknown_suggestion_returns_409(self) -> None:
        """An id absent from the fresh re-score is stale → 409 with reason."""
        world = EndorseWorld()
        with TestClient(world.app) as client:
            response = client.post(
                f"/api/v1/novels/{ENDORSE_NOVEL_ID}/kb/resolution/suggestions/"
                "deadbeefdeadbeef/endorse",
                json={},
            )

        assert response.status_code == 409
        assert response.json()["code"] == "CONFLICT"
        assert world.kb_repo.updates == []  # nothing was merged

    def test_endorse_low_band_pair_returns_409(self) -> None:
        """A SUPPRESSED pair has no surfaced suggestion → 409 (below review)."""
        world = EndorseWorld()
        world.entries[:] = low_band_entries()
        pair_id = suggestion_id_for(world.entries[0].id, world.entries[1].id)

        with TestClient(world.app) as client:
            response = client.post(
                f"/api/v1/novels/{ENDORSE_NOVEL_ID}/kb/resolution/suggestions/{pair_id}/endorse",
                json={},
            )

        assert response.status_code == 409
        assert response.json()["code"] == "CONFLICT"
        assert world.kb_repo.updates == []

    def test_endorse_with_survivor_override_honored(self) -> None:
        """Body {survivor_id} overrides the deterministic pick (§6.1)."""
        world = EndorseWorld()
        with TestClient(world.app) as client:
            analyzed = client.post(
                f"/api/v1/novels/{ENDORSE_NOVEL_ID}/kb/resolution/analyze",
                json={"refresh": False},
            )
            suggestion_id = analyzed.json()["suggestions"][0]["suggestion_id"]

            endorsed = client.post(
                f"/api/v1/novels/{ENDORSE_NOVEL_ID}/kb/resolution/suggestions/"
                f"{suggestion_id}/endorse",
                json={"survivor_id": str(world.anna.id)},
            )

        assert endorsed.status_code == 200
        result = endorsed.json()
        assert result["survivor_id"] == str(world.anna.id)
        assert result["loser_id"] == str(world.meyer.id)
        assert world.kb_repo.get_one(world.meyer.id).status == "deprecated"
        assert world.kb_repo.get_one(world.anna.id).status == "active"

    def test_endorse_without_body_selects_survivor_deterministically(self) -> None:
        """No override → select_survivor on (min_id, max_id) order (§6.1)."""
        world = EndorseWorld()
        with TestClient(world.app) as client:
            analyzed = client.post(
                f"/api/v1/novels/{ENDORSE_NOVEL_ID}/kb/resolution/analyze",
                json={"refresh": False},
            )
            suggestion_id = analyzed.json()["suggestions"][0]["suggestion_id"]

            endorsed = client.post(
                f"/api/v1/novels/{ENDORSE_NOVEL_ID}/kb/resolution/suggestions/"
                f"{suggestion_id}/endorse",
            )

        assert endorsed.status_code == 200
        # Equal metadata/relationships → the longer name wins the rank.
        assert endorsed.json()["survivor_id"] == str(world.meyer.id)
        assert endorsed.json()["loser_id"] == str(world.anna.id)


# --- Reject endpoint ------------------------------------------------------------------


class TestRejectEndpoint:
    def test_reject_returns_204_and_persists_dismissal(self) -> None:
        """Reject persists the dismissal via the dismissed-suggestions pattern."""
        world = EndorseWorld()
        with TestClient(world.app) as client:
            analyzed = client.post(
                f"/api/v1/novels/{ENDORSE_NOVEL_ID}/kb/resolution/analyze",
                json={"refresh": False},
            )
            suggestion_id = analyzed.json()["suggestions"][0]["suggestion_id"]

            rejected = client.post(
                f"/api/v1/novels/{ENDORSE_NOVEL_ID}/kb/resolution/suggestions/"
                f"{suggestion_id}/reject"
            )

        assert analyzed.status_code == 200
        assert rejected.status_code == 204
        assert world.store.dismiss_calls == [(ENDORSE_NOVEL_ID, suggestion_id)]
        assert world.kb_repo.updates == []  # reject never touches entries

    def test_rejected_pair_excluded_from_suggestions_but_cache_stays(self) -> None:
        """Rejection filters the served list; the cached analysis is kept."""
        world = EndorseWorld()
        with TestClient(world.app) as client:
            analyzed = client.post(
                f"/api/v1/novels/{ENDORSE_NOVEL_ID}/kb/resolution/analyze",
                json={"refresh": False},
            )
            suggestion_id = analyzed.json()["suggestions"][0]["suggestion_id"]

            client.post(
                f"/api/v1/novels/{ENDORSE_NOVEL_ID}/kb/resolution/suggestions/"
                f"{suggestion_id}/reject"
            )
            after = client.get(f"/api/v1/novels/{ENDORSE_NOVEL_ID}/kb/resolution/suggestions")

        assert after.status_code == 200
        # cache_hit=True proves the cache survived the reject; the pair is
        # filtered at the read seam, not evicted.
        assert after.json()["cache_hit"] is True
        assert after.json()["suggestions"] == []
        assert after.json()["stats"] == {"review": 0, "auto_eligible": 0, "suppressed": 0}
