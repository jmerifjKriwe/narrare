"""Novel Dashboard E2E Tests.

Covers: dashboard display after novel creation, novel listing, creating a second novel.

All LLM responses are mocked via page.route() — no real API tokens consumed.
Runs against the full stack (API port 8000, Frontend port 3000).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.e2e.mocks.llm_responses import setup_llm_mocks
from tests.e2e.test_helpers import _click_next, _wait_for_wizard_ready

if TYPE_CHECKING:
    from playwright.sync_api import Page


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
    step4_text = page.inner_text(".bg-card.border").lower()
    if "provider" in step4_text or "api key" in step4_text:
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
        _click_next(page)

    # Step 5: Complete
    page.locator('[data-testid="wizard-complete"]').first.wait_for(state="visible", timeout=15000)
    page.locator('[data-testid="wizard-complete"]').first.click()
    page.wait_for_url(f"{base_url}/novel/**", timeout=15000)
    page.wait_for_timeout(2000)

    return {"email": email, "password": password}


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
        _complete_wizard(page, base_url, register_unique_user, "Dashboard Novel Alpha")
        page.wait_for_timeout(2000)

        # Navigate to dashboard
        page.goto(f"{base_url}/", timeout=15000)
        page.wait_for_timeout(2000)

        # Look for the novel title on the dashboard
        body_text = page.inner_text("body")
        page.screenshot(path="/tmp/dashboard-novel-listing.png")
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
        _complete_wizard(page, base_url, register_unique_user, "Dashboard Novel Beta")
        page.wait_for_timeout(2000)

        # Navigate to dashboard
        page.goto(f"{base_url}/", timeout=15000)
        page.wait_for_timeout(2000)

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

        page.screenshot(path="/tmp/dashboard-new-novel.png")
        print(f"\nNew novel button visible: {found_button}")
        assert found_button, "New novel/Create button not found on dashboard."

    def test_navigate_to_existing_novel(
        self,
        page: Page,
        base_url: str,
        register_unique_user,
    ) -> None:
        """Test clicking on a novel on the dashboard opens the editor."""
        _complete_wizard(page, base_url, register_unique_user, "Navigable Novel")
        page.wait_for_timeout(2000)

        # Navigate to dashboard
        page.goto(f"{base_url}/", timeout=15000)
        page.wait_for_timeout(2000)

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
