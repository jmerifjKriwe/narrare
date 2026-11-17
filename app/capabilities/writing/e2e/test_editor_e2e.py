"""The editor goes real (W4 Task 12): browser, API, Postgres.

The scene's prose is edited through TipTap and debounced into the scene's
PUT; the one save-status owner feeds the editor foot, the topbar chip and
the rail sync dot alike. A refused write is named beside the text and never
worn as „gesichert"; the body it carried stays in memory and a retry lands
it against the recovered service — proven on the real stack, outage included
(``Stack.stop_api`` is the refusal, nothing simulated). Leaving with a body
that never reached the server asks first: a scene switch and a route leave
pass the flush gate and raise the states sheet's Abschiedsschutz (Kachel 10)
after their flush fails, and a reload mid-failure meets the browser's own
unload prompt. Every face clears the axe WCAG A/AA floor, light and dark.
"""

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Dialog, Page, expect

from app.capabilities.writing.e2e.conftest import (
    create_chapter,
    create_novel,
    set_theme,
    write_scene,
)
from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.stack import WEB_URL

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

BASE = WEB_URL
PROSE = "Szenenprosa"  # the textbox's accessible name (editor.proseLabel)


def _seed_scene(title: str = "Die Szene", body: str = "") -> tuple[str, str]:
    """One book, one chapter, one scene — return (novel_id, scene_id)."""
    novel = create_novel("Das Editor-Buch")
    chapter = create_chapter(str(novel["id"]), "Erstes Kapitel")
    scene = write_scene(str(chapter["id"]), body, title=title)
    return str(novel["id"]), str(scene["id"])


def _open(page: Page, novel_id: str) -> None:
    page.goto(f"{BASE}/novels/{novel_id}")
    expect(page.get_by_role("heading", level=1)).to_be_visible()


def _type(page: Page, text: str) -> None:
    page.get_by_role("textbox", name=PROSE).click()
    page.keyboard.type(text)


def test_typing_autosaves_and_survives_a_reload(page: Page, installed: Stack) -> None:
    """type → the engaged indicator → the landed save → the row after reload.
    The foot's live count moves with the writing; the chrome's chip and the
    rail dot rest green once the server answered."""
    novel_id, scene_id = _seed_scene()
    _open(page, novel_id)

    # A clean workspace rests at the green face before a word is typed.
    expect(page.get_by_text("Automatisch gesichert")).to_be_visible()
    expect(page.locator("header").get_by_text("Gespeichert")).to_be_visible()

    with page.expect_response(
        lambda r: f"/api/writing/scenes/{scene_id}" in r.url and r.request.method == "PUT"
    ) as saved:
        _type(page, "Der erste Satz.")
        # The engaged indicator stands while the debounce runs (Kachel 9's pill).
        expect(page.get_by_text("Ungesicherte Änderungen")).to_be_visible()
    assert saved.value.ok

    # The landed save: the foot's live count, the green faces, no failure.
    expect(page.get_by_text("3 Wörter im Gesamtabschnitt")).to_be_visible()
    expect(page.get_by_text("Automatisch gesichert")).to_be_visible()
    expect(page.locator("header").get_by_text("Gespeichert")).to_be_visible()
    expect(page.get_by_text("Ungesicherte Änderungen")).to_have_count(0)
    # The tree's scene count follows the saved row (the invalidation family).
    expect(page.get_by_text("3 W.").first).to_be_visible()

    # The row, not the in-memory body: a reload carries the words.
    page.reload()
    expect(page.get_by_role("textbox", name=PROSE)).to_contain_text("Der erste Satz.")
    assert_accessible(page)


def test_a_refused_save_is_named_and_retries(page: Page, installed: Stack) -> None:
    """The outage names the failure beside the text and in the chrome; the
    body stays in the editor, Wiederholen lands it after recovery, and the
    row survives the reload."""
    novel_id, _scene_id = _seed_scene()
    _open(page, novel_id)

    installed.stop_api()
    try:
        _type(page, "Den niemand speichert.")
        expect(page.get_by_text("Automatische Sicherung fehlgeschlagen")).to_be_visible(
            timeout=10_000
        )
        expect(page.get_by_text("Wiederholen")).to_be_visible()
        expect(page.locator("header").get_by_text("Sicherung fehlgeschlagen")).to_be_visible()
        expect(page.get_by_text("Automatisch gesichert")).to_have_count(0)
        # The failure face clears the axe floor before the retry.
        assert_accessible(page)
    finally:
        installed.start_api()

    # The retry re-sends the body still held in the editor.
    page.get_by_role("button", name="Wiederholen").click()
    expect(page.get_by_text("Automatisch gesichert")).to_be_visible(timeout=10_000)
    expect(page.locator("header").get_by_text("Gespeichert")).to_be_visible()

    page.reload()
    expect(page.get_by_role("textbox", name=PROSE)).to_contain_text("Den niemand speichert.")
    assert_accessible(page)


