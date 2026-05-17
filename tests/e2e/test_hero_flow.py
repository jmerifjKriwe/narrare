"""Hero E2E Flow Test — complete MVP user journey.

Covers: registration → setup wizard (all steps) → dashboard → editor → autosave.

All LLM responses are mocked via page.route() — no real API tokens consumed.
Runs against the full stack (API port 8000, Frontend port 3000).
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

import pytest

from tests.e2e.mocks.llm_responses import setup_llm_mocks

if TYPE_CHECKING:
    from playwright.sync_api import Page


@pytest.mark.e2e
class TestHeroFlow:
    """Single test class covering the complete MVP user journey."""

    def test_complete_user_journey(
        self,
        page: Page,
        base_url: str,
        api_url: str,
        register_unique_user,
    ) -> None:
        """Complete user journey: signup → wizard → demo → editor → autosave."""
        # Install LLM mocks BEFORE any interaction that could trigger LLM calls
        setup_llm_mocks(page)

        # ===================================================================
        # Step 2.1 — Register a new user via API
        # ===================================================================
        user = register_unique_user()
        access_token = user["access_token"]
        assert access_token, "Registration did not return an access token"

        # Set up auth: intercept all /api/v1/ requests and inject the token
        def _add_auth_header(route):
            headers = {
                **route.request.headers,
                "Authorization": f"Bearer {access_token}",
            }
            route.continue_(headers=headers)

        page.route("**/api/v1/**", _add_auth_header)

        # Inject cookie for the middleware (proxy.ts)
        # This is needed because the middleware runs on the server and checks cookies,
        # but the test otherwise only provides the token via header interception.
        page.context.add_cookies(
            [
                {
                    "name": "narrare_auth",
                    "value": access_token,
                    "url": base_url,
                }
            ]
        )

        # Re-install LLM mocks (route order matters — auth + LLM mocks coexist)
        setup_llm_mocks(page)

        # ===================================================================
        # Step 2.2 — Navigate to setup wizard, complete step 1
        # ===================================================================
        page.goto(f"{base_url}/wizard")
        page.wait_for_load_state("networkidle")

        # Step 1: Project name, language, autosave interval
        # Fill in the project name field
        project_name_input = page.locator(
            'input[name="project_name"], input[id="project_name"], input[placeholder*="project" i]'
        ).first
        if project_name_input.is_visible():
            project_name_input.fill("My Fantasy Novel")
        else:
            # Fallback: try to find any text input on the page
            text_inputs = page.locator('input[type="text"]')
            if text_inputs.count() > 0:
                text_inputs.first.fill("My Fantasy Novel")

        # Click next/continue button for step 1
        _click_next(page)

        # ===================================================================
        # Step 2.3 — Complete step 2 (starter content selection)
        # ===================================================================
        fantasy_selectors = [
            'button:has-text("Fantasy")',
            "text=Fantasy",
        ]
        for selector in fantasy_selectors:
            locator = page.locator(selector).first
            if locator.is_visible():
                locator.click()
                break

        _click_next(page)

        # ===================================================================
        # Step 2.4 — Complete step 3 (novel metadata: title, author, genre)
        # ===================================================================
        title_input = page.locator(
            'input[name="title"], input[id="title"], input[placeholder*="title" i]'
        ).first
        if title_input.is_visible():
            title_input.fill("The Dragon's Apprentice")

        _click_next(page)

        # ===================================================================
        # Step 2.5 — Step 4: Provider setup (may be skipped if user has providers)
        # ===================================================================
        page_text = page.inner_text(".bg-card.border").lower()
        if "provider" in page_text or "openai" in page_text or "api key" in page_text:
            provider_selectors = ['button:has-text("OpenAI")']
            for selector in provider_selectors:
                locator = page.locator(selector).first
                if locator.is_visible():
                    locator.click()
                    break

            api_key_input = page.locator(
                'input[name="api_key"], input[id="api_key"], input[type="password"]'
            ).first
            if api_key_input.is_visible():
                api_key_input.fill("sk-test-e2e-mock-key-not-real")

            _click_next(page)

        # ===================================================================
        # Step 2.6 — Confirm setup, verify redirect to dashboard/editor
        # ===================================================================
        complete_selectors = [
            'button:has-text("Complete")',
            'button:has-text("Finish")',
            'button:has-text("Start")',
            'button[type="submit"]',
        ]
        for selector in complete_selectors:
            locator = page.locator(selector).first
            if locator.is_visible():
                locator.click()
                break

        # Wait for redirect — could be dashboard or novel editor
        print(f"\n=== POST-COMPLETE: Current URL = {page.url}")
        print(f"Page title: {page.title()}")
        try:
            page.wait_for_url(f"{base_url}/novel/**", timeout=15000)
            print(f"Redirected to novel: {page.url}")
        except Exception:
            print(f"Not on novel. Current URL: {page.url}")
            page.wait_for_url(f"{base_url}/dashboard**", timeout=5000)

        # ===================================================================
        # Step 2.7 — If on dashboard, navigate to editor
        # ===================================================================
        if "/dashboard" in page.url:
            novel_card = page.locator(
                '[data-testid="novel-card"], a[href*="/novel/"], .novel-card'
            ).first
            novel_card.wait_for(state="visible", timeout=10000)
            novel_card.click()
            page.wait_for_url(f"{base_url}/novel/**", timeout=10000)

        # ===================================================================
        # Step 2.8 — Editor loads content, type text, verify autosave
        # ===================================================================

        # Wait for editor to be ready — the Sidebar auto-selects first chapter
        # Give it time for the sidebar to fetch chapters and auto-select
        page.wait_for_timeout(2000)

        # Check if a chapter was selected
        print(f"\n=== EDITOR DEBUG ===")
        print(f"Current URL: {page.url}")
        page_text = page.inner_text("body")[:500]
        print(f"Page text: {page_text}")

        # Take screenshot for debugging
        page.screenshot(path="/tmp/editor-state.png")
        print("Screenshot saved to /tmp/editor-state.png")

        # Look for the editor area
        editor_area = page.locator(
            '.tiptap, [data-testid="editor"], .ProseMirror, [contenteditable="true"]'
        ).first
        is_visible = editor_area.is_visible()
        print(f"Editor area visible: {is_visible}")

        if not is_visible:
            # Maybe we need to click on a chapter in the sidebar first
            chapter_buttons = page.locator("button:has-text('Kapitel')")
            if chapter_buttons.count() == 0:
                # Try clicking the first chapter button in the sidebar
                sidebar_chapters = page.locator(".space-y-1 button").first
                if sidebar_chapters.is_visible():
                    sidebar_chapters.click()
                    page.wait_for_timeout(1000)
                    print("Clicked first sidebar chapter")

            editor_area = page.locator(
                '.tiptap, [data-testid="editor"], .ProseMirror, [contenteditable="true"]'
            ).first
            editor_area.wait_for(state="visible", timeout=10000)

        # Type some text in the editor
        test_text = f" E2E autosave test {uuid.uuid4().hex[:6]}"
        editor_area.type(test_text)

        # -------------------------------------------------------------------
        # Save: set up comprehensive request logging BEFORE triggering save.
        # The actual endpoint is PUT /novels/{id}/chapters/{id}/content
        # (see packages/web/lib/api/client.ts → chaptersApi.updateContent)
        #
        # IMPORTANT: page.on("request") does NOT fire for requests intercepted
        # by page.route(). We must capture inside the route handlers themselves.
        # We re-route the auth handler to also log, and add a catch-all route
        # at the end to capture anything that slips through.
        # -------------------------------------------------------------------

        captured_requests: list[str] = []

        def _log_request_entry(method: str, url: str, post_data: str | None = None) -> None:
            """Append a formatted request entry to captured_requests."""
            entry = f"{method} {url}"
            if post_data:
                entry += f"  [body: {post_data[:200]}]"
            captured_requests.append(entry)
            print(f"  [CAPTURED] {entry}")

        # Replace the auth route with one that also logs requests.
        # We unroute the old one first, then add the logging version.
        page.unroute("**/api/v1/**")

        def _add_auth_header_with_logging(route):
            _log_request_entry(route.request.method, route.request.url, route.request.post_data)
            headers = {
                **route.request.headers,
                "Authorization": f"Bearer {access_token}",
            }
            route.continue_(headers=headers)

        page.route("**/api/v1/**", _add_auth_header_with_logging)

        # Also add a catch-all route to capture any non-API requests (e.g.
        # static assets, websocket upgrades, etc.) — this fires AFTER the
        # more specific routes so it only sees what they didn't handle.
        def _catch_all_logging(route):
            url = route.request.url
            # Skip noisy static/resource requests to keep output readable
            if not any(skip in url for skip in [".png", ".jpg", ".svg", ".css", "favicon"]):
                _log_request_entry(route.request.method, url, route.request.post_data)
            route.continue_()

        page.route("**/*", _catch_all_logging)

        # Global listener as a final fallback (fires for non-routed requests)
        page.on("request", lambda req: _log_request_entry(req.method, req.url, req.post_data))

        # Screenshot right before save attempt — shows editor state at save time
        page.screenshot(path="/tmp/before-save.png")
        print("Screenshot before save saved to /tmp/before-save.png")

        # Click the Save button directly — more reliable than keyboard shortcuts
        # in headless mode where Meta/Ctrl key mapping is inconsistent.
        # The Save button is in the header bar with bg-primary styling and a Save icon.
        # Try multiple selectors to handle i18n (Save/Speichern/Enregistrer).
        save_button = page.locator(
            'button:has(svg):has-text("Save"), '
            'button:has(svg):has-text("Speichern"), '
            'button:has(svg):has-text("Enregistrer")'
        ).first

        if not save_button.is_visible():
            # Fallback: the Save button is the last button in the header bar
            # with bg-primary styling (unique among header buttons)
            save_button = page.locator("button.bg-primary").first

        if not save_button.is_visible():
            # Last resort: last button in the header action area
            save_button = page.locator(".flex.items-center.gap-4 button").last

        save_button.wait_for(state="visible", timeout=5000)
        print(f"\n=== SAVE BUTTON ===")
        print(f"Save button visible: {save_button.is_visible()}")
        print(
            f"Save button text: {save_button.inner_text() if save_button.is_visible() else 'N/A'}"
        )

        # Click save and wait for requests to fire.
        save_button.click()
        page.wait_for_timeout(2000)

        # Print ALL captured requests immediately after the click so we can
        # see whether the save triggered any network activity at all.
        print(f"\n=== REQUESTS AFTER SAVE CLICK ({len(captured_requests)} so far) ===")
        for req_entry in captured_requests:
            print(f"  {req_entry}")

        # Now wait up to 15s total for the autosave PUT request to appear.
        # We poll captured_requests instead of using expect_request, because
        # expect_request swallows intermediate output on timeout.
        autosave_request = None

        start = time.monotonic()
        while time.monotonic() - start < 15:
            # Find the autosave PUT request in our captured list
            for entry in captured_requests:
                if (
                    entry.startswith("PUT ")
                    and "/chapters/" in entry
                    and entry.endswith("/content")
                ):
                    autosave_request = entry
                    break
            if autosave_request:
                break
            page.wait_for_timeout(500)

        if autosave_request is None:
            # Build a detailed error message with every request we saw
            request_log = "\n  ".join(captured_requests) if captured_requests else "(none captured)"
            # Take a screenshot after timeout too
            page.screenshot(path="/tmp/after-save-timeout.png")
            raise AssertionError(
                f"Autosave did not fire after clicking Save (timeout 15s).\n"
                f"Save button was visible: {save_button.is_visible()}\n"
                f"Editor URL: {page.url}\n"
                f"Screenshot after timeout: /tmp/after-save-timeout.png\n"
                f"All captured requests ({len(captured_requests)}):\n  {request_log}"
            )

        print(f"\n=== AUTOSAVE REQUEST FOUND ===")
        print(f"  {autosave_request}")

        # Verify the request body contains our typed text
        assert "content" in autosave_request, "Autosave request body missing 'content' field"
        assert test_text.strip() in autosave_request, (
            f"Autosave request body missing typed text. Expected substring of: {test_text.strip()!r}"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _click_next(page: Page) -> None:
    """Click the next/continue/submit button on the current wizard step."""
    next_selectors = [
        'button:has-text("Next")',
        'button:has-text("Continue")',
        'button:has-text("Weiter")',
        'button[type="submit"]',
    ]
    for selector in next_selectors:
        locator = page.locator(selector).first
        if locator.is_visible():
            locator.click()
            # Small wait for animation/transition
            page.wait_for_timeout(500)
            return

    # Fallback: try the last button on the page
    buttons = page.locator("button")
    count = buttons.count()
    if count > 0:
        buttons.last.click()
        page.wait_for_timeout(500)
