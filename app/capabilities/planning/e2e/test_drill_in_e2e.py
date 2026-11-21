# The German face's own quotes and dashes are the catalog text these tests
# assert literally — intentional characters, not confusable typos.
"""The scene drill-in on the real stack (W6 Task 6): the aggregate editor
and its stale-version contract, proven over browser, API and Postgres.

The dock keeps a working copy of the chapter's scene list; one save PUTs
the whole aggregate — edits, beats, order, the minted create and the
confirmed remove land together, and the server's rows are asked back after
every save. The version-conflict face is driven by a genuine divergent
write: the chapter's aggregate is PUT out-of-band between the dock's load
and the writer's save, exactly the other-window scenario the face names —
the snapshot refuses, no PUT crosses on the stale stamp, the fresh load
adopts the server's copy, and the honest overwrite is last-writer-wins on
the whole list, named as the overwrite it is.
"""

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Locator, Page, expect

from app.capabilities.planning.e2e.conftest import (
    create_chapter,
    create_novel,
    goto_storyboard,
    read_scenes,
    save_scenes,
    scene,
)
from app.kernel.testing.a11y import assert_accessible

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]


def _open_with_dock(page: Page, novel_id: str, chapter_title: str) -> Locator:
    """The board with one chapter's dock open — the drill-in's standing
    preamble. Returns the dock."""
    goto_storyboard(page, novel_id)
    card = page.get_by_test_id("storyboard-card").filter(has_text=chapter_title)
    card.get_by_text(chapter_title).click()
    dock = page.get_by_test_id("drill-in")
    expect(dock).to_be_visible()
    return dock


def _edit_scene(page: Page, dock: Locator, scene_title: str, purpose: str) -> None:
    """One scene's purpose through the edit dialog — applied into the copy,
    nothing written until the dock's save."""
    row = dock.get_by_test_id("drill-in-scene").filter(has_text=scene_title)
    row.get_by_role("button", name="Szene bearbeiten").click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible()
    dialog.get_by_label("Zweck").fill(purpose)
    dialog.get_by_role("button", name="Änderungen speichern").click()
    expect(page.get_by_role("dialog")).to_have_count(0)


def test_the_dock_saves_the_whole_list(page: Page, installed: Stack) -> None:
    """Edit a scene's purpose and a beat, move its sibling up, one save —
    the server keeps the new order, the fields and the renumbered rows."""
    novel = create_novel("Das Signal")
    novel_id = str(novel["id"])
    chapter = create_chapter(novel_id, "Notfall-Code")
    chapter_id = str(chapter["id"])
    first = scene("Kalibrierung der Messsonde", purpose="Die Ruhe vor dem Ausfall.")
    second = scene("Der Ausfall", status="in_progress")
    save_scenes(novel_id, chapter_id, [first, second])

    dock = _open_with_dock(page, novel_id, "Notfall-Code")
    expect(dock).to_contain_text("KAPITEL 1 · 2 SZENEN")
    expect(dock).to_contain_text("Szene 1.1: Kalibrierung der Messsonde")
    expect(dock).to_contain_text("In Arbeit")

    _edit_scene(page, dock, "Kalibrierung der Messsonde", "Die Isolation des Außenpostens zeigen.")

    # The move reorders the copy without a write; the save commits both.
    rows = dock.get_by_test_id("drill-in-scene")
    rows.filter(has_text="Der Ausfall").get_by_role("button", name="Nach oben").click()
    dock.get_by_role("button", name="Szenen speichern").click()
    expect(dock.get_by_role("button", name="Szenen speichern")).to_have_count(0)
    expect(dock).to_contain_text("Szene 1.1: Der Ausfall")

    aggregate = read_scenes(novel_id, chapter_id)
    assert [row["title"] for row in aggregate["scenes"]] == [
        "Der Ausfall",
        "Kalibrierung der Messsonde",
    ]
    assert [row["position"] for row in aggregate["scenes"]] == [1, 2]
    assert aggregate["scenes"][1]["purpose"] == "Die Isolation des Außenpostens zeigen."
    assert aggregate["scenes"][1]["status"] == "planned"