def test_leaving_with_a_failed_save_asks_first(page: Page, installed: Stack) -> None:
    """A scene switch and a route leave flush first; only the failed write
    raises the Abschiedsschutz. Bleiben keeps the work, Verwerfen und
    verlassen drops it and goes — the honest second step."""
    novel = create_novel("Das Schutz-Buch")
    novel_id = str(novel["id"])
    chapter = create_chapter(novel_id, "Erstes Kapitel")
    write_scene(str(chapter["id"]), "", title="Die erste")
    write_scene(str(chapter["id"]), "", title="Die zweite")
    _open(page, novel_id)
    # The last-created scene leads — „Die zweite".
    expect(page.get_by_role("heading", name="Die zweite", exact=True)).to_be_visible()

    installed.stop_api()
    try:
        _type(page, "Bleibt hier.")
        expect(page.get_by_text("Automatische Sicherung fehlgeschlagen")).to_be_visible(
            timeout=10_000
        )

        # A scene switch flushes, fails, asks. Bleiben keeps the scene + text.
        page.get_by_role("button", name=re.compile("Szene 1 · Die erste")).click()
        guard = page.get_by_role("alertdialog")
        expect(guard).to_be_visible(timeout=10_000)
        expect(guard.get_by_text("Ungesicherte Änderungen verlassen?")).to_be_visible()
        assert_accessible(page)
        guard.get_by_role("button", name="Bleiben").click()
        expect(guard).to_have_count(0)
        expect(page.get_by_role("heading", name="Die zweite", exact=True)).to_be_visible()
        expect(page.get_by_role("textbox", name=PROSE)).to_contain_text("Bleibt hier.")

        # A route leave (the topbar's Manuscripts link) asks the same way.
        page.locator("header").get_by_role("link", name="Manuscripts").click()
        guard = page.get_by_role("alertdialog")
        expect(guard).to_be_visible(timeout=10_000)
        guard.get_by_role("button", name="Bleiben").click()
        expect(guard).to_have_count(0)
        expect(page.get_by_role("heading", name="Die zweite", exact=True)).to_be_visible()

        # Verwerfen und verlassen drops the draft and switches scenes.
        page.get_by_role("button", name=re.compile("Szene 1 · Die erste")).click()
        guard = page.get_by_role("alertdialog")
        expect(guard).to_be_visible(timeout=10_000)
        guard.get_by_role("button", name="Verwerfen und verlassen").click()
        expect(page.get_by_role("heading", name="Die erste", exact=True)).to_be_visible()
        expect(guard).to_have_count(0)
    finally:
        installed.start_api()

    # The discarded words never reached the server: the first scene is empty.
    page.reload()
    expect(page.get_by_role("textbox", name=PROSE)).to_have_text("")
    assert_accessible(page)


def test_closing_a_tab_with_a_failed_save_asks(page: Page, installed: Stack) -> None:
    """The unload prompt fires only while the scene holds text the server
    lacks — a clean reload asks nothing, a failed body meets the browser's
    own beforeunload dialog (a reload runs the handlers; page.close skips
    them on this build)."""
    novel_id, _scene_id = _seed_scene()
    _open(page, novel_id)

    seen: list[str] = []

    def accept(dialog: Dialog) -> None:
        seen.append(dialog.type)
        dialog.accept()

    page.on("dialog", accept)

    # The negative control: a clean scene reloads with no dialog at all.
    page.reload()
    expect(page.get_by_role("textbox", name=PROSE)).to_be_visible()
    assert seen == []

    installed.stop_api()
    try:
        _type(page, "Nicht verlieren.")
        expect(page.get_by_text("Automatische Sicherung fehlgeschlagen")).to_be_visible(
            timeout=10_000
        )
        # The reload leaves the page; the browser's own dialog answers for the
        # text that never reached the server. Accepting lets it through; the
        # fresh page loads against the stopped service and names it.
        page.reload()
        expect(page.get_by_role("alert")).to_be_visible(timeout=10_000)
        assert seen == ["beforeunload"]
    finally:
        installed.start_api()


def test_the_dark_editor_face_clears_the_axe_floor(page: Page, installed: Stack) -> None:
    """The dark face edits and saves on the tokens' dark halves and clears
    the same axe floor the light face rides."""
    set_theme("dark")
    novel_id, scene_id = _seed_scene()
    _open(page, novel_id)
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")

    with page.expect_response(
        lambda r: f"/api/writing/scenes/{scene_id}" in r.url and r.request.method == "PUT"
    ):
        _type(page, "Im Dunkeln geschrieben.")
    expect(page.get_by_text("Automatisch gesichert")).to_be_visible()
    assert_accessible(page)

    # The dark failure face and the amber pill clear the same floor.
    installed.stop_api()
    try:
        _type(page, " Und ein Wort zu viel.")
        expect(page.get_by_text("Automatische Sicherung fehlgeschlagen")).to_be_visible(
            timeout=10_000
        )
        expect(page.get_by_text("Ungesicherte Änderungen")).to_be_visible()
        assert_accessible(page)
    finally:
        installed.start_api()
