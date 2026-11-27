# The German face's own quotes and dashes are the catalog text these tests
# assert literally — intentional characters, not confusable typos.
"""The sources archive on the real stack (W5 Task 7): documents and search.

The upload rides the real multipart door through the page's own picker (the
client-side bounds refuse before the wire — the legs count the POSTs to prove
it), the delete rides the destructive confirm family with the settled list
refetch, and the semantic search round-trips the real query through the fake
embedding's signed feature hash — the server's ordering is the truth, never
an invented score. The disabled areas (view doors, footnote, fact-check)
stay inert in the live browser, and the dark face clears the axe floor.
"""

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

from app.capabilities.knowledge.e2e.conftest import (
    DATABASE,
    create_novel,
    set_theme,
    upload_document,
)
from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.db_rows import rows
from app.kernel.testing.stack import WEB_URL

if TYPE_CHECKING:
    from pathlib import Path

    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

BASE = WEB_URL

# The fake embedding matches words, not meaning: „Der Hafen." shares the
# query's one token at cosine 0.707, the nebula note shares none at 0.0 —
# the ranking the search leg asserts is the server's own ordering.
HAFEN_TEXT = "Der Hafen."
NEBEL_TEXT = "Nebel zog über das Dorf."


def _goto_sources(page: Page, novel_id: str) -> None:
    page.goto(f"{BASE}/novels/{novel_id}/knowledge/sources")
    expect(page.get_by_test_id("sources-page")).to_be_visible()


def _novel_id() -> str:
    return str(create_novel("Das Signal")["id"])


def test_the_upload_round_trip(page: Page, installed: Stack, tmp_path: Path) -> None:
    """The picker's file lands as the server's row — title, real byte size,
    upload date, real chunk count — and the list's meta derives from the
    real titles. The empty archive's invitation is a live upload door."""
    novel_id = _novel_id()
    _goto_sources(page, novel_id)
    expect(page.get_by_test_id("sources-empty")).to_be_visible()

    content = "Mira und Kavic im Hafen.\n\nDer Leuchtturm schwieg."
    file = tmp_path / "Notizen.md"
    file.write_text(content, encoding="utf-8")
    page.get_by_test_id("sources-file-input").set_input_files(str(file))

    document = page.get_by_test_id("sources-document")
    expect(document).to_be_visible()
    expect(document).to_contain_text("Notizen.md")
    expect(document).to_contain_text(f"{len(content.encode('utf-8'))} B")
    expect(document).to_contain_text("Hochgeladen:")
    expect(document).to_contain_text("1 Chunk")
    expect(page.get_by_test_id("sources-file-meta")).to_contain_text("1 Datei (.md)")
    assert rows(DATABASE, "SELECT title, byte_size FROM documents") == [
        ("Notizen.md", len(content.encode("utf-8")))
    ]
    assert rows(DATABASE, "SELECT count(*) FROM chunks") == [(1,)]

    # A second upload through the header door — newest first, the meta grows.
    second = tmp_path / "Zweite.md"
    second.write_text(NEBEL_TEXT, encoding="utf-8")
    page.get_by_test_id("sources-file-input").set_input_files(str(second))
    expect(page.get_by_test_id("sources-document")).to_have_count(2)
    expect(page.get_by_test_id("sources-document").nth(0)).to_contain_text("Zweite.md")
    expect(page.get_by_test_id("sources-file-meta")).to_contain_text("2 Dateien (.md)")


def test_the_size_and_type_refusals_never_send(page: Page, installed: Stack) -> None:
    """The picker mirrors the service's bounds FIRST: an over-large file and
    a binary are refused client-side, named in their own words, and no POST
    leaves the browser. A valid file afterwards still lands."""
    novel_id = _novel_id()
    _goto_sources(page, novel_id)
    posts: list[str] = []
    page.on(
        "request",
        lambda request: (
            posts.append(request.url)
            if request.method == "POST" and "/api/knowledge/documents" in request.url
            else None
        ),
    )

    page.get_by_test_id("sources-file-input").set_input_files(
        {"name": "Riesig.txt", "mimeType": "text/plain", "buffer": b"x" * 1_000_001}
    )
    error = page.get_by_test_id("sources-upload-error")
    expect(error).to_contain_text(
        "Die Datei überschreitet das Limit von 1 MB und wurde nicht aufgenommen."
    )
    assert posts == []

    page.get_by_test_id("sources-file-input").set_input_files(
        {"name": "Bild.png", "mimeType": "image/png", "buffer": b"\x89PNG\r\n\x1a\n"}
    )
    expect(error).to_contain_text(
        "Nur Textdateien (.txt, .md) werden aufgenommen — die Datei wurde nicht gesendet."
    )
    assert posts == []
    expect(page.get_by_test_id("sources-document")).to_have_count(0)

    # The picker recovers: the very next valid file rides the real wire.
    page.get_by_test_id("sources-file-input").set_input_files(
        {"name": "Notiz.txt", "mimeType": "text/plain", "buffer": HAFEN_TEXT.encode("utf-8")}
    )
    expect(page.get_by_test_id("sources-document")).to_have_count(1)
    assert len(posts) == 1


