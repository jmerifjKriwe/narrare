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
The tab itself comes from the generated dock registry: one tab per dock that
exists, labeled by its capability, pressed exactly while its child route is
showing — and the open route is the dock's whole URL state, so a closed dock
leaves a clean URL (no dock param anywhere the app itself produces).

The proposal tests drive the bus that crosses the dock/editor seam: a
completed dock answer offered as a variant becomes ghost text in the editor
(never document text without Tab), and an offer does not survive leaving the
novel — there is no editor to haunt, so there must be no ghost on return.
"""

import re
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
    # the panel's own close button once it exists. The tab comes from the
    # generated dock registry: the label is the capability's own dockTitle,
    # the pressed state the match of its child route.
    tab = page.get_by_role("button", name="Chat", exact=True)
    expect(tab).to_have_attribute("aria-pressed", "false")
    tab.click()
    expect(tab).to_have_attribute("aria-pressed", "true")
    dock = page.get_by_role("complementary", name="Chat")
    editor = page.locator(".ProseMirror")
    expect(dock).to_be_visible()
    expect(editor).to_be_visible()
    # The open dock is URL state: the child route is the whole of it. No
    # dock param rides along — omit-at-default, like focus.
    assert page.url.split("?")[0].endswith("/chat")
    assert "dock=" not in page.url

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

    tab = page.get_by_role("button", name="Chat", exact=True)
    tab.click()
    expect(page.get_by_role("complementary", name="Chat")).to_be_visible()

    # Opening the dock was a navigation: the browser's back button is a
    # first-class way to close it again — and the tab's pressed state is
    # the route match, so it walks back too.
    page.go_back()
    expect(page.get_by_role("complementary", name="Chat")).to_have_count(0)
    expect(tab).to_have_attribute("aria-pressed", "false")
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

    tab = page.get_by_role("button", name="Chat", exact=True)
    tab.click()
    assert "rail=false" in page.url and "focus=1" in page.url
    assert page.url.split("?")[0].endswith("/chat")
    assert "dock=" not in page.url
    # Focus 1 suppresses the panel whatever the URL holds; the step back
    # brings it back without losing the collapsed rail.
    expect(page.get_by_role("complementary", name="Chat")).to_have_count(0)
    page.keyboard.press("Escape")
    expect(page.get_by_role("complementary", name="Chat")).to_be_visible()
    expect(page.get_by_role("complementary")).to_have_count(1)
    assert "rail=false" in page.url
    # The ride-along pin: the focus step is a search write on whatever route
    # is showing, so stepping back must leave the dock child route in place
    # — not just the panel state at the test's endpoints.
    assert page.url.split("?")[0].endswith("/chat")

    # Closing the tab is the clean way out: back on the novel URL, the
    # collapsed rail intact, and not one dock param left behind — a closed
    # dock leaves a clean URL.
    tab.click()
    expect(page.get_by_role("complementary")).to_have_count(0)
    assert re.search(r"/novels/[^/]+$", page.url.split("?")[0])
    assert "rail=false" in page.url
    assert "dock=" not in page.url

    assert_accessible(page)


def _ask_in_dock(page: Page, tmp_path: Path, title: str, passage: str, question: str) -> None:
    """A novel with a chapter, the dock open, one answered question inside it.

    The module's database is shared, so a test owns its passage, question and
    title the way it owns its novel: identical passages tie in retrieval and
    the answer's five-source limit would drop some other test's document —
    and a title that shares a substring breaks the upload checks' unique
    resolution.
    """
    source = tmp_path / "notizen.txt"
    source.write_text(passage, encoding="utf-8")
    page.goto("http://127.0.0.1:3100/knowledge")
    page.get_by_label("Dokument").set_input_files(str(source))
    page.get_by_label("Titel (optional)").fill(title)
    page.get_by_role("button", name="Hochladen").click()
    expect(page.get_by_text(title)).to_be_visible()

    _open_workspace(page, f"Die {title}")

    page.get_by_role("button", name="Chat", exact=True).click()
    dock = page.get_by_role("complementary", name="Chat")
    expect(dock).to_be_visible()
    dock.get_by_label("Frage").fill(question)
    dock.get_by_role("button", name="Fragen").click()
    expect(dock.get_by_role("region", name="Antwort")).to_contain_text(passage)


def test_an_answer_becomes_a_ghost_the_editor_decides(
    page: Page, stack: Stack, tmp_path: Path
) -> None:
    # The words the answer will quote are this test's own: the ghost, the
    # editor and the reload all assert on them.
    offered = "Die Kaimauer glänzte vom Regen."
    _ask_in_dock(page, tmp_path, "Variantenkarte", offered, "Wie glänzte die Kaimauer?")

    dock = page.get_by_role("complementary", name="Chat")
    editor = page.locator(".ProseMirror")
    editor.click()
    page.keyboard.type("Der Wirt sah zur Tür.")
    expect(page.get_by_text("Gespeichert")).to_be_visible()

    # The completed answer carries its offer: a card that hands the text to
    # the editor — where it is a ghost, not text, until a keypress says so.
    card = dock.get_by_role("region", name="Als Variante übernehmen")
    expect(card).to_be_visible()
    card.get_by_role("button", name="Übernehmen", exact=True).click()

    ghost = editor.locator(".ghost")
    expect(ghost).to_contain_text(offered)
    # The offer is announced — and it is decoration, not document: with the
    # ghost widget stripped from a copy of the editor DOM, not one letter
    # of the offer remains. Only Tab can make it the chapter's text.
    expect(page.locator("[data-live-announcer]")).to_contain_text("Am Cursor wartet ein Vorschlag.")
    document_text = page.evaluate(
        """() => {
          const copy = document.querySelector(".ProseMirror").cloneNode(true);
          copy.querySelectorAll(".ghost").forEach((node) => node.remove());
          return copy.textContent;
        }"""
    )
    assert offered not in document_text
    # The card is spent: its accept cannot offer the same text twice.
    expect(dock.get_by_role("region", name="Als Variante übernehmen")).to_have_count(0)

    page.keyboard.press("Tab")

    expect(editor.locator(".ghost")).to_have_count(0)
    expect(editor).to_contain_text(offered)
    expect(page.locator("[data-live-announcer]")).to_contain_text("Vorschlag übernommen.")

    # The stream ended; the 800 ms debounce writes. Reload is the proof the
    # accept persisted — nothing else writes the chapter.
    page.wait_for_timeout(1500)
    page.reload()
    expect(page.locator(".ProseMirror")).to_contain_text("Der Wirt sah zur Tür.")
    expect(page.locator(".ProseMirror")).to_contain_text(offered)

    assert_accessible(page)


def test_an_offered_ghost_does_not_survive_leaving_the_novel(
    page: Page, stack: Stack, tmp_path: Path
) -> None:
    offered = "Der Fährmann packte die Segel."
    _ask_in_dock(page, tmp_path, "Abschiedsgabe", offered, "Was packte der Fährmann?")

    dock = page.get_by_role("complementary", name="Chat")
    editor = page.locator(".ProseMirror")
    dock.get_by_role("region", name="Als Variante übernehmen").get_by_role(
        "button", name="Übernehmen", exact=True
    ).click()
    expect(editor.locator(".ghost")).to_contain_text(offered)

    # Leaving the novel tears the offer's audience away; coming back must
    # not resurrect it — not as a ghost, and never as unasked-for text.
    page.get_by_role("link", name="Alle Romane").click()
    expect(page.get_by_role("heading", name="Romane")).to_be_visible()
    page.get_by_role("link", name="Die Abschiedsgabe").click()
    expect(page.locator(".ProseMirror")).to_be_visible()

    expect(page.locator(".ProseMirror .ghost")).to_have_count(0)
    expect(page.locator(".ProseMirror")).not_to_contain_text(offered)

    assert_accessible(page)
