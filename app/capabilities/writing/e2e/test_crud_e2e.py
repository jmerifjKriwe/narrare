"""The tree's CRUD goes live (W4 Task 13): browser, API, Postgres.

Every test opens on a freshly installed instance (``e2e/conftest.py``) and
seeds exactly the population it asserts on through the writing API. The
create flow walks D16's canonical path — empty book → first chapter (zero
scenes) → the empty-chapter face → first scene → the editor — and the
tree's counts go live with the landed save (the invalidation family, no
reload). Reorder rides REAL HTML5 drag at both levels (the draft's grips;
the focused grip's arrow-key step is the keyboard's own drag, unit-proven)
and persists; a second tab's addition makes the whole-set PUT stale, and
the 409's stored ids surface honestly — the tree reconciles to the current
truth, the notice's retry asks it again, never re-sends the stale order.
The last scene's delete leaves the chapter empty (D16), the chapter's
delete cascades its scenes after the confirm names the loss, and rename +
metadata round-trip through the dialogs (the labels present-and-nullable).
Every face clears the axe WCAG A/AA floor, light and dark.
"""

from typing import TYPE_CHECKING

import httpx
import pytest
from playwright.sync_api import Locator, Page, expect

from app.capabilities.writing.e2e.conftest import (
    create_chapter,
    create_novel,
    set_theme,
    word_body,
    write_scene,
)
from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.stack import API_URL, WEB_URL

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

BASE = WEB_URL
PROSE = "Szenenprosa"  # the textbox's accessible name (editor.proseLabel)
CONFLICT_NOTE = "Die Struktur wurde anderswo geändert — der Baum zeigt den aktuellen Stand."


def _open(page: Page, novel_id: str) -> None:
    page.goto(f"{BASE}/novels/{novel_id}")
    # The ready-state surface, not any h1: the loading skeleton carries an
    # sr-only heading Playwright counts as visible (a 1x1 box), and a gate
    # on it would race the scene reads — an API seed landing mid-fetch
    # would join the initial answer instead of staying a second tab's truth.
    expect(
        page.get_by_test_id("explorer-tree").or_(page.get_by_test_id("explorer-empty-book"))
    ).to_be_visible()


def _scene_ids(chapter_id: str) -> list[str]:
    """The stored scene order — the server's truth, read through the API."""
    with httpx.Client(base_url=API_URL, timeout=30.0) as client:
        response = client.get(f"/api/writing/chapters/{chapter_id}/scenes")
    response.raise_for_status()
    return [scene["id"] for scene in response.json()]


def _chapter_ids(novel_id: str) -> list[str]:
    with httpx.Client(base_url=API_URL, timeout=30.0) as client:
        response = client.get(f"/api/writing/novels/{novel_id}/chapters")
    response.raise_for_status()
    return [chapter["id"] for chapter in response.json()]


def _drag_below(grip: Locator, target: Locator) -> None:
    """Drag the grip onto the target's LOWER half — the insertion edge is
    the midpoint, and a center drop on fractional layout can land a hair
    above it (a no-op order, honestly no write). The lower half is the
    unambiguous „after the target" ask."""
    box = target.bounding_box()
    assert box is not None
    grip.drag_to(target, target_position={"x": box["width"] / 2, "y": box["height"] - 4})


def _row_menu(page: Page, testid: str, options: str) -> None:
    """Open the row's options menu (the trigger reveals on hover). The
    name is exact: a chapter card contains its scenes' menus too."""
    row = page.get_by_test_id(testid)
    row.hover()
    row.get_by_role("button", name=options, exact=True).click()


