"""Helper functions for E2E tests.

Shared utilities used across multiple E2E test modules to avoid code duplication.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from tests.e2e.test_helpers_wizard import (  # re-export for backward compat
    _complete_wizard_to_editor as _complete_wizard_to_editor,
)

if TYPE_CHECKING:
    from playwright.sync_api import Page


# narrare: allow reason="function is exported for use by other e2e test modules"
def _click_next(page: Page, expected_step: int | None = None) -> None:
    """Click the Next/Continue button in the setup wizard.

    Uses data-testid selectors for reliability. Waits for the button
    to be ready before clicking. Takes debug screenshot on timeout.

    Args:
        page: Playwright Page object
        expected_step: Optional step number to verify after clicking
    """
    # Primary: use data-testid selector
    next_button = page.locator('[data-testid="wizard-next"]').first
    try:
        next_button.wait_for(state="visible", timeout=10000)
        next_button.click()
    except Exception:
        # Fallback: try legacy text-based selectors
        fallback_selectors = [
            'button:has-text("Next")',
            'button:has-text("Continue")',
            'button[type="submit"]:has-text("Next")',
        ]
        clicked = False
        for selector in fallback_selectors:
            try:
                locator = page.locator(selector).first
                if locator.is_visible():
                    locator.click()
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            # Debug: take screenshot and print page state
            page.screenshot(path="/tmp/e2e-click-next-failure.png")
            body_text = page.inner_text("body")[:500]
            print("\n=== _click_next FAILURE DEBUG ===")
            print(f"  URL: {page.url}")
            print(f"  Body text (first 500): {body_text}")
            page.locator("form button").last.click()

    # If expected_step is provided, wait for the step indicator
    if expected_step is not None:
        step_selector = f'[data-testid="wizard-step-{expected_step}"]'
        try:
            page.locator(step_selector).first.wait_for(state="visible", timeout=15000)
        except Exception:
            # Fallback to aria-current selector for backwards compat
            page.screenshot(path=f"/tmp/e2e-step-{expected_step}-timeout.png")
            body_text = page.inner_text("body")[:500]
            active_steps = page.locator('[aria-current="step"]')
            active_text = active_steps.first.inner_text() if active_steps.count() > 0 else "none"
            print("\n=== STEP TRANSITION TIMEOUT ===")
            print(f"  Expected step: {expected_step}")
            print(f"  Current active step text: {active_text}")
            print(f"  URL: {page.url}")
            print(f"  Body text (first 500): {body_text}")
            raise


def _wait_for_wizard_ready(page: Page, timeout: int = 15000) -> None:
    """Wait for the wizard to fully load (step 1 indicator visible)."""
    page.locator('[data-testid="wizard-step-1"]').first.wait_for(state="visible", timeout=timeout)


# ---------------------------------------------------------------------------
# Dashboard API mocks
# ---------------------------------------------------------------------------
# These make dashboard navigation fast and deterministic in E2E tests,
# avoiding the real API's cold-start (~30s) and the POST /auth/refresh
# hanging issue during page load. Only call before page.goto(…"/"…).
# ---------------------------------------------------------------------------


def setup_dashboard_api_mocks(page: Page, *, mock_novels: bool = False) -> None:
    """Mock the API endpoints called during dashboard page load.

    The dashboard triggers these requests on page load:
      1. POST /api/v1/auth/refresh — refresh httpOnly cookie → new access_token
      2. GET  /api/v1/auth/me      — fetch current user
      3. GET  /api/v1/novels       — list novels for the dashboard

    Mocks (1) and (2) are **always** set up — they prevent the POST
    /auth/refresh hanging issue during page load (no-body POST through the
    Next.js dev proxy).

    Mock (3) is optional — pass ``mock_novels=True`` to return an empty
    novels list. Use this for tests that only check UI structure (buttons,
    navigation) and don't need real novel data.

    Must be called **before** ``page.goto`` so the route is registered in time.
    """
    _setup_auth_mocks(page)
    if mock_novels:
        _setup_novels_mock(page)


def _setup_auth_mocks(page: Page) -> None:
    """Mock POST /auth/refresh and GET /auth/me."""
    page.route(
        "**/api/v1/auth/refresh",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"access_token": "e2e-mock-access-token", "token_type": "bearer"}),
        ),
    )
    page.route(
        "**/api/v1/auth/me",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "email": "dashboard-mock@example.com",
                    "display_name": "Dashboard Mock User",
                    "is_active": True,
                }
            ),
        ),
    )


def _setup_novels_mock(page: Page) -> None:
    """Mock GET /novels to return an empty list."""
    page.route(
        "**/api/v1/novels**",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps([]),
        ),
    )


# ---------------------------------------------------------------------------
# Wizard helper — see test_helpers_wizard.py (split for RULE-04)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Auth proxy helper
# ---------------------------------------------------------------------------


def _setup_auth_proxy(page: Page, access_token: str) -> None:
    """Set up auth proxy route handler that injects real JWT into API requests.

    Uses ``route.fetch()`` to bypass the browser connection-pool hang that
    occurs when the app fires concurrent fetch requests during page load.

    Sets:
      - ``narrare_auth`` cookie for Next.js middleware (server-side route
        protection)
      - ``Authorization: Bearer {access_token}`` header on all API requests
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


