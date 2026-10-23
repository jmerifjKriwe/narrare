"""A question asked in the browser must come back quoting the uploaded passage.

The upload happens through the knowledge page, so the passage the answer cites is
one that reached Postgres in this same run. The browser, the API and Postgres are
the real ones; the provider and the embedding model are the catalog's fakes.

Two further tests pin what the route move to the capability folder must not
change: the page's Tailwind styling, and a conversation's survival of a
language switch (the move puts the page behind React.lazy — a remount on
re-render would silently drop the answer).

The dock tests drive the same ask/answer flow inside the novel workspace: the
chat panel is a child route of the workspace, so opening it is a navigation
(URL truth, back button closes it) and the editor stays mounted beside it.
"""

from contextlib import suppress
from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

from app.kernel.testing.a11y import assert_accessible

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

PASSAGE = "Der Leuchtturm am Horizont war seit Jahren dunkel."


def test_answer_quotes_the_uploaded_passage(page: Page, stack: Stack, tmp_path: Path) -> None:
    source = tmp_path / "notizen.txt"
    source.write_text(PASSAGE, encoding="utf-8")

    page.goto("http://127.0.0.1:3100/knowledge")
    page.get_by_label("Dokument").set_input_files(str(source))
    page.get_by_label("Titel (optional)").fill("Notizen")
    page.get_by_role("button", name="Hochladen").click()
    expect(page.get_by_text("Notizen")).to_be_visible()

    page.goto("http://127.0.0.1:3100/chat")
    page.get_by_label("Frage").fill("Wo war der Leuchtturm?")
    page.get_by_role("button", name="Fragen").click()

    expect(page.get_by_role("region", name="Antwort")).to_contain_text(PASSAGE)
    expect(page.get_by_role("region", name="Quellen")).to_contain_text("Notizen")

    assert_accessible(page)


def test_chat_styling_survives_the_move(page: Page, stack: Stack, tmp_path: Path) -> None:
    # Each test in this module uploads its own document (the stack's database
    # is module-scoped), and the titles share no substring so a page listing
    # every upload still resolves each one to a single element.
    source = tmp_path / "notizen.txt"
    source.write_text(PASSAGE, encoding="utf-8")

    page.goto("http://127.0.0.1:3100/knowledge")
    page.get_by_label("Dokument").set_input_files(str(source))
    page.get_by_label("Titel (optional)").fill("Stylistik")
    page.get_by_role("button", name="Hochladen").click()
    expect(page.get_by_text("Stylistik")).to_be_visible()

    page.goto("http://127.0.0.1:3100/chat")
    page.get_by_label("Frage").fill("Wo war der Leuchtturm?")
    page.get_by_role("button", name="Fragen").click()

    expect(page.get_by_role("region", name="Antwort")).to_contain_text(PASSAGE)

    ask = page.get_by_role("button", name="Fragen")
    bg = ask.evaluate("el => getComputedStyle(el).backgroundColor")
    assert bg not in ("", "rgba(0, 0, 0, 0)")  # Tailwind painted the button

    # The button's bg-primary also exists on other pages, so it alone would
    # not prove Tailwind scanned the capability's folder. whitespace-pre-wrap
    # is the chat page's alone: if the moved file was not a source, the rule
    # is absent and the computed style is the browser's default ("normal").
    answer = page.get_by_role("region", name="Antwort").locator("p").first
    assert answer.evaluate("el => getComputedStyle(el).whiteSpace") == "pre-wrap"

    assert_accessible(page)


def test_conversation_survives_a_locale_switch(page: Page, stack: Stack, tmp_path: Path) -> None:
    source = tmp_path / "notizen.txt"
    source.write_text(PASSAGE, encoding="utf-8")

    page.goto("http://127.0.0.1:3100/knowledge")
    page.get_by_label("Dokument").set_input_files(str(source))
    page.get_by_label("Titel (optional)").fill("Sprachwechsel")
    page.get_by_role("button", name="Hochladen").click()
    expect(page.get_by_text("Sprachwechsel")).to_be_visible()

    page.goto("http://127.0.0.1:3100/chat")
    page.get_by_label("Frage").fill("Wo war der Leuchtturm?")
    page.get_by_role("button", name="Fragen").click()

    expect(page.get_by_role("region", name="Antwort")).to_contain_text(PASSAGE)

    try:
        # The top bar's select switches the shell's language. The English
        # region names prove the switch landed; the passage still in them
        # proves the lazy capability page was re-rendered, not remounted —
        # a remount would drop the answer the user is reading.
        page.get_by_role("combobox").select_option("en")
        expect(page.get_by_role("region", name="Answer")).to_contain_text(PASSAGE)
        expect(page.get_by_role("region", name="Sources")).to_contain_text("Sprachwechsel")

        assert_accessible(page)
    finally:
        # The choice is user data in the stack's shared database: leaving
        # "en" behind would boot the module's other tests in English, and
        # their German-label setup would wait forever. Restore the
        # nobody-chosen state whatever order pytest-randomly picks.
        with suppress(Exception):
            page.get_by_role("combobox").select_option("auto")