def test_create_chapter_then_scene_and_the_counts_go_live(page: Page, installed: Stack) -> None:
    """D16's canonical path end to end: the invitation creates the chapter
    (zero scenes), the empty-chapter face creates the scene, the typing
    lands and the tree's counts move with it — no reload. A second chapter
    from the tree door starts empty too."""
    novel = create_novel("Das CRUD-Buch")
    novel_id = str(novel["id"])
    _open(page, novel_id)
    expect(page.get_by_role("heading", name="Ein unbeschriebenes Werk")).to_be_visible()
    assert_accessible(page)

    # The invitation door → the chapter with zero scenes → Kachel 4's face.
    page.get_by_role("button", name="+ Erstes Kapitel anlegen").click()
    expect(page.get_by_role("heading", name="Erste Szene starten")).to_be_visible()
    expect(page.get_by_text("Kapitel 1 — Unbenanntes Kapitel")).to_be_visible()
    expect(page.get_by_text("Keine Szenen angelegt")).to_be_visible()
    assert_accessible(page)

    # Kachel 4's door → the scene, born empty, the editor open on it.
    page.get_by_role("button", name="+ Szene 1 anlegen").click()
    box = page.get_by_role("textbox", name=PROSE)
    expect(box).to_be_visible()
    expect(page.get_by_role("heading", name="Unbenannte Szene", exact=True)).to_be_visible()

    # Type → the landed save → the tree's live counts (the invalidation
    # family: scene row, chapter Σ, the book total, the topbar chip).
    with page.expect_response(
        lambda r: "/api/writing/scenes/" in r.url and r.request.method == "PUT"
    ) as saved:
        box.click()
        page.keyboard.type("Der erste Satz.")
    assert saved.value.ok
    expect(page.get_by_text("3 Wörter im Gesamtabschnitt")).to_be_visible()
    expect(page.get_by_text("3 W.").first).to_be_visible()
    expect(page.get_by_text("Gesamt: 3 W.")).to_be_visible()
    expect(page.locator("header").get_by_text("3 Wörter")).to_be_visible()
    assert_accessible(page)

    # The tree's chapter door: a second chapter, zero scenes, selected —
    # the empty-chapter face again (no auto-created scene).
    page.get_by_role("button", name="Neues Kapitel", exact=True).click()
    expect(page.get_by_text("Kapitel 2 — Unbenanntes Kapitel")).to_be_visible()
    expect(page.get_by_role("heading", name="Erste Szene starten")).to_be_visible()
    assert _chapter_ids(novel_id) and len(_chapter_ids(novel_id)) == 2

    # The words survive the reload — the row, not the in-memory body.
    page.reload()
    expect(page.get_by_role("textbox", name=PROSE)).to_contain_text("Der erste Satz.")
    assert_accessible(page)


def test_reorder_both_levels_by_real_drag(page: Page, installed: Stack) -> None:
    """The draft's grips drag for real: a scene within its chapter, a
    chapter on the rail — each PUTs the whole set, each order survives the
    reload. (The focused grip's arrow keys are the keyboard's own drag,
    proven in the unit suite; the draft draws no keyboard affordance.)"""
    novel = create_novel("Das Reihenfolge-Buch")
    novel_id = str(novel["id"])
    chapter1 = create_chapter(novel_id, "Erstes")
    chapter2 = create_chapter(novel_id, "Zweites")
    c1, c2 = str(chapter1["id"]), str(chapter2["id"])
    alpha = write_scene(c1, word_body(3), title="Alpha")
    beta = write_scene(c1, word_body(4), title="Beta")
    write_scene(c2, word_body(5), title="Gamma")
    _open(page, novel_id)

    # Scene level: drag Alpha's grip onto Beta's row — Beta leads after.
    grip = page.get_by_role("button", name="Szene 1 in Kapitel 1 verschieben", exact=True)
    target = page.get_by_test_id(f"tree-scene-{beta['id']}")
    with page.expect_response(
        lambda r: f"/api/writing/chapters/{c1}/scene-order" in r.url and r.request.method == "PUT"
    ) as moved:
        _drag_below(grip, target)
    assert moved.value.status == 204
    card = page.get_by_test_id(f"tree-chapter-{c1}")
    expect(card.get_by_text("Szene 1 · Beta")).to_be_visible()
    expect(card.get_by_text("Szene 2 · Alpha")).to_be_visible()
    assert _scene_ids(c1) == [str(beta["id"]), str(alpha["id"])]

    # Chapter level: drag the first chapter's grip onto the second card.
    order_url = f"/api/writing/novels/{novel_id}/chapter-order"
    with page.expect_response(lambda r: order_url in r.url and r.request.method == "PUT") as moved:
        _drag_below(
            page.get_by_role("button", name="Kapitel 1 verschieben", exact=True),
            page.get_by_test_id(f"tree-chapter-{c2}"),
        )
    assert moved.value.status == 204
    expect(page.get_by_text("Kapitel 1 — Zweites")).to_be_visible()
    expect(page.get_by_text("Kapitel 2 — Erstes")).to_be_visible()
    assert _chapter_ids(novel_id) == [c2, c1]
    assert_accessible(page)

    # Both arrangements are the server's rows — the reload carries them.
    page.reload()
    expect(page.get_by_text("Kapitel 1 — Zweites")).to_be_visible()
    expect(page.get_by_test_id(f"tree-chapter-{c1}").get_by_text("Szene 1 · Beta")).to_be_visible()
    assert_accessible(page)


