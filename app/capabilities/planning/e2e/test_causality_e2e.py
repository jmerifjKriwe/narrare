# The German face's own quotes and dashes are the catalog text these tests
# assert literally — intentional characters, not confusable typos.
"""The causality strip on the real stack (W6 Task 6): the wave's proof face.

The chain renders the novel's real scenes — chapter-grouped, the „Erzwingt"
connectors between a scene and its successor, the „Kapitel-Übergang" only
where both sides carry scenes — on the fields the server keeps: a missing
conflict or resolution renders the honest „—" and names the gap count, a
gapless chain reads as closed, an empty novel walks to the storyboard where
scenes are planned. The sibling doors stand on every face.
"""

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

from app.capabilities.planning.e2e.conftest import (
    create_chapter,
    create_novel,
    goto_causality,
    save_scenes,
    scene,
    set_theme,
)
from app.kernel.testing.a11y import assert_accessible

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]


def _seed_chain(novel_id: str) -> list[str]:
    """Three chapters: a full scene, a gapped one, an answered one, and a
    chapter the fan answers with nothing — the label card stands alone."""
    first = create_chapter(novel_id, "Ankunft")
    second = create_chapter(novel_id, "Notfall-Code")
    third = create_chapter(novel_id, "Der Nebel")
    save_scenes(
        novel_id,
        str(first["id"]),
        [
            scene(
                "Kalibrierung der Messsonde",
                conflict="Die Sonde schlägt bei 14.2 Hz aus.",
                resolution="Der Außenposten wird evakuiert.",
                status="complete",
            ),
            scene("Der Ausfall", conflict="Der Strom fällt aus.", status="planned"),
        ],
    )
    save_scenes(
        novel_id,
        str(second["id"]),
        [
            scene(
                "Die Evakuierung",
                conflict="Zu wenige Kapseln für alle.",
                resolution="Die Crew teilt sich auf.",
                status="complete",
            )
        ],
    )
    return [str(first["id"]), str(second["id"]), str(third["id"])]


def test_the_chain_renders_the_seeded_scenes(page: Page, installed: Stack) -> None:
    """The real fan-out's answer, chained: the counts and the gap chip on
    the fields' own math, the connectors exactly where the fields support
    them, the missing answer the honest „—", and the empty chapter's label
    card without an arrow into emptiness."""
    novel = create_novel("Das Signal")
    novel_id = str(novel["id"])
    _seed_chain(novel_id)
    goto_causality(page, novel_id)

    counts = page.get_by_test_id("causality-counts")
    expect(counts).to_contain_text("3 Kapitel")
    expect(counts).to_contain_text("3 Szenen gesamt")
    expect(page.get_by_test_id("causality-chain")).to_contain_text("Kausaler Faden: 1 offene Lücke")

    chapters = page.get_by_test_id("causality-chapter")
    expect(chapters).to_have_count(3)
    expect(chapters.filter(has_text="Ankunft")).to_contain_text(
        "Szene 1.1: Kalibrierung der Messsonde"
    )
    expect(chapters.filter(has_text="Ankunft")).to_contain_text("Szene 1.2: Der Ausfall")

    # The fields: the answered scene carries its words, the gapped one the
    # honest dash on its resolution — and the status badges say Verfasst /
    # Geplant from the lifecycle.
    kalibrierung = page.get_by_test_id("causality-scene").filter(
        has_text="Kalibrierung der Messsonde"
    )
    expect(kalibrierung).to_contain_text("Die Sonde schlägt bei 14.2 Hz aus.")
    expect(kalibrierung).to_contain_text("Der Außenposten wird evakuiert.")
    expect(kalibrierung).to_contain_text("Verfasst")
    ausfall = page.get_by_test_id("causality-scene").filter(has_text="Der Ausfall")
    expect(ausfall).to_contain_text("Der Strom fällt aus.")
    expect(ausfall).to_contain_text("Geplant")
    expect(ausfall.get_by_text("—", exact=True)).to_have_count(1)

    # The connectors: „Erzwingt" between the two scenes of one chapter,
    # „Kapitel-Übergang" only into the next chapter that carries scenes —
    # the empty third stands with its label card alone.
    expect(page.get_by_test_id("causality-link")).to_have_count(1)
    expect(page.get_by_test_id("causality-link").get_by_text("Erzwingt")).to_be_visible()
    expect(page.get_by_test_id("causality-transition")).to_have_count(1)
    expect(
        page.get_by_test_id("causality-transition").get_by_text("Kapitel-Übergang")
    ).to_be_visible()
    expect(chapters.filter(has_text="Der Nebel")).to_contain_text("0 Szenen")

    # The methodology row counts the same truth.
    expect(page.get_by_test_id("causality-bento")).to_contain_text("Status: 1 offene Lücke")

    # The sibling doors walk on the populated face.
    page.get_by_test_id("causality-timeline-door").click()
    expect(page.get_by_test_id("timeline-page")).to_be_visible()
    page.go_back()
    expect(page.get_by_test_id("causality-page")).to_be_visible()
    page.get_by_test_id("causality-storyboard-door").click()
    expect(page.get_by_test_id("storyboard-page")).to_be_visible()
    assert_accessible(page)


