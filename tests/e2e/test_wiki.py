"""Wiki E2E specs — WIKI-001 lifecycle on the REAL generation pipeline.

Entity summaries generate through the real refresh service under TestModel
(factory layer); the first-generation path is the M11 fix (Tasks 3+4).
Chapter summaries generate only on the chapter.finalized event (D-8) —
seeded via the authenticated API's service path, asserted in the editor's
metadata panel. The never-generated chapter renders the graceful empty
state (N20 — Task 5's fix, pinned green).

Runtime budget: ≤ 1.5 min (spec §7). Markers: e2e.

Calibration (live in-tree, recorded per the brief):
- "Generate Wiki" is ``kb.wiki.generateAll`` exactly (M11 empty-state
  affordance in WikiOverviewPanel); the M11 fix routes it through the
  paged entries fetch + per-entity refresh service.
- The chapter summary panel mounts ONLY inside the editor's metadata
  right panel (``EditorPanelContent.tsx`` case "metadata" →
  ``WikiChapterSummaryPanel``); the panel opens via the header toggle
  button (``aria-label="Metadata"``, ``metadataSidebar.toggle``) and the
  right panel starts CLOSED (editorStore default).
- "Chapter Wiki Summary" (the panel header) renders ONLY when a summary
  exists; a never-generated chapter renders solely the ``noSummaryYet``
  copy "Chapter wiki summary not yet available." — which is exactly the
  N20 pin.
- The overview's entity cards render NO status text (WikiStatusDot is a
  bare colored dot); the only status TEXT on the wiki surface is the
  always-visible stats bar ("Fresh: N" / "Stale: N" / "Pending: N" —
  WikiIndexStats) plus the per-entity/chapter panels. The staleness
  probes therefore anchor on the STATS-COUNT FLIP ("Stale: 0" →
  "Stale: 1" after Mark All Stale, "Fresh: 1" after Refresh Stale),
  cross-checked against the summaries API (server truth).
- ``filter(has_text=...)`` with a STRING does literal substring
  matching — ``re.escape(title)`` as a string matches nothing (the
  backslashes become literals). Chapter-title filters pass a compiled
  regex (``re.compile(re.escape(title))``), same as editor_ai.
- The metadata-panel hook (useWikiChapterSummary) maps the 404 → null
  with no refetch loop, so the finalized-chapter test polls the REAL
  summary endpoint server-side until the D-8 listener's generation has
  landed BEFORE opening the panel (a panel mounted earlier would cache
  null forever).
- After ``page.reload()`` the editor auto-selects the FIRST chapter;
  with pytest-randomized order that is not necessarily the test's own
  chapter, so both chapter tests re-select their chapter explicitly
  (``chapter-item`` sidebar pattern from editor_ai.prepare_ai_chapter).
  The SAME shared-page coupling applies at the novel level: every
  NovelContext fixture wraps ``module_stable_user.page``, so a sibling
  test (or an earlier module) can leave it on another novel's URL —
  the chapter tests navigate to their own novel first
  (``_open_novel``) instead of trusting the current URL.
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

import pytest

from tests.e2e.config import BASE_URL
from tests.e2e.foundation import NovelContext, make_authed_request
from tests.e2e.helpers.editor_ai import prepare_ai_chapter
from tests.e2e.helpers.kb_world import open_kb_mode, open_worldbuilding, seed_kb_entity
from tests.e2e.helpers.novel_factory import complete_wizard

if TYPE_CHECKING:
    from collections.abc import Callable

    import requests as http_requests
    from playwright.sync_api import Page


@pytest.fixture(scope="module")
def wiki_novel(module_stable_user) -> NovelContext:
    novel = complete_wizard(module_stable_user.page, BASE_URL)
    return NovelContext(
        page=module_stable_user.page,
        novel_id=novel["novel_id"],
        email=module_stable_user.email,
        password=module_stable_user.password,
        access_token=module_stable_user.access_token,
    )


@pytest.fixture
def fresh_wiki_novel(module_stable_user) -> NovelContext:
    """Per-test novel for the entity-summary tests.

    The empty-state and staleness tests each need a KNOWN wiki state; a
    shared module novel would couple them to test order (the runner may
    randomize). ~15 s of wizard per test, inside this file's budget.
    """
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
    wiki_novel: NovelContext,
) -> Callable[..., http_requests.Response]:
    return make_authed_request(api_request, wiki_novel)


def _open_novel(page: Page, novel_id: str) -> None:
    """Navigate the shared module page to the novel's editor.

    All NovelContext fixtures wrap the SAME physical page
    (``module_stable_user.page``); under pytest-randomly a sibling test
    may have left it on another novel's URL (e.g. the worldbuilding
    wiki). ``prepare_ai_chapter`` only reloads the CURRENT URL — the
    editor tests must target their own novel explicitly.
    """
    page.goto(f"{BASE_URL}/novel/{novel_id}")
    page.wait_for_load_state("domcontentloaded")


def _open_chapter_summary_panel(page: Page, chapter_title: str | None = None) -> None:
    """Open the editor's metadata right panel hosting the wiki panel.

    The right panel starts closed (editorStore default); the header toggle
    carries ``aria-label="Metadata"``. When *chapter_title* is given the
    chapter is (re-)selected first — after a reload the editor auto-picks
    the FIRST chapter, which under randomized order is not necessarily the
    one under test.
    """
    if chapter_title is not None:
        chapter_button = page.locator('[data-testid="chapter-item"]').filter(
            has_text=re.compile(re.escape(chapter_title))
        )
        chapter_button.last.click()
        page.locator(".ProseMirror").first.wait_for(state="visible", timeout=15_000)
    toggle = page.get_by_role("button", name="Metadata", exact=True)
    if not toggle.is_visible():
        pytest.fail("Editor header with the Metadata toggle is not visible")
    if page.get_by_text("Chapter Info").first.is_visible():
        return  # panel already open — toggling would close it
    toggle.click()
    page.get_by_text("Chapter Info").first.wait_for(state="visible", timeout=15_000)


@pytest.mark.e2e
class TestWikiFirstGeneration:
    def test_empty_state_generates_from_kb_with_names(
        self,
        fresh_wiki_novel: NovelContext,
        authed_request: Callable[..., http_requests.Response],
    ) -> None:
        page = fresh_wiki_novel.page
        seed_kb_entity(
            authed_request,
            fresh_wiki_novel.novel_id,
            name="Piet Voss",
            body="A lamplighter who fears the upper districts.",
        )
        open_worldbuilding(page)
        open_kb_mode(page, "wiki")

        # M11 pin: the empty state offers generation (pre-fix: terminal copy).
        page.get_by_role("button", name="Generate Wiki").click()

        # Names render (Task 3+4 pin — not raw UUIDs) and rows leave the
        # "not yet generated" state via the REAL refresh pipeline.
        page.get_by_text("Piet Voss").first.wait_for(state="visible", timeout=60_000)
        page.wait_for_function(
            "() => !document.body.innerText.includes('Wiki not yet generated')",
            timeout=60_000,
        )
        assert page.get_by_text(re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}", re.I)).count() == 0


@pytest.mark.e2e
class TestWikiStalenessLifecycle:
    def test_mark_all_stale_then_refresh_regenerates(
        self,
        fresh_wiki_novel: NovelContext,
        authed_request: Callable[..., http_requests.Response],
    ) -> None:
        page = fresh_wiki_novel.page
        novel_id = fresh_wiki_novel.novel_id
        entry = seed_kb_entity(
            authed_request,
            fresh_wiki_novel.novel_id,
            name="Rooke Fell",
            body="A bell-founder with a ledgers obsession.",
        )
        refreshed = authed_request(
            "POST",
            f"/api/v1/novels/{fresh_wiki_novel.novel_id}/wiki/summaries/{entry['id']}/refresh",
            json={"force": False},
        )
        assert refreshed.status_code == 200, refreshed.text[:300]
        assert refreshed.json()["status"] == "fresh", refreshed.json()
        open_worldbuilding(page)
        open_kb_mode(page, "wiki")

        page.get_by_text("Rooke Fell").first.wait_for(state="visible", timeout=30_000)
        page.get_by_role("button", name="Mark All Stale").click()

        # Server truth: the route marks version-gated IN-REQUEST — the row
        # carries the wiki_prompt_version stamp, without which the UPDATE
        # matches nothing and the status never flips (kept-fix pin).
        def _listing_status() -> str:
            listing = authed_request("GET", f"/api/v1/novels/{novel_id}/wiki/summaries")
            assert listing.status_code == 200, listing.text[:300]
            rows = [s for s in listing.json()["items"] if s["entity_id"] == entry["id"]]
            assert rows, listing.json()
            return str(rows[0]["status"])

        status = ""
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            status = _listing_status()
            if status == "stale":
                break
            time.sleep(0.5)
        assert status == "stale", f"summary never went stale (last: {status!r})"

        # UI flip: the stats bar always renders "Stale: N" — 0 before the
        # click, 1 after the mutation's invalidation refetch.
        page.get_by_text(re.compile(r"Stale:\s*1")).first.wait_for(state="visible", timeout=30_000)

        page.get_by_role("button", name="Refresh Stale").click()
        status = ""
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            status = _listing_status()
            if status == "fresh":
                break
            time.sleep(0.5)
        assert status == "fresh", f"refresh never regenerated (last: {status!r})"
        page.get_by_text(re.compile(r"Fresh:\s*1")).first.wait_for(state="visible", timeout=30_000)


@pytest.mark.e2e
class TestWikiChapterSummaryPanel:
    def test_finalized_chapter_summary_renders_in_editor(
        self,
        wiki_novel: NovelContext,
        authed_request: Callable[..., http_requests.Response],
    ) -> None:
        _open_novel(wiki_novel.page, wiki_novel.novel_id)
        chapter = prepare_ai_chapter(
            page=wiki_novel.page,
            api_request=authed_request,
            novel_id=wiki_novel.novel_id,
            title="Finalized Chapter",
            content="The tide gate closed for the season. Ashwin kept counting.",
        )
        # D-8: the REAL event path — the transition into status final
        # publishes chapter.finalized; the wiki listener generates the
        # chapter summary under TestModel. The PATCH meta route is
        # novel-scoped (chapters/router.py:104, UpdateChapterMetaRequest
        # accepts status "draft|reviewed|final").
        patched = authed_request(
            "PATCH",
            f"/api/v1/novels/{wiki_novel.novel_id}/chapters/{chapter['chapter_id']}",
            json={"status": "final"},
        )
        assert patched.status_code == 200, patched.text[:300]

        # Wait for the listener's generation on the REAL endpoint BEFORE
        # mounting the panel: the hook caches a 404 → null and never
        # refetches on its own (module docstring calibration).
        deadline = time.monotonic() + 30
        summary_status = 0
        while time.monotonic() < deadline:
            probe = authed_request(
                "GET",
                f"/api/v1/novels/{wiki_novel.novel_id}"
                f"/wiki/chapters/{chapter['chapter_id']}/summary",
            )
            summary_status = probe.status_code
            if probe.status_code == 200:
                break
            time.sleep(0.5)
        assert summary_status == 200, "chapter summary not generated within 30s (D-8)"

        page = wiki_novel.page
        page.reload()
        page.locator(".ProseMirror").first.wait_for(state="visible", timeout=15_000)
        _open_chapter_summary_panel(page, chapter_title="Finalized Chapter")
        page.get_by_text("Chapter Wiki Summary").first.wait_for(state="visible", timeout=30_000)

    def test_never_generated_chapter_is_graceful_empty_state(
        self,
        wiki_novel: NovelContext,
        authed_request: Callable[..., http_requests.Response],
    ) -> None:
        """N20 pin (fixed in Task 5): the never-generated 404 maps to null
        in useWikiChapterSummary — the panel shows the friendly copy, not
        the load-error box.
        """
        _open_novel(wiki_novel.page, wiki_novel.novel_id)
        prepare_ai_chapter(
            page=wiki_novel.page,
            api_request=authed_request,
            novel_id=wiki_novel.novel_id,
            title="Draft Only Chapter",
            content="Draft content that was never finalized.",
        )
        # No reload here: prepare_ai_chapter already reloaded and selected
        # the chapter; a second reload would auto-select the FIRST chapter
        # (randomized order — could be the finalized one with a summary).
        page = wiki_novel.page
        _open_chapter_summary_panel(page, chapter_title="Draft Only Chapter")

        page.get_by_text("Chapter wiki summary not yet available.").first.wait_for(
            state="visible", timeout=15_000
        )