def test_the_delete_confirm_and_the_honest_list(page: Page, installed: Stack) -> None:
    """The destructive family: the consequence named before it happens, the
    safe answer focused, Escape and Abbrechen cancel, the delete refetches
    the list from the server, and the focus lands on the surviving page."""
    novel_id = _novel_id()
    upload_document("Erste Notiz.md", HAFEN_TEXT)
    upload_document("Zweite Notiz.md", NEBEL_TEXT)
    _goto_sources(page, novel_id)
    documents = page.get_by_test_id("sources-document")
    expect(documents).to_have_count(2)
    expect(documents.nth(0)).to_contain_text("Zweite Notiz.md")

    # The confirm names the row and its chunk consequence; the safe answer
    # owns the focus.
    documents.nth(0).get_by_test_id("sources-delete").click()
    dialog = page.get_by_role("alertdialog", name="Dokument löschen?")
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text(
        "„Zweite Notiz.md“ wird mit 1 Chunk gelöscht. Die Suche findet seinen Text nicht wieder."
    )
    assert page.evaluate("document.activeElement?.textContent") == "Abbrechen"

    # Escape cancels; the row stands.
    page.keyboard.press("Escape")
    expect(dialog).to_have_count(0)
    expect(documents).to_have_count(2)

    # Abbrechen cancels too.
    documents.nth(0).get_by_test_id("sources-delete").click()
    dialog.get_by_role("button", name="Abbrechen").click()
    expect(dialog).to_have_count(0)
    expect(documents).to_have_count(2)

    # The delete: the settled list refetches — the server's truth, the
    # chunks cascade, the focus lands on the page root that survives.
    documents.nth(0).get_by_test_id("sources-delete").click()
    dialog.get_by_role("button", name="Löschen", exact=True).click()
    expect(dialog).to_have_count(0)
    expect(documents).to_have_count(1)
    expect(documents.nth(0)).to_contain_text("Erste Notiz.md")
    expect(page.get_by_test_id("sources-file-meta")).to_contain_text("1 Datei (.md)")
    assert page.evaluate("document.activeElement?.id") == "sources-page"
    assert rows(DATABASE, "SELECT title FROM documents") == [("Erste Notiz.md",)]
    assert rows(DATABASE, "SELECT count(*) FROM chunks") == [(1,)]


def test_the_semantic_search_orders_by_the_servers_truth(page: Page, installed: Stack) -> None:
    """The submit fires the real query; the hits carry the rank badge (the
    server's ordering), the document title and the chunk's own words — no
    invented score, no chunk/page meta the contract does not carry."""
    novel_id = _novel_id()
    upload_document("Hafen.md", HAFEN_TEXT)
    upload_document("Nebel.md", NEBEL_TEXT)
    _goto_sources(page, novel_id)

    page.get_by_test_id("sources-search").fill("Hafen")
    page.get_by_test_id("sources-search-button").click()
    hits = page.get_by_test_id("sources-hit")
    expect(hits).to_have_count(2)
    expect(page.get_by_test_id("sources-hit-count")).to_contain_text("2 Treffer gefunden")
    # The shared-token chunk leads — the fake's cosine, the server's order.
    expect(hits.nth(0)).to_contain_text("Rang 1")
    expect(hits.nth(0)).to_contain_text("Hafen.md")
    expect(hits.nth(0)).to_contain_text(f"»{HAFEN_TEXT}«")
    expect(hits.nth(1)).to_contain_text("Rang 2")
    expect(hits.nth(1)).to_contain_text("Nebel.md")
    # No invented percentage rides the results.
    expect(hits.nth(0)).not_to_contain_text("%")
    assert_accessible(page)


def test_the_no_hit_face_names_the_query(page: Page, installed: Stack) -> None:
    """An empty corpus answers the honest no-hit face — the query named,
    never an outage and never an invented result."""
    novel_id = _novel_id()
    _goto_sources(page, novel_id)
    page.get_by_test_id("sources-search").fill("Hafen")
    page.get_by_test_id("sources-search-button").click()
    no_hits = page.get_by_test_id("sources-no-hits")
    expect(no_hits).to_be_visible()
    expect(no_hits).to_contain_text("Keine Treffer für „Hafen“.")


def test_the_disabled_areas_stay_inert(page: Page, installed: Stack) -> None:
    """The view doors, the footnote and the fact-check areas stand disabled
    with the draft's gap note — zero interactive children, no dead promise."""
    novel_id = _novel_id()
    upload_document("Hafen.md", HAFEN_TEXT)
    _goto_sources(page, novel_id)

    view = page.get_by_test_id("sources-view")
    expect(view).to_be_disabled()
    expect(view).to_have_attribute("title", "Noch nicht verfügbar.")
    for testid, label in (
        ("sources-footnote-gap", "Automatische Fußnoten- & Zitatverknüpfung ins Manuskript"),
        ("sources-factcheck-gap", "Automatisierter Faktencheck & Kausalitäts-Abgleich"),
    ):
        gap = page.get_by_test_id(testid)
        expect(gap).to_have_attribute("aria-disabled", "true")
        expect(gap).to_contain_text(label)
        expect(gap).to_contain_text("Noch nicht verfügbar.")
        expect(gap.get_by_role("button")).to_have_count(0)

    # The hit card's original door is the same honest gap.
    page.get_by_test_id("sources-search").fill("Hafen")
    page.get_by_test_id("sources-search-button").click()
    original = page.get_by_test_id("sources-open-original")
    expect(original).to_be_disabled()
    expect(original).to_have_attribute("title", "Noch nicht verfügbar.")


def test_the_dark_sources_face_clears_the_axe_floor(page: Page, installed: Stack) -> None:
    """The archive with standing hits on the tokens' dark halves — the same
    WCAG A/AA floor the light face clears."""
    set_theme("dark")
    novel_id = _novel_id()
    upload_document("Hafen.md", HAFEN_TEXT)
    _goto_sources(page, novel_id)
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    page.get_by_test_id("sources-search").fill("Hafen")
    page.get_by_test_id("sources-search-button").click()
    expect(page.get_by_test_id("sources-hit")).to_have_count(1)
    assert_accessible(page)
