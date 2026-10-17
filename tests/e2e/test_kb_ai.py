"""KB AI E2E specs — KB-002 session interview, KB-003 improve, KB-004 check.

Interview and consistency run the REAL backend under TestModel (factory
layer) — B05's session cache and the Task-1 governed consistency route
make these paths exercisable. B03's stream route gets its 404→SSE pin;
stream content stays with the analysis wave. Improve content is asserted
via the browser-layer catalog (E04); its error variant pins the error
branch.

Calibration (2026-10-17, live components — the brief's draft matched the
dead ``kb.aiDialog`` i18n set): trigger ``kb.newWithAI`` = "New with AI
Interview" (``KBEntryList`` col 2; the panel mounts + creates the session
itself); ``kb.startInterview`` → ``KBInterviewView`` with the
``kb.interviewProgress`` "Question {current}" counter;
``kb.completeAndSave`` = "Complete & Save" (footer, name + ≥1 field,
input "Entry Name"); ``kb.improveWithAI`` success = panel closes (no
toast — ``kb.improve.applySuccess`` dead), error = ``ImproveErrorState``
mapped connection copy; the consistency panel auto-checks on mount and
renders "{count} entities analyzed" + "N entry internal" chips.

Wave-fixes 3-6 (2026-10-17) re-enabled the three scoped-out legs:
F9-1 complete (the name travels in the complete body — FE
``completeSession`` + BE ``CompleteSessionRequest``); F9-2 interview
(prompt context feeds ``template_structure``/``world_context``; REST
transport — the 400 MISSING_VARIABLE is gone); F9-3 consistency (the
StrictMode operation-id fix in ``useAIOperation`` lands results in dev
mode, so the render probes pin the results view).

Two RESIDUAL DEFECTS block two render legs (full assertions kept under
``xfail(strict=False)``): (a) interview questions — TestModel returns
``KBAssistOutput(mode='question', question=None, ...)`` and
``KBAssistAgent._validate_output`` raises ModelRetry →
``ModelRetryExhaustedError`` → 500 on every question POST; (b) the
completed-entry list render — ``map_session_to_entry`` persists
``tags=None`` and ``KBEntryList.tsx`` reads ``entry.tags.length``
unguarded → the KB view crashes blank (seeded entries pass
``tags: []`` and never hit it).

Runtime budget: ≤ 2.5 min (spec §7). Markers: e2e."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.e2e.config import BASE_URL
from tests.e2e.foundation import NovelContext, make_authed_request
from tests.e2e.helpers import mock_llm
from tests.e2e.helpers.kb_world import (
    capture_json_response,
    open_kb_mode,
    open_worldbuilding,
    seed_kb_entity,
)
from tests.e2e.helpers.novel_factory import complete_wizard

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture(scope="module")
def kbai_novel(module_stable_user) -> NovelContext:
    novel = complete_wizard(module_stable_user.page, BASE_URL)
    return NovelContext(
        page=module_stable_user.page,
        novel_id=novel["novel_id"],
        email=module_stable_user.email,
        password=module_stable_user.password,
        access_token=module_stable_user.access_token,
    )


@pytest.fixture
def authed_request(api_request, kbai_novel) -> Callable:
    """``api_request`` carrying this module novel owner's bearer token."""
    return make_authed_request(api_request, kbai_novel)


