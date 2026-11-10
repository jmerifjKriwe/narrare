"""The knowledge page: one upload dialog, search, and the honest outage.

The browser, the API and Postgres with pgvector are the real ones; only the
embedding provider is behind its boundary, served by a local stand-in whose
width the test flips — exactly what a user changing models does. The flows
this module carries: the documents area is one panel behind one "+ Dokument"
control; an uploaded passage comes back from search; a model change refuses
search until the documents are re-embedded; a refused re-embed names itself
and its retry heals; a dead local service — on load, or under an upload —
reads as an outage, never as an empty library or a silent dialog. The
documents list states what it holds — size, passages, date — and a wrong
upload can be deleted for good, passages and all.
"""

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING

import httpx
import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.db import testsupport
from app.kernel.db.testsupport import url_for
from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.jobs import wait_for_job
from app.kernel.testing.stack import API_URL, WEB_URL
from app.kernel.testing.viewport import assert_page_fits

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack
    from app.kernel.testing.vendor import EmbeddingsVendor

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

TEXT = "Der Leuchtturm am Horizont war seit Jahren dunkel.\n\nNiemand im Dorf sprach noch über ihn."


def _upload(page: Page, source: Path, title: str | None) -> None:
    """Upload one document through the one "+ Dokument" dialog.

    The page holds exactly one control that opens the upload form; the
    dialog owns the fields and stays open on a refusal.
    """
    page.get_by_role("button", name="+ Dokument").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Dokument").set_input_files(str(source))
    if title is not None:
        dialog.get_by_label("Titel (optional)").fill(title)
    dialog.get_by_role("button", name="Hochladen").click()
    expect(page.get_by_role("dialog")).to_have_count(0)


def test_the_documents_area_is_one_panel_with_one_upload_control(
    page: Page, stack: Stack, tmp_path: Path
) -> None:
    """The documents area is a Panel list with exactly one "+ Dokument" control.

    The upload form lives behind the dialog, not on the page: the page
    must not carry a second way to upload, and the list must carry its
    heading so the area is nameable.
    """
    page.goto(f"{WEB_URL}/knowledge")
    expect(page.get_by_role("heading", name="Dokumente")).to_be_visible()
    expect(page.get_by_role("button", name="+ Dokument")).to_have_count(1)

    source = tmp_path / "notizen.txt"
    source.write_text(TEXT, encoding="utf-8")
    _upload(page, source, "Notizen")
    expect(page.get_by_text("Notizen")).to_be_visible()

    assert_accessible(page)


def test_uploaded_passage_is_returned_by_search(page: Page, stack: Stack, tmp_path: Path) -> None:
    source = tmp_path / "notizen.txt"
    source.write_text(TEXT, encoding="utf-8")

    page.goto(f"{WEB_URL}/knowledge")
    _upload(page, source, "Notizen")
    expect(page.get_by_text("Notizen")).to_be_visible()

    page.get_by_label("Suchbegriff").fill("Leuchtturm")
    page.get_by_role("button", name="Suchen").click()
    expect(page.get_by_text("Der Leuchtturm am Horizont war seit Jahren dunkel.")).to_be_visible()

    assert_accessible(page)


def test_a_model_change_is_refused_and_reembedding_restores_search(
    page: Page, vendor: EmbeddingsVendor, stack: Stack, tmp_path: Path
) -> None:
    source = tmp_path / "notizen.txt"
    source.write_text(TEXT, encoding="utf-8")

    page.goto(f"{WEB_URL}/knowledge")
    _upload(page, source, None)
    expect(page.get_by_text("notizen.txt")).to_be_visible()

    # The user switches models: the vendor answers another width from now on.
    vendor.set_width(768)

    page.get_by_label("Suchbegriff").fill("Leuchtturm")
    page.get_by_role("button", name="Suchen").click()
    expect(page.get_by_text("Das Embedding-Modell hat sich geändert")).to_be_visible()

    page.get_by_role("button", name="Dokumente neu einbetten").click()
    expect(page.get_by_text("Das Embedding-Modell hat sich geändert")).not_to_be_visible()

    page.get_by_role("button", name="Suchen").click()
    expect(page.get_by_text("Der Leuchtturm am Horizont war seit Jahren dunkel.")).to_be_visible()

    assert_accessible(page)


