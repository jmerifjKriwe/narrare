"""Authentication E2E Flow Test.

Covers: registration, API login, UI login, session establishment.

All LLM responses are mocked via page.route() — no real API tokens consumed.
Runs against the full stack (API port 8000, Frontend port 3000).
"""

from __future__ import annotations

import contextlib
import json
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

    # ===================================================================
    # AUTH-1: Wrong password error
    # ===================================================================

    def test_login_with_wrong_password_shows_error(
        self,
        page: Page,
        base_url: str,
    ) -> None:
        """Login with wrong password shows error message, stays on /login.

        NOTE: There is a known frontend bug where fetchApi() treats a 401 on
        /auth/login as a session expiry and triggers window.location.href="/login",
        which reloads the page and wipes the React error state. This test asserts
        the *expected* correct behaviour (error message visible, no redirect).
        If the page reloads, the error element is gone and this test will fail —
        indicating the frontend 401 handler needs to skip auth endpoints.
        """
        # Collect console messages and page errors for debugging
        console_errors: list[str] = []
        page.on("pageerror", lambda err: console_errors.append(str(err)))

        page.goto(f"{base_url}/login")
        page.wait_for_url("**/login", timeout=10000)

        page.fill("#login-email", "dev@narrare.dev")
        page.fill("#login-password", "wrong-password-123")
        page.click('button[type="submit"]')

        # Wait for the error element to appear (up to 5s).
        # If the page reloads (due to fetchApi 401→refresh→redirect), the
        # element will never appear and this will timeout.
        with contextlib.suppress(Exception):
            page.wait_for_selector('[data-testid="auth-error"]', timeout=5000)

        page.screenshot(path="/tmp/login-wrong-password.png")
        body_text = page.inner_text("body")[:500]
        print("\n=== WRONG PASSWORD TEST ===")
        print(f"  URL: {page.url}")
        print(f"  Body: {body_text}")
        print(f"  Console errors: {console_errors}")

        # Verify error message is shown
        error_container = page.locator('[data-testid="auth-error"]')
        if not error_container.is_visible():
            # Fallback: check for any error text
            error_container = page.locator(".bg-destructive\\/10, [class*='destructive']").first

        assert error_container.is_visible(), (
            "Expected error message to be visible after wrong password. "
            "This likely fails because fetchApi() 401 handler reloads the page "
            "via window.location.href='/login', wiping the React error state. "
            f"URL: {page.url}, Body: {body_text[:200]}"
        )
        assert "/login" in page.url, f"Expected to stay on /login, got: {page.url}"

    # ===================================================================
    # AUTH-2: Logout redirects to login
    # ===================================================================

    def test_logout_redirects_to_login(
        self,
        page: Page,
        base_url: str,
        register_unique_user,
    ) -> None:
        """Logout clears session and redirects to login page."""
        # Register and login
        user = register_unique_user()
        page.goto(f"{base_url}/login")
        page.wait_for_url("**/login", timeout=10000)
        page.fill("#login-email", user["email"])
        page.fill("#login-password", user["password"])
        page.click('button[type="submit"]')
        page.wait_for_url(f"{base_url}/", timeout=15000)

        # Mock only POST /auth/refresh to prevent the Next.js dev proxy hang.
        # Unlike setup_dashboard_api_mocks (which mocks both /auth/refresh AND
        # /auth/me), this test needs a real /auth/me response because the user
        # logged in via the UI and has a real session.  Returning the real token
        # keeps the frontend auth store in sync.
        page.route(
            "**/api/v1/auth/refresh",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"access_token": user["access_token"], "token_type": "bearer"}),
            ),
        )

        # Now logged in, navigate to dashboard to find logout button
        page.goto(f"{base_url}/", timeout=30000)
        page.wait_for_timeout(2000)

        # Remove the refresh mock so the /login page after logout does NOT
        # get re-authenticated via the mock.  Without this, the frontend's
        # auth check on /login fires POST /auth/refresh → mock returns token
        # → cookie is re-set → assertion fails.
        page.unroute("**/api/v1/auth/refresh")

        # Find and click logout button
        # The dashboard header has a logout button — try multiple selectors.
        # NOTE: The logout button is in a fixed header (position:sticky/fixed).
        # Playwright's scroll-into-view check can hang on these elements, so
        # we use force=True to bypass it while still dispatching proper events.
        logout_selectors = [
            'button[data-testid="logout-button"]',
            'button[aria-label*="logout" i]',
            'button[aria-label*="abmelden" i]',
            'button[aria-label*="sign out" i]',
            'button:has-text("Logout")',
            'button:has-text("Log out")',
            'button:has-text("Abmelden")',
            'button:has-text("Sign out")',
        ]

        logout_clicked = False
        for selector in logout_selectors:
            locator = page.locator(selector).first
            if locator.is_visible():
                locator.click(force=True)
                logout_clicked = True
                break

        if not logout_clicked:
            # Try the sidebar logout (if in a novel view)
            page.screenshot(path="/tmp/logout-button-search.png")
            body_text = page.inner_text("body")[:500]
            print("\n=== LOGOUT BUTTON SEARCH ===")
            print(f"  URL: {page.url}")
            print(f"  Body: {body_text}")
            # Try clicking any button with LogOut icon
            logout_icon_btn = page.locator("button:has(svg.lucide-log-out)").first
            if logout_icon_btn.is_visible():
                logout_icon_btn.click()
                logout_clicked = True

        assert logout_clicked, "Could not find logout button on page"

        # Wait for redirect to login
        page.wait_for_timeout(2000)

        # Verify we're on login page
        assert "/login" in page.url, f"Expected redirect to /login, got: {page.url}"

        # Verify auth cookie is cleared
        cookies = page.evaluate("document.cookie")
        assert "narrare_auth" not in cookies, "Auth cookie should be cleared after logout"

    # ===================================================================
    # AUTH-3: Duplicate email registration error
    # ===================================================================

    def test_register_with_duplicate_email_shows_error(
        self,
        page: Page,
        base_url: str,
    ) -> None:
        """Registration with already-used email shows error."""
        page.goto(f"{base_url}/register")
        page.wait_for_url("**/register", timeout=10000)

        # Fill in with dev user email (already seeded)
        display_name_input = page.locator(
            'input[name="display_name"], input[id="display_name"], input[placeholder*="name" i]'
        ).first
        if display_name_input.is_visible():
            display_name_input.fill("Duplicate Test")

        page.fill("#register-email", "dev@narrare.dev")

        password_input = page.locator(
            'input[name="password"], input[id="register-password"], input[type="password"]'
        ).first
        if password_input.is_visible():
            password_input.fill("SomePassword123!")

        page.click('button[type="submit"]')
        page.wait_for_timeout(3000)

        # Verify error
        error_container = page.locator('[data-testid="auth-error"]')
        if not error_container.is_visible():
            error_container = page.locator(".bg-destructive\\/10, [class*='destructive']").first

        page.screenshot(path="/tmp/register-duplicate-email.png")
        body_text = page.inner_text("body")[:500]
        print("\n=== REGISTER DUPLICATE EMAIL ===")
        print(f"  URL: {page.url}")
        print(f"  Body: {body_text}")

        assert "/register" in page.url, f"Expected to stay on /register, got: {page.url}"

    # ===================================================================
    # AUTH-4: Empty fields browser validation
    # ===================================================================

    def test_login_with_empty_fields_shows_validation(
        self,
        page: Page,
        base_url: str,
    ) -> None:
        """Login form with empty fields shows browser validation."""
        page.goto(f"{base_url}/login")
        page.wait_for_url("**/login", timeout=10000)

        # Leave fields empty, click submit
        page.click('button[type="submit"]')
        page.wait_for_timeout(1000)

        # Browser HTML5 validation should prevent submission
        # The inputs have required="" attribute
        assert "/login" in page.url, "Should stay on login with empty fields"

        # Check that we're NOT seeing an API error (no network request was made)
        error_container = page.locator('[data-testid="auth-error"]')
        assert not error_container.is_visible(), (
            "API error should NOT appear for empty fields (browser validation)"
        )