def test_a_reorder_conflict_surfaces_and_reconciles(page: Page, installed: Stack) -> None:
    """A second tab's scene makes the whole-set PUT stale: the 409 names
    the stored ids, the tree reconciles to the current truth (the new row
    appears), the notice speaks honestly and its retry asks the truth
    again — never re-sends the stale order. A fresh drag then lands."""
    novel = create_novel("Das Konflikt-Buch")
    novel_id = str(novel["id"])
    chapter = create_chapter(novel_id, "Erstes")
    chapter_id = str(chapter["id"])
    alpha = write_scene(chapter_id, word_body(3), title="Alpha")
    beta = write_scene(chapter_id, word_body(4), title="Beta")
    _open(page, novel_id)

    # The second tab adds a scene — the page's list does not know it.
    gamma = write_scene(chapter_id, word_body(2), title="Gamma")

    # The drag's whole set lacks Gamma → the 409, the honest notice, the
    # reconciled tree (the stored order, Gamma standing in it).
    with page.expect_response(
        lambda r: f"/api/writing/chapters/{chapter_id}/scene-order" in r.url and r.status == 409
    ):
        _drag_below(
            page.get_by_role("button", name="Szene 1 in Kapitel 1 verschieben", exact=True),
            page.get_by_test_id(f"tree-scene-{beta['id']}"),
        )
    notice = page.get_by_test_id("explorer-notice")
    expect(notice.get_by_text(CONFLICT_NOTE)).to_be_visible()
    expect(page.get_by_text("Szene 3 · Gamma")).to_be_visible()
    assert _scene_ids(chapter_id) == [str(alpha["id"]), str(beta["id"]), str(gamma["id"])]
    assert_accessible(page)

    # The retry asks the truth again — a refetch, no stale PUT re-sent.
    notice.get_by_role("button", name="Erneut versuchen").click()
    expect(notice).to_have_count(0)
    expect(page.get_by_text("Szene 3 · Gamma")).to_be_visible()

    # A fresh arrangement on the current whole lands and persists.
    with page.expect_response(
        lambda r: f"/api/writing/chapters/{chapter_id}/scene-order" in r.url and r.status == 204
    ):
        _drag_below(
            page.get_by_role("button", name="Szene 3 in Kapitel 1 verschieben", exact=True),
            page.get_by_test_id(f"tree-scene-{alpha['id']}"),
        )
    assert _scene_ids(chapter_id) == [str(alpha["id"]), str(gamma["id"]), str(beta["id"])]
    page.reload()
    expect(page.get_by_text("Szene 2 · Gamma")).to_be_visible()
    assert_accessible(page)


def test_delete_the_last_scene_leaves_the_chapter_empty(page: Page, installed: Stack) -> None:
    """D16: the last scene may go — the confirm names the loss and the
    chapter remaining, the tree reads zero, Kachel 4's face stands, and
    the chapter itself stays."""
    novel = create_novel("Das Lösch-Buch")
    novel_id = str(novel["id"])
    chapter = create_chapter(novel_id, "Erstes Kapitel")
    chapter_id = str(chapter["id"])
    scene = write_scene(chapter_id, word_body(5), title="Die einzige")
    _open(page, novel_id)
    expect(page.get_by_text("Gesamt: 5 W.")).to_be_visible()

    _row_menu(page, f"tree-scene-{scene['id']}", "Szenen-Optionen")
    page.get_by_role("button", name="Löschen", exact=True).click()
    dialog = page.get_by_role("alertdialog")
    expect(dialog.get_by_text("Szene löschen?")).to_be_visible()
    expect(
        dialog.get_by_text("«Die einzige» wird endgültig gelöscht. Das Kapitel bleibt bestehen.")
    ).to_be_visible()
    assert_accessible(page)
    dialog.get_by_role("button", name="Endgültig löschen").click()

    expect(page.get_by_role("heading", name="Erste Szene starten")).to_be_visible()
    expect(page.get_by_text("Keine Szenen angelegt")).to_be_visible()
    expect(page.get_by_text("Kapitel 1 — Erstes Kapitel")).to_be_visible()
    expect(page.get_by_text("Gesamt: 0 W.")).to_be_visible()
    assert _scene_ids(chapter_id) == []
    assert_accessible(page)

    page.reload()
    expect(page.get_by_role("heading", name="Erste Szene starten")).to_be_visible()
    expect(page.get_by_text("Kapitel 1 — Erstes Kapitel")).to_be_visible()