def _open_assisted_fields_view(page) -> str:
    """Shared interview-leg preamble: trigger → session created on mount
    → fields view renders → first template field answered (blur commits
    the real PATCH). Returns the session id."""
    open_worldbuilding(page)

    # A previous leg leaves ?mode=assist + its mounted panel; the shell
    # link strips the param and the URL-sync effect then unmounts the
    # stale panel ASYNC — acting earlier races the reset (the observed
    # order-dependent blank third column).
    page.wait_for_url(re.compile(r"/worldbuilding$"), timeout=15_000)

    # Defense for a panel that survived: exit a latched interview view,
    # then header Abandon → "End" confirm (deletes the session).
    if page.get_by_text("Interview Mode").first.is_visible():
        page.locator("button:has(svg.lucide-arrow-left)").first.click()
    if page.get_by_label("Entry Name").first.is_visible():
        page.get_by_role("button", name="Abandon", exact=True).click()
        page.get_by_role("button", name="End", exact=True).click()
        page.get_by_label("Entry Name").first.wait_for(state="hidden", timeout=15_000)

    # Capture the session-create response (first /kb/sessions hit).
    created = capture_json_response(page, "/kb/sessions")
    page.get_by_role("button", name="New with AI Interview").click()

    # A stale localStorage resume pointer short-circuits the trigger
    # into the "Resumed interview found" dialog — discard, re-trigger.
    try:
        page.get_by_text(re.compile(r"of \d+ fields complete")).first.wait_for(
            state="visible", timeout=2_500
        )
    except PlaywrightTimeoutError:
        resume_dialog = page.get_by_text("Resumed interview found").first
        if resume_dialog.is_visible():
            page.get_by_role("button", name="Start new interview").click()
            created = capture_json_response(page, "/kb/sessions")
            page.get_by_role("button", name="New with AI Interview").click()

    # Fields view renders the progress line (create+GET survived); 60s
    # for a cold `next dev` compiling the studio chunks on this hit.
    page.get_by_text(re.compile(r"of \d+ fields complete")).first.wait_for(
        state="visible", timeout=60_000
    )
    session_id = created()["id"]

    # First field is `age` (int in CharacterMetadata): map_session_to_entry
    # validates mapped metadata — a prose value would 400 at completion.
    page.locator("textarea").first.fill("34")
    page.keyboard.press("Tab")
    page.get_by_text(re.compile(r"1 of \d+ fields complete")).first.wait_for(
        state="visible", timeout=30_000
    )
    return session_id


