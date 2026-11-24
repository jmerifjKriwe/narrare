# The German face's own quotes and dashes are the catalog text these tests
# assert literally — intentional characters, not confusable typos.
"""The dossiers on the real stack (W5 Task 7): the browsing surface.

The same seeded canon the graph draws (extraction → accept through the real
API), browsed as the draft's grid: the contract's eight type tabs with their
real counts, the search over name AND body, the shared EntityDossier on
selection — one component, two homes — and the sibling doors that carry only
a LIVING selection across the three surfaces. The invented fields stand as
honest disabled areas in the live browser, and the dark face clears the same
axe floor the light one does.
"""

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

from app.capabilities.knowledge.e2e.conftest import (
    create_chapter,
    create_novel,
    list_entities,
    seed_canon,
    set_theme,
    write_scene,
)
from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.stack import WEB_URL

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

BASE = WEB_URL

CAST_PROSE = "Mira trifft Kavic auf Vulkan."


def _seed_dossiers() -> tuple[str, dict[str, str]]:
    """The novel and its canon's ids by name — the chain of two edges."""
    novel = create_novel("Das Signal")
    novel_id = str(novel["id"])
    chapter = create_chapter(novel_id, "Ankunft")
    write_scene(str(chapter["id"]), CAST_PROSE)
    seed_canon(novel_id, str(chapter["id"]), accept_order=["Vulkan", "Kavic", "Mira"])
    return novel_id, {row["name"]: str(row["id"]) for row in list_entities(novel_id)}


def _goto_dossiers(page: Page, novel_id: str) -> None:
    page.goto(f"{BASE}/novels/{novel_id}/knowledge/dossiers")
    expect(page.get_by_test_id("dossiers-page")).to_be_visible()


def test_the_dossiers_browse_the_real_cast(page: Page, installed: Stack) -> None:
    """The grid on the rows' own facts, the contract's nine tabs with real
    counts (a type the canon does not carry stands at zero), the live create
    door, and the no-selection prompt — never an invented dossier."""
    novel_id, _ = _seed_dossiers()
    _goto_dossiers(page, novel_id)

    cards = page.get_by_test_id("dossier-card")
    expect(cards).to_have_count(3)
    expect(cards.filter(has_text="Kavic")).to_contain_text("Ort")
    expect(cards.filter(has_text="Kavic")).to_contain_text("Kavic appears in the chapter.")
    expect(cards.filter(has_text="Kavic")).to_contain_text("2 verknüpfte Relationen")
    expect(cards.filter(has_text="Mira")).to_contain_text("1 verknüpfte Relation")
    expect(cards.filter(has_text="Vulkan")).to_contain_text("1 verknüpfte Relation")
    # The draft's invented „Aktiv" status is not rendered.
    expect(cards.filter(has_text="Kavic")).not_to_contain_text("Aktiv")

    tabs = page.get_by_test_id("dossier-type-tab")
    expect(tabs).to_have_count(9)
    expect(tabs.filter(has_text="Alle Typen")).to_contain_text("3")
    expect(tabs.filter(has_text="Figur")).to_contain_text("1")
    expect(tabs.filter(has_text="Fraktion")).to_contain_text("1")
    expect(tabs.filter(has_text="Objekt")).to_contain_text("0")

    # The create door: live since W9 — it opens the hand-made create.
    create = page.get_by_role("button", name="Neues Dossier")
    expect(create).to_be_enabled()
    expect(page.get_by_test_id("dossiers-no-selection")).to_be_visible()
    assert_accessible(page)


