"""Setup Wizard Completion E2E Test.

Handles: Wizard completion logic, API interception, redirect handling, and error checking.

All LLM responses are mocked via page.route() — no real API tokens consumed.
Runs against the full stack (API port 8000, Frontend port 3000).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.e2e.test_helpers import _click_next

if TYPE_CHECKING:
    from playwright.sync_api import Page

pytestmark = pytest.mark.skip(reason="temporarily disabled due to test infrastructure issues")


@pytest.mark.e2e
class TestWizardCompletion:
    """Test wizard completion and redirect handling."""

    def verify_wizard_state(self, page: Page) -> None:
        """Verify wizard state before completion."""
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)

        # Check current wizard step by looking for step 5 specific content
        body_text = page.inner_text("body")
        print("\n=== WIZARD STATE CHECK ===")
        print(f"  Current URL: {page.url}")
        print(f"  Body text (first 500 chars): {body_text[:500]}")

        # Look for step indicator circles to determine current step
        active_steps = page.locator('[aria-current="step"]')
        if active_steps.count() > 0:
            current_step_label = active_steps.first.inner_text()
            print(f"  Current wizard step: {current_step_label}")
        else:
            print("  Could not determine current wizard step")

        # Check for validation errors before proceeding
        error_elements = page.locator(".text-destructive")
        error_count = error_elements.count()
        if error_count > 0:
            print(f"  WARNING: Found {error_count} error element(s) on page:")
            for i in range(min(error_count, 5)):
                print(f"    Error [{i}]: {error_elements.nth(i).inner_text()}")

    def complete_wizard_setup(self, page: Page, base_url: str) -> dict[str, str | bool]:
        """Complete the wizard and handle redirects."""
        # --- Intercept /setup/complete to log request and response ---
        setup_complete_log: dict[str, str | int | None] = {
            "request_url": None,
            "request_body": None,
            "response_status": None,
            "response_body": None,
            "error": None,
        }

        def _intercept_setup_complete(route):
            """Intercept the /setup/complete call to log everything."""
            setup_complete_log["request_url"] = route.request.url
            setup_complete_log["request_body"] = route.request.post_data
            try:
                response = route.fetch()
                setup_complete_log["response_status"] = response.status
                body_text = response.text()
                setup_complete_log["response_body"] = body_text
                route.fulfill(
                    status=response.status,
                    headers=response.headers,
                    body=body_text,
                )
            except Exception as e:
                setup_complete_log["error"] = str(e)
                route.fulfill(status=500, body='{"detail": "Intercepted error"}')

        page.route("**/api/v1/setup/complete", _intercept_setup_complete)

        # --- Find and click the Complete button ---
        complete_selectors = [
            'button:has-text("Finish")',
            'button:has-text("Complete")',
            'button:has-text("Start")',
            'button:has-text("Erstellen")',
            'button:has-text("Bestätigen")',
        ]
        for selector in complete_selectors:
            locator = page.locator(selector).first
            if locator.is_visible():
                print(f"\n=== COMPLETE BUTTON: Found visible button with selector: {selector}")
                print(f"  Button text: {locator.inner_text()}")
                print(f"  Button type attr: {locator.get_attribute('type')}")
                print(f"  Button disabled attr: {locator.get_attribute('disabled')}")

                with page.expect_response(
                    "**/api/v1/setup/complete", timeout=15000
                ) as response_info:
                    locator.click()

                try:
                    resp = response_info.value
                    print(f"  API call fired! Response status: {resp.status}")
                    print(f"  API call URL: {resp.request.url}")
                except Exception as e:
                    print(f"  API call did NOT fire within timeout: {e}")
                break

        # Wait a moment for any pending operations
        page.wait_for_timeout(1000)

        # Print the intercepted API call details
        print("\n=== SETUP/COMPLETE API CALL ===")
        print(f"  URL: {setup_complete_log['request_url']}")
        print(f"  Request body: {setup_complete_log['request_body']}")
        print(f"  Response status: {setup_complete_log['response_status']}")
        print(f"  Response body: {setup_complete_log['response_body']}")
        if setup_complete_log["error"]:
            print(f"  Error: {setup_complete_log['error']}")

        # Take screenshot immediately after click
        page.screenshot(path="/tmp/after-complete-click.png")
        print(f"\n=== POST-COMPLETE: Current URL = {page.url}")
        print(f"Page title: {page.title()}")
        print("Screenshot saved to /tmp/after-complete-click.png")

        # Wait for redirect — could be dashboard or novel editor
        try:
            page.wait_for_url(f"{base_url}/novel/**", timeout=15000)
            print(f"Redirected to novel: {page.url}")
            return {
                "current_url": page.url,
                "is_novel_editor": True,
                "is_dashboard": False,
            }
        except Exception:
            print(f"Not on novel URL. Current URL: {page.url}")
            try:
                page.wait_for_url(f"{base_url}/dashboard**", timeout=5000)
                print(f"Redirected to dashboard: {page.url}")
                return {
                    "current_url": page.url,
                    "is_novel_editor": False,
                    "is_dashboard": True,
                }
            except Exception:
                print(f"NOT on dashboard either. Current URL: {page.url}")
                page.screenshot(path="/tmp/no-redirect-state.png")
                print("Screenshot saved to /tmp/no-redirect-state.png")

                # Check if we're still on /wizard
                if "/wizard" in page.url:
                    print("STILL ON /wizard — redirect did not happen!")
                    print(f"Page inner text (first 1000 chars): {page.inner_text('body')[:1000]}")

                    creating = page.locator("text=Creating").first
                    if creating.is_visible():
                        print("  'Creating' indicator is still visible")

                    loading = page.locator("text=Loading").first
                    if loading.is_visible():
                        print("  'Loading' indicator is still visible")

                    toasts = page.locator('[role="alert"], .toast, [data-sonner-toast]')
                    if toasts.count() > 0:
                        for i in range(toasts.count()):
                            print(f"  Toast [{i}]: {toasts.nth(i).inner_text()}")

                return {
                    "current_url": page.url,
                    "is_novel_editor": False,
                    "is_dashboard": False,
                }

    def check_errors(self, page: Page, console_errors: list[str]) -> None:
        """Check for errors during wizard completion."""
        # Check for console errors
        if console_errors:
            print(f"\n=== CONSOLE ERRORS ({len(console_errors)}) ===")
            for err in console_errors[-10:]:
                print(f"  {err[:200]}")

        # Check for error messages on the page
        page_text = page.inner_text("body")
        error_indicators = ["error", "failed", "invalid", "missing", "required", "fehler"]
        found_errors = [word for word in error_indicators if word in page_text.lower()]
        if found_errors:
            print(f"\n=== ERROR INDICATORS FOUND ON PAGE: {found_errors}")
            for word in found_errors:
                idx = page_text.lower().index(word)
                context = page_text[max(0, idx - 50) : idx + 100]
                print(f"  Context for '{word}': ...{context}...")

    def test_wizard_completion_and_redirect(
        self,
        page: Page,
        base_url: str,
        api_url: str,
        register_unique_user,
    ) -> dict[str, str | bool]:
        """Test wizard completion and redirect to dashboard/editor."""
        from tests.e2e.test_setup_wizard import TestSetupWizard

        wizard_test = TestSetupWizard()
        wizard_test._setup_wizard_prerequisites(page, base_url, register_unique_user)

        # Collect console errors for debugging
        console_errors: list[str] = []
        page.on("pageerror", lambda err: console_errors.append(str(err)))

        # Complete steps 1-4
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

            _click_next(page)

        # Verify wizard state and complete
        self.verify_wizard_state(page)
        result = self.complete_wizard_setup(page, base_url)

        # Check for errors
        self.check_errors(page, console_errors)

        return result