def test_a_refused_reembed_names_itself_and_the_retry_heals(
    page: Page, vendor: EmbeddingsVendor, stack: Stack, tmp_path: Path
) -> None:
    """A re-embed that does not happen must say so (F15).

    The old page returned silently on a refused re-embed: the model-change
    warning stood forever and nothing said the repair had failed. The
    refusal is an alert beside the warning, and the notice's retry is the
    way back once the local service answers again.
    """
    source = tmp_path / "notizen.txt"
    source.write_text(TEXT, encoding="utf-8")

    page.goto(f"{WEB_URL}/knowledge")
    _upload(page, source, None)
    expect(page.get_by_text("notizen.txt")).to_be_visible()

    vendor.set_width(768)
    page.get_by_label("Suchbegriff").fill("Leuchtturm")
    page.get_by_role("button", name="Suchen").click()
    expect(page.get_by_text("Das Embedding-Modell hat sich geändert")).to_be_visible()

    # The local service dies mid-flow: the re-embed cannot happen.
    stack.stop_api()
    try:
        page.get_by_role("button", name="Dokumente neu einbetten").click()
        expect(page.get_by_role("alert").filter(has_text="fehlgeschlagen")).to_be_visible()
    finally:
        stack.start_api()

    # The retry on the notice is the way back: the repair runs, the
    # warning retires, and search speaks again.
    page.get_by_role("button", name="Erneut versuchen").click()
    expect(page.get_by_text("Das Embedding-Modell hat sich geändert")).not_to_be_visible()
    page.get_by_role("button", name="Suchen").click()
    expect(page.get_by_text("Der Leuchtturm am Horizont war seit Jahren dunkel.")).to_be_visible()

    assert_accessible(page)


def test_an_upload_against_a_dead_service_names_itself(
    page: Page, stack: Stack, tmp_path: Path
) -> None:
    """An upload against a dead local service says so inside the dialog.

    The request is aborted at the network boundary — what the browser
    really sees when the local service is gone, whatever a dev proxy
    answers on its behalf — so the fetch rejects and only the page's own
    catch can answer. The dialog stays open — the typed work is the
    user's — and the danger notice names the upload's refusal where the
    retry (the same button) sits. A silent dialog would leave the writer
    reading an upload that quietly never happened.
    """
    source = tmp_path / "notizen.txt"
    source.write_text(TEXT, encoding="utf-8")

    page.goto(f"{WEB_URL}/knowledge")
    stack.stop_api()
    try:
        page.get_by_role("button", name="+ Dokument").click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_label("Dokument").set_input_files(str(source))
        # The abort makes the refusal bite: without it the dev proxy
        # resolves a 502, which the response branch alone could answer.
        page.route("**/api/knowledge/documents", lambda route: route.abort())
        dialog.get_by_role("button", name="Hochladen").click()
        expect(
            dialog.get_by_role("alert").filter(has_text="Hochladen fehlgeschlagen")
        ).to_be_visible()
        # The dialog stays open with its fields, so nothing typed is lost.
        expect(dialog.get_by_label("Dokument")).to_be_visible()
    finally:
        stack.start_api()

    assert_accessible(page)


def test_a_dead_service_on_load_names_the_outage(page: Page, stack: Stack) -> None:
    """An unreachable API on /knowledge reads as an outage, never as empty (F14).

    The old page read the failed load as "Noch keine Dokumente" — the empty
    state worn as a mask over a missing answer. The outage is an alert with
    a working retry; the empty claim must stay silent.
    """
    page.goto(f"{WEB_URL}/knowledge")
    expect(page.get_by_text("Noch keine Dokumente")).to_be_visible()

    stack.stop_api()
    try:
        page.reload()
        expect(
            page.get_by_role("alert").filter(has_text="Dokumente konnten nicht geladen")
        ).to_be_visible()
        # The empty state must not stand in for the missing answer.
        expect(page.get_by_text("Noch keine Dokumente")).to_have_count(0)
    finally:
        stack.start_api()

    # Recovery through the notice's retry: the honest answer again, no
    # alert left standing.
    page.get_by_role("button", name="Erneut versuchen").click()
    expect(page.get_by_text("Noch keine Dokumente")).to_be_visible()
    expect(page.get_by_role("alert")).to_have_count(0)

    assert_accessible(page)


def _rows(statement: str, params: dict[str, object] | None = None) -> list[tuple[object, ...]]:
    """Rows from the stack's database as plain tuples, in a worker thread.

    The novels suite's own reader, copied local — a shared helper across
    the capability suites is parked as a follow-up, and this copy keeps
    its place until then. The worker thread because pytest-asyncio keeps
    a session loop running and asyncio.run refuses a second one in the
    same thread.
    """
    database = testsupport.test_database("narrare_v2_knowledge_e2e")

    async def run() -> list[tuple[object, ...]]:
        engine = create_async_engine(url_for(database))
        try:
            async with engine.connect() as connection:
                return [
                    tuple(each) for each in await connection.execute(text(statement), params or {})
                ]
        finally:
            await engine.dispose()

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, run()).result()


