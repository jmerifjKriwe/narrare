"""The writing workbench: autosave, a chapter rail beside the editor, panel state in the URL.

Every flow drives the real stack — browser, API, Postgres — and ends on the
accessibility floor.
"""

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

from app.kernel.testing.a11y import assert_accessible

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]


def _create_book(page: Page, title: str) -> None:
    """Create a novel the only way a user can, then open its workspace.

    The module's database is shared, so every test owns a title no other uses.
    """
    page.goto("http://127.0.0.1:3100/")
    page.get_by_role("button", name="Neues Buch").click()
    page.get_by_label("Titel").fill(title)
    page.get_by_role("button", name="Anlegen").click()
    page.get_by_role("link", name=title).click()
    expect(page.get_by_role("heading", name=title)).to_be_visible()


def test_typed_chapter_body_survives_reload(page: Page, stack: Stack) -> None:
    page.goto("http://127.0.0.1:3100/")
    page.get_by_role("button", name="Neues Buch").click()
    page.get_by_label("Titel").fill("Der Nebel")
    page.get_by_role("button", name="Anlegen").click()

    page.get_by_role("link", name="Der Nebel").click()
    expect(page.get_by_role("heading", name="Der Nebel")).to_be_visible()

    page.get_by_role("button", name="Neues Kapitel").click()
    editor = page.locator(".ProseMirror")
    editor.click()
    page.keyboard.type("Der Nebel kam von See.")

    # No save button: the indicator is the only proof the debounce fired.
    expect(page.get_by_text("Gespeichert")).to_be_visible()

    page.reload()
    expect(page.locator(".ProseMirror")).to_contain_text("Der Nebel kam von See.")

    assert_accessible(page)


def test_rail_sits_beside_the_editor_without_scrolling(page: Page, stack: Stack) -> None:
    _create_book(page, "Die Salzwiese")
    page.get_by_role("button", name="Neues Kapitel").click()

    rail = page.get_by_role("complementary")
    editor = page.locator(".ProseMirror")
    expect(rail).to_be_visible()
    expect(editor).to_be_visible()

    # Beside, not above: the rail ends where the editor begins.
    rail_box = rail.bounding_box()
    editor_box = editor.bounding_box()
    assert rail_box is not None and editor_box is not None
    assert rail_box["x"] + rail_box["width"] <= editor_box["x"]

    # Both fit the viewport at once: writing no longer scrolls past the list.
    viewport = page.viewport_size
    assert viewport is not None
    for box in (rail_box, editor_box):
        assert box["x"] >= 0 and box["x"] + box["width"] <= viewport["width"]
        assert box["y"] >= 0 and box["y"] + box["height"] <= viewport["height"]

    assert_accessible(page)


def test_rail_zero_url_renders_collapsed(page: Page, stack: Stack) -> None:
    _create_book(page, "Das Wrack")
    page.get_by_role("button", name="Neues Kapitel").click()

    # A shared link lands exactly in the state it was shared in.
    page.goto(f"{page.url.split('?')[0]}?rail=0")

    # The editor's visibility proves the page loaded — only then does an
    # absent rail mean "collapsed", not "not rendered yet".
    expect(page.locator(".ProseMirror")).to_be_visible()
    expect(page.get_by_role("complementary")).to_have_count(0)
    # The way back is on the page, not only in the browser's history.
    expect(page.get_by_role("button", name="Kapitelleiste einblenden")).to_be_visible()

    assert_accessible(page)


def test_back_button_restores_the_expanded_rail(page: Page, stack: Stack) -> None:
    _create_book(page, "Der Leuchtturm")
    page.get_by_role("button", name="Neues Kapitel").click()
    expect(page.get_by_role("complementary")).to_be_visible()

    page.get_by_role("button", name="Kapitelleiste ausblenden").click()
    expect(page.get_by_role("complementary")).to_have_count(0)
    # The collapse is a navigation: the state lives in the URL.
    assert "rail=false" in page.url

    page.go_back()
    expect(page.get_by_role("complementary")).to_be_visible()
    expect(page.locator(".ProseMirror")).to_be_visible()

    assert_accessible(page)