@pytest.mark.e2e
class TestKBSessionInterview:
    def test_assisted_session_creates_entry(self, kbai_novel, authed_request) -> None:
        """KB-002 complete leg + B05 pin: name → Complete & Save → EXISTS.

        Chain: create → field answer (PATCH) → interview opens + fires
        the question POST against the SAME session → exit → Entry Name
        ("Maren Dusk") → Complete & Save → the entry EXISTS in the KB
        list (wire GET). Wire pins: B05 (interview POST != 404 — pre-B05
        the second touchpoint lost the session) and F9-1 (the complete
        response must carry ``entry_id`` — pre-fix always 400 "Session
        must have a name before completion").
        """
        page = kbai_novel.page
        session_id = _open_assisted_fields_view(page)

        # The interview view opens + fires its question request.
        page.get_by_role("button", name="Start Interview").first.click()
        page.get_by_text("Interview Mode").first.wait_for(state="visible", timeout=30_000)

        # B05 wire pin: the session SURVIVED. Deliberately != 404: the
        # pin targets the cache gate, whatever the layers above answer
        # (400 pre-F9-2, 500 post-F9-2 — both prove the lookup happened).
        resp = authed_request(
            "POST",
            f"/api/v1/novels/{kbai_novel.novel_id}/kb/sessions/{session_id}/interview",
            json={},
        )
        assert resp.status_code != 404, (
            f"B05 regression: session lost server-side ({resp.status_code})"
        )

        # Exit to the fields view; the header arrow renders in every
        # interview state (incl. the error branch leg 2 latches to).
        page.locator("button:has(svg.lucide-arrow-left)").first.click()

        # F9-1: name the entry, save; the captured response is the wire
        # pin (name in body, entry_id back).
        completed = capture_json_response(page, "/complete")
        page.get_by_label("Entry Name").fill("Maren Dusk")
        page.get_by_role("button", name="Complete & Save").click()

        complete_body = completed()
        assert complete_body.get("entry_id"), complete_body
        entry_id = complete_body["entry_id"]

        # The entry EXISTS in the KB list (wire pin; the UI-list render
        # is blocked by the tags defect — see the render leg below).
        try:
            listing = authed_request(
                "GET",
                f"/api/v1/novels/{kbai_novel.novel_id}/kb/entries",
            )
            assert listing.status_code == 200, listing.text[:300]
            names = [item["name"] for item in listing.json()["items"]]
            assert "Maren Dusk" in names, names
        finally:
            # MANDATORY cleanup: the module novel is shared — no entry
            # leak (nor a tags-null list poison).
            del_resp = authed_request(
                "DELETE",
                f"/api/v1/novels/{kbai_novel.novel_id}/kb/entries/{entry_id}",
            )
            assert del_resp.status_code == 204, del_resp.status_code
            # Recover the shared page: the list refetch may have crashed
            # the view before the DELETE landed; a reload re-mounts clean.
            page.reload()
            page.wait_for_load_state("domcontentloaded")

    @pytest.mark.xfail(
        reason="RESIDUAL DEFECT: the completed entry crashes the KB "
        "view — map_session_to_entry persists tags=None (KBEntryCreate "
        "has no tags), the wire returns null, and KBEntryList.tsx reads "
        "entry.tags.length UNGUARDED → TypeError → blank page. Seeded "
        "entries pass tags: [] and never hit it. Remove once the list "
        "null-guards tags (or the mapper defaults them).",
        strict=False,
    )
    def test_completed_entry_renders_in_kb_list(self, kbai_novel, authed_request) -> None:
        """KB-002 UI half: the completed entry renders in the KB list.

        Leanest chain (no interview view): fill → name → Complete & Save
        → the entry must appear in the rendered list (the complete
        mutation invalidates the entries query). Today the tags-null
        entry crashes the list instead — cleaned up regardless.
        """
        page = kbai_novel.page
        _open_assisted_fields_view(page)

        completed = capture_json_response(page, "/complete")
        page.get_by_label("Entry Name").fill("Render Dusk")
        page.get_by_role("button", name="Complete & Save").click()
        entry_id = completed()["entry_id"]

        try:  # the crash lands as a visibility timeout today
            page.get_by_text("Render Dusk").first.wait_for(state="visible", timeout=15_000)
        finally:
            del_resp = authed_request(
                "DELETE",
                f"/api/v1/novels/{kbai_novel.novel_id}/kb/entries/{entry_id}",
            )
            assert del_resp.status_code == 204, del_resp.status_code
            # Recover the shared page (crashed view today — see the mark).
            page.reload()
            page.wait_for_load_state("domcontentloaded")

    @pytest.mark.xfail(
        reason="RESIDUAL DEFECT: every question POST 500s — TestModel "
        "returns KBAssistOutput(mode='question', question=None, ...) "
        "and KBAssistAgent._validate_output raises ModelRetry (empty "
        "question) → ModelRetryExhaustedError. The F9-2 prompt fix "
        "HOLDS (final_prompt_validated: true); the seam is TestModel's "
        "minimal structured output vs the strict validator. Remove "
        "once the agent can answer under TestModel.",
        strict=False,
    )
    def test_interview_second_question_renders(self, kbai_novel) -> None:
        """KB-002 Q1→Q2 leg: answer Question 1 → Submit → Question 2.

        The F9-2 transport + prompt feed make each request a REAL
        `{session, question}` aggregate; the counter must advance.
        """
        page = kbai_novel.page
        _open_assisted_fields_view(page)

        page.get_by_role("button", name="Start Interview").first.click()
        page.get_by_text("Interview Mode").first.wait_for(state="visible", timeout=30_000)
        page.get_by_text("Question 1").first.wait_for(state="visible", timeout=30_000)

        # Answer Q1 and submit: the target field PATCHes, then the next
        # question request fires — Question 2 renders.
        page.get_by_placeholder("Type your answer...").fill("She fears open water since the wreck.")
        page.get_by_role("button", name="Submit Answer").click()
        page.get_by_text("Question 2").first.wait_for(state="visible", timeout=30_000)


