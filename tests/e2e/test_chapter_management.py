"""Chapter Management E2E Tests.

Covers: chapter creation, renaming, deletion, and switching between chapters.

All LLM responses are mocked via NARRARE_E2E_TEST env var (server-side TestModel)
and page.route() (browser-side). No real API tokens consumed.
Runs against the full stack (API port 8000, Frontend port 3000).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from tests.e2e.test_helpers import (
    _click_chapter_in_sidebar,
    _complete_wizard_to_editor,
    _get_chapter_count_in_sidebar,
    _insert_editor_text,
    _save_editor,
    _setup_auth_proxy,
)

if TYPE_CHECKING:
    from playwright.sync_api import Page


@pytest.mark.e2e
class TestChapterManagement:
    """Test chapter CRUD operations in the novel editor."""

    # CH-1: Create new chapter via sidebar
    def test_create_new_chapter_via_sidebar(
        self,
        page: Page,
        base_url: str,
        register_unique_user,
    ) -> None:
        """Creating a new chapter via sidebar adds it to the chapter list."""
        result = _complete_wizard_to_editor(page, base_url, register_unique_user)
        _setup_auth_proxy(page, result["access_token"])

        page.wait_for_timeout(2000)  # Wait for editor to fully load

        # Count initial chapters (should be 1 from wizard)
        initial_count = _get_chapter_count_in_sidebar(page)
        print(f"\n=== INITIAL CHAPTER COUNT: {initial_count} ===")

        # Click "New Chapter" button
        new_chapter_selectors = [
            'button[data-testid="new-chapter-btn"]',
            'button:has-text("New Chapter")',
            'button:has-text("Neues Kapitel")',
            'button:has-text("+")',
        ]

        clicked = False
        for selector in new_chapter_selectors:
            locator = page.locator(selector).first
            if locator.is_visible():
                locator.click()
                clicked = True
                print(f"  Clicked new chapter button: {selector}")
                break

        assert clicked, "Could not find 'New Chapter' button in sidebar"

        # Wait for chapter creation + React Query refetch
        page.wait_for_timeout(3000)

        # Verify chapter count increased
        new_count = _get_chapter_count_in_sidebar(page)
        print(f"  New chapter count: {new_count}")
        assert new_count == initial_count + 1, (
            f"Expected {initial_count + 1} chapters after creation, got {new_count}"
        )

        # Verify editor is still visible (no empty state)
        editor = page.locator(
            '.tiptap, [data-testid="editor"], .ProseMirror, [contenteditable="true"]'
        ).first
        assert editor.is_visible(), "Editor should be visible after chapter creation"

    # CH-2: Rename chapter via header input
    def test_rename_chapter_via_header_input(
        self,
        page: Page,
        base_url: str,
        register_unique_user,
    ) -> None:
        """Renaming a chapter via the header input persists after page reload."""
        result = _complete_wizard_to_editor(page, base_url, register_unique_user)
        _setup_auth_proxy(page, result["access_token"])

        page.wait_for_timeout(2000)

        # Diagnostic: capture API response statuses during save
        api_responses: list[tuple[str, int, str]] = []
        page.on(
            "response",
            lambda resp: (
                api_responses.append((resp.request.method, resp.status, resp.url))
                if "/api/v1/" in resp.url
                else None
            ),
        )

        # Find the chapter title input in the header
        title_input_selectors = [
            'input[data-testid="chapter-title-input"]',
            "input.bg-transparent.border-none",
            '.border-b input[type="text"]',
        ]

        title_input = None
        for selector in title_input_selectors:
            locator = page.locator(selector).first
            if locator.is_visible():
                title_input = locator
                break

        assert title_input is not None, "Could not find chapter title input in header"

        # Clear and type new title
        new_title = f"Renamed Chapter {uuid.uuid4().hex[:6]}"
        title_input.click()
        title_input.fill("")
        title_input.fill(new_title)
        page.wait_for_timeout(500)

        # Save — _save_editor waits for the API response internally
        _save_editor(page)

        # Wait for sidebar to reflect the new title (React Query invalidation → refetch)
        try:
            page.wait_for_function(
                "(title) => document.body.innerText.includes(title)",
                arg=new_title,
                timeout=10000,
            )
        except Exception:
            body_text = page.inner_text("body")[:500]
            print("\n=== RENAME FAILURE DIAGNOSTICS ===")
            print(f"  Expected title: {new_title}")
            print(f"  Body text: {body_text}")
            print("  API responses during save:")
            for method, status, url in api_responses:
                print(f"    {method} {status} {url}")
            raise

        # Reload and verify persistence
        current_url = page.url
        page.goto(current_url)
        page.wait_for_timeout(3000)

        # Re-find the title input
        title_input_2 = None
        for selector in title_input_selectors:
            locator = page.locator(selector).first
            if locator.is_visible():
                title_input_2 = locator
                break

        if title_input_2:
            value = title_input_2.input_value()
            assert new_title in value, f"Expected title '{new_title}' after reload, got '{value}'"

    # CH-3: Delete chapter via API and verify sidebar updates
    def test_delete_chapter_via_api_and_sidebar_updates(
        self,
        page: Page,
        base_url: str,
        api_url: str,
        register_unique_user,
    ) -> None:
        """Deleting a chapter via API updates the sidebar correctly."""
        import requests as http_requests

        result = _complete_wizard_to_editor(page, base_url, register_unique_user)
        _setup_auth_proxy(page, result["access_token"])

        page.wait_for_timeout(2000)

        novel_id = result["novel_id"]
        access_token = result["access_token"]

        # Create a second chapter via API
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        create_resp = http_requests.post(
            f"{api_url}/api/v1/novels/{novel_id}/chapters",
            json={"title": "Chapter To Delete", "position": 1},
            headers=headers,
            timeout=30,
        )
        assert create_resp.status_code in (200, 201), (
            f"Chapter creation failed: {create_resp.status_code} {create_resp.text}"
        )
        chapter_data = create_resp.json()
        chapter_id = chapter_data.get("id") or chapter_data.get("chapter_id")
        print(f"\n=== Created chapter {chapter_id} ===")

        # Reload page to see new chapter
        page.goto(page.url)
        page.wait_for_timeout(3000)

        # Count chapters (should be 2)
        count_before = _get_chapter_count_in_sidebar(page)
        print(f"  Chapters before delete: {count_before}")
        assert count_before >= 2, f"Expected >= 2 chapters, got {count_before}"

        # Delete the chapter via API
        delete_resp = http_requests.delete(
            f"{api_url}/api/v1/novels/{novel_id}/chapters/{chapter_id}",
            headers=headers,
            timeout=30,
        )
        print(f"  Delete response: {delete_resp.status_code}")
        assert delete_resp.status_code in (200, 204), (
            f"Chapter deletion failed: {delete_resp.status_code} {delete_resp.text}"
        )

        # Reload and verify chapter count decreased
        page.goto(page.url)
        page.wait_for_timeout(3000)

        count_after = _get_chapter_count_in_sidebar(page)
        print(f"  Chapters after delete: {count_after}")
        assert count_after == count_before - 1, (
            f"Expected {count_before - 1} chapters after deletion, got {count_after}"
        )

    # CH-4: Switch between chapters shows different content
    def test_switch_chapters_shows_different_content(
        self,
        page: Page,
        base_url: str,
        api_url: str,
        register_unique_user,
    ) -> None:
        """Switching chapters replaces editor content correctly."""
        import requests as http_requests

        result = _complete_wizard_to_editor(page, base_url, register_unique_user)
        _setup_auth_proxy(page, result["access_token"])

        page.wait_for_timeout(2000)

        # Diagnostic: capture API response statuses during save
        api_responses: list[tuple[str, int, str]] = []
        page.on(
            "response",
            lambda resp: (
                api_responses.append((resp.request.method, resp.status, resp.url))
                if "/api/v1/" in resp.url
                else None
            ),
        )

        novel_id = result["novel_id"]
        access_token = result["access_token"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Create a second chapter via API
        create_resp = http_requests.post(
            f"{api_url}/api/v1/novels/{novel_id}/chapters",
            json={"title": "Chapter B", "position": 1},
            headers=headers,
            timeout=30,
        )
        assert create_resp.status_code in (200, 201)

        # Reload to see both chapters
        page.goto(page.url)
        page.wait_for_timeout(3000)

        # Wait for editor
        editor = page.locator(
            '.tiptap, [data-testid="editor"], .ProseMirror, [contenteditable="true"]'
        ).first
        editor.wait_for(state="visible", timeout=10000)

        # Insert unique text into current chapter (first chapter from wizard)
        text_a = f"Content Alpha {uuid.uuid4().hex[:8]}"
        insert_result = _insert_editor_text(page, text_a)
        assert insert_result == "ok", f"Insert failed: {insert_result}"
        _save_editor(page)

        # Switch to second chapter
        # Click the second chapter in sidebar (index 1)
        _click_chapter_in_sidebar(page, index=1)
        page.wait_for_timeout(2000)

        # Verify chapter A's text is NOT in editor
        editor_html = page.evaluate(
            """() => {
                const el = document.querySelector('.ProseMirror');
                return el ? el.innerHTML : '';
            }"""
        )
        assert text_a not in editor_html, "Chapter A content should not appear in chapter B"

        # Insert unique text into chapter B
        text_b = f"Content Beta {uuid.uuid4().hex[:8]}"
        insert_result = _insert_editor_text(page, text_b)
        assert insert_result == "ok", f"Insert failed: {insert_result}"
        _save_editor(page)

        # Switch back to first chapter
        _click_chapter_in_sidebar(page, index=0)
        page.wait_for_timeout(2000)

        # Verify chapter A's text IS in editor, chapter B's is NOT
        editor_html_2 = page.evaluate(
            """() => {
                const el = document.querySelector('.ProseMirror');
                return el ? el.innerHTML : '';
            }"""
        )
        assert text_a in editor_html_2, (
            f"Chapter A content should be restored when switching back. "
            f"Expected '{text_a}' in editor HTML."
        )
        assert text_b not in editor_html_2, "Chapter B content should not appear in chapter A"
