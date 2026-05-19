"""Setup Wizard E2E Flow Test.

Covers: complete wizard flow including project setup, genre selection, metadata, and provider setup.

All LLM responses are mocked via page.route() — no real API tokens consumed.
Runs against the full stack (API port 8000, Frontend port 3000).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.e2e.mocks.llm_responses import setup_llm_mocks
from tests.e2e.test_helpers import _click_next

if TYPE_CHECKING:
    from playwright.sync_api import Page


@pytest.mark.e2e
class TestSetupWizard:
    """Test setup wizard flow including all steps."""

    def _setup_wizard_prerequisites(
        self,
        page: Page,
        base_url: str,
        register_unique_user,
    ) -> None:
        """Shared setup method: register user, login, and navigate to wizard."""
        # Install LLM mocks BEFORE any interaction that could trigger LLM calls
        setup_llm_mocks(page)

        # Register and login user
        user = register_unique_user()
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
        page.wait_for_timeout(1000)

    def test_wizard_step_1_project_setup(
        self,
        page: Page,
        base_url: str,
        register_unique_user,
    ) -> None:
        """Test wizard step 1: Project name, language, autosave interval."""
        self._setup_wizard_prerequisites(page, base_url, register_unique_user)

        # Step 1: Project name, language, autosave interval
        project_name_input = page.locator(
            'input[name="project_name"], input[id="project_name"], input[placeholder*="project" i]'
        ).first
        if project_name_input.is_visible():
            project_name_input.fill("My Fantasy Novel")
        else:
            text_inputs = page.locator('input[type="text"]')
            if text_inputs.count() > 0:
                text_inputs.first.fill("My Fantasy Novel")

        # Click next/continue button for step 1
        _click_next(page, expected_step=2)

    def test_wizard_step_2_genre_selection(
        self,
        page: Page,
        base_url: str,
        register_unique_user,
    ) -> None:
        """Test wizard step 2: Genre selection (fantasy)."""
        self._setup_wizard_prerequisites(page, base_url, register_unique_user)

        # Complete step 1 first
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

        # Step 2: Genre selection (fantasy)
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

    def test_wizard_step_3_metadata(
        self,
        page: Page,
        base_url: str,
        register_unique_user,
    ) -> None:
        """Test wizard step 3: Novel metadata (title, author, genre)."""
        self._setup_wizard_prerequisites(page, base_url, register_unique_user)

        # Complete steps 1-2
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

        # Step 3: Novel metadata
        title_input = page.locator(
            'input[name="title"], input[id="title"], input[placeholder*="title" i]'
        ).first
        if title_input.is_visible():
            title_input.fill("The Dragon's Apprentice")

        _click_next(page, expected_step=4)

    def test_wizard_step_4_provider_setup(
        self,
        page: Page,
        base_url: str,
        register_unique_user,
    ) -> None:
        """Test wizard step 4: Provider setup (OpenAI)."""
        self._setup_wizard_prerequisites(page, base_url, register_unique_user)

        # Complete steps 1-3
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

        title_input = page.locator(
            'input[name="title"], input[id="title"], input[placeholder*="title" i]'
        ).first
        if title_input.is_visible():
            title_input.fill("The Dragon's Apprentice")

        _click_next(page, expected_step=4)

        # Step 4: Provider setup
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