def test_add_and_remove_ride_the_same_put(page: Page, installed: Stack) -> None:
    """A scene is born in the copy (minted, untitled) and leaves through
    its confirm — one save commits membership with everything else."""
    novel = create_novel("Der Nebel")
    novel_id = str(novel["id"])
    chapter = create_chapter(novel_id, "Ankunft")
    chapter_id = str(chapter["id"])
    first = scene("Kalibrierung der Messsonde")
    save_scenes(novel_id, chapter_id, [first])

    dock = _open_with_dock(page, novel_id, "Ankunft")
    dock.get_by_role("button", name="Szene zu Kapitel 1 hinzufügen").click()
    rows = dock.get_by_test_id("drill-in-scene")
    expect(rows).to_have_count(2)
    expect(rows.filter(has_text="Ohne Titel")).to_be_visible()

    rows.filter(has_text="Kalibrierung der Messsonde").get_by_role(
        "button", name="Szene aus dem Kapitel entfernen"
    ).click()
    confirm = page.get_by_role("alertdialog")
    expect(confirm).to_contain_text("„Kalibrierung der Messsonde“ verschwindet aus dem Kapitel.")
    confirm.get_by_role("button", name="Entfernen").click()
    expect(rows).to_have_count(1)

    dock.get_by_role("button", name="Szenen speichern").click()
    expect(dock.get_by_role("button", name="Szenen speichern")).to_have_count(0)
    aggregate = read_scenes(novel_id, chapter_id)
    assert len(aggregate["scenes"]) == 1
    added = aggregate["scenes"][0]
    assert added["id"] != first["id"]
    assert added["title"] == ""
    assert added["status"] == "planned"


def test_the_stale_version_refuses_as_the_conflict_face(page: Page, installed: Stack) -> None:
    """A divergent write between the dock's load and the save: the stamp
    moved, so the save refuses as the conflict face — no PUT crossed — the
    fresh load adopts the server's copy, and the honest overwrite is the
    last writer winning, on the whole list."""
    novel = create_novel("Das Winterhaus")
    novel_id = str(novel["id"])
    chapter = create_chapter(novel_id, "Ankunft")
    chapter_id = str(chapter["id"])
    save_scenes(novel_id, chapter_id, [scene("Kalibrierung der Messsonde")])

    dock = _open_with_dock(page, novel_id, "Ankunft")
    expect(dock).to_contain_text("Kalibrierung der Messsonde")

    # The other window: the chapter's aggregate moves under the dock's
    # snapshot — a real write, through the real API.
    divergent = read_scenes(novel_id, chapter_id)
    divergent["scenes"][0]["title"] = "Vom anderen Fenster geschrieben"
    save_scenes(novel_id, chapter_id, divergent["scenes"])

    # The local copy dirties on an answer the server never saw.
    _edit_scene(page, dock, "Kalibrierung der Messsonde", "Lokale Antwort, die der Server nie sah.")
    dock.get_by_role("button", name="Szenen speichern").click()

    # The refusal face stands, and the server keeps the divergent rows:
    # the stale snapshot never reached the wire.
    conflict = page.get_by_test_id("drill-in-conflict")
    expect(conflict).to_contain_text("Die Szenen haben sich geändert")
    stale = read_scenes(novel_id, chapter_id)
    assert stale["scenes"][0]["title"] == "Vom anderen Fenster geschrieben"
    assert stale["scenes"][0]["purpose"] == ""

    # „Frisch laden" folds the copy onto the server's rows — the draft's
    # answer is gone, the divergent title stands in the dock.
    conflict.get_by_role("button", name="Frisch laden").click()
    expect(page.get_by_test_id("drill-in-conflict")).to_have_count(0)
    expect(dock.get_by_role("button", name="Szenen speichern")).to_have_count(0)
    expect(dock).to_contain_text("Vom anderen Fenster geschrieben")
    expect(dock).not_to_contain_text("Lokale Antwort, die der Server nie sah.")

    # The second divergence, then the named overwrite: the local answers
    # replace the whole list — last-writer-wins, with open eyes.
    divergent = read_scenes(novel_id, chapter_id)
    divergent["scenes"][0]["title"] = "Zweitens geändert"
    save_scenes(novel_id, chapter_id, divergent["scenes"])
    _edit_scene(page, dock, "Vom anderen Fenster geschrieben", "Die lokale Antwort gewinnt.")
    dock.get_by_role("button", name="Szenen speichern").click()
    conflict = page.get_by_test_id("drill-in-conflict")
    expect(conflict).to_be_visible()
    conflict.get_by_role("button", name="Trotzdem speichern").click()
    expect(page.get_by_test_id("drill-in-conflict")).to_have_count(0)
    expect(dock.get_by_role("button", name="Szenen speichern")).to_have_count(0)

    overwritten = read_scenes(novel_id, chapter_id)
    assert len(overwritten["scenes"]) == 1
    assert overwritten["scenes"][0]["title"] == "Vom anderen Fenster geschrieben"
    assert overwritten["scenes"][0]["purpose"] == "Die lokale Antwort gewinnt."
    assert_accessible(page)
