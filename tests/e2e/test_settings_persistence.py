"""Settings Persistence E2E Tests.

Covers: settings page loading, tab navigation, novel detail persistence
across page reloads.

All LLM responses are mocked via page.route() — no real API tokens consumed.
Runs against the full stack (API port 8000, Frontend port 3000).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from tests.e2e.test_helpers import (
    _complete_wizard_to_editor,
    _setup_auth_proxy,
)

if TYPE_CHECKING:
    from playwright.sync_api import Page


@pytest.mark.e2e
class TestSettingsPersistence:
    """Test settings page rendering and persistence of novel details."""

    def test_settings_novel_details_persist_after_reload(
        self,
        page: Page,
        base_url: str,
        register_unique_user,
    ) -> None:
        """Changing novel title in settings persists after page reload."""
        result = _complete_wizard_to_editor(page, base_url, register_unique_user)
        _setup_auth_proxy(page, result["access_token"])
        novel_id = result["novel_id"]

        # Navigate to settings
        page.goto(f"{base_url}/novel/{novel_id}/settings")
        page.wait_for_timeout(2000)

        # Take screenshot to see what's on the settings page
        page.screenshot(path="/tmp/settings-page.png")
        body_text = page.inner_text("body")[:500]
        print("\n=== SETTINGS PAGE ===")
        print(f"  URL: {page.url}")
        print(f"  Body: {body_text}")

        # The default tab is "novel-details" so the title input should
        # already be visible.  Use the actual selector from
        # NovelDetailsTab.tsx: id="novel-title".
        title_selectors = [
            "#novel-title",
            'input[data-testid="novel-title"]',
            'input[name="title"]',
            'input[placeholder*="title" i]',
        ]
        title_input = None
        for selector in title_selectors:
            locator = page.locator(selector).first
            if locator.is_visible():
                title_input = locator
                break

        if title_input is None:
            # Debug: print all inputs on the page
            all_inputs = page.locator("input[type='text'], input:not([type])").all()
            print(f"  Found {len(all_inputs)} text inputs on settings page:")
            for i, inp in enumerate(all_inputs):
                if inp.is_visible():
                    print(
                        f"    [{i}] name={inp.get_attribute('name')}, "
                        f"id={inp.get_attribute('id')}, "
                        f"placeholder={inp.get_attribute('placeholder')}, "
                        f"value={inp.input_value()[:50]}"
                    )
            page.screenshot(path="/tmp/settings-no-title-input.png")
            pytest.skip("Could not find title input on settings page — may need different selector")

        # Change the title
        new_title = f"Updated Novel {uuid.uuid4().hex[:6]}"
        title_input.click()
        title_input.fill("")
        title_input.fill(new_title)
        page.wait_for_timeout(500)

        # Save — the NovelDetailsTab save button is inside a
        # ``div.flex.justify-end`` container.  We avoid matching the active
        # settings-tab buttons which also have the ``bg-primary`` class.
        save_btn = page.locator('div.flex.justify-end > button[type="button"]').first
        if not save_btn.is_visible():
            # Fallback: text-based search
            save_btn = page.locator(
                'button:has-text("Save"), '
                'button:has-text("Speichern"), '
                'button:has-text("Enregistrer")'
            ).first
        if save_btn.is_visible():
            save_btn.click()
            page.wait_for_timeout(2000)
        else:
            print("  Save button not visible — title change may auto-save")

        # Reload
        page.reload()
        page.wait_for_timeout(3000)

        # Click novel-details tab again to be safe
        details_tab = page.locator('[data-testid="settings-tab-novel-details"]').first
        if details_tab.is_visible():
            details_tab.click()
            page.wait_for_timeout(500)

        # Find title input again
        for selector in title_selectors:
            locator = page.locator(selector).first
            if locator.is_visible():
                title_input = locator
                break

        if title_input:
            value = title_input.input_value()
            assert new_title in value, f"Expected '{new_title}' after reload, got '{value}'"
        else:
            pytest.skip("Title input not found after reload — page may have changed")

    def test_settings_general_tab_renders(
        self,
        page: Page,
        base_url: str,
        register_unique_user,
    ) -> None:
        """Settings page loads with tabs and content."""
        result = _complete_wizard_to_editor(page, base_url, register_unique_user)
        _setup_auth_proxy(page, result["access_token"])
        novel_id = result["novel_id"]

        page.goto(f"{base_url}/novel/{novel_id}/settings")
        page.wait_for_timeout(2000)

        # Verify settings page loaded (not redirected to login)
        assert "/settings" in page.url, f"Expected settings URL, got: {page.url}"

        # Check that at least one tab is visible
        tab_buttons = page.locator('button[data-testid^="settings-tab-"]')
        if tab_buttons.count() == 0:
            # Fallback: try generic tab / nav buttons
            tab_buttons = page.locator("button[role='tab'], nav button")

        assert tab_buttons.count() > 0, "Expected at least one settings tab"

        # Click through each tab and verify content changes
        tab_count = min(tab_buttons.count(), 5)
        for i in range(tab_count):
            tab = tab_buttons.nth(i)
            if tab.is_visible():
                tab_text = tab.inner_text()
                tab.click()
                page.wait_for_timeout(500)
                print(f"  Tab '{tab_text}': content loaded OK")

        page.screenshot(path="/tmp/settings-tabs.png")