def _document_id(page: Page, title: str) -> str:
    """The uploaded document's id, read through the API the way a second device would."""
    response = page.request.get(f"{API_URL}/api/knowledge/documents")
    assert response.ok, response.text()
    matches = [str(row["id"]) for row in response.json() if row["title"] == title]
    assert len(matches) == 1, matches
    return matches[0]


def test_the_empty_state_names_text_files_up_to_one_megabyte(page: Page, stack: Stack) -> None:
    """The empty state is the library's own invitation, and it names the shelf.

    What the server holds is text files up to 1 MB — the endpoint weighs
    bytes, not names, so the invitation promises no extension and the
    writer does not learn a rule the server never had.
    """
    page.goto(f"{WEB_URL}/knowledge")
    empty = page.get_by_text("Noch keine Dokumente")
    expect(empty).to_be_visible()
    expect(empty).to_contain_text("Textdateien bis 1 MB")

    assert_accessible(page)


def test_deleting_a_document_removes_its_passages_from_search(
    page: Page, stack: Stack, tmp_path: Path
) -> None:
    """The confirmed delete is final exactly where it says it is.

    The passages answered search before anything died — their later
    absence is the delete's doing, not a corpus that never held them.
    The row's own control opens a warning that says the one thing a
    writer needs before confirming: this is final, and the original file
    on disk stays. After the confirm the same words find nothing, the
    row leaves the list, and the database holds no chunk of the document
    — the cascade is proven, not presumed.
    """
    source = tmp_path / "notizen.txt"
    source.write_text(TEXT, encoding="utf-8")

    page.goto(f"{WEB_URL}/knowledge")
    _upload(page, source, "Notizen")
    expect(page.get_by_text("Notizen")).to_be_visible()

    # The row states what it holds — the stored size (plain bytes under a
    # thousand), the passages it answers search with, the day it came in —
    # before any of it is asked to die.
    row = page.get_by_role("button", name="Notizen löschen").locator("..")
    expect(row).to_contain_text(re.compile(r"\d+ B"))
    expect(row).to_contain_text(re.compile(r"Passagen?"))
    expect(row).to_contain_text("Hochgeladen am")

    # The corpus answers BEFORE the delete: the passage is findable, and
    # the document owns its chunks in the database.
    page.get_by_label("Suchbegriff").fill("Leuchtturm")
    page.get_by_role("button", name="Suchen").click()
    expect(page.get_by_text("Der Leuchtturm am Horizont war seit Jahren dunkel.")).to_be_visible()
    document_id = _document_id(page, "Notizen")
    # The document owned passages before anything died: the zero the test
    # asserts after the delete is about rows that existed.
    assert _rows("SELECT count(*) FROM chunks WHERE document_id = :id", {"id": document_id}) != [
        (0,)
    ]

    # The row's own control opens the warning; the open dialog is on the
    # accessibility floor too, because focus containment and the warning's
    # name are exactly what a closed page cannot show.
    page.get_by_role("button", name="Notizen löschen").click()
    dialog = page.get_by_role("dialog", name="Dokument löschen")
    expect(dialog).to_contain_text("Originaldatei bleibt")
    assert_accessible(page)

    # The confirm is one press and final: the dialog closes, the same
    # words find nothing, the list has lost the row, and not one chunk of
    # the document lives in the database.
    dialog.get_by_role("button", name="Löschen", exact=True).click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    page.get_by_role("button", name="Suchen").click()
    expect(page.get_by_text("Keine Treffer")).to_be_visible()
    expect(page.get_by_text("Notizen")).to_have_count(0)
    assert _rows("SELECT count(*) FROM chunks WHERE document_id = :id", {"id": document_id}) == [
        (0,)
    ]

    assert_accessible(page)


def test_one_documents_row_keeps_its_height_and_fits_a_phone(
    page: Page, stack: Stack, tmp_path: Path
) -> None:
    """A document's row states its facts without demanding height or width.

    On a desk the row is one line at the 28 px control height — the size
    the loading skeleton already paints, so the answer's arrival moves
    nothing. At a phone's 360 px the facts and the trigger are content,
    not chrome: the row wraps them under the title instead of
    manufacturing a sideways scroll inside the shell's box — the fit
    floor measures the box, not a screenshot.
    """
    source = tmp_path / "notizen.txt"
    source.write_text(TEXT, encoding="utf-8")

    page.goto(f"{WEB_URL}/knowledge")
    _upload(page, source, "Notizen")
    expect(page.get_by_text("Notizen")).to_be_visible()

    # One line, one control's height: the row the skeleton promised.
    row = page.get_by_role("button", name="Notizen löschen").locator("..")
    page.set_viewport_size({"width": 1280, "height": 720})
    assert row.evaluate("element => element.clientHeight") == 28

    page.set_viewport_size({"width": 360, "height": 720})
    assert_page_fits(page)

    assert_accessible(page)


