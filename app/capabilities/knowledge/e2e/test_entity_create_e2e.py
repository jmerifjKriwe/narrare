# The German face's own quotes and dashes are the catalog text these tests
# assert literally — intentional characters, not confusable typos.
"""Creating an entity by hand on the real stack (W9): the create dialog's
two doors.

The canon is seeded through the real extraction → accept path, and the
location's name is then corrected to the brief's «Forschungsstation 7» through
the real PATCH — the fake derives «Forschungsstation» from the prose, and the
test's relation target must be a row the writer can resolve. Every leg drives
the real dialog: a name and type gate the save, a tag rides its Enter key, a
relation row resolves by name, a duplicate name is a notice that still saves,
and a saved row is selected at once in the graph or the dossiers.
"""

from typing import TYPE_CHECKING

import httpx
import pytest
from playwright.sync_api import Locator, Page, expect

from app.capabilities.knowledge.e2e.conftest import (
    create_chapter,
    create_novel,
    list_entities,
    seed_canon,
    write_scene,
)
from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.stack import API_URL, WEB_URL

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

BASE = WEB_URL

# The fake derives the capitalized names, in order: Mira (character), Kavic
# (location), Forschungsstation (faction). The correction names the location
# the brief asks for.
CAST_PROSE = "Mira trifft Kavic auf Forschungsstation."
STATION_NAME = "Forschungsstation 7"


def _rename_entity(entity_id: str, name: str) -> None:
    with httpx.Client(base_url=API_URL, timeout=30.0) as client:
        response = client.patch(f"/api/knowledge/entities/{entity_id}", json={"name": name})
    response.raise_for_status()


def _seed_canon_with_station() -> str:
    """The novel whose canon the dialog resolves against; the station's row is
    renamed through the real correction path."""
    novel = create_novel("Das Signal")
    novel_id = str(novel["id"])
    chapter = create_chapter(novel_id, "Ankunft")
    write_scene(str(chapter["id"]), CAST_PROSE)
    seed_canon(novel_id, str(chapter["id"]))
    by_name = {row["name"]: row for row in list_entities(novel_id)}
    _rename_entity(str(by_name["Forschungsstation"]["id"]), STATION_NAME)
    return novel_id


def _goto_graph(page: Page, novel_id: str) -> None:
    page.goto(f"{BASE}/novels/{novel_id}/knowledge/graph")
    expect(page.get_by_test_id("graph-page")).to_be_visible()


def _goto_dossiers(page: Page, novel_id: str) -> None:
    page.goto(f"{BASE}/novels/{novel_id}/knowledge/dossiers")
    expect(page.get_by_test_id("dossiers-page")).to_be_visible()


def _open_create(page: Page, door: str) -> Locator:
    page.get_by_test_id(door).click()
    dialog = page.get_by_test_id("entity-create-dialog")
    expect(dialog).to_be_visible()
    return dialog


def test_create_by_hand_from_the_graph(page: Page, installed: Stack) -> None:
    """The graph's «Neue Entität» opens the dialog; name, type, a tag and one
    resolved relation save together, and the new row is selected at once."""
    novel_id = _seed_canon_with_station()
    _goto_graph(page, novel_id)

    dialog = _open_create(page, "graph-new-entity")
    dialog.get_by_test_id("entity-create-name").fill("Nevada-Trümmerfeld")
    dialog.get_by_test_id("entity-create-type").select_option("location")
    tags = dialog.get_by_test_id("entity-create-tags")
    tags.fill("Ruine")
    tags.press("Enter")
    expect(dialog.get_by_text("Ruine")).to_be_visible()

    dialog.get_by_test_id("entity-create-add-relation").click()
    dialog.get_by_test_id("entity-create-relation-0-entity").fill(STATION_NAME)
    dialog.get_by_test_id("entity-create-relation-0-label").fill("Liegt in")
    dialog.get_by_test_id("entity-create-save").click()
    expect(dialog).not_to_be_visible()

    # The save selects the new row: its dossier names the entity and the edge.
    dossier = page.get_by_test_id("entity-dossier")
    expect(dossier).to_be_visible()
    expect(dossier).to_contain_text("Nevada-Trümmerfeld")
    expect(dossier).to_contain_text(STATION_NAME)
    expect(dossier).to_contain_text("Liegt in")
    assert_accessible(page)


def test_create_by_hand_from_the_dossiers(page: Page, installed: Stack) -> None:
    """The dossiers page's «Neues Dossier» opens the same dialog; a saved row
    appears in the list and opens its dossier."""
    novel = create_novel("Das leere Buch")
    novel_id = str(novel["id"])
    _goto_dossiers(page, novel_id)

    dialog = _open_create(page, "dossiers-new-dossier")
    dialog.get_by_test_id("entity-create-name").fill("Nebelhaus")
    dialog.get_by_test_id("entity-create-type").select_option("location")
    dialog.get_by_test_id("entity-create-save").click()
    expect(dialog).not_to_be_visible()

    card = page.get_by_test_id("dossier-card").filter(has_text="Nebelhaus")
    expect(card).to_be_visible()
    expect(page.get_by_test_id("entity-dossier")).to_contain_text("Nebelhaus")
    assert_accessible(page)


def test_duplicate_name_is_a_notice_not_a_refusal(page: Page, installed: Stack) -> None:
    """An existing name shows the quiet notice and still saves: the canon may
    hold two rows the writer will merge later."""
    novel_id = _seed_canon_with_station()
    _goto_graph(page, novel_id)

    dialog = _open_create(page, "graph-new-entity")
    dialog.get_by_test_id("entity-create-name").fill("  Mira  ")
    dialog.get_by_test_id("entity-create-type").select_option("character")

    expect(dialog.get_by_test_id("entity-create-duplicate-note")).to_contain_text(
        "Eine Entität mit diesem Namen gibt es schon. Speichern ist trotzdem möglich."
    )
    save = dialog.get_by_test_id("entity-create-save")
    expect(save).to_be_enabled()
    save.click()
    expect(dialog).not_to_be_visible()

    # The refusal never fired; the new duplicate stands beside the old row.
    expect(page.get_by_test_id("graph-node").filter(has_text="Mira")).to_have_count(2)
    assert_accessible(page)


def test_required_fields_keep_save_disabled(page: Page, installed: Stack) -> None:
    """Name and type gate the save: neither alone enables it, and cancelling
    writes nothing."""
    novel_id = _seed_canon_with_station()
    before = len(list_entities(novel_id))
    _goto_graph(page, novel_id)

    dialog = _open_create(page, "graph-new-entity")
    save = dialog.get_by_test_id("entity-create-save")
    expect(save).to_be_disabled()
    dialog.get_by_test_id("entity-create-name").fill("Nur ein Name")
    expect(save).to_be_disabled()
    dialog.get_by_test_id("entity-create-type").select_option("location")
    expect(save).to_be_enabled()

    dialog.get_by_test_id("entity-create-cancel").click()
    expect(dialog).not_to_be_visible()
    assert len(list_entities(novel_id)) == before
    assert_accessible(page)