def _upload(page: Page, tmp_path: Path, title: str) -> None:
    """Seed the knowledge base through the only door a user has."""
    source = tmp_path / "notizen.txt"
    source.write_text(PASSAGE, encoding="utf-8")

    page.goto("http://127.0.0.1:3100/knowledge")
    page.get_by_label("Dokument").set_input_files(str(source))
    page.get_by_label("Titel (optional)").fill(title)
    page.get_by_role("button", name="Hochladen").click()
    expect(page.get_by_text(title)).to_be_visible()


def _open_workspace(page: Page, title: str) -> None:
    """Create a novel the only way a user can, open it, start a chapter.

    The module's database is shared, so every test owns a title no other uses.
    """
    page.goto("http://127.0.0.1:3100/")
    page.get_by_role("button", name="Neues Buch").click()
    page.get_by_label("Titel").fill(title)
    page.get_by_role("button", name="Anlegen").click()
    page.get_by_role("link", name=title).click()
    expect(page.get_by_role("heading", name=title)).to_be_visible()
    page.get_by_role("button", name="Neues Kapitel").click()
    expect(page.locator(".ProseMirror")).to_be_visible()


def test_dock_answers_beside_the_editor(page: Page, stack: Stack, tmp_path: Path) -> None:
    _upload(page, tmp_path, "Docknotizen")
    _open_workspace(page, "Die Dockschote")

    # The tab's label is also the top bar's — the bar's is a link, the tab a
    # button, so the role tells them apart; exact keeps "Chat" from matching
    # the panel's own close button once it exists.
    page.get_by_role("button", name="Chat", exact=True).click()
    dock = page.get_by_role("complementary", name="Chat")
    editor = page.locator(".ProseMirror")
    expect(dock).to_be_visible()
    expect(editor).to_be_visible()
    # The open dock is URL state beside rail and focus.
    assert "dock=chat" in page.url

    # Beside, not below: the editor ends where the dock begins — and both
    # fit the viewport at once, like the rail does.
    editor_box = editor.bounding_box()
    dock_box = dock.bounding_box()
    assert editor_box is not None and dock_box is not None
    assert editor_box["x"] + editor_box["width"] <= dock_box["x"]
    viewport = page.viewport_size
    assert viewport is not None
    for box in (editor_box, dock_box):
        assert box["x"] >= 0 and box["x"] + box["width"] <= viewport["width"]
        assert box["y"] >= 0 and box["y"] + box["height"] <= viewport["height"]

    # The same ask/answer flow as the standalone page, inside the dock —
    # the editor keeps its text while the answer streams.
    editor.click()
    page.keyboard.type("Text beim Plaudern.")
    dock.get_by_label("Frage").fill("Wo war der Leuchtturm?")
    dock.get_by_role("button", name="Fragen").click()
    expect(dock.get_by_role("region", name="Antwort")).to_contain_text(PASSAGE)
    expect(dock.get_by_role("region", name="Quellen")).to_contain_text("Docknotizen")
    expect(editor).to_contain_text("Text beim Plaudern.")

    assert_accessible(page)


def test_back_button_closes_the_dock(page: Page, stack: Stack) -> None:
    _open_workspace(page, "Die Dockkante")

    page.get_by_role("button", name="Chat", exact=True).click()
    expect(page.get_by_role("complementary", name="Chat")).to_be_visible()

    # Opening the dock was a navigation: the browser's back button is a
    # first-class way to close it again.
    page.go_back()
    expect(page.get_by_role("complementary", name="Chat")).to_have_count(0)
    expect(page.locator(".ProseMirror")).to_be_visible()

    assert_accessible(page)


def test_dock_toggle_preserves_rail_and_focus(page: Page, stack: Stack) -> None:
    _open_workspace(page, "Der Dockanker")

    # A workspace state the dock must not disturb: rail collapsed, focus at
    # depth 1 — both URL state, both carried by the dock's own navigation.
    page.get_by_role("button", name="Kapitelleiste ausblenden").click()
    expect(page.get_by_role("complementary")).to_have_count(0)
    page.keyboard.press("F9")
    assert "rail=false" in page.url and "focus=1" in page.url

    page.get_by_role("button", name="Chat", exact=True).click()
    assert "rail=false" in page.url and "focus=1" in page.url
    assert "dock=chat" in page.url
    # Focus 1 suppresses the panel whatever the URL holds; the step back
    # brings it back without losing the collapsed rail.
    expect(page.get_by_role("complementary", name="Chat")).to_have_count(0)
    page.keyboard.press("Escape")
    expect(page.get_by_role("complementary", name="Chat")).to_be_visible()
    expect(page.get_by_role("complementary")).to_have_count(1)
    assert "rail=false" in page.url and "dock=chat" in page.url

    assert_accessible(page)