def test_the_tabs_and_search_filter_the_cast(page: Page, installed: Stack) -> None:
    """The type tabs and the search compose (AND); the search reads name AND
    body; the no-results face clears both."""
    novel_id, _ = _seed_dossiers()
    _goto_dossiers(page, novel_id)
    cards = page.get_by_test_id("dossier-card")

    page.get_by_test_id("dossier-type-tab").filter(has_text="Figur").click()
    expect(cards).to_have_count(1)
    expect(cards).to_contain_text("Mira")
    page.get_by_test_id("dossier-type-tab").filter(has_text="Ort").click()
    expect(cards).to_have_count(1)
    expect(cards).to_contain_text("Kavic")
    page.get_by_test_id("dossier-type-tab").filter(has_text="Alle Typen").click()
    expect(cards).to_have_count(3)

    # The name search, then the body search — the description's own words.
    page.get_by_test_id("dossier-search").fill("kavic")
    expect(cards).to_have_count(1)
    page.get_by_test_id("dossier-search").fill("appears")
    expect(cards).to_have_count(3)
    page.get_by_test_id("dossier-search").fill("")

    # The composition matches nothing; the clear door resets both.
    page.get_by_test_id("dossier-type-tab").filter(has_text="Fraktion").click()
    page.get_by_test_id("dossier-search").fill("mira")
    expect(page.get_by_test_id("dossiers-no-results")).to_be_visible()
    page.get_by_role("button", name="Filter zurücksetzen").click()
    expect(cards).to_have_count(3)
    expect(page.get_by_test_id("dossier-search")).to_have_value("")


def test_a_card_opens_the_shared_dossier(page: Page, installed: Stack) -> None:
    """The selection mounts the SAME dossier the graph shows — real fields,
    the page's two profile gap areas, the overview rail's real model fields,
    the live graph door and the AI-sparring gap."""
    novel_id, _ = _seed_dossiers()
    _goto_dossiers(page, novel_id)

    card = page.get_by_test_id("dossier-card").filter(has_text="Kavic")
    card.click()
    expect(card).to_have_attribute("aria-pressed", "true")
    dossier = page.get_by_test_id("entity-dossier")
    expect(dossier).to_be_visible()
    expect(dossier.get_by_role("heading", name="Kavic")).to_be_visible()
    expect(dossier).to_contain_text("Kavic appears in the chapter.")
    expect(dossier).to_contain_text("Verknüpfte Relationen (2)")
    # The shared component's own honesty: the status gap row, the excerpts.
    expect(dossier).to_contain_text("Fundstellen im Manuskript werden noch nicht erfasst.")

    # The page's profile areas — honest disabled, never fake content.
    for testid in ("dossier-psych-gap", "dossier-linguistic-gap"):
        gap = page.get_by_test_id(testid)
        expect(gap).to_have_attribute("aria-disabled", "true")
        expect(gap).to_contain_text("Kommt mit einer späteren Welle")
        expect(gap.get_by_role("button")).to_have_count(0)
    expect(page.get_by_test_id("dossier-psych-gap")).to_contain_text(
        "Psychologisches Profil & Motivation"
    )
    expect(page.get_by_test_id("dossier-linguistic-gap")).to_contain_text(
        "Linguistisches Profil & Dialog-Muster"
    )

    # The overview rail: the selection's REAL model fields.
    overview = page.get_by_test_id("dossier-overview")
    expect(overview).to_contain_text("Kavic")
    expect(overview).to_contain_text("Ort")
    expect(overview).to_contain_text("2 verknüpft")
    expect(page.get_by_test_id("dossier-open-graph")).to_be_enabled()
    ai_gap = page.get_by_test_id("dossier-ai-gap")
    expect(ai_gap).to_have_attribute("aria-disabled", "true")
    expect(ai_gap).to_contain_text("KI-Sparring & Dialog-Simulation")

    # The close returns the honest prompt face.
    page.get_by_role("button", name="Dossier schließen").click()
    expect(page.get_by_test_id("dossiers-no-selection")).to_be_visible()


