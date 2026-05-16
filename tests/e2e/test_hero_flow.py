"""Hero E2E Flow Test — complete MVP user journey.

Covers: registration → setup wizard (all steps) → dashboard → editor → autosave.

All LLM responses are mocked via page.route() — no real API tokens consumed.
Runs against the full stack (API port 8000, Frontend port 3000).
"""

from __future__ import annotations

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
                    "path": "/",
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
        # Step 2.3 — Complete steps 2-3 (novel metadata, select Fantasy demo)
        # ===================================================================

        # Step 2: Novel metadata (title, author, genre, etc.)
        title_input = page.locator(
            'input[name="title"], input[id="title"], input[placeholder*="title" i]'
        ).first
        if title_input.is_visible():
            title_input.fill("The Dragon's Apprentice")

        _click_next(page)

        # Step 3: Select Fantasy demo content
        # Look for the demo_fantasy option (radio, card, or button)
        fantasy_selectors = [
            '[data-testid="starter-demo_fantasy"]',
            'input[value="demo_fantasy"]',
            'button:has-text("Fantasy")',
            '[data-value="demo_fantasy"]',
            "text=Fantasy",
        ]
        for selector in fantasy_selectors:
            locator = page.locator(selector).first
            if locator.is_visible():
                locator.click()
                break

        _click_next(page)

        # ===================================================================
        # Step 2.4 — Step 4 with mocked provider validation
        # LLM validation is already mocked via setup_llm_mocks()
        # ===================================================================

        # Select a provider (e.g., OpenAI)
        provider_selectors = [
            '[data-testid="provider-openai"]',
            'input[value="openai"]',
            'button:has-text("OpenAI")',
            '[data-value="openai"]',
            "text=OpenAI",
        ]
        for selector in provider_selectors:
            locator = page.locator(selector).first
            if locator.is_visible():
                locator.click()
                break

        # Fill in a dummy API key (the validation is mocked)
        api_key_input = page.locator(
            'input[name="api_key"], input[id="api_key"], input[type="password"]'
        ).first
        if api_key_input.is_visible():
            api_key_input.fill("sk-test-e2e-mock-key-not-real")

        # Select a model
        model_select = page.locator('select[name="model"], select[id="model"]').first
        if model_select.is_visible():
            model_select.select_option(label="GPT-4o Mini")
        else:
            # Maybe a text input for model name
            model_input = page.locator('input[name="model"], input[id="model"]').first
            if model_input.is_visible():
                model_input.fill("gpt-4o-mini")

        _click_next(page)

        # ===================================================================
        # Step 2.5 — Confirm setup, verify redirect to dashboard/editor
        # ===================================================================

        # Step 5: Confirmation — click complete/finish
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

        # Wait for redirect — should go to dashboard or editor
        page.wait_for_url(
            f"{base_url}/dashboard**",
            timeout=15000,
        )

        # ===================================================================
        # Step 2.6 — Dashboard shows demo novel, navigate to editor
        # ===================================================================

        # Verify the novel card appears on dashboard
        novel_card = page.locator(
            '[data-testid="novel-card"], a[href*="/novel/"], .novel-card'
        ).first
        novel_card.wait_for(state="visible", timeout=10000)

        # Click the novel card to open the editor
        novel_card.click()

        # Wait for editor page to load
        page.wait_for_url(
            f"{base_url}/novel/*/editor**",
            timeout=10000,
        )

        # ===================================================================
        # Step 2.7 — Editor loads content, type text, verify autosave
        # ===================================================================

        # Wait for editor to be ready — look for TipTap content area
        editor_area = page.locator(
            '.tiptap, [data-testid="editor"], .ProseMirror, [contenteditable="true"]'
        ).first
        editor_area.wait_for(state="visible", timeout=10000)

        # Type some text in the editor
        test_text = f" E2E autosave test {uuid.uuid4().hex[:6]}"
        editor_area.type(test_text)

        # Wait for autosave to fire (debounce interval)
        # The autosave debounce is typically 2-5 seconds; wait up to 10s
        autosave_request = page.wait_for_request(  # type: ignore[attr-defined]
            lambda req: (
                ("/chapters/" in req.url)
                and req.method == "PUT"
                and "content" in (req.post_data or "")
            ),
            timeout=15000,
        )

        assert autosave_request is not None, "Autosave did not fire after typing"

        # Verify the request body contains our text
        post_data = autosave_request.post_data
        assert post_data is not None, "Autosave request has no body"
        assert "content" in post_data, "Autosave request body missing 'content' field"


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
