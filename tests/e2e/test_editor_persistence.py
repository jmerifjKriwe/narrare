"""Editor Content Persistence E2E Test.

Covers: content persists after navigating away from editor and back.

All LLM responses are mocked via page.route() — no real API tokens consumed.
"""

from __future__ import annotations

import uuid
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


@pytest.mark.e2e
class TestEditorPersistence:
    """Test editor content persistence across navigation."""

    def test_editor_content_persists_after_page_navigate(
        self,
        page: Page,
        base_url: str,
        register_unique_user,
    ) -> None:
        """Test editor content persists after navigating away and back."""
        setup_llm_mocks(page)
        user = register_unique_user()
        email = user["email"]
        password = user["password"]
        access_token = user["access_token"]

        # Login and complete wizard
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
            project_input.fill("Persistence Test Novel")
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
            title_input.fill("The Persistent Tale")
        _click_next(page, expected_step=4)

        # Step 4
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
                page.wait_for_function(
                    "document.querySelector('[data-testid=\"wizard-next\"]')"
                    " && !document.querySelector('[data-testid=\"wizard-next\"]').disabled",
                    timeout=10000,
                )

        # ALWAYS click Next at Step 4, even if text detection didn't match
        _click_next(page)

        # Step 5: Complete
        page.locator('[data-testid="wizard-complete"]').first.wait_for(
            state="visible", timeout=15000
        )
        page.locator('[data-testid="wizard-complete"]').first.click()
        # Accept either /novel/** or /dashboard as valid completion targets
        page.wait_for_url(
            lambda url: "/novel/" in url or "/dashboard" in url,
            timeout=15000,
        )

        # If wizard redirected to /dashboard, navigate to the novel from there
        if "/novel/" not in page.url:
            page.wait_for_timeout(1000)
            novel_link = page.locator('a[href*="/novel/"]').first
            if novel_link.is_visible():
                novel_link.click()
                page.wait_for_url(lambda url: "/novel/" in url, timeout=15000)

        # Insert text into editor
        page.wait_for_timeout(2000)
        editor = page.locator(
            '.tiptap, [data-testid="editor"], .ProseMirror, [contenteditable="true"]'
        ).first
        editor.wait_for(state="visible", timeout=10000)

        test_text = f"Persistent content {uuid.uuid4().hex[:6]}"
        insert_result = page.evaluate(
            """(text) => {
                const editor = window.__narrareEditor;
                if (!editor) return 'no-editor';
                editor.commands.insertContent(text);
                editor.commands.focus();
                return 'ok';
            }""",
            test_text,
        )
        assert insert_result == "ok", f"Insert failed: {insert_result}"

        # Explicitly save the content via the Save button to ensure the
        # inserted text is persisted to the API before navigating away.
        # Relying on autosave debounce alone is fragile in E2E tests.
        page.wait_for_timeout(500)  # Let TipTap's onUpdate process
        save_button = page.locator(
            'button:has(svg):has-text("Save"), '
            'button:has(svg):has-text("Speichern"), '
            'button:has(svg):has-text("Enregistrer")'
        ).first
        if not save_button.is_visible():
            save_button = page.locator("button.bg-primary").first
        if not save_button.is_visible():
            save_button = page.locator(".flex.items-center.gap-4 button").last
        if save_button.is_visible():
            save_button.click()
            page.wait_for_timeout(2000)  # Wait for PUT to complete
        else:
            # Fallback: wait longer for autosave debounce
            page.wait_for_timeout(5000)

        # Store the novel URL before navigating away
        novel_url = page.url

        # Set up auth proxy: cookie for middleware + route.fetch() for API calls.
        # This avoids the browser hang AND ensures real API calls get a valid token.
        # Mock auth endpoints BEFORE _setup_auth_proxy to prevent POST /auth/refresh
        # hang during page load.  Auth mocks match first (Playwright route order).
        setup_dashboard_api_mocks(page)
        _setup_auth_proxy(page, access_token)
        page.goto(f"{base_url}/", timeout=15000, wait_until="domcontentloaded")
        page.wait_for_timeout(1000)

        # Navigate back to editor using the stored URL
        page.goto(novel_url, timeout=15000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Check if editor content persisted
        editor_html = page.evaluate(
            """() => {
                const el = document.querySelector('.ProseMirror');
                return el ? el.innerHTML : '';
            }"""
        )
        print("\n=== PERSISTENCE CHECK ===")
        print(f"  Expected text: {test_text}")
        print(f"  Editor contains text: {test_text in editor_html}")
        assert test_text in editor_html, (
            f"Editor content did not persist after navigate. Expected '{test_text}' in editor HTML."
        )