def test_delete_a_chapter_cascades_its_scenes(page: Page, installed: Stack) -> None:
    """The confirm names the cascade (the chapter's own scene count);
    Abbrechen keeps everything, the delete takes the chapter and its
    scenes, the survivors renumber and the total drops."""
    novel = create_novel("Das Kaskaden-Buch")
    novel_id = str(novel["id"])
    chapter1 = create_chapter(novel_id, "Erstes")
    chapter2 = create_chapter(novel_id, "Zweites")
    c1, c2 = str(chapter1["id"]), str(chapter2["id"])
    write_scene(c1, word_body(3), title="Alpha")
    write_scene(c1, word_body(4), title="Beta")
    write_scene(c2, word_body(5), title="Gamma")
    _open(page, novel_id)
    expect(page.get_by_text("Gesamt: 12 W.")).to_be_visible()

    # Abbrechen keeps the chapter — no write, the tree stands.
    _row_menu(page, f"tree-chapter-{c1}", "Kapitel-Optionen")
    page.get_by_role("button", name="Löschen", exact=True).click()
    dialog = page.get_by_role("alertdialog")
    expect(dialog.get_by_text("«Erstes» wird mit 2 Szenen endgültig gelöscht.")).to_be_visible()
    assert_accessible(page)
    dialog.get_by_role("button", name="Abbrechen").click()
    expect(dialog).to_have_count(0)
    expect(page.get_by_text("Kapitel 1 — Erstes")).to_be_visible()

    # The delete cascades: the chapter and both scenes go, Gamma's chapter
    # renumbers to Kapitel 1, the total is Gamma's own.
    _row_menu(page, f"tree-chapter-{c1}", "Kapitel-Optionen")
    page.get_by_role("button", name="Löschen", exact=True).click()
    page.get_by_role("alertdialog").get_by_role("button", name="Endgültig löschen").click()
    expect(page.get_by_text("Kapitel 1 — Zweites")).to_be_visible()
    expect(page.get_by_text("Szene 1 · Alpha")).to_have_count(0)
    expect(page.get_by_text("Szene 2 · Beta")).to_have_count(0)
    expect(page.get_by_text("Gesamt: 5 W.")).to_be_visible()
    assert _chapter_ids(novel_id) == [c2]
    assert_accessible(page)

    page.reload()
    expect(page.get_by_text("Kapitel 1 — Zweites")).to_be_visible()
    expect(page.get_by_text("Szene 1 · Gamma")).to_be_visible()


