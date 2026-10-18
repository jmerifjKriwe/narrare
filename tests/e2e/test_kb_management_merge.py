"""KB merge + suggestions E2E specs — KB-009 (N16) + KB-005 (N15).

Merge flow: the ADR-085 review UI is mounted inside the bulk panel's
review mode and armed only by a COMPLETED corpus job's dedup block
(BulkExtractionPanel → DedupCard → ResolutionSuggestionsList). The spec
drives that REAL path with NEAR-duplicate entities (exact dupes are
suppressed by design) — the audit's "unreachable in practice" is the
documented reachability constraint, not a defect fixed here.
Suggestions: zero FE consumers (ADR-088 dormancy) — pinned by an
authenticated API probe of the healthy contract.

D-7 route (live-verified 2026-10-16, deterministic-corpus): the pair is
calibrated to the PURE detection engine's documented thresholds (spec §4,
code-pinned constants — "Selene" ⊂ "Selene Marrow" is SUBSET tier 0.7;
a shared ``profession`` attribute family feeds S3 +1.0; a shared neighbor
relationship feeds S4 +1.0 → confidence 0.545 ≥ REVIEW_THRESHOLD 0.45,
band REVIEW). The brief's draft pair ("Selene Marrow"/"Selene Marrowe",
FUZZY 0.4, no corroboration) is deterministically SUPPRESSED by the same
engine (RED run: the naive pair never surfaced — the wait timed out);
near-dupe names alone never clear the review band, so the seed below is
the engine's documented near-dupe shape ("short form of a longer name",
name_tiers SUBSET docstring). Adjudication of the REVIEW band runs under
TestModel (the wizard persists a provider + default model server-side
via SetupService.complete) and deterministically yields the
empty-decision note "Adjudication returned no decision." (live-probed):
the suggestion stays surfaced and endorsable, which is what the spec pins.

Runtime budget: ≤ 2.5 min (spec §7; corpus polling dominates). Markers: e2e.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from tests.e2e.config import BASE_URL
from tests.e2e.foundation import NovelContext, make_authed_request
from tests.e2e.helpers.editor_ai import prepare_ai_chapter
from tests.e2e.helpers.kb_world import seed_kb_entity, seed_relationship
from tests.e2e.helpers.novel_factory import complete_wizard, create_chapter_via_api

if TYPE_CHECKING:
    from collections.abc import Callable

    import requests as http_requests

# SUBSET-tier near-dupe pair: "Selene" is the short form of "Selene Marrow"
# (token subset, first tokens match → S1 = 0.7). With the shared attribute
# family (S3 +1.0) and the shared neighbor (S4 +1.0) both entries carry,
# confidence = 0.35·0.7 + 0.20·1.0 + 0.10·1.0 = 0.545 → REVIEW band.
_NEAR_DUPE_A = "Selene"
_NEAR_DUPE_B = "Selene Marrow"
_SHARED_BODY = "A cartographer of the drowned districts."
_SHARED_NEIGHBOR = "Drowned Districts"


@pytest.fixture(scope="module")
def merge_novel(module_stable_user) -> NovelContext:
    novel = complete_wizard(module_stable_user.page, BASE_URL)
    return NovelContext(
        page=module_stable_user.page,
        novel_id=novel["novel_id"],
        email=module_stable_user.email,
        password=module_stable_user.password,
        access_token=module_stable_user.access_token,
    )


@pytest.fixture
def authed_request(
    api_request: Callable[..., http_requests.Response],
    merge_novel: NovelContext,
) -> Callable[..., http_requests.Response]:
    return make_authed_request(api_request, merge_novel)


def _pair_ids(authed_request: Callable[..., http_requests.Response], novel_id: str) -> list[str]:
    """Entry ids of the seeded near-dupe pair (by exact name match)."""
    listed = authed_request("GET", f"/api/v1/novels/{novel_id}/kb/entries").json()
    return [item["id"] for item in listed["items"] if item["name"] in (_NEAR_DUPE_A, _NEAR_DUPE_B)]


@pytest.mark.e2e
class TestKBMergeFlow:
    def test_near_dupes_merge_via_corpus_review(
        self, merge_novel: NovelContext, authed_request: Callable[..., http_requests.Response]
    ) -> None:
        page = merge_novel.page
        # The near-dupe pair PLUS its deterministic corroboration: a shared
        # attribute family (S3) and a shared neighbor entry (S4) — the
        # engine's pure math (0.545, REVIEW) then surfaces the pair without
        # any LLM contribution (see module docstring, D-7 route).
        seed_kb_entity(
            authed_request,
            merge_novel.novel_id,
            name=_NEAR_DUPE_A,
            body=_SHARED_BODY,
            metadata={"profession": "cartographer"},
        )
        seed_kb_entity(
            authed_request,
            merge_novel.novel_id,
            name=_NEAR_DUPE_B,
            body=_SHARED_BODY,
            metadata={"profession": "cartographer"},
        )
        neighbor = seed_kb_entity(
            authed_request,
            merge_novel.novel_id,
            name=_SHARED_NEIGHBOR,
            body="The flooded low city.",
            entity_type="location",
        )
        for dupe_id in _pair_ids(authed_request, merge_novel.novel_id):
            seed_relationship(
                authed_request,
                merge_novel.novel_id,
                dupe_id,
                neighbor["id"],
                "associated_with",
            )
        prepare_ai_chapter(
            page,
            authed_request,
            merge_novel.novel_id,
            title="Corpus Source",
            content=(
                "Selene inked the drowned districts onto wax paper. "
                "The tide gates opened twice before noon."
            ),
        )

        # Corpus pass entry (editor sidebar) → estimate dialog → start.
        page.get_by_test_id("corpus-pass-btn").click()
        page.get_by_test_id("corpus-estimate-start-btn").click()

        # Review mode with the dedup card (corpus jobs arm the dedup block;
        # the post-pass analysis records {analyzed, suggestion_count}).
        dialog = page.get_by_role("dialog")
        dialog.get_by_text(re.compile(r"review|Results", re.I)).first.wait_for(
            state="visible", timeout=90_000
        )
        dialog.get_by_test_id("dedup-card").wait_for(state="visible", timeout=30_000)

        # Analyze (LLM-adjudicated; under E2E TestModel the adjudication
        # deterministically degrades to a note) → the suggestions list
        # renders the near-dupe pair.
        dialog.get_by_role("button", name=re.compile(r"Re-check|Analyze|Check", re.I)).first.click()
        # The pair row, scoped to the suggestions list (the optimistic row
        # removal makes a whole-dialog text probe racy).
        suggestions = dialog.get_by_test_id("resolution-suggestions")
        suggestions.get_by_text(_NEAR_DUPE_A).first.wait_for(state="visible", timeout=60_000)

        # Endorse executes the REAL deterministic merge (§6.1 survivor pick,
        # no LLM): the loser entry is deprecated. Anchored to the list's OWN
        # status paragraph — it renders only on mutation success (the
        # browser has the 200, so the server-side merge is ordered before
        # any subsequent direct-API read). A bare /merged/i text probe is
        # collision-prone (the KB "Merged" source badge and the
        # dedup-unavailable copy both match it).
        suggestions.get_by_role("button", name=re.compile(r"^Merge$")).first.click()
        dialog.get_by_role("status").filter(has_text=re.compile(r"merged", re.I)).first.wait_for(
            state="visible", timeout=30_000
        )

        # Server-side effect via the UI's own dispatch surface: the merged
        # (deprecated) entry is hidden from the default list.
        listed = authed_request("GET", f"/api/v1/novels/{merge_novel.novel_id}/kb/entries").json()
        names = [item["name"] for item in listed["items"]]
        assert names.count(_NEAR_DUPE_A) + names.count(_NEAR_DUPE_B) == 1, names


@pytest.mark.e2e
class TestKBSuggestionsProbe:
    def test_suggestions_api_contract_is_healthy_dormant_ui(
        self, merge_novel: NovelContext, authed_request: Callable[..., http_requests.Response]
    ) -> None:
        """KB-005 / N15: API healthy, zero FE consumers (ADR-088 dormancy).

        Probe-by-default: assert the contract the (future) FE consumer
        will render — relevance_score + reason per suggestion for a
        chapter with entity-bearing content. The dormancy itself is
        documented in docs/development/e2e-coverage.md (Task 12).

        Seeds its OWN chapter: the suite's randomized test order
        (pytest-randomly) may run this probe before the merge test, and
        the blank-starter wizard novel ships with zero chapters.
        """
        create_chapter_via_api(
            authed_request,
            merge_novel.novel_id,
            title="Suggestions Probe Chapter",
            content="Selene walked the drowned districts before the tide gates opened.",
        )
        chapters = authed_request("GET", f"/api/v1/novels/{merge_novel.novel_id}/chapters").json()
        chapter_id = chapters["items"][0]["id"] if isinstance(chapters, dict) else chapters[0]["id"]

        resp = authed_request(
            "GET",
            f"/api/v1/novels/{merge_novel.novel_id}/kb/suggestions/{chapter_id}",
        )

        assert resp.status_code == 200, f"{resp.status_code} {resp.text[:300]}"
        suggestions = resp.json()
        assert isinstance(suggestions, list)
        for suggestion in suggestions:
            assert "relevance_score" in suggestion
            assert "reason" in suggestion