def test_the_gapless_chain_reads_as_closed(page: Page, installed: Stack) -> None:
    """Every scene answered: the chain chip names the chain closed — the
    real zero, not a dressed-up gap count."""
    novel = create_novel("Das Winterhaus")
    novel_id = str(novel["id"])
    chapter = create_chapter(novel_id, "Ankunft")
    save_scenes(
        novel_id,
        str(chapter["id"]),
        [
            scene(
                "Der Ausfall",
                conflict="Der Strom fällt aus.",
                resolution="Notstrom übernimmt.",
                status="complete",
            ),
            scene(
                "Der Marsch",
                conflict="Der Weg ist vereist.",
                resolution="Die Crew seilt sich ab.",
                status="in_progress",
            ),
        ],
    )
    goto_causality(page, novel_id)
    expect(page.get_by_test_id("causality-chain")).to_contain_text(
        "Kausaler Faden: lückenlos geschlossen"
    )
    expect(page.get_by_test_id("causality-bento")).to_contain_text("Status: 0 offene Lücken")
    expect(page.get_by_test_id("causality-scene")).to_have_count(2)
    expect(page.get_by_test_id("causality-link")).to_have_count(1)


def test_the_empty_novel_doors_to_the_storyboard(page: Page, installed: Stack) -> None:
    """The unbesetzt banner walks to the storyboard, where scenes are
    planned — planning owns no scene-create seam — and the doors back keep
    the round trip honest."""
    novel = create_novel("Das leere Buch")
    novel_id = str(novel["id"])
    goto_causality(page, novel_id)

    empty = page.get_by_test_id("causality-empty")
    expect(empty).to_contain_text("Noch keine Szenen verfasst")
    manuscript = page.get_by_test_id("causality-manuscript-door")
    expect(manuscript).to_have_attribute("href", f"/novels/{novel_id}")

    # The verketten door and the banner's own door both walk to the
    # storyboard's guidance face.
    page.get_by_test_id("causality-verketten-door").click()
    expect(page.get_by_test_id("storyboard-page")).to_be_visible()
    expect(page.get_by_test_id("storyboard-empty")).to_be_visible()
    expect(page.get_by_role("link", name="Im Schreib-Workspace weitermachen")).to_have_attribute(
        "href", f"/novels/{novel_id}"
    )

    # Back to the strip: its empty face keeps its own doors.
    page.get_by_test_id("storyboard-causality-door").click()
    expect(page.get_by_test_id("causality-empty")).to_be_visible()
    page.get_by_role("button", name="Zum Storyboard wechseln").click()
    expect(page.get_by_test_id("storyboard-empty")).to_be_visible()


def test_the_dark_chain_clears_the_axe_floor(page: Page, installed: Stack) -> None:
    """The populated chain on the tokens' dark halves — the same WCAG A/AA
    floor the light face clears."""
    set_theme("dark")
    novel = create_novel("Das dunkle Buch")
    novel_id = str(novel["id"])
    _seed_chain(novel_id)
    goto_causality(page, novel_id)
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    expect(
        page.get_by_test_id("causality-scene").filter(has_text="Kalibrierung der Messsonde")
    ).to_be_visible()
    assert_accessible(page)
