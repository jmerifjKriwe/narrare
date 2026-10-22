"""KB bulk + corpus E2E specs — KB-007 and the corpus pass lifecycle.

All job endpoints run the REAL backend (bulk extraction executes
server-side; TestModel factory layer). The dedup/merge surface that
review mode also hosts is covered by test_kb_management_merge.py.

Runtime budget: ≤ 1.5 min (spec §7; job polling dominates). Markers: e2e.

Calibration (live in-tree, recorded per the brief):
- The job view's id field is ``job_id`` (``BulkExtractionJobView``,
  bulk_extraction/schemas.py) — NOT ``id``.
- Job statuses are the normative ``BulkJobStatus`` set {pending, running,
  cancelling, completed, cancelled, failed}; "review" is a UI panel MODE,
  never a job status — the post-review-wait status assertion pins
  ``completed`` (and ``cancelled`` on the cancel path).
- The corpus START POST targets ``…/kb/extract/bulk/corpus`` (201) while
  the estimate GET targets ``…/kb/extract/bulk/corpus/estimate`` — both
  share the capture needle, so the response listener is attached only
  AFTER the estimate line has rendered (estimate fetch already done).
- Start button = ``corpus-estimate-start-btn`` ("Start corpus pass"); the
  Radix estimate dialog unmounts on start and the BulkExtractionPanel
  (``role="dialog"``) replaces it (Task 8 proven shape).
- The cancel affordance is the progress view's "Cancel extraction"
  button (``kb.bulkExtraction.cancel``); the header close button is bare
  "Cancel" — full-string name matching keeps them apart. After the
  cooperative cancel lands, the panel flips to review mode and renders
  the "Cancelled" banner (``kb.bulkExtraction.cancelled``).
- The cancel test seeds 8 chapters (brief draft said 3): 3 tiny TestModel
  chapters can complete before the click lands (cancel on a terminal job
  → 409). 8 keeps the job mid-flight at click time with wide margin.
- The corpus pass covers the WHOLE novel's position-order prefix by
  design, and the two tests share the module novel — under pytest-random
  order the sibling test's chapters are part of the run. The happy test
  therefore pins its OWN chapter (title-keyed) in the status/results
  views instead of the row count.
- The BulkExtractionPanel is a FULL-VIEWPORT modal (``fixed inset-0
  z-50``) on the shared module-scoped page: a test that opens it and
  leaves it mounted blocks every later sidebar click (its overlay
  intercepts pointer events — observed RED). Both tests therefore close
  the panel via the header close button (``kb.extractionCancel`` =
  "Cancel", unique in both progress and review mode) before finishing.
- Chapters are seeded via API (out-of-band), but ``corpus-pass-btn``
  renders only when the client-cached chapter list (``hasNovelChapters``)
  includes them. If the sidebar's mount-fetch resolved BEFORE the API
  write, no refetch fires and the button never renders (wave triage
  2026-10-20: count=0 for the whole 30s window under suite conditions,
  instant render after one reload). ``_start_corpus_pass_from_ui``
  therefore reloads before clicking — the ``prepare_ai_chapter`` pattern,
  via the hardened ``reload_page`` (domcontentloaded + retry).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from tests.e2e.config import BASE_URL
from tests.e2e.foundation import NovelContext, make_authed_request
from tests.e2e.helpers.kb_world import capture_json_response
from tests.e2e.helpers.novel_factory import complete_wizard, create_chapter_via_api
from tests.e2e.test_helpers import reload_page

if TYPE_CHECKING:
    from collections.abc import Callable

    import requests as http_requests
    from playwright.sync_api import Page


@pytest.fixture(scope="module")
def bulk_novel(module_stable_user) -> NovelContext:
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
    bulk_novel: NovelContext,
) -> Callable[..., http_requests.Response]:
    return make_authed_request(api_request, bulk_novel)


def _close_bulk_panel(page: Page) -> None:
    """Close the BulkExtractionPanel modal (header close, "Cancel").

    Module-page hygiene (see module docstring): the panel's overlay covers
    the whole viewport — leaving it mounted would intercept the next
    test's sidebar clicks on the shared module-scoped page.
    """
    dialog = page.get_by_role("dialog")
    dialog.get_by_role("button", name="Cancel", exact=True).click()
    dialog.wait_for(state="detached", timeout=15_000)


def _start_corpus_pass_from_ui(page: Page) -> dict:
    """Drive estimate dialog → start; return the START POST's job view.

    Reloads FIRST (prepare_ai_chapter pattern): the chapters are seeded
    via API out-of-band, but ``corpus-pass-btn`` renders only when the
    SPA's client-cached chapter list (``hasNovelChapters``) knows about
    them. A sidebar mount-fetch that resolved before the API write never
    refetches, so without the reload the button may not render at all
    (wave triage 2026-10-20: count=0 across the whole window under suite
    conditions; instant render after one reload). Uses the hardened
    ``reload_page`` (domcontentloaded + one retry) — a bare ``reload``
    stalls 30s on dev-proxy stalls (see tests/e2e/test_helpers.py).

    The response listener is attached AFTER the estimate line rendered:
    the needle ``/kb/extract/bulk/corpus`` also matches the estimate GET
    (``…/corpus/estimate``), so attaching earlier would bind the capture
    to the estimate instead of the start POST.
    """
    reload_page(page)
    page.get_by_test_id("corpus-pass-btn").click()
    page.get_by_test_id("corpus-estimate-line").wait_for(state="visible", timeout=30_000)
    get_job = capture_json_response(page, "/kb/extract/bulk/corpus")
    page.get_by_test_id("corpus-estimate-start-btn").click()
    return get_job()


@pytest.mark.e2e
class TestCorpusLifecycle:
    def test_estimate_start_status_results(
        self,
        bulk_novel: NovelContext,
        authed_request: Callable[..., http_requests.Response],
    ) -> None:
        novel_id = bulk_novel.novel_id
        create_chapter_via_api(
            authed_request,
            novel_id,
            title="Corpus One",
            content="Ashwin repaired the tide bell with stolen solder.",
        )

        # Honest estimate (real GET; audit verified WORKING).
        estimate = authed_request(
            "GET", f"/api/v1/novels/{novel_id}/kb/extract/bulk/corpus/estimate"
        )
        assert estimate.status_code == 200, estimate.text[:300]
        assert estimate.json()["chapter_count"] >= 1

        # UI path: estimate dialog → start → the panel adopts the job. The
        # START POST's JSON response carries the job view (job_id + status).
        page = bulk_novel.page
        job = _start_corpus_pass_from_ui(page)
        assert job["job_id"], job
        assert job["status"] in {"pending", "running"}, job

        dialog = page.get_by_role("dialog")
        dialog.get_by_text(re.compile(r"review|Results", re.I)).first.wait_for(
            state="visible", timeout=90_000
        )

        # Status through the REAL URL shape with the captured job id — the
        # review mode only renders for a terminal job, and a happy corpus
        # run terminates as "completed" (normative BulkJobStatus set).
        status = authed_request(
            "GET",
            f"/api/v1/novels/{novel_id}/kb/extract/bulk/{job['job_id']}/status",
        )
        assert status.status_code == 200, status.text[:300]
        assert status.json()["status"] == "completed", status.json()

        # Results view (spec §4.3): readable in any state; the test's OWN
        # chapter carries its extraction output. Row COUNT is not pinned:
        # the corpus pass covers the whole novel prefix, and the sibling
        # test's seeded chapters join the run under randomized order.
        results = authed_request(
            "GET",
            f"/api/v1/novels/{novel_id}/kb/extract/bulk/{job['job_id']}/results",
        )
        assert results.status_code == 200, results.text[:300]
        own = [c for c in results.json()["chapters"] if c["title"] == "Corpus One"]
        assert len(own) == 1, results.json()
        assert own[0]["output"], own[0]

        # Module-page hygiene: free the viewport modal for the next test.
        _close_bulk_panel(page)

    def test_cancel_interrupts_running_job(
        self,
        bulk_novel: NovelContext,
        authed_request: Callable[..., http_requests.Response],
    ) -> None:
        novel_id = bulk_novel.novel_id
        # 8 chapters (calibration, see module docstring): the runner must
        # still be mid-flight when the cancel click lands.
        for i in range(8):
            create_chapter_via_api(
                authed_request,
                novel_id,
                title=f"Cancel Source {i}",
                content="Maren counts the tide strikes and trades seals.",
            )

        page = bulk_novel.page
        job = _start_corpus_pass_from_ui(page)

        dialog = page.get_by_role("dialog")
        # Progress mode's cancel affordance, clicked the moment it renders
        # (Playwright auto-wait) — the cooperative cancel POSTs while the
        # runner is between chapters.
        dialog.get_by_role("button", name="Cancel extraction").click()

        # Terminal "Cancelled" banner (BulkReviewView) — the interrupted
        # state surfaces in the panel (the transient "Cancelling…" label
        # does not match this regex, so the wait proves the terminal flip).
        dialog.get_by_text(re.compile(r"interrupted|cancelled|canceled", re.I)).first.wait_for(
            state="visible", timeout=30_000
        )

        # Server-side effect: the job is terminally cancelled.
        status = authed_request(
            "GET",
            f"/api/v1/novels/{novel_id}/kb/extract/bulk/{job['job_id']}/status",
        )
        assert status.status_code == 200, status.text[:300]
        assert status.json()["status"] == "cancelled", status.json()

        # Module-page hygiene: free the viewport modal for the next test.
        _close_bulk_panel(page)