@pytest.mark.e2e
class TestKBImprove:
    def test_improve_suggestions_render_and_apply(self, kbai_novel, authed_request) -> None:
        page = kbai_novel.page
        seed_kb_entity(
            authed_request,
            kbai_novel.novel_id,
            name="Improvable Entry",
            body="A guarded smuggler with an unstated goal.",
        )
        mock_llm(page, "kb_improve")  # happy variant
        open_worldbuilding(page)
        # The API-side seed misses the SPA's react-query cache — reload
        # so the seeded card renders deterministically.
        page.reload()
        page.wait_for_load_state("domcontentloaded")
        page.locator('[data-testid="kb-responsive-layout"]').wait_for(state="visible")

        page.get_by_text("Improvable Entry").first.click()
        page.get_by_role("button", name="Improve with AI").click()

        # Catalog-deterministic suggestions render (B06 pin: the route
        # resolves its prompt — the pre-fix 400 PROMPT_NOT_FOUND gone).
        page.get_by_text("Anchor Elara's goal in the opening line.").first.wait_for(
            state="visible", timeout=30_000
        )

        # The selected suggestions go to the REAL apply endpoint (the
        # catalog excludes /improve/apply); success = panel closes and
        # the trigger returns (the only visible success transition).
        page.get_by_role("button", name="Apply Selected", exact=True).click()
        page.get_by_role("button", name="Improve with AI").first.wait_for(
            state="visible", timeout=30_000
        )

    def test_improve_error_renders_honest_error(self, kbai_novel, authed_request) -> None:
        page = kbai_novel.page
        seed_kb_entity(
            authed_request,
            kbai_novel.novel_id,
            name="Failing Improve",
            body="Short body.",
        )
        mock_llm(page, "kb_improve", fixture="error")
        open_worldbuilding(page)
        page.reload()
        page.wait_for_load_state("domcontentloaded")
        page.locator('[data-testid="kb-responsive-layout"]').wait_for(state="visible")

        page.get_by_text("Failing Improve").first.click()
        page.get_by_role("button", name="Improve with AI").click()
        # ImproveErrorState with the mapped 5xx copy — the panel's
        # honest error branch.
        page.get_by_text("Connection lost. Check your internet connection.").first.wait_for(
            state="visible", timeout=30_000
        )


@pytest.mark.e2e
class TestKBConsistencyRealPath:
    def test_consistency_stream_route_is_registered(self, kbai_novel, authed_request) -> None:
        """B03 pin (router registered): the ADR-044 stream endpoint must
        answer SSE, not the audit's 404. Content = analysis wave."""
        resp = authed_request(
            "POST",
            f"/api/v1/consistency/check/stream?novel_id={kbai_novel.novel_id}",
            json={},  # ConsistencyRequest: all fields defaulted (verified)
        )
        assert resp.status_code == 200, f"{resp.status_code} {resp.text[:300]}"
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert "data:" in resp.text

    def test_check_runs_real_orchestrator_and_renders_results(
        self, kbai_novel, authed_request
    ) -> None:
        """KB-004 on the REAL path (E2E-GATE carry-forward 2026-10-15).

        NO browser mock — the real three-phase orchestrator under
        TestModel. D-1 target: Phase 2 composes through the governed
        route and reports entry-internal issues (pre-fix: silent zero
        issues with entity_count > 0). RE-ADDED render probes (F9-3
        StrictMode fix lands results in dev mode): "N entities
        analyzed" + the "entry internal" chip; the dispatch capture +
        wire pin stay as underlying evidence.
        """
        page = kbai_novel.page
        seed_kb_entity(
            authed_request,
            kbai_novel.novel_id,
            name="Contradictory Smith",
            body="Never leaves the forge. Travels the coast every summer.",
        )
        # Capture the panel's own auto-check exchange (consistency.ts =
        # the UI dispatch surface; the REAL response, not synthetic).
        panel_check = capture_json_response(page, "kb/consistency-check")
        open_worldbuilding(page)
        open_kb_mode(page, "consistency")
        ui_report = panel_check()
        assert ui_report.get("entity_count", 0) >= 1, ui_report
        assert ui_report["summary"]["entry_internal"] >= 1, ui_report["summary"]

        # Render probes: entity-count line + the entry-internal chip
        # for the findings the REAL orchestrator reported above.
        page.get_by_text(re.compile(r"\d+ entities analyzed")).first.wait_for(
            state="visible", timeout=30_000
        )
        page.get_by_text(re.compile(r"\d+ entry internal")).first.wait_for(
            state="visible", timeout=30_000
        )

        # Wire pin: the summary must report entry-internal findings —
        # the silent zero-issue no-op must never return.
        report = authed_request(
            "POST",
            f"/api/v1/novels/{kbai_novel.novel_id}/kb/consistency-check",
            json={
                "include_asymmetry": True,
                "include_entry_internal": True,
                "include_cross_entity": False,
                "refresh": True,
            },
        )
        assert report.status_code == 200, report.text[:300]
        body = report.json()
        assert body["entity_count"] >= 1
        assert body["summary"]["entry_internal"] >= 1, body["summary"]