def test_rename_and_metadata_round_trip(page: Page, installed: Stack) -> None:
    """The chapter rename and the scene's three fields round-trip through
    the dialogs: the tree speaks the new name, the overline carries the
    labels, the reload persists them, and an empty label clears to the
    honest unset (present-and-nullable)."""
    novel = create_novel("Das Namen-Buch")
    novel_id = str(novel["id"])
    chapter = create_chapter(novel_id, "Alter Name")
    chapter_id = str(chapter["id"])
    scene = write_scene(chapter_id, "Prosa.", title="Alte Szene")
    scene_id = str(scene["id"])
    _open(page, novel_id)

    # The chapter rename — the stored title in the field, the tree follows.
    _row_menu(page, f"tree-chapter-{chapter_id}", "Kapitel-Optionen")
    page.get_by_role("button", name="Umbenennen").click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_text("Kapitel umbenennen")).to_be_visible()
    title = dialog.get_by_role("textbox", name="Titel")
    expect(title).to_have_value("Alter Name")
    assert_accessible(page)
    title.fill("Neuer Name")
    dialog.get_by_role("button", name="Speichern").click()
    expect(page.get_by_text("Kapitel 1 — Neuer Name")).to_be_visible()

    # The scene edit — title and both labels; the overline appears.
    _row_menu(page, f"tree-scene-{scene_id}", "Szenen-Optionen")
    page.get_by_role("button", name="Bearbeiten").click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_text("Szene bearbeiten")).to_be_visible()
    dialog.get_by_role("textbox", name="Titel").fill("Neue Szene")
    dialog.get_by_role("textbox", name="Ort").fill("Hafen bei Nacht")
    dialog.get_by_role("textbox", name="Zeit").fill("Dritte Stunde")
    assert_accessible(page)
    dialog.get_by_role("button", name="Speichern").click()
    expect(page.get_by_role("heading", name="Neue Szene", exact=True)).to_be_visible()
    expect(page.get_by_text("Hafen bei Nacht · Dritte Stunde")).to_be_visible()
    expect(page.get_by_text("Szene 1 · Neue Szene")).to_be_visible()

    # The rows, not the dialog's memory: the reload carries all three.
    page.reload()
    expect(page.get_by_text("Kapitel 1 — Neuer Name")).to_be_visible()
    expect(page.get_by_text("Hafen bei Nacht · Dritte Stunde")).to_be_visible()
    assert_accessible(page)

    # Empty labels clear to the honest unset — the overline goes.
    _row_menu(page, f"tree-scene-{scene_id}", "Szenen-Optionen")
    page.get_by_role("button", name="Bearbeiten").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_role("textbox", name="Ort").fill("")
    dialog.get_by_role("textbox", name="Zeit").fill("")
    dialog.get_by_role("button", name="Speichern").click()
    expect(page.get_by_text("Hafen bei Nacht · Dritte Stunde")).to_have_count(0)
    expect(page.get_by_role("heading", name="Neue Szene", exact=True)).to_be_visible()
    with httpx.Client(base_url=API_URL, timeout=30.0) as client:
        stored = client.get(f"/api/writing/scenes/{scene_id}").json()
    assert stored["title"] == "Neue Szene"
    assert stored["setting"] is None
    assert stored["story_time"] is None
    assert_accessible(page)


def test_the_dark_crud_faces_clear_the_axe_floor(page: Page, installed: Stack) -> None:
    """The dark face rides the same CRUD: the menu, the edit dialog, the
    delete confirm and the create flow all clear the axe floor on the
    tokens' dark halves."""
    set_theme("dark")
    novel = create_novel("Das Dunkel-Buch")
    novel_id = str(novel["id"])
    chapter = create_chapter(novel_id, "Erstes")
    chapter_id = str(chapter["id"])
    scene = write_scene(chapter_id, "Prosa.", title="Die Szene")
    scene_id = str(scene["id"])
    _open(page, novel_id)
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")

    # The open menu and the edit dialog.
    _row_menu(page, f"tree-scene-{scene_id}", "Szenen-Optionen")
    assert_accessible(page)
    page.get_by_role("button", name="Bearbeiten").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_role("textbox", name="Ort").fill("Nacht")
    assert_accessible(page)
    dialog.get_by_role("button", name="Speichern").click()
    expect(page.get_by_text("Nacht")).to_be_visible()

    # The delete confirm — and Abbrechen keeps the scene.
    _row_menu(page, f"tree-scene-{scene_id}", "Szenen-Optionen")
    page.get_by_role("button", name="Löschen", exact=True).click()
    assert_accessible(page)
    page.get_by_role("alertdialog").get_by_role("button", name="Abbrechen").click()

    # The create flow in the dark: a second chapter, its first scene, a
    # landed save — every face on the dark halves.
    page.get_by_role("button", name="Neues Kapitel", exact=True).click()
    expect(page.get_by_role("heading", name="Erste Szene starten")).to_be_visible()
    assert_accessible(page)
    page.get_by_role("button", name="+ Szene 1 anlegen").click()
    box = page.get_by_role("textbox", name=PROSE)
    with page.expect_response(
        lambda r: "/api/writing/scenes/" in r.url and r.request.method == "PUT"
    ):
        box.click()
        page.keyboard.type("Im Dunkeln geschrieben.")
    expect(page.get_by_text("Automatisch gesichert")).to_be_visible()
    assert_accessible(page)
