"""KB interview-leg preamble — shared by the KB AI E2E specs.

``open_assisted_fields_view`` extracted from ``test_kb_ai.py`` per
RULE-04 (the spec module crossed the 400-line test hard limit when the
two xfail render legs flipped green). One responsibility: drive the
assisted-creation fields view into its deterministic "first field
answered" state and hand back the session id.
"""

from __future__ import annotations

import re

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.e2e.helpers.kb_world import capture_json_response, open_worldbuilding

# RULE-18: named constants, not literals at the call site. Values mirror
# the original inline ones in test_kb_ai.py (calibrated 2026-10-17).
WORLDBUILDING_URL_TIMEOUT_MS: int = 15_000
PANEL_RESET_TIMEOUT_MS: int = 15_000
RESUME_DIALOG_PROBE_MS: int = 2_500
COLD_COMPILE_TIMEOUT_MS: int = 60_000
FIELD_COMMIT_TIMEOUT_MS: int = 30_000


def open_assisted_fields_view(page: Page) -> str:
    """Shared interview-leg preamble: trigger → session created on mount
    → fields view renders → first template field answered (blur commits
    the real PATCH). Returns the session id."""
    open_worldbuilding(page)

    # A previous leg leaves ?mode=assist + its mounted panel; the shell
    # link strips the param and the URL-sync effect then unmounts the
    # stale panel ASYNC — acting earlier races the reset (the observed
    # order-dependent blank third column).
    page.wait_for_url(re.compile(r"/worldbuilding$"), timeout=WORLDBUILDING_URL_TIMEOUT_MS)

    # Defense for a panel that survived: exit a latched interview view,
    # then header Abandon → "End" confirm (deletes the session).
    if page.get_by_text("Interview Mode").first.is_visible():
        page.locator("button:has(svg.lucide-arrow-left)").first.click()
    if page.get_by_label("Entry Name").first.is_visible():
        page.get_by_role("button", name="Abandon", exact=True).click()
        page.get_by_role("button", name="End", exact=True).click()
        page.get_by_label("Entry Name").first.wait_for(
            state="hidden", timeout=PANEL_RESET_TIMEOUT_MS
        )

    # Capture the session-create response (first /kb/sessions hit).
    created = capture_json_response(page, "/kb/sessions")
    page.get_by_role("button", name="New with AI Interview").click()

    # A stale localStorage resume pointer short-circuits the trigger
    # into the "Resumed interview found" dialog — discard, re-trigger.
    try:
        page.get_by_text(re.compile(r"of \d+ fields complete")).first.wait_for(
            state="visible", timeout=RESUME_DIALOG_PROBE_MS
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
        state="visible", timeout=COLD_COMPILE_TIMEOUT_MS
    )
    session_id = created()["id"]

    # First field is `age` (int in CharacterMetadata): map_session_to_entry
    # validates mapped metadata — a prose value would 400 at completion.
    page.locator("textarea").first.fill("34")
    page.keyboard.press("Tab")
    page.get_by_text(re.compile(r"1 of \d+ fields complete")).first.wait_for(
        state="visible", timeout=FIELD_COMMIT_TIMEOUT_MS
    )
    return session_id
