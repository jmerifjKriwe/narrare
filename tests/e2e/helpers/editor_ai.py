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
from tests.e2e.test_helpers import reload_page

if TYPE_CHECKING:
    from collections.abc import Callable

    import requests
    from playwright.sync_api import Page

_EDITOR_SELECTOR = ".ProseMirror"
_SIDEBAR_CHAPTER = '[data-testid="chapter-item"]'
_UI_WAIT_MS: int = 15_000
_HYDRATION_WAIT_MS: int = 15_000
"""Budget for the TipTap hydration gate (editor instance attaches on mount)."""


def wait_editor_hydrated(page: Page) -> None:
    """Block until the TipTap instance is actually attached to the page.

    Hydration signal: ``window.__narrareEditor``, set by
    ``useEditorInstance.ts`` when the editor is created — the same hook
    ``test_helpers._insert_editor_text`` relies on. ``.ProseMirror`` being
    VISIBLE is not sufficient: keystrokes typed between first paint and
    editor attachment are swallowed, so downstream waits (ghost-text
    auto-trigger, suggestion streaming) burn their whole budget on input
    that never reached the editor.

    Prevents the Oct-16 nightly class (run 38867487325,
    ``TestGhostText::test_ghost_text_tab_accept_inserts_suggestion``:
    suggestion never visible, ZERO ``/suggest`` calls in the 30s window —
    the frontend never fired the request because the typed seed never
    landed in a hydrated editor).
    """
    page.wait_for_function(
        "() => Boolean(window.__narrareEditor) && Boolean(document.querySelector('.ProseMirror'))",
        timeout=_HYDRATION_WAIT_MS,
    )


def type_into_editor(page: Page, text: str) -> None:
    """Hydration-safe typing into the chapter editor.

    Waits for the editor instance, focuses, types, then CONFIRMS the text
    landed in ``.ProseMirror`` before returning (deterministic: a dropped
    keystroke fails here in seconds with a precise message instead of as a
    30s "downstream element never appeared" timeout).

    Trailing whitespace is trimmed from the confirmation seed: the ghost
    widgets render INSIDE ``.ProseMirror`` (extensions/GhostText.ts), so
    ``innerText`` may normalize a document-trailing typed space.
    """
    wait_editor_hydrated(page)
    page.locator(_EDITOR_SELECTOR).first.click()
    page.keyboard.type(text)
    page.wait_for_function(
        "(seed) => document.querySelector('.ProseMirror')?.innerText.includes(seed)",
        arg=text.rstrip(),
        timeout=_HYDRATION_WAIT_MS,
    )


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

    Reload hardening: ``reload_page`` (``domcontentloaded`` + one retry,
    commit-168945f4 pattern) instead of a bare ``page.reload()`` whose
    default ``load`` wait stalls 30s on a dev-proxy stall — the Oct-15
    nightly class (run 38700481557: ``Page.reload: Timeout 30000ms`` in
    ``test_ai_writing_selection.py::TestCoAuthor`` and
    ``test_ai_writing.py::TestGenerateErrorPaths::test_empty_form…``).
    Returns only after the editor is hydrated (see
    :func:`wait_editor_hydrated`), so callers can interact immediately.
    """
    created = create_chapter_via_api(api_request, novel_id, title=title, content=content)
    reload_page(page)
    chapter_button = page.locator(_SIDEBAR_CHAPTER, has_text=re.compile(re.escape(title)))
    chapter_button.last.wait_for(state="visible", timeout=_UI_WAIT_MS)
    chapter_button.last.click()
    page.locator(_EDITOR_SELECTOR).first.wait_for(state="visible", timeout=_UI_WAIT_MS)
    wait_editor_hydrated(page)
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
