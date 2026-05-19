"""Helper functions for E2E tests.

Shared utilities used across multiple E2E test modules to avoid code duplication.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page


# narrare: allow reason="function is exported for use by other e2e test modules"
def _click_next(page: Page, expected_step: int | None = None) -> None:
    """Click the Next/Continue button in the setup wizard.

    Args:
        page: Playwright Page object
        expected_step: Optional step number to verify after clicking
    """
    # Try various selectors for Next/Continue buttons in the wizard
    next_selectors = [
        'button:has-text("Next")',
        'button:has-text("Continue")',
        'button[type="submit"]:has-text("Next")',
        'button[type="submit"]:has-text("Continue")',
        'a:has-text("Next")',
        '[role="button"]:has-text("Next")',
    ]

    clicked = False
    for selector in next_selectors:
        try:
            locator = page.locator(selector).first
            if locator.is_visible():
                locator.click()
                clicked = True
                break
        except Exception:
            continue

    if not clicked:
        # Fallback: try any button in a form context
        page.locator("form button").last.click()

    # If expected_step is provided, wait for the step to be active
    if expected_step is not None:
        # The wizard is an SPA — steps change via Zustand client state, NOT URL routing.
        # The active step indicator has aria-current="step" and contains the step number.
        # Before the transition, this locator matches 0 elements (old step has different
        # text), so wait_for correctly blocks until the new step becomes active.
        page.locator('[aria-current="step"]').filter(has_text=str(expected_step)).first.wait_for(
            state="visible", timeout=5000
        )
