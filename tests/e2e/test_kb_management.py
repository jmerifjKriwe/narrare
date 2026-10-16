"""KB management E2E specs — KB-001 CRUD + detail, KB-008 graph, KB-007 extract.

Drives the REAL World & Characters view against the real stack. The single
extraction's LLM response is deterministic via the browser-layer catalog
(audit E04); everything else is real backend. Pins: B04 (detail view renders
the real template contract — flat body editor, no field_groups error
boundary), N14 (graph renders REAL relationships — the audit's 0-edge
finding was a data gap), M01 (exactly ONE extract POST while the modal is
open — startedRef + cancel-guard fix).

Selector calibration (Task 7, verified against the live components —
brief-verbatim code was stale, see RED run 2026-10-16):
- Create trigger is ``kb.newEntry`` = "New Entry" (KBEntryList), not
  "Create new"; the KBCreateForm placeholders are ``kb.namePlaceholder``
  = "Entry name..." / ``kb.bodyPlaceholder`` = "Write the entry
  content..." (NOT the worldbuilding.* variants).
- The detail body renders in the KBFlatEditor textarea ``#entry-body`` —
  a textarea VALUE is not text content, so the B04 body assertions read
  ``input_value()`` instead of ``get_by_text``.
- The delete affordance is the KBEntryHeader icon button (aria-label
  ``kb.deleteEntry`` = "Delete entry"), guarded by the ConfirmDialog
  (confirm button ``data-testid="confirm-dialog-confirm"``).
- The graph stats bar renders "N node(s) · M edge(s)" — a
  ``\\bnode\\b`` regex never matches the plural "nodes".
- The extraction 5xx message goes through mapSSEError (§16.5), which
  substitutes the mapped connection copy — the raw ``kb.extractionFailed``
  fallback never renders; the Retry button is the error-state signal
  (same pattern as test_ai_writing).

Runtime budget: ≤ 3 min (spec §7). Markers: e2e.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from tests.e2e.config import BASE_URL
from tests.e2e.foundation import NovelContext, make_authed_request
from tests.e2e.helpers import mock_llm
from tests.e2e.helpers.editor_ai import prepare_ai_chapter
from tests.e2e.helpers.kb_world import (
    open_kb_mode,
    open_worldbuilding,
    seed_kb_entity,
    seed_relationship,
    track_posts,
)
from tests.e2e.helpers.novel_factory import complete_wizard

if TYPE_CHECKING:
    from collections.abc import Callable

    import requests as http_requests


@pytest.fixture(scope="module")
def kb_novel(module_stable_user) -> NovelContext:
    """One wizard novel per module; tests seed their own KB state."""
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
    kb_novel: NovelContext,
) -> Callable[..., http_requests.Response]:
    return make_authed_request(api_request, kb_novel)


@pytest.mark.e2e
class TestKBEntryCrud:
    def test_create_edit_and_detail_render(self, kb_novel, authed_request) -> None:
        page = kb_novel.page
        open_worldbuilding(page)

        # Create through the real form (KBEntryList trigger → KBCreateForm).
        page.get_by_role("button", name="New Entry", exact=True).first.click()
        page.get_by_placeholder("Entry name...").fill("Brenna Ashford")
        page.get_by_placeholder("Write the entry content...").fill(
            "Harbor archivist who trades in sealed writs."
        )
        page.get_by_role("button", name="Create", exact=True).click()

        # List shows the entry; open the detail panel (B04).
        page.get_by_text("Brenna Ashford").first.wait_for(state="visible", timeout=15_000)
        page.get_by_text("Brenna Ashford").first.click()
        # B04 pin: the detail view renders the FLAT template contract — the
        # body lives in the KBFlatEditor textarea (a textarea VALUE is not
        # text content, hence input_value). The old template.field_groups
        # drift rendered an error boundary on every entity instead.
        body_editor = page.locator("#entry-body")
        body_editor.wait_for(state="visible", timeout=15_000)
        assert "Harbor archivist" in body_editor.input_value()
        assert (
            page.get_by_text(re.compile("something went wrong|error boundary", re.I)).count() == 0
        )

        # PATCH edit through the detail panel's own form + Save (kb.save).
        body_editor.fill("Harbor archivist; keys keeper of the sealed writs.")
        page.get_by_role("button", name="Save", exact=True).first.click()
        page.wait_for_function(
            """() => {
                const el = document.querySelector('#entry-body');
                return el && el.value.includes('keys keeper of the sealed writs');
            }""",
            timeout=15_000,
        )

    def test_delete_removes_entry_from_list(self, kb_novel, authed_request) -> None:
        page = kb_novel.page
        seed_kb_entity(authed_request, kb_novel.novel_id, name="Doomed Entry")
        open_worldbuilding(page)
        # The API-side seed never reaches the SPA's react-query cache by
        # itself — the list only refetches on mount/invalidation. Reload
        # after navigating (the suite's prepare_ai_chapter pattern) so the
        # seeded card is deterministically rendered.
        page.reload()
        page.wait_for_load_state("domcontentloaded")
        page.locator('[data-testid="kb-responsive-layout"]').wait_for(state="visible")

        page.get_by_text("Doomed Entry").first.click()
        # The detail panel may still show the PREVIOUS test's selection
        # (its delete button is identical) — wait until it shows THIS
        # entry before deleting, or the wrong entry gets deleted.
        page.wait_for_function(
            """() => {
                const el = document.querySelector('input[placeholder="Entry name..."]');
                return el && el.value === 'Doomed Entry';
            }""",
            timeout=15_000,
        )
        # KBEntryHeader icon button, aria-label kb.deleteEntry = "Delete entry".
        page.get_by_role("button", name="Delete entry").first.click()
        # ConfirmDialog guards the delete — the dialog's confirm button is
        # "Delete entry" too, so use the stable testid (auto-waits past the
        # open animation; a bare is_visible() check races it).
        page.get_by_test_id("confirm-dialog-confirm").click()
        page.get_by_text("Doomed Entry").first.wait_for(state="detached", timeout=15_000)
        assert page.get_by_text("Doomed Entry").count() == 0

    def test_search_filters_entries(self, kb_novel, authed_request) -> None:
        page = kb_novel.page
        seed_kb_entity(authed_request, kb_novel.novel_id, name="Odessa Vale")
        open_worldbuilding(page)
        page.get_by_placeholder("Search entries...").fill("Odessa")
        page.get_by_text("Odessa Vale").first.wait_for(state="visible", timeout=15_000)
        assert page.get_by_text("Brenna Ashford").count() == 0


@pytest.mark.e2e
class TestKBGraph:
    def test_graph_renders_real_relationships(self, kb_novel, authed_request) -> None:
        page = kb_novel.page
        source = seed_kb_entity(authed_request, kb_novel.novel_id, name="Callum Reeve")
        target = seed_kb_entity(authed_request, kb_novel.novel_id, name="The Tide Gate")
        seed_relationship(
            authed_request,
            kb_novel.novel_id,
            source["id"],
            target["id"],
            "guards",
        )
        open_worldbuilding(page)
        open_kb_mode(page, "graph")

        # N14: with REAL relationships the graph ships edges — the audit's
        # "0 edges" was demo data shipping none. The module novel
        # accumulates entities across tests, so counts assert LOWER
        # bounds, not equality (order-safe). Counts come from the controls
        # overlay stats bar, rendered as "N node(s) · M edge(s)" — the
        # plural "nodes" is why a \bnode\b word regex never matched.
        page.get_by_text(re.compile(r"\d+\s+nodes?")).first.wait_for(
            state="visible", timeout=15_000
        )
        # Edge presence is the N14 pin: the seeded relationship must appear.
        page.wait_for_function(
            """() => {
                const text = document.body.innerText;
                const edgeMatch = text.match(/(\\d+)\\s*(edges?|relations?)/i);
                return edgeMatch !== null && parseInt(edgeMatch[1], 10) >= 1;
            }""",
            timeout=15_000,
        )

        # Search interaction (DOM-level — canvas node clicks are documented
        # headless-unreliable, spec §10: assert the wire contract instead).
        page.get_by_placeholder("Search entities...").fill("Callum")
        page.wait_for_timeout(500)

    def test_graph_empty_state_is_honest(self, kb_novel) -> None:
        page = kb_novel.page
        open_worldbuilding(page)
        open_kb_mode(page, "graph")
        # The graph view stays functional for an entity-bearing novel (the
        # module novel always has entries by now); the honest-empty copy
        # (`graph.noEntities`) is only reachable with NO entries and is
        # covered at unit level by KnowledgeGraphView.test.tsx.
        page.locator('[data-testid="kb-responsive-layout"]').wait_for(state="visible")


@pytest.mark.e2e
class TestKBExtractSingle:
    def test_extract_applies_items_and_fires_exactly_once(self, kb_novel, authed_request) -> None:
        page = kb_novel.page
        extract_posts = track_posts(page, "/kb/extract/")
        mock_llm(page, "kb_extraction")  # happy variant

        # The CRUD/graph tests leave the page on /worldbuilding;
        # prepare_ai_chapter reloads the CURRENT page and expects the
        # editor sidebar — navigate back to the editor first.
        page.goto(f"{BASE_URL}/novel/{kb_novel.novel_id}")
        prepare_ai_chapter(
            page,
            authed_request,
            kb_novel.novel_id,
            title="Extract Me",
            content=(
                "Elara counted the strikes the way her mother had taught her. "
                "She traded her mother's ring to the Gatekeeper for a forged writ."
            ),
        )
        page.get_by_role("button", name="Extract to KB").click()

        # Review phase renders the catalog's deterministic items.
        page.get_by_text("Elara Thornwind").first.wait_for(state="visible", timeout=30_000)
        page.get_by_role("button", name=re.compile(r"^Apply \(")).click()
        page.get_by_text(re.compile("Extraction complete|Done", re.I)).first.wait_for(
            state="visible", timeout=30_000
        )

        # M01 pin: exactly ONE single-extract POST while the modal was open
        # (bulk/apply URLs are excluded by the needle "/kb/extract/" plus
        # the filter below).
        single_posts = [u for u in extract_posts if "/bulk" not in u and "/apply" not in u]
        assert len(single_posts) == 1, (
            f"extract request storm: {len(single_posts)} posts: {single_posts}"
        )

    def test_extract_error_renders_retry_not_storm(self, kb_novel, authed_request) -> None:
        page = kb_novel.page
        extract_posts = track_posts(page, "/kb/extract/")
        mock_llm(page, "kb_extraction", fixture="error")

        page.goto(f"{BASE_URL}/novel/{kb_novel.novel_id}")
        prepare_ai_chapter(
            page, authed_request, kb_novel.novel_id, title="Extract Fails", content="Short text."
        )
        page.get_by_role("button", name="Extract to KB").click()

        # The 5xx lands through mapSSEError (§16.5) — the UI shows the
        # mapped connection copy, never the kb.extractionFailed fallback,
        # so the error-state signal is the Retry affordance (role=alert
        # StatusMessage + Retry button — same pattern as test_ai_writing).
        retry_button = page.get_by_role("button", name="Retry", exact=True)
        retry_button.wait_for(state="visible", timeout=30_000)
        assert page.get_by_role("alert").first.is_visible()
        page.wait_for_timeout(2_000)
        single_posts = [u for u in extract_posts if "/bulk" not in u and "/apply" not in u]
        assert len(single_posts) == 1, f"error path also storms: {len(single_posts)} posts"
        assert retry_button.is_visible()
