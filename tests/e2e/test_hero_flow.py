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

        # Collect console errors for debugging
        console_errors: list[str] = []
        page.on("pageerror", lambda err: console_errors.append(str(err)))

        # ===================================================================
        # Step 2.1 — Register a new user via API
        # ===================================================================
        user = register_unique_user()
        email = user["email"]
        password = user["password"]
        access_token = user["access_token"]
        assert access_token, "Registration did not return an access token"

        # ===================================================================
        # Step 2.2 — Login via UI (like a real user) to establish proper session
        # ===================================================================
        # The UI login calls the frontend auth store which sets the access token
        # via setAccessToken(), ensuring the frontend and API proxy are in sync.
        # Manually injecting cookies bypasses this flow and causes redirects to
        # /login after the wizard completes.
        page.goto(f"{base_url}/login")
        page.wait_for_load_state("networkidle")

        # Fill credentials using the known input IDs from the login page
        page.fill("#login-email", email)
        page.fill("#login-password", password)

        # Click the login submit button and wait for the async form submission.
        # The login page calls authStore.login() (async API call), then
        # router.push("/") on success. The root page "/" IS the dashboard —
        # there is no /dashboard route. New users see the empty dashboard
        # with a "New Novel" button that leads to /wizard.
        with page.expect_response("**/api/v1/auth/login", timeout=15000) as login_response_info:
            page.click('button[type="submit"]')

        login_response = login_response_info.value
        login_status = login_response.status
        print(f"\n=== LOGIN API RESPONSE: HTTP {login_status} ===")

        if login_status >= 400:
            try:
                body = login_response.json()
                print(f"  Response body: {body}")
            except Exception:
                print(f"  Response text: {login_response.text()[:500]}")

        # Wait for the redirect to "/" (the dashboard page).
        # The login component does router.push("/") after successful login.
        page.wait_for_url(f"{base_url}/", timeout=10000)
        print(f"Login redirect successful. Current URL: {page.url}")

        # Verify the dashboard actually loaded (not a redirect back to /login).
        # The DashboardView shows a loading spinner first, then either:
        # - the dashboard title (novels loaded)
        # - the empty state (no novels yet)
        # - or redirects back to /login if authApi.me() fails
        page.wait_for_load_state("networkidle")
        current_url = page.url
        page_text = page.inner_text("body")

        print(f"  Final URL after networkidle: {current_url}")
        print(f"  Page text (first 300 chars): {page_text[:300]}")

        # If we got redirected back to /login, the auth token wasn't set properly
        if "/login" in current_url:
            # Check for error message on the login page
            error_div = page.locator(".bg-destructive\\/10").first
            if error_div.is_visible():
                print(f"  Login error message: {error_div.inner_text()}")
            raise AssertionError(
                f"Login redirected back to /login. URL: {current_url}\n"
                f"Page text: {page_text[:500]}\n"
                f"Login API returned HTTP {login_status}."
            )

        # ===================================================================
        # Step 2.3 — Navigate to setup wizard, complete step 1
        # ===================================================================
        # The dashboard ("/") is the landing page after login. New users see
        # an empty dashboard with a "New Novel" button. Navigate to /wizard
        # to start the setup flow.
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
        _click_next(page, expected_step=2)

        # ===================================================================
        # Step 2.4 — Complete step 2 (starter content selection)
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

        _click_next(page, expected_step=3)

        # ===================================================================
        # Step 2.5 — Complete step 3 (novel metadata: title, author, genre)
        # ===================================================================
        title_input = page.locator(
            'input[name="title"], input[id="title"], input[placeholder*="title" i]'
        ).first
        if title_input.is_visible():
            title_input.fill("The Dragon's Apprentice")

        _click_next(page, expected_step=4)

        # ===================================================================
        # Step 2.6 — Step 4: Provider setup (may be skipped if user has providers)
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

            _click_next(page)  # Step 4 → 5, or skip to 5 if providers exist

        # ===================================================================
        # Step 2.7 — Confirm setup, verify redirect to dashboard/editor
        # ===================================================================

        # --- Verify we're actually on step 5 before attempting complete ---
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)

        # Check current wizard step by looking for step 5 specific content
        body_text = page.inner_text("body")
        print(f"\n=== WIZARD STATE CHECK ===")
        print(f"  Current URL: {page.url}")
        print(f"  Body text (first 500 chars): {body_text[:500]}")

        # Look for step indicator circles to determine current step
        active_steps = page.locator('[aria-current="step"]')
        if active_steps.count() > 0:
            current_step_label = active_steps.first.inner_text()
            print(f"  Current wizard step: {current_step_label}")
        else:
            print("  Could not determine current wizard step")

        # Check for validation errors before proceeding
        error_elements = page.locator(".text-destructive")
        error_count = error_elements.count()
        if error_count > 0:
            print(f"  WARNING: Found {error_count} error element(s) on page:")
            for i in range(min(error_count, 5)):
                print(f"    Error [{i}]: {error_elements.nth(i).inner_text()}")

        # --- Intercept /setup/complete to log request and response ---
        # IMPORTANT: Set up interceptor BEFORE clicking the button
        setup_complete_log: dict[str, str | int | None] = {
            "request_url": None,
            "request_body": None,
            "response_status": None,
            "response_body": None,
            "error": None,
        }

        def _intercept_setup_complete(route):
            """Intercept the /setup/complete call to log everything."""
            setup_complete_log["request_url"] = route.request.url
            setup_complete_log["request_body"] = route.request.post_data
            try:
                # Let the request through to the real backend.
                # IMPORTANT: We must capture the body text BEFORE calling
                # route.fulfill(), because route.fetch() returns a response
                # whose body can only be read once. If we read it via
                # response.text() and then pass the response object to
                # route.fulfill(), the body stream is already exhausted
                # and the browser receives an empty response.
                response = route.fetch()
                setup_complete_log["response_status"] = response.status
                body_text = response.text()
                setup_complete_log["response_body"] = body_text
                # Fulfill with explicit parameters — body_text already captured
                route.fulfill(
                    status=response.status,
                    headers=response.headers,
                    body=body_text,
                )
            except Exception as e:
                setup_complete_log["error"] = str(e)
                # Return a 500 so the frontend error handler fires
                route.fulfill(status=500, body='{"detail": "Intercepted error"}')

        page.route("**/api/v1/setup/complete", _intercept_setup_complete)

        # --- Find and click the Complete button ---
        # The button text is "Finish ✓" (from i18n common.json "finish" key + ✓)
        # Button has type="button" with onClick={handleComplete}
        complete_selectors = [
            'button:has-text("Finish")',
            'button:has-text("Complete")',
            'button:has-text("Start")',
            'button:has-text("Erstellen")',  # German "Create"
            'button:has-text("Bestätigen")',  # German "Confirm"
        ]
        clicked_selector = None
        for selector in complete_selectors:
            locator = page.locator(selector).first
            if locator.is_visible():
                print(f"\n=== COMPLETE BUTTON: Found visible button with selector: {selector}")
                print(f"  Button text: {locator.inner_text()}")
                print(f"  Button type attr: {locator.get_attribute('type')}")
                print(f"  Button disabled attr: {locator.get_attribute('disabled')}")

                # Use expect_response to wait for the API call to fire
                with page.expect_response(
                    "**/api/v1/setup/complete", timeout=15000
                ) as response_info:
                    locator.click()

                # Wait for the response to complete
                try:
                    resp = response_info.value
                    print(f"  API call fired! Response status: {resp.status}")
                    print(f"  API call URL: {resp.request.url}")
                    clicked_selector = selector
                except Exception as e:
                    print(f"  API call did NOT fire within timeout: {e}")
                break

        if clicked_selector is None:
            # Dump all visible buttons for debugging
            all_buttons = page.locator("button")
            count = all_buttons.count()
            print(f"\n=== COMPLETE BUTTON: No matching selector found. Total buttons: {count}")
            for i in range(min(count, 20)):
                btn = all_buttons.nth(i)
                if btn.is_visible():
                    print(
                        f"  [{i}] text='{btn.inner_text()}' type='{btn.get_attribute('type') or 'button'}'"
                    )

        # Wait a moment for any pending operations
        page.wait_for_timeout(1000)

        # Print the intercepted API call details
        print(f"\n=== SETUP/COMPLETE API CALL ===")
        print(f"  URL: {setup_complete_log['request_url']}")
        print(f"  Request body: {setup_complete_log['request_body']}")
        print(f"  Response status: {setup_complete_log['response_status']}")
        print(f"  Response body: {setup_complete_log['response_body']}")
        if setup_complete_log["error"]:
            print(f"  Error: {setup_complete_log['error']}")

        # Check for console errors
        # (collected via page.on("pageerror") if needed)

        # Check for console errors collected during the test
        if console_errors:
            print(f"\n=== CONSOLE ERRORS ({len(console_errors)}) ===")
            for err in console_errors[-10:]:  # Last 10 errors
                print(f"  {err[:200]}")

        # Check for error messages on the page
        page_text = page.inner_text("body")
        error_indicators = ["error", "failed", "invalid", "missing", "required", "fehler"]
        found_errors = [word for word in error_indicators if word in page_text.lower()]
        if found_errors:
            print(f"\n=== ERROR INDICATORS FOUND ON PAGE: {found_errors}")
            # Extract context around error words
            for word in found_errors:
                idx = page_text.lower().index(word)
                context = page_text[max(0, idx - 50) : idx + 100]
                print(f"  Context for '{word}': ...{context}...")

        # Take screenshot immediately after click
        page.screenshot(path="/tmp/after-complete-click.png")
        print(f"\n=== POST-COMPLETE: Current URL = {page.url}")
        print(f"Page title: {page.title()}")
        print("Screenshot saved to /tmp/after-complete-click.png")

        # Wait for redirect — could be dashboard or novel editor
        try:
            page.wait_for_url(f"{base_url}/novel/**", timeout=15000)
            print(f"Redirected to novel: {page.url}")
        except Exception:
            print(f"Not on novel URL. Current URL: {page.url}")
            try:
                page.wait_for_url(f"{base_url}/dashboard**", timeout=5000)
                print(f"Redirected to dashboard: {page.url}")
            except Exception:
                print(f"NOT on dashboard either. Current URL: {page.url}")
                # Final screenshot showing where we ended up
                page.screenshot(path="/tmp/no-redirect-state.png")
                print("Screenshot saved to /tmp/no-redirect-state.png")

                # Check if we're still on /wizard
                if "/wizard" in page.url:
                    print("STILL ON /wizard — redirect did not happen!")
                    print(f"Page inner text (first 1000 chars): {page.inner_text('body')[:1000]}")

                    # Check if there's a loading/creating indicator still showing
                    creating = page.locator("text=Creating").first
                    if creating.is_visible():
                        print(
                            "  'Creating' indicator is still visible — API call may still be in progress"
                        )
                    loading = page.locator("text=Loading").first
                    if loading.is_visible():
                        print("  'Loading' indicator is still visible")

                    # Check for any toast/notification elements
                    toasts = page.locator('[role="alert"], .toast, [data-sonner-toast]')
                    if toasts.count() > 0:
                        for i in range(toasts.count()):
                            print(f"  Toast [{i}]: {toasts.nth(i).inner_text()}")

        # ===================================================================
        # Step 2.8 — If on dashboard, navigate to editor
        # ===================================================================
        if "/dashboard" in page.url:
            novel_card = page.locator(
                '[data-testid="novel-card"], a[href*="/novel/"], .novel-card'
            ).first
            novel_card.wait_for(state="visible", timeout=10000)
            novel_card.click()
            page.wait_for_url(f"{base_url}/novel/**", timeout=10000)

        # -------------------------------------------------------------------
        # Set up request logging BEFORE any editor interaction.
        # The actual endpoint is PUT /novels/{id}/chapters/{id}/content
        # (see packages/web/lib/api/client.ts → chaptersApi.updateContent)
        #
        # IMPORTANT: page.on("request") does NOT fire for requests intercepted
        # by page.route(). We must capture inside the route handlers themselves.
        # -------------------------------------------------------------------

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
        # Step 2.9 — Editor loads content, insert text via TipTap API, save
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
        # ProseMirror (TipTap's engine) attaches its EditorView to the DOM
        # element as `el.view`. We dispatch a transaction to insert content,
        # which properly fires TipTap's onUpdate → onChange → autosave chain.
        # -------------------------------------------------------------------
        test_text = f"E2E autosave test {uuid.uuid4().hex[:6]}"

        # Use ProseMirror's dispatch to insert content — this fires all
        # TipTap lifecycle hooks (onUpdate, onChange, autosave debounce).
        insert_result = page.evaluate(
            """
            (text) => {
                const el = document.querySelector('.ProseMirror');
                if (!el || !el.view) return 'no-prosemirror-view';

                const { view } = el;
                const { tr } = view.state;
                const { from, to } = view.state.selection;

                // Insert text at current cursor position
                tr.insertText(text, from, to);
                view.dispatch(tr);

                // Also scroll into view and focus to ensure visibility
                el.focus();
                return 'ok';
            }
            """,
            test_text,
        )
        assert insert_result == "ok", (
            f"Failed to insert text into editor: {insert_result}. "
            "ProseMirror view not found on .ProseMirror element."
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
        print(f"\n=== EDITOR CONTENT CHECK ===")
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _click_next(page: Page, expected_step: int | None = None) -> None:
    """Click the next/continue/submit button on the current wizard step.

    Args:
        page: Playwright page object.
        expected_step: If provided, verify the wizard advances to this step.
    """
    next_selectors = [
        'button:has-text("Next")',
        'button:has-text("Continue")',
        'button:has-text("Weiter")',
        'button[type="submit"]',
    ]
    clicked = False
    for selector in next_selectors:
        locator = page.locator(selector).first
        if locator.is_visible():
            btn_text = locator.inner_text()
            btn_type = locator.get_attribute("type") or "button"
            print(
                f"  _click_next: clicking selector='{selector}' text='{btn_text}' type='{btn_type}'"
            )
            locator.click()
            clicked = True
            break

    if not clicked:
        # Fallback: try the last button on the page
        buttons = page.locator("button")
        count = buttons.count()
        if count > 0:
            last_btn = buttons.last
            if last_btn.is_visible():
                print(
                    f"  _click_next: fallback clicking last button text='{last_btn.inner_text()}'"
                )
                last_btn.click()
                clicked = True

    # Wait for animation/transition
    page.wait_for_timeout(500)

    # Verify step advancement if expected_step provided
    if expected_step is not None and clicked:
        active_steps = page.locator('[aria-current="step"]')
        if active_steps.count() > 0:
            current_label = active_steps.first.inner_text()
            print(f"  _click_next: wizard now on step {current_label} (expected {expected_step})")
