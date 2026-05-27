"""Editor Content Persistence E2E Test.

Covers: content persists after navigating away from editor and back.

All LLM responses are mocked via page.route() — no real API tokens consumed.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from tests.e2e.mocks.llm_responses import setup_llm_mocks
from tests.e2e.test_helpers import _click_next, _wait_for_wizard_ready

if TYPE_CHECKING:
    from playwright.sync_api import Page


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
        page_text = page.inner_text(".bg-card.border").lower()
        if "provider" in page_text or "api key" in page_text:
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
        page.locator('[data-testid="wizard-complete"]').first.wait_for(
            state="visible", timeout=15000
        )
        page.locator('[data-testid="wizard-complete"]').first.click()
        page.wait_for_url(f"{base_url}/novel/**", timeout=15000)

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
                return 'ok';
            }""",
            test_text,
        )
        assert insert_result == "ok", f"Insert failed: {insert_result}"

        # Navigate away to dashboard
        page.goto(f"{base_url}/", timeout=15000)
        page.wait_for_timeout(1000)

        # Navigate back to editor
        novel_link = page.locator('a[href*="/novel/"]').first
        if novel_link.is_visible():
            novel_link.click()
        else:
            page.goto(page.url + "/novel", timeout=15000)
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
