"""Authentication E2E Flow Test.

Covers: registration, API login, UI login, session establishment.

All LLM responses are mocked via page.route() — no real API tokens consumed.
Runs against the full stack (API port 8000, Frontend port 3000).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.e2e.mocks.llm_responses import setup_llm_mocks

if TYPE_CHECKING:
    from playwright.sync_api import Page

# E2E tests are enabled - run with: pytest tests/e2e/ -m e2e


@pytest.mark.e2e
class TestAuthFlow:
    """Test authentication flow including registration and UI login."""

    def test_complete_user_registration_and_login(
        self,
        page: Page,
        base_url: str,
        api_url: str,
        register_unique_user,
    ) -> None:
        """Complete user journey: signup → UI login → session establishment."""
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
        page.wait_for_url("**/login", timeout=10000)

        # --- Debug: verify we actually landed on the login page ---
        current_url = page.url
        page_title = page.title()
        print("\n=== LOGIN PAGE DEBUG ===")
        print(f"  Navigated to: {base_url}/login")
        print(f"  Current URL:  {current_url}")
        print(f"  Page title:   {page_title}")

        # Take a screenshot to see what the browser actually rendered
        page.screenshot(path="/tmp/login-page-state.png")
        print("  Screenshot saved to /tmp/login-page-state.png")

        # Check if we were redirected away from /login (e.g. already logged in)
        if "/login" not in current_url:
            print(f"  NOT on /login — redirected to {current_url}")
            print("  Likely already authenticated. Skipping UI login.")
            # We're already on a post-auth page (dashboard or similar).
            # Proceed to the wizard without attempting login.
            _skip_login = True
        else:
            _skip_login = False

            # Explicitly wait for the login form to be visible.
            # page.fill() has its own auto-wait, but an explicit wait gives
            # a clearer error message if the form never appears.
            email_input = page.locator("#login-email")
            email_input.wait_for(state="visible", timeout=10000)

            # Fill credentials using the known input IDs from the login page
            page.fill("#login-email", email)
            page.fill("#login-password", password)

            # Click the login submit button and wait for the async form submission.
            # The login page calls authStore.login() (async API call), then
            # router.push("/") on success. The root page "/" IS the dashboard —
            # there is no /dashboard route. New users see the empty dashboard
            # with a "New Novel" button that leads to /wizard.
            # Click submit and wait for redirect to "/" (dashboard).
            # The login component does router.push("/") after successful login.
            # We don't wait for the API response because Next.js rewrites proxy
            # the request server-side, making expect_response unreliable.
            page.click('button[type="submit"]')
            page.wait_for_url(f"{base_url}/", timeout=15000)
            print(f"Login redirect successful. Current URL: {page.url}")

            # Verify the dashboard actually loaded (not a redirect back to /login).
            # The DashboardView shows a loading spinner first, then either:
            # - the dashboard title (novels loaded)
            # - the empty state (no novels yet)
            # - or redirects back to /login if authApi.me() fails
            page.wait_for_timeout(1000)  # Kurz warten bis UI stabil
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
                    f"Page text: {page_text[:500]}"
                )

        # Session is now established — no return needed (pytest tests must return None)
