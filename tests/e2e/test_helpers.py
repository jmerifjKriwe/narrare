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