def test_typed_text_survives_a_chapter_switch(page: Page, stack: Stack) -> None:
    _create_book(page, "Die Mole")
    page.get_by_role("button", name="Neues Kapitel").click()
    editor = page.locator(".ProseMirror")
    editor.click()
    page.keyboard.type("Erster Satz am Kai.")

    # Switch inside the 800 ms debounce: nothing is written yet and the
    # indicator is quiet (it stays hidden while the save is pending).
    # Waiting for "Gespeichert" here would exercise only the settled path;
    # the unmount flush is what this test is about.
    expect(page.get_by_role("status")).to_have_count(0)

    # The switch is the flush's cue. Wait for its PUT on the wire rather
    # than for a clock: the response is the fact that the pending text
    # reached the server.
    with page.expect_response(
        lambda response: (
            "/api/writing/chapters/" in response.url and response.request.method == "PUT"
        )
    ) as flushed:
        page.get_by_role("button", name="Neues Kapitel").click()
    assert flushed.value.ok

    # A fresh chapter starts empty; the written one keeps its text — and
    # the reload proves the row, not the in-memory body the switch carried.
    expect(page.locator(".ProseMirror")).to_have_text("")
    page.reload()
    page.get_by_role("button", name="Kapitel 1", exact=True).click()
    expect(page.locator(".ProseMirror")).to_contain_text("Erster Satz am Kai.")

    assert_accessible(page)


def test_the_latest_touched_chapter_opens_first(page: Page, stack: Stack) -> None:
    _create_book(page, "Deichgraf")
    page.get_by_role("button", name="Neues Kapitel").click()
    editor = page.locator(".ProseMirror")
    editor.click()
    page.keyboard.type("Kalter Wind.")
    expect(page.get_by_text("Gespeichert")).to_be_visible()

    # The second chapter is not just created later — it is written in later.
    page.get_by_role("button", name="Neues Kapitel").click()
    page.locator(".ProseMirror").click()
    page.keyboard.type("Springflut.")
    expect(page.get_by_text("Gespeichert")).to_be_visible()

    # The reload opens the chapter last written in, not the first one.
    page.reload()
    expect(page.locator(".ProseMirror")).to_contain_text("Springflut.")
    expect(page.locator(".ProseMirror")).not_to_contain_text("Kalter Wind.")

    assert_accessible(page)


def test_the_workbench_names_a_book_it_cannot_load(page: Page, stack: Stack) -> None:
    """An unreachable book is an error with a retry, never an empty workbench."""
    _create_book(page, "Das erreichbare Buch")
    url = page.url  # the real workspace URL, for the recovery half

    # The workbench cannot reach the service — a real condition of a local
    # app, produced by stopping the real API, not by faking a response.
    stack.stop_api()
    try:
        page.goto(url)
        expect(page.get_by_role("alert").filter(has_text="konnte nicht geladen")).to_be_visible()
        expect(page.get_by_role("button", name="Erneut versuchen")).to_be_visible()
    finally:
        stack.start_api()

    # One press, no reload: the workbench is back.
    page.get_by_role("button", name="Erneut versuchen").click()
    expect(page.get_by_role("heading", name="Das erreichbare Buch")).to_be_visible()

    assert_accessible(page)


def test_the_workbench_names_a_book_that_does_not_exist(page: Page, stack: Stack) -> None:
    """A 404 is the same honesty: the error copy, not an empty chapter rail."""
    page.goto("http://127.0.0.1:3100/novels/00000000-0000-4000-8000-000000000000")
    expect(page.get_by_role("alert").filter(has_text="konnte nicht geladen")).to_be_visible()
    # The empty-rail copy is a loaded book's truth, not a missing one's.
    expect(page.get_by_text("Noch kein Kapitel")).not_to_be_visible()

    # The retry says the same thing: the book is still not there.
    page.get_by_role("button", name="Erneut versuchen").click()
    expect(page.get_by_role("alert").filter(has_text="konnte nicht geladen")).to_be_visible()

    assert_accessible(page)
