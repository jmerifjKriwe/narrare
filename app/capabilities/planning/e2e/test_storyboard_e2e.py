# The German face's own quotes and dashes are the catalog text these tests
# assert literally — intentional characters, not confusable typos.
"""The storyboard on the real stack (W6 Task 6): the structure math and its
doors, proven over browser, API and Postgres.

A seeded novel reads the server's own answer — the three-act default with
its suggested columns, the cards' real facts (words, sync, assignment
source, scene counts from the fan-out) and the word-total chip from the
novel's real fields. The stage select is the assignment PUT, the switcher
walks the remap contract's two steps — the preview that writes nothing,
the confirm that writes exactly the previewed mapping — and the API's
refusal for a structure id outside the registry leaves the stored rows
untouched. The empty novel keeps the columns, the switcher and the doors.
"""

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Locator, Page, expect

from app.capabilities.planning.e2e.conftest import (
    create_chapter,
    create_novel,
    get_storyboard,
    goto_storyboard,
    remap,
    save_scenes,
    scene,
    set_theme,
)
from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.stack import WEB_URL

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

BASE = WEB_URL

STRUCTURES = {
    "Drei-Akt (Standard)": "three-act",
    "Heldenreise (12 Stufen)": "heros-journey",
    "Save the Cat (15 Beats)": "save-the-cat",
    "Fünf-Akt (Klassisch / Freytag)": "five-act",
    "Seven Point (7 Punkte)": "seven-point",
}


def _open(page: Page, novel_id: str) -> None:
    goto_storyboard(page, novel_id)


def _stage(page: Page, label: str) -> Locator:
    """One stage column by its registry title. The section's aria-label, not
    its text: every card's select offers all the stages, so a text filter
    would match every occupied column."""
    return page.locator(f'section[data-testid="storyboard-stage"][aria-label="{label}"]')


def _seed_three_chapters(novel_id: str) -> list[str]:
    """Three chapters, two with planned scenes — the fan-out's real answer."""
    first = create_chapter(novel_id, "Ankunft")
    second = create_chapter(novel_id, "Notfall-Code")
    third = create_chapter(novel_id, "Der Nebel")
    save_scenes(novel_id, str(first["id"]), [scene("Kalibrierung der Messsonde", status="planned")])
    save_scenes(novel_id, str(second["id"]), [scene("Der Ausfall", status="planned")])
    return [str(first["id"]), str(second["id"]), str(third["id"])]


def test_the_board_reads_the_three_act_default(page: Page, installed: Stack) -> None:
    """The unremapped novel reads the default structure through the server:
    three suggested columns, the cards' real facts and the fan-out's scene
    counts, the word-total chip on the novel's own target."""
    novel = create_novel("Das Signal", target_words=65000)
    novel_id = str(novel["id"])
    _seed_three_chapters(novel_id)
    _open(page, novel_id)

    # The switcher offers the five real ids; the standing one is pressed.
    switcher = page.get_by_test_id("storyboard-structure-switcher")
    for label in STRUCTURES:
        expect(switcher.get_by_role("button", name=label)).to_be_visible()
    expect(switcher.get_by_role("button", name="Drei-Akt (Standard)")).to_have_attribute(
        "aria-pressed", "true"
    )

    # The three-act columns stand under their registry titles.
    for stage in ("Exposition", "Konfrontation", "Auflösung"):
        expect(_stage(page, stage)).to_be_visible()

    # The cards: the suggested stage wins (position ratios 0, ½, 1), the
    # facts are the rows' own.
    ankunft = page.get_by_test_id("storyboard-card").filter(has_text="Ankunft")
    expect(ankunft).to_contain_text("Kapitel 1")
    expect(ankunft).to_contain_text("0 Wörter")
    expect(ankunft).to_contain_text("1 Szene")
    expect(ankunft).to_contain_text("Geplant · Vorschlag")
    nebel = page.get_by_test_id("storyboard-card").filter(has_text="Der Nebel")
    expect(nebel).to_contain_text("Ohne Szenen")
    expect(
        _stage(page, "Auflösung").get_by_test_id("storyboard-card").filter(has_text="Der Nebel")
    ).to_be_visible()
    expect(
        _stage(page, "Konfrontation")
        .get_by_test_id("storyboard-card")
        .filter(has_text="Notfall-Code")
    ).to_be_visible()

    # The word-total chip: the novel's real fields, the counts only once
    # the chapters read answered.
    progress = page.get_by_test_id("storyboard-progress")
    expect(progress).to_contain_text("0 / 65.000 Wörter")
    expect(progress).to_contain_text("0 % erreicht")
    expect(progress).to_contain_text("3 Kapitel")
    expect(progress).to_contain_text("2 Szenen gesamt")

    # The dock waits honestly beside the board — no chapter stands selected.
    expect(page.get_by_test_id("drill-in")).to_contain_text(
        "Wähle ein Kapitel, um seine Szenen zu bearbeiten."
    )
    # The sibling doors stand on the populated face.
    expect(page.get_by_test_id("storyboard-timeline-door")).to_be_visible()
    expect(page.get_by_test_id("storyboard-causality-door")).to_be_visible()
    assert_accessible(page)


def test_the_stage_put_moves_the_card_by_hand(page: Page, installed: Stack) -> None:
    """The stage select is the assignment PUT: the card lands in the chosen
    column wearing „Von Hand", and the server keeps the assignment."""
    novel = create_novel("Das Winterhaus")
    novel_id = str(novel["id"])
    chapter_ids = _seed_three_chapters(novel_id)
    _open(page, novel_id)

    ankunft = page.get_by_test_id("storyboard-card").filter(has_text="Ankunft")
    ankunft.get_by_role("combobox", name="Phase des Kapitels").select_option(label="Auflösung")
    resolution = _stage(page, "Auflösung")
    moved = resolution.get_by_test_id("storyboard-card").filter(has_text="Ankunft")
    expect(moved).to_be_visible()
    expect(moved).to_contain_text("Von Hand")

    storyboard = get_storyboard(novel_id)
    row = storyboard["stages"][2]["chapters"][0]
    assert row["chapter_id"] == chapter_ids[0]
    assert row["stage_key"] == "resolution"
    assert row["assignment_source"] == "assigned"


