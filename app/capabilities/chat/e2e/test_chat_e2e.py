"""A question asked in the browser must come back quoting the uploaded passage.

The upload happens through the knowledge page, so the passage the answer cites is
one that reached Postgres in this same run. The browser, the API and Postgres are
the real ones; the provider and the embedding model are the catalog's fakes.

Two further tests pin what the route move to the capability folder must not
change: the page's Tailwind styling, and a conversation's survival of a
language switch (the move puts the page behind React.lazy — a remount on
re-render would silently drop the answer).
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