def _seed_graph_novel() -> tuple[str, str, str]:
    """A novel with two accepted entities joined by one edge, through the API.

    The entities enter the world the only way they can — the extraction
    job over a real chapter, and the review's accept — and the edge rides
    the real relation create. Returns the novel's id and the two entity
    names, the words the canvas must then show.
    """
    with httpx.Client(base_url=API_URL, timeout=30) as api:
        novel = api.post("/api/writing/novels", json={"title": "Die graphische Bucht"})
        novel.raise_for_status()
        novel_id = novel.json()["id"]
        chapter = api.post(f"/api/writing/novels/{novel_id}/chapters", json={"title": "Ankunft"})
        chapter.raise_for_status()
        chapter_id = chapter.json()["id"]
        saved = api.put(
            f"/api/writing/chapters/{chapter_id}",
            json={"body": "Mira betrat das alte Haus am See. Draußen schwieg der Leuchtturm."},
        )
        saved.raise_for_status()
        enqueued = api.post(
            f"/api/knowledge/extraction/{novel_id}", json={"chapter_id": chapter_id}
        )
        enqueued.raise_for_status()
        job = wait_for_job(api, enqueued.json()["job_id"])
        assert job["status"] == "done"
        suggestions = api.get(f"/api/knowledge/novels/{novel_id}/suggestions")
        suggestions.raise_for_status()
        assert len(suggestions.json()) >= 2
        first = api.post(f"/api/knowledge/suggestions/{suggestions.json()[0]['id']}/accept")
        first.raise_for_status()
        second = api.post(f"/api/knowledge/suggestions/{suggestions.json()[1]['id']}/accept")
        second.raise_for_status()
        listed = api.get(f"/api/knowledge/novels/{novel_id}/entities")
        listed.raise_for_status()
        names = [row["name"] for row in listed.json()]
        assert len(names) == 2
        edge = api.post(
            f"/api/knowledge/entities/{listed.json()[0]['id']}/relations",
            json={"to_entity_id": listed.json()[1]["id"], "relation_type": "friend_of"},
        )
        edge.raise_for_status()
    return novel_id, names[0], names[1]


def test_the_graph_canvas_shows_two_entities_and_their_edge(page: Page, stack: Stack) -> None:
    """The full-page canvas: two nodes, the line between them, the detail.

    The entry rides the knowledge page's own link — no novel is named
    there, so the canvas first asks which book to draw and then draws
    exactly what the seed filed: both names on the canvas, the one edge
    as its line, the whole novel accounted for in the showing note. A
    click selects: the detail reads the entity's words and the edge in
    German, and the only door out names the dock — the canvas never
    writes. At a desk's 1280 px the canvas owns the page without widening
    it: no horizontal scrollbar on the document.
    """
    novel_id, first, second = _seed_graph_novel()

    page.goto(f"{WEB_URL}/knowledge")
    page.get_by_role("link", name="Im Graphen öffnen").click()
    expect(page).to_have_url(re.compile(r"/knowledge/graph"))
    # No novel named yet: the canvas asks which book, it does not guess.
    page.get_by_role("link", name="Die graphische Bucht").click()
    expect(page).to_have_url(f"{WEB_URL}/knowledge/graph?novel={novel_id}")

    expect(page.get_by_role("heading", name="Entitätengraph")).to_be_visible()
    expect(page.get_by_role("button", name=first)).to_be_visible()
    expect(page.get_by_role("button", name=second)).to_be_visible()
    expect(page.locator("svg line")).to_have_count(1)
    expect(page.get_by_text("Zeigt 2 von 2 Entitäten · 1 von 1 Beziehungen")).to_be_visible()

    page.get_by_role("button", name=first).click()
    detail = page.get_by_role("region", name=first)
    expect(detail).to_contain_text(f"{second} · Befreundet mit")
    expect(detail.get_by_role("link", name="Im Dock bearbeiten")).to_have_attribute(
        "href", re.compile(r"/novels/.+/knowledge\?entity=.+")
    )
    expect(detail.get_by_role("button")).to_have_count(0)

    page.set_viewport_size({"width": 1280, "height": 800})
    assert page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth") <= 0
    # The shell scrolls inside #main (P8): a canvas wider than the page
    # would scroll there while the document stays viewport-wide, so the
    # document face alone cannot fail — width only, the page's own
    # vertical scroll stays allowed by design. The +1 is sub-pixel
    # rounding, the viewport floor's own tolerance.
    main = page.evaluate(
        "() => { const main = document.getElementById('main');"
        " return main === null ? null :"
        " { scroll: main.scrollWidth, client: main.clientWidth }; }"
    )
    assert main is not None
    assert main["scroll"] <= main["client"] + 1

    assert_accessible(page)
