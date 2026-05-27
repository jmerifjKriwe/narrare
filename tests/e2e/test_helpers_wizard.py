"""Wizard-related helpers for E2E tests.

Extracted from test_helpers.py to satisfy RULE-04 (file size limits).
Contains the wizard completion helper used by multiple E2E test modules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page


def _complete_wizard_to_editor(
    page: Page,
    base_url: str,
    register_unique_user,
    novel_title: str = "My Fantasy Novel",
) -> dict[str, str]:
    """Complete the setup wizard and arrive at the novel editor.

    Registers a fresh user, logs in via the login form, completes all 5
    wizard steps, and waits for the redirect to ``/novel/{id}``.

    Args:
        page: Playwright Page object.
        base_url: Frontend base URL (e.g. ``http://localhost:3000``).
        register_unique_user: Fixture that registers a fresh test user.
        novel_title: Title used for the wizard project name and novel title.
            Defaults to ``"My Fantasy Novel"``.

    Returns:
        dict with keys: email, password, access_token, novel_id

    Key implementation details (derived from the 4 test files that
    duplicate this pattern):
      - Uses ``page.inner_text("body").lower()`` for Step 4 text detection
        (more reliable than ``.bg-card.border`` which may not be rendered).
      - ``_click_next(page)`` is called **outside** the Step 4 if-block so
        the wizard always advances even if the text detection didn't match.
      - After the API key is filled, waits for the Next button to become
        enabled (the wizard disables it while ``model === ""``).
    """
    # Lazy imports to avoid circular dependency with test_helpers
    from tests.e2e.mocks.llm_responses import setup_llm_mocks
    from tests.e2e.test_helpers import (
        _click_next,
        _extract_novel_id_from_url,
        _wait_for_wizard_ready,
    )

    # Install LLM mocks BEFORE any interaction that could trigger LLM calls
    setup_llm_mocks(page)

    # Register user
    user = register_unique_user()
    email: str = user["email"]
    password: str = user["password"]
    access_token: str = user["access_token"]
    _skip_login: bool = user.get("skip_login", False)

    # Login via form if needed
    if not _skip_login:
        page.goto(f"{base_url}/login")
        page.wait_for_url("**/login", timeout=10000)

        email_input = page.locator("#login-email")
        email_input.wait_for(state="visible", timeout=10000)
        page.fill("#login-email", email)
        page.fill("#login-password", password)

        page.click('button[type="submit"]')
        page.wait_for_url(f"{base_url}/", timeout=15000)

    # Navigate to wizard
    page.goto(f"{base_url}/wizard")
    _wait_for_wizard_ready(page)

    # Step 1: Project name
    project_name_input = page.locator(
        'input[name="project_name"], input[id="project_name"], input[placeholder*="project" i]'
    ).first
    if project_name_input.is_visible():
        project_name_input.fill(novel_title)
    else:
        text_inputs = page.locator('input[type="text"]')
        if text_inputs.count() > 0:
            text_inputs.first.fill(novel_title)
    _click_next(page, expected_step=2)

    # Step 2: Genre — select Fantasy
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

    # Step 3: Title
    title_input = page.locator(
        'input[name="title"], input[id="title"], input[placeholder*="title" i]'
    ).first
    if title_input.is_visible():
        title_input.fill(novel_title)
    _click_next(page, expected_step=4)

    # Step 4: Provider setup
    page.wait_for_timeout(500)  # Let Step 4 render
    page_text = page.inner_text("body").lower()

    if "provider" in page_text or "openai" in page_text or "api key" in page_text:
        provider_btn = page.locator('button:has-text("OpenAI")').first
        if provider_btn.is_visible():
            provider_btn.click()

        api_key_input = page.locator(
            'input[name="api_key"], input[id="api_key"], input[type="password"]'
        ).first
        if api_key_input.is_visible():
            api_key_input.fill("sk-test-e2e-mock-key-not-real")

            # Wait for loadModels() to complete and auto-select a model.
            # The Next button is disabled while model === "" (WizardStep4.tsx
            # line 214: disabled={validating || !model}).  Without this wait
            # the click is silently swallowed by the browser.
            page.wait_for_function(
                "document.querySelector('[data-testid=\"wizard-next\"]')"
                " && !document.querySelector('[data-testid=\"wizard-next\"]').disabled",
                timeout=10000,
            )

    # ALWAYS click Next at Step 4, even if the text detection didn't match
    # (the wizard might already be past Step 4 due to hasProviders)
    _click_next(page)

    # Step 5: Wait for complete button, then click it
    page.locator('[data-testid="wizard-complete"]').first.wait_for(state="visible", timeout=15000)
    page.locator('[data-testid="wizard-complete"]').first.click()

    # Wait for redirect to the novel editor (may go to /novel/** or /dashboard)
    page.wait_for_url(
        lambda url: "/novel/" in url or "/dashboard" in url,
        timeout=15000,
    )

    # If redirected to dashboard instead of novel, navigate to the novel
    if "/novel/" not in page.url:
        page.wait_for_timeout(1000)
        novel_link = page.locator('a[href*="/novel/"]').first
        if novel_link.is_visible():
            novel_link.click()
            page.wait_for_url(lambda url: "/novel/" in url, timeout=15000)

    # Extract novel ID from the URL
    novel_id = _extract_novel_id_from_url(page)

    return {
        "email": email,
        "password": password,
        "access_token": access_token,
        "novel_id": novel_id,
    }
