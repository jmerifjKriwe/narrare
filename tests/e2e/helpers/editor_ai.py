"""Editor prep for AI-writing E2E specs (spec §4 helpers package).

Owns the recurring "put the editor into a known state" concerns so the
AI-writing specs assert instead of navigating: chapter seeding via API,
sidebar selection, editor text/caret access, and the generation-panel
entry point. No auth or wizard concerns (RULE-04 — compose with the
conftest stable_* fixtures and novel_factory).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from tests.e2e.helpers.novel_factory import create_chapter_via_api

if TYPE_CHECKING:
    from collections.abc import Callable

    import requests
    from playwright.sync_api import Page

_EDITOR_SELECTOR = ".ProseMirror"
_SIDEBAR_CHAPTER = '[data-testid="chapter-item"]'
_UI_WAIT_MS: int = 15_000


def prepare_ai_chapter(
    page: Page,
    api_request: Callable[..., requests.Response],
    novel_id: str,
    *,
    title: str = "AI Flow Chapter",
    content: str = "",
) -> dict[str, str]:
    """Create a chapter via API and open it in the editor.

    Returns ``{"chapter_id": …, "title": …}``. Reloads the novel page so the
    sidebar picks up the new chapter, then selects it by title (the editor
    auto-selects the FIRST chapter — ours is newest/last).
    """
    created = create_chapter_via_api(api_request, novel_id, title=title, content=content)
    page.reload()
    page.wait_for_load_state("domcontentloaded")
    chapter_button = page.locator(_SIDEBAR_CHAPTER, has_text=re.compile(re.escape(title)))
    chapter_button.last.wait_for(state="visible", timeout=_UI_WAIT_MS)
    chapter_button.last.click()
    page.locator(_EDITOR_SELECTOR).first.wait_for(state="visible", timeout=_UI_WAIT_MS)
    return {"chapter_id": created["id"], "title": title}


def editor_text(page: Page) -> str:
    """The editor's visible text (assertion basis for AI insertions)."""
    return page.locator(_EDITOR_SELECTOR).first.inner_text()


def focus_editor_end(page: Page) -> None:
    """Focus the editor and place the caret at the document end."""
    editor = page.locator(_EDITOR_SELECTOR).first
    editor.click()
    page.keyboard.press("Control+End")


def open_generation_panel(page: Page) -> None:
    """Open the right-hand generation panel from the toolbar.

    No-op when the panel is already open: the panel state syncs to the URL
    (``?panel=generation``), so it survives ``page.reload()`` — and with the
    panel open a bare ``get_by_role("Generate")`` click would be a strict-
    mode collision (toolbar toggle + panel button share the name).
    """
    panel_title = page.get_by_text("AI Generation").first
    if panel_title.is_visible():
        return
    page.get_by_role("button", name="Generate", exact=True).click()
    panel_title.wait_for(state="visible", timeout=_UI_WAIT_MS)


def click_panel_generate(page: Page) -> None:
    """Click the Generate button INSIDE the open generation panel.

    Scoped to the right panel on purpose: once the panel is open, the
    toolbar toggle shares the accessible name "Generate" and a bare
    ``get_by_role`` click is a strict-mode collision.
    """
    page.get_by_test_id("editor-right-panel").get_by_role(
        "button", name="Generate", exact=True
    ).click()
