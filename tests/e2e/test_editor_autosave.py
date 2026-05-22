"""Editor Autosave E2E Test.

Covers: Editor loading, content insertion via TipTap API, and autosave functionality.

All LLM responses are mocked via page.route() — no real API tokens consumed.
Runs against the full stack (API port 8000, Frontend port 3000).
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

import pytest

from tests.e2e.mocks.llm_responses import setup_llm_mocks
from tests.e2e.test_helpers import _click_next, _wait_for_wizard_ready

if TYPE_CHECKING:
    from playwright.sync_api import Page


@pytest.mark.e2e
class TestEditorAutosave:
    """Test editor content and autosave functionality."""

    def test_editor_content_and_autosave(
        self,
        page: Page,
        base_url: str,
        api_url: str,
        register_unique_user,
    ) -> None:
        """Test editor loads content, inserts text via TipTap API, and saves."""
        # Install LLM mocks BEFORE any interaction that could trigger LLM calls
        setup_llm_mocks(page)

        # Collect console errors for debugging
        console_errors: list[str] = []
        page.on("pageerror", lambda err: console_errors.append(str(err)))

        # Register and login user
        user = register_unique_user()
        access_token = user["access_token"]
        email = user["email"]
        password = user["password"]
        _skip_login = user.get("skip_login", False)

        # Navigate to login UI if needed
        if not _skip_login:
            page.goto(f"{base_url}/login")
            page.wait_for_url("**/login", timeout=10000)

            # Fill credentials and login
            email_input = page.locator("#login-email")
            email_input.wait_for(state="visible", timeout=10000)
            page.fill("#login-email", email)
            page.fill("#login-password", password)

            page.click('button[type="submit"]')
            page.wait_for_url(f"{base_url}/", timeout=15000)

        # Navigate to wizard
        page.goto(f"{base_url}/wizard")
        # Wait for wizard to fully load (step 1 visible)
        _wait_for_wizard_ready(page)

        # Complete wizard setup first
        project_name_input = page.locator(
            'input[name="project_name"], input[id="project_name"], input[placeholder*="project" i]'
        ).first
        if project_name_input.is_visible():
            project_name_input.fill("My Fantasy Novel")
        else:
            text_inputs = page.locator('input[type="text"]')
            if text_inputs.count() > 0:
                text_inputs.first.fill("My Fantasy Novel")

        _click_next(page, expected_step=2)

        # Genre selection
        fantasy_selectors = [
            'button:has-text("Fantasy")',
            "text=Fantasy",
        ]
        for selector in fantasy_selectors:
            locator = page.locator(selector).first
            if locator.is_visible():
                locator.click()
                break

        _click_next(page, expected_step=3)

        # Title input
        title_input = page.locator(
            'input[name="title"], input[id="title"], input[placeholder*="title" i]'
        ).first
        if title_input.is_visible():
            title_input.fill("The Dragon's Apprentice")

        _click_next(page, expected_step=4)

        # Provider setup
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

        # Wait for step 5 (confirmation) to render before looking for the complete button.
        # Without this wait, the test immediately checks is_visible() on selectors that
        # haven't rendered yet, silently skips the loop, and wait_for_url times out.
        page.locator('[data-testid="wizard-complete"]').first.wait_for(
            state="visible", timeout=15000
        )

        # Complete wizard — use data-testid selector (most reliable, matches WizardStep5.tsx)
        complete_button = page.locator('[data-testid="wizard-complete"]').first
        with page.expect_response("**/api/v1/setup/complete", timeout=15000):
            complete_button.click()

        # Wait for redirect to novel editor
        page.wait_for_url(f"{base_url}/novel/**", timeout=15000)

        # ===================================================================
        # Set up request logging BEFORE any editor interaction.
        # The actual endpoint is PUT /novels/{id}/chapters/{id}/content
        # (see packages/web/lib/api/client.ts → chaptersApi.updateContent)
        #
        # IMPORTANT: page.on("request") does NOT fire for requests intercepted
        # by page.route(). We must capture inside the route handlers themselves.
        # ===================================================================

        captured_requests: list[dict[str, str]] = []

        def _log_request_entry(method: str, url: str, post_data: str | None = None) -> None:
            """Append a formatted request entry to captured_requests."""
            entry = {
                "method": method,
                "url": url,
                "body": post_data or "",
                "display": f"{method} {url}",
            }
            if post_data:
                entry["display"] += f"  [body: {post_data[:200]}]"
            captured_requests.append(entry)
            print(f"  [CAPTURED] {entry['display']}")

        # Replace the auth route with one that also logs requests.
        page.unroute("**/api/v1/**")

        def _add_auth_header_with_logging(route):
            _log_request_entry(route.request.method, route.request.url, route.request.post_data)
            headers = {
                **route.request.headers,
                "Authorization": f"Bearer {access_token}",
            }
            route.continue_(headers=headers)

        page.route("**/api/v1/**", _add_auth_header_with_logging)

        # Also add a catch-all route to capture any non-API requests
        def _catch_all_logging(route):
            url = route.request.url
            if not any(skip in url for skip in [".png", ".jpg", ".svg", ".css", "favicon"]):
                _log_request_entry(route.request.method, url, route.request.post_data)
            route.continue_()

        page.route("**/*", _catch_all_logging)

        # ===================================================================
        # Editor loads content, insert text via TipTap API, save
        # ===================================================================

        # Wait for editor to be ready — the Sidebar auto-selects first chapter
        # Give it time for the sidebar to fetch chapters and auto-select
        page.wait_for_timeout(2000)

        # Check if a chapter was selected
        print("\n=== EDITOR DEBUG ===")
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

        # -------------------------------------------------------------------
        # Insert text via TipTap's API using page.evaluate().
        #
        # Playwright's .type() on a contenteditable div does NOT reliably
        # trigger TipTap's onUpdate lifecycle — the text may appear in the
        # DOM but TipTap's internal document state stays unchanged. This means
        # editor.getHTML() returns stale content and the save sends old data.
        #
        # TipTap exposes its Editor instance on window.__narrareEditor (set in
        # TipTapEditor.tsx). We use editor.commands.insertContent() which
        # properly fires TipTap's onUpdate → onChange → autosave chain.
        # -------------------------------------------------------------------
        test_text = f"E2E autosave test {uuid.uuid4().hex[:6]}"

        # Use TipTap's insertContent command — this fires all lifecycle hooks
        # (onUpdate, onChange, autosave debounce).
        insert_result = page.evaluate(
            """
            (text) => {
                const editor = window.__narrareEditor;
                if (!editor) return 'no-editor-instance';

                editor.commands.insertContent(text);
                editor.commands.focus();
                return 'ok';
            }
            """,
            test_text,
        )
        assert insert_result == "ok", (
            f"Failed to insert text into editor: {insert_result}. "
            "TipTap editor instance not found on window.__narrareEditor."
        )

        # Give TipTap's onUpdate + debounce a moment to process
        page.wait_for_timeout(500)

        # Verify the text actually made it into the editor's HTML
        editor_html = page.evaluate(
            """
            () => {
                const el = document.querySelector('.ProseMirror');
                return el ? el.innerHTML : '';
            }
            """
        )
        print("\n=== EDITOR CONTENT CHECK ===")
        print(f"Editor HTML length: {len(editor_html)}")
        print(f"Text in editor HTML: {test_text in editor_html}")

        assert test_text in editor_html, (
            f"Typed text '{test_text}' not found in editor HTML after insertContent().\n"
            f"Editor HTML (first 500 chars): {editor_html[:500]}"
        )

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
        print("\n=== SAVE BUTTON ===")
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
            print(f"  {req_entry['display']}")

        # Now wait up to 15s total for the autosave PUT request to appear.
        # We poll captured_requests instead of using expect_request, because
        # expect_request swallows intermediate output on timeout.
        autosave_request: dict[str, str] | None = None

        start = time.monotonic()
        while time.monotonic() - start < 15:
            # Find the autosave PUT request in our captured list
            for entry in captured_requests:
                if (
                    entry["method"] == "PUT"
                    and "/chapters/" in entry["url"]
                    and entry["url"].rstrip("/").endswith("/content")
                ):
                    autosave_request = entry
                    break
            if autosave_request:
                break
            page.wait_for_timeout(500)

        if autosave_request is None:
            # Build a detailed error message with every request we saw
            request_log = (
                "\n  ".join(r["display"] for r in captured_requests)
                if captured_requests
                else "(none captured)"
            )
            # Take a screenshot after timeout too
            page.screenshot(path="/tmp/after-save-timeout.png")
            raise AssertionError(
                f"Autosave did not fire after clicking Save (timeout 15s).\n"
                f"Save button was visible: {save_button.is_visible()}\n"
                f"Editor URL: {page.url}\n"
                f"Screenshot after timeout: /tmp/after-save-timeout.png\n"
                f"All captured requests ({len(captured_requests)}):\n  {request_log}"
            )

        print("\n=== AUTOSAVE REQUEST FOUND ===")
        print(f"  {autosave_request['display']}")

        # Verify the request body contains our typed text
        request_body = autosave_request.get("body", "")
        assert "content" in request_body, "Autosave request body missing 'content' field"
        assert test_text in request_body, (
            f"Autosave request body missing typed text. "
            f"Expected substring of: {test_text!r}\n"
            f"Request body (first 500 chars): {request_body[:500]}"
        )