# ---------------------------------------------------------------------------
# Editor interaction helpers
# ---------------------------------------------------------------------------


def _insert_editor_text(page: Page, text: str) -> str:
    """Insert text into TipTap editor via its JavaScript API.

    Args:
        page: Playwright Page with a loaded editor.
        text: The text content to insert at the cursor position.

    Returns:
        ``'ok'`` on success, or an error string like ``'no-editor-instance'``.
    """
    return page.evaluate(
        """(text) => {
            const editor = window.__narrareEditor;
            if (!editor) return 'no-editor-instance';
            editor.commands.insertContent(text);
            editor.commands.focus();
            return 'ok';
        }""",
        text,
    )


def _save_editor(page: Page, timeout: int = 10000) -> None:
    """Click the Save button in the editor header and wait for the content PUT.

    Tries multiple selectors to accommodate i18n variants (English, German,
    French button labels).
    """
    save_selectors = [
        'button[data-testid="save-button"]',
        'button:has(svg):has-text("Save")',
        'button:has(svg):has-text("Speichern")',
        'button:has(svg):has-text("Enregistrer")',
    ]
    save_button = None
    for selector in save_selectors:
        locator = page.locator(selector).first
        if locator.is_visible():
            save_button = locator
            break

    if save_button is None:
        save_button = page.locator("button.bg-primary").first

    save_button.wait_for(state="visible", timeout=5000)
    save_button.click()
    page.wait_for_timeout(2000)


# ---------------------------------------------------------------------------
# URL / sidebar helpers
# ---------------------------------------------------------------------------


def _extract_novel_id_from_url(page: Page) -> str:
    """Extract novel UUID from the current page URL.

    Raises:
        ValueError: If the URL does not contain a ``/novel/{uuid}`` path.
    """
    match = re.search(r"/novel/([a-f0-9-]+)", page.url)
    if not match:
        raise ValueError(f"No novel ID found in URL: {page.url}")
    return match.group(1)


def _click_chapter_in_sidebar(page: Page, index: int = 0) -> None:
    """Click the chapter at the given index in the sidebar chapter list.

    Args:
        page: Playwright Page with the editor loaded.
        index: Zero-based chapter index (default: first chapter).

    Raises:
        IndexError: If the requested index is out of range.
    """
    chapters = page.locator('[data-testid="chapter-item"]')
    if chapters.count() == 0:
        # Fallback: try generic sidebar buttons
        chapters = page.locator(".space-y-1 button[type='button']")
    if chapters.count() > index:
        chapters.nth(index).click()
        page.wait_for_timeout(1000)
    else:
        raise IndexError(f"Chapter index {index} out of range (found {chapters.count()} chapters)")


def _get_chapter_count_in_sidebar(page: Page) -> int:
    """Return the number of chapters shown in the sidebar."""
    chapters = page.locator('[data-testid="chapter-item"]')
    if chapters.count() == 0:
        chapters = page.locator(".space-y-1 button[type='button']")
    return chapters.count()