def test_the_remap_walks_preview_then_confirm(page: Page, installed: Stack) -> None:
    """The switcher prepares, never writes: the notice's apply opens the
    server's own two-step contract — the preview lists every chapter's
    move, the confirm writes exactly that mapping — and a cancelled second
    change writes nothing at all."""
    novel = create_novel("Der Nebel")
    novel_id = str(novel["id"])
    _seed_three_chapters(novel_id)
    _open(page, novel_id)

    page.get_by_test_id("storyboard-structure-switcher").get_by_role(
        "button", name="Heldenreise (12 Stufen)"
    ).click()
    notice = page.get_by_test_id("storyboard-remap-notice")
    expect(notice).to_be_visible()
    # The preview is a read: the stored structure is still the default.
    assert get_storyboard(novel_id)["structure_id"] == "three-act"

    notice.get_by_role("button", name="Remap anwenden").click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_text("Struktur wechseln")).to_be_visible()
    expect(
        dialog.get_by_role("listitem").filter(has_text="Kapitel 1: Exposition → Gewohnte Welt")
    ).to_be_visible()
    expect(
        dialog.get_by_role("listitem").filter(
            has_text="Kapitel 2: Konfrontation → Bewährungsproben, Verbündete, Feinde"
        )
    ).to_be_visible()
    expect(
        dialog.get_by_role("listitem").filter(
            has_text="Kapitel 3: Auflösung → Rückkehr mit dem Elixier"
        )
    ).to_be_visible()

    dialog.get_by_role("button", name="Anwenden", exact=True).click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    switcher = page.get_by_test_id("storyboard-structure-switcher")
    expect(switcher.get_by_role("button", name="Heldenreise (12 Stufen)")).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(_stage(page, "Gewohnte Welt")).to_be_visible()
    expect(
        _stage(page, "Gewohnte Welt").get_by_test_id("storyboard-card").filter(has_text="Ankunft")
    ).to_contain_text("Von Hand")

    storyboard = get_storyboard(novel_id)
    assert storyboard["structure_id"] == "heros-journey"
    assert len(storyboard["stages"]) == 12

    # The cancelled change: the notice stands down, nothing is written.
    switcher.get_by_role("button", name="Seven Point (7 Punkte)").click()
    notice = page.get_by_test_id("storyboard-remap-notice")
    notice.get_by_role("button", name="Remap anwenden").click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_text("Struktur wechseln")).to_be_visible()
    dialog.get_by_role("button", name="Abbrechen").click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(switcher.get_by_role("button", name="Heldenreise (12 Stufen)")).to_have_attribute(
        "aria-pressed", "true"
    )
    assert get_storyboard(novel_id)["structure_id"] == "heros-journey"


def test_the_unknown_structure_refusal_writes_nothing(page: Page, installed: Stack) -> None:
    """A structure id outside the registry is a 422 that writes nothing —
    preview and confirm alike — and the board behind it never bricks."""
    novel = create_novel("Das Signal")
    novel_id = str(novel["id"])
    _seed_three_chapters(novel_id)
    _open(page, novel_id)

    preview = remap(novel_id, "kyring-zyklus", confirm=False)
    assert preview.status_code == 422
    assert preview.json()["detail"] == "unknown structure: kyring-zyklus"
    confirm = remap(novel_id, "kyring-zyklus", confirm=True)
    assert confirm.status_code == 422

    # Nothing was written, and the switcher still stands with its five
    # real doors — the refusal named itself at the boundary.
    storyboard = get_storyboard(novel_id)
    assert storyboard["structure_id"] == "three-act"
    switcher = page.get_by_test_id("storyboard-structure-switcher")
    for label in STRUCTURES:
        expect(switcher.get_by_role("button", name=label)).to_be_visible()


def test_the_empty_storyboard_keeps_the_switcher(page: Page, installed: Stack) -> None:
    """An empty novel keeps the columns, the switcher and the doors, and
    its guidance card walks to the workspace, where chapters are created."""
    novel = create_novel("Das leere Buch")
    novel_id = str(novel["id"])
    _open(page, novel_id)

    expect(page.get_by_test_id("storyboard-empty")).to_contain_text("Noch keine Kapitel")
    door = page.get_by_role("link", name="Im Schreib-Workspace weitermachen")
    expect(door).to_have_attribute("href", f"/novels/{novel_id}")
    switcher = page.get_by_test_id("storyboard-structure-switcher")
    for label in STRUCTURES:
        expect(switcher.get_by_role("button", name=label)).to_be_visible()
    expect(page.get_by_test_id("storyboard-timeline-door")).to_be_visible()
    expect(page.get_by_test_id("storyboard-causality-door")).to_be_visible()
    assert_accessible(page)


def test_the_dark_storyboard_clears_the_axe_floor(page: Page, installed: Stack) -> None:
    """The staged board on the tokens' dark halves — the same WCAG A/AA
    floor the light face clears."""
    set_theme("dark")
    novel = create_novel("Das dunkle Buch")
    novel_id = str(novel["id"])
    _seed_three_chapters(novel_id)
    _open(page, novel_id)
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    expect(page.get_by_test_id("storyboard-card").filter(has_text="Ankunft")).to_be_visible()
    assert_accessible(page)