def test_the_sibling_doors_carry_living_selections(page: Page, installed: Stack) -> None:
    """One consistent mechanism across the three surfaces: a living selection
    travels graph ↔ dossiers, the sources doors carry none (the documents
    are the library's), and a dead id never crosses."""
    novel_id, ids = _seed_dossiers()
    _goto_dossiers(page, novel_id)

    # dossiers → graph with the selection; the graph's dossier opens on it.
    page.get_by_test_id("dossier-card").filter(has_text="Kavic").click()
    page.get_by_test_id("dossiers-graph-door").click()
    expect(page).to_have_url(f"{BASE}/novels/{novel_id}/knowledge/graph?entity={ids['Kavic']}")
    dossier = page.get_by_test_id("entity-dossier")
    expect(dossier.get_by_role("heading", name="Kavic")).to_be_visible()

    # graph → dossiers back, the same entity selected.
    page.get_by_test_id("graph-dossiers-door").click()
    expect(page).to_have_url(f"{BASE}/novels/{novel_id}/knowledge/dossiers?entity={ids['Kavic']}")
    expect(dossier.get_by_role("heading", name="Kavic")).to_be_visible()

    # The rail's graph area is the entity-scoped second crossing.
    page.get_by_test_id("dossier-open-graph").click()
    expect(page).to_have_url(f"{BASE}/novels/{novel_id}/knowledge/graph?entity={ids['Kavic']}")
    page.get_by_test_id("graph-dossiers-door").click()
    expect(page.get_by_test_id("dossiers-page")).to_be_visible()

    # The sources doors carry no selection — documents are the library's.
    page.get_by_test_id("dossiers-sources-door").click()
    expect(page).to_have_url(f"{BASE}/novels/{novel_id}/knowledge/sources")
    expect(page.get_by_test_id("sources-page")).to_be_visible()
    page.get_by_test_id("sources-dossiers-door").click()
    expect(page).to_have_url(f"{BASE}/novels/{novel_id}/knowledge/dossiers")
    expect(page.get_by_test_id("dossiers-no-selection")).to_be_visible()

    # A dead id on the URL resolves to no dossier and never crosses.
    page.goto(f"{BASE}/novels/{novel_id}/knowledge/dossiers?entity=ghost")
    expect(page.get_by_test_id("dossiers-no-selection")).to_be_visible()
    page.get_by_test_id("dossiers-graph-door").click()
    expect(page).to_have_url(f"{BASE}/novels/{novel_id}/knowledge/graph")
    expect(page.get_by_test_id("entity-dossier")).to_have_count(0)


def test_the_empty_canon_keeps_the_sibling_doors(page: Page, installed: Stack) -> None:
    """PR #923's review fix: the subbar stands in every honest state. An
    empty canon still offers the sibling doors beside its empty face — and
    each crossed surface answers with its own empty face and its doors
    back, the one mechanism across all three pages."""
    novel = create_novel("Das leere Buch")
    novel_id = str(novel["id"])
    _goto_dossiers(page, novel_id)
    expect(page.get_by_test_id("dossiers-empty")).to_be_visible()

    # The doors stand beside the honest face and carry no selection.
    page.get_by_test_id("dossiers-graph-door").click()
    expect(page).to_have_url(f"{BASE}/novels/{novel_id}/knowledge/graph")
    expect(page.get_by_test_id("graph-empty")).to_be_visible()
    page.get_by_test_id("graph-sources-door").click()
    expect(page).to_have_url(f"{BASE}/novels/{novel_id}/knowledge/sources")
    expect(page.get_by_test_id("sources-empty")).to_be_visible()
    page.get_by_test_id("sources-dossiers-door").click()
    expect(page).to_have_url(f"{BASE}/novels/{novel_id}/knowledge/dossiers")
    expect(page.get_by_test_id("dossiers-empty")).to_be_visible()


def test_the_dark_dossiers_face_clears_the_axe_floor(page: Page, installed: Stack) -> None:
    """The grid and the open dossier on the tokens' dark halves — the same
    WCAG A/AA floor the light face clears."""
    set_theme("dark")
    novel_id, _ = _seed_dossiers()
    _goto_dossiers(page, novel_id)
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    page.get_by_test_id("dossier-card").filter(has_text="Mira").click()
    expect(page.get_by_test_id("entity-dossier")).to_be_visible()
    assert_accessible(page)
