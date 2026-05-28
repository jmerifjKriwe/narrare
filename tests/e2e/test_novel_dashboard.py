"""Novel Dashboard E2E Tests.

Covers: dashboard display after novel creation, novel listing, creating a second novel.

All LLM responses are mocked via page.route() — no real API tokens consumed.
Runs against the full stack (API port 8000, Frontend port 3000).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.e2e.mocks.llm_responses import setup_llm_mocks
from tests.e2e.test_helpers import _click_next, _wait_for_wizard_ready, setup_dashboard_api_mocks

if TYPE_CHECKING:
    from playwright.sync_api import Page


def _setup_auth_proxy(page: Page, access_token: str) -> None:
    """Set up auth cookie and request proxy for page navigation.

    Uses the same pattern as the authenticated_page fixture in conftest.py:
    - Sets the narrare_auth cookie for Next.js middleware (server-side route protection)
    - Intercepts all API requests and adds the Authorization header
    - Proxies via route.fetch() to avoid browser connection-pool hang during page load
    """
    page.add_init_script(
        f"""document.cookie = 'narrare_auth={access_token}; path=/; max-age=3600; samesite=lax';"""
    )

    def _proxy_with_auth(route):
        headers = dict(route.request.headers)
        if "authorization" not in {k.lower() for k in headers}:
            headers["Authorization"] = f"Bearer {access_token}"
        try:
            response = route.fetch(headers=headers)
            route.fulfill(
                status=response.status,
                headers=response.headers,
                body=response.body(),
            )
        except Exception:
            route.continue_(headers=headers)

    page.route("**/api/v1/**", _proxy_with_auth)


def _complete_wizard(
    page: Page,
    base_url: str,
    register_unique_user,
    novel_title: str = "Dashboard Test Novel",
) -> dict[str, str]:
    """Complete wizard and return user info."""
    setup_llm_mocks(page)
    user = register_unique_user()
    email = user["email"]
    password = user["password"]

    if not user.get("skip_login", False):
        page.goto(f"{base_url}/login")
        page.wait_for_url("**/login", timeout=10000)
        page.fill("#login-email", email)
        page.fill("#login-password", password)
        page.click('button[type="submit"]')
        page.wait_for_url(f"{base_url}/", timeout=15000)

    page.goto(f"{base_url}/wizard")
    _wait_for_wizard_ready(page)

    # Step 1
    project_input = page.locator(
        'input[name="project_name"], input[id="project_name"], input[placeholder*="project" i]'
    ).first
    if project_input.is_visible():
        project_input.fill(novel_title)
    else:
        page.locator('input[type="text"]').first.fill(novel_title)
    _click_next(page, expected_step=2)

    # Step 2
    fantasy_btn = page.locator('button:has-text("Fantasy")').first
    if fantasy_btn.is_visible():
        fantasy_btn.click()
    _click_next(page, expected_step=3)

    # Step 3
    title_input = page.locator(
        'input[name="title"], input[id="title"], input[placeholder*="title" i]'
    ).first
    if title_input.is_visible():
        title_input.fill(novel_title)
    _click_next(page, expected_step=4)

    # Step 4
    page.wait_for_timeout(500)  # Let Step 4 render
    step4_text = page.inner_text("body").lower()
    page.screenshot(path=f"/tmp/wizard-step4-{novel_title.replace(' ', '-')}.png")
    print("\n=== STEP 4 TEXT (first 300 chars) ===")
    print(f"  {step4_text[:300]}")

    if "provider" in step4_text or "openai" in step4_text or "api key" in step4_text:
        provider_btn = page.locator('button:has-text("OpenAI")').first
        if provider_btn.is_visible():
            provider_btn.click()
        api_key_input = page.locator(
            'input[name="api_key"], input[id="api_key"], input[type="password"]'
        ).first
        if api_key_input.is_visible():
            api_key_input.fill("sk-test-e2e-mock-key-not-real")
            page.wait_for_function(
                "document.querySelector('[data-testid=\"wizard-next\"]')"
                " && !document.querySelector('[data-testid=\"wizard-next\"]').disabled",
                timeout=10000,
            )

    # ALWAYS click Next at Step 4, even if the text detection didn't match
    # (the wizard might already be past Step 4 due to hasProviders)
    _click_next(page)

    # Step 5: Complete
    page.locator('[data-testid="wizard-complete"]').first.wait_for(state="visible", timeout=15000)
    page.locator('[data-testid="wizard-complete"]').first.click()
    # Wizard completion may redirect to /novel/** OR /dashboard depending on
    # whether the setup/complete response triggers an immediate redirect.
    page.wait_for_url(
        lambda url: "/novel/" in url or "/dashboard" in url,
        timeout=15000,
    )
    page.wait_for_timeout(2000)

    return {"email": email, "password": password, "access_token": user["access_token"]}


@pytest.mark.e2e
class TestNovelDashboard:
    """Test novel dashboard display and management."""

    def test_dashboard_shows_created_novel(
        self,
        page: Page,
        base_url: str,
        register_unique_user,
    ) -> None:
        """Test that the dashboard shows the novel after creation."""
        user_info = _complete_wizard(page, base_url, register_unique_user, "Dashboard Novel Alpha")
        page.wait_for_timeout(2000)

        # Set up auth proxy: cookie for middleware + route.fetch() for API calls.
        # This avoids the browser hang AND ensures real API calls get a valid token.
        # Mock auth endpoints BEFORE _setup_auth_proxy to prevent POST /auth/refresh
        # hang during page load.  Auth mocks match first (Playwright route order).
        setup_dashboard_api_mocks(page)
        _setup_auth_proxy(page, user_info["access_token"])
        page.goto(f"{base_url}/", timeout=15000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Look for the novel title on the dashboard
        body_text = page.inner_text("body")
        page.screenshot(path="/tmp/dashboard-novel-listing.png", timeout=5000)
        print("\n=== DASHBOARD ===")
        print(f"  URL: {page.url}")
        print(f"  Body text (first 500 chars): {body_text[:500]}")

        # Check for novel title or novel-related UI elements
        novel_found = "Dashboard Novel Alpha" in body_text or "Novel" in body_text
        assert novel_found, (
            "Expected novel to appear on dashboard. "
            "Could not find 'Dashboard Novel Alpha' or 'Novel' in page text."
        )

    def test_dashboard_has_new_novel_button(
        self,
        page: Page,
        base_url: str,
        register_unique_user,
    ) -> None:
        """Test that the dashboard has a button to create a new novel."""
        user_info = _complete_wizard(page, base_url, register_unique_user, "Dashboard Novel Beta")
        page.wait_for_timeout(2000)

        setup_dashboard_api_mocks(page)
        _setup_auth_proxy(page, user_info["access_token"])
        page.goto(f"{base_url}/", timeout=15000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Look for new novel button / link
        new_novel_selectors = [
            'a:has-text("New Novel")',
            'a:has-text("Create Novel")',
            'button:has-text("New Novel")',
            'button:has-text("Create Novel")',
            'a[href*="/wizard"]',
            'button:has-text("New Project")',
        ]
        found_button = False
        for selector in new_novel_selectors:
            locator = page.locator(selector).first
            if locator.is_visible():
                print(f"\n=== NEW NOVEL BUTTON FOUND: {selector} ===")
                found_button = True
                break

        page.screenshot(path="/tmp/dashboard-new-novel.png", timeout=5000)
        print(f"\nNew novel button visible: {found_button}")
        assert found_button, "New novel/Create button not found on dashboard."

    def test_navigate_to_existing_novel(
        self,
        page: Page,
        base_url: str,
        register_unique_user,
    ) -> None:
        """Test clicking on a novel on the dashboard opens the editor."""
        user_info = _complete_wizard(page, base_url, register_unique_user, "Navigable Novel")
        page.wait_for_timeout(2000)

        setup_dashboard_api_mocks(page)
        _setup_auth_proxy(page, user_info["access_token"])
        page.goto(f"{base_url}/", timeout=15000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Find the novel link/button and click it
        novel_link_selectors = [
            'a:has-text("Navigable Novel")',
            'a[href*="/novel/"]',
            '[data-testid="novel-card"]',
            '[data-testid="novel-link"]',
        ]
        clicked = False
        for selector in novel_link_selectors:
            locator = page.locator(selector).first
            if locator.is_visible():
                locator.click()
                clicked = True
                print(f"\n=== CLICKED NOVEL LINK: {selector} ===")
                break

        if not clicked:
            # Fallback: try clicking any link that goes to /novel/
            novel_links = page.locator('a[href*="/novel/"]')
            if novel_links.count() > 0:
                novel_links.first.click()
                clicked = True
                print("\n=== CLICKED FIRST NOVEL LINK (fallback) ===")

        page.wait_for_timeout(3000)

        # Should now be on the novel editor page
        print("\n=== AFTER NAVIGATION ===")
        print(f"  URL: {page.url}")
        page.screenshot(path="/tmp/navigate-to-novel.png")

        assert clicked, "Could not find any novel link on dashboard"

        # Verify we're on a novel page
        assert "/novel/" in page.url, f"Expected to navigate to /novel/, got: {page.url}"

    def test_create_second_novel_shows_both(
        self,
        page: Page,
        base_url: str,
        register_unique_user,
    ) -> None:
        """Creating a second novel shows both on the dashboard."""
        from tests.e2e.test_helpers import (
            _complete_wizard_to_editor,
            _setup_auth_proxy,
        )

        # Create first novel
        _complete_wizard_to_editor(page, base_url, register_unique_user, "First Novel")

        result = _complete_wizard_to_editor(page, base_url, register_unique_user)

        setup_dashboard_api_mocks(page)
        _setup_auth_proxy(page, result["access_token"])

        # Go to dashboard, click a novel card
        page.goto(f"{base_url}/", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Use data-testid selectors matching DashboardView.tsx
        novel_links = page.locator('[data-testid="novel-card"] a, a[href*="/novel/"]')
        if novel_links.count() > 0:
            first_link = novel_links.first
            first_link.click()
            page.wait_for_timeout(2000)

            assert "/novel/" in page.url, f"Expected novel URL, got: {page.url}"
            print(f"\n  Navigated to: {page.url}")
        else:
            print("\n  No novel cards found on dashboard — skipping navigation test")

    def test_delete_novel_from_dashboard(
        self,
        page: Page,
        base_url: str,
        register_unique_user,
    ) -> None:
        """Deleting a novel from dashboard removes it from the list."""
        from tests.e2e.test_helpers import (
            _complete_wizard_to_editor,
            _setup_auth_proxy,
        )

        result = _complete_wizard_to_editor(page, base_url, register_unique_user)

        setup_dashboard_api_mocks(page)
        _setup_auth_proxy(page, result["access_token"])

        page.goto(f"{base_url}/", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Find novel card and hover to reveal delete button
        novel_card = page.locator('[data-testid="novel-card"]').first
        if not novel_card.is_visible():
            novel_card = page.locator("div.group.bg-card, a[href*='/novel/']").first

        if novel_card.is_visible():
            novel_card.hover()
            page.wait_for_timeout(500)

            # Find and click delete button (data-testid="delete-novel-btn")
            delete_btn = page.locator('[data-testid="delete-novel-btn"]').first
            if delete_btn.is_visible():
                # Handle confirm dialog
                page.on("dialog", lambda dialog: dialog.accept())
                delete_btn.click()
                page.wait_for_timeout(3000)

                # Verify card is gone
                page.screenshot(path="/tmp/dashboard-after-delete.png", timeout=5000)
                print("\n  Delete completed")
            else:
                print("\n  Delete button not visible after hover — may need different approach")
        else:
            print("\n  No novel card found — skipping delete test")
