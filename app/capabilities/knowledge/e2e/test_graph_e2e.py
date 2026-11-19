# The German face's own quotes and dashes are the catalog text these tests
# assert literally — intentional characters, not confusable typos.
"""The lore graph on the real stack (W5 Task 7): the deterministic web.

The canon is seeded through the real extraction → accept path (the fake
derives three names from the prose; the accept order steers which proposed
relations land), one edge carries a note through the real PATCH. The legs
pin what jsdom could not: the deterministic layout drawing identically across
a remount, the edge's LIVE keyboard focus ring (an outline on the SVG group),
Enter/Escape owning the note popover with the focus return, and the zoom
HUD's honest reset. The dossier panel, the client-side filters and the CRUD
dialog ride the same real API the vitest pins mock at the client boundary.
"""

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

from app.capabilities.knowledge.e2e.conftest import (
    create_chapter,
    create_novel,
    list_entities,
    list_relations,
    patch_relation,
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

# Three capitalized names — Mira, Kavic, Vulkan — typed character, location,
# faction by the vocabulary cycle. Accepted in reverse, the chain's two
# proposals land: Mira → Kavic and Kavic → Vulkan.
CAST_PROSE = "Mira trifft Kavic auf Vulkan."
EDGE_NOTE = "Sie kennen sich seit Jahren."


def _seed_graph() -> str:
    """The novel whose canon the graph draws; the Mira → Kavic edge carries
    a note, the other stands honest without one."""
    novel = create_novel("Das Signal")
    novel_id = str(novel["id"])
    chapter = create_chapter(novel_id, "Ankunft")
    write_scene(str(chapter["id"]), CAST_PROSE)
    seed_canon(novel_id, str(chapter["id"]), accept_order=["Vulkan", "Kavic", "Mira"])
    by_name = {row["name"]: row for row in list_entities(novel_id)}
    for relation in list_relations(novel_id):
        if (
            relation["from_entity_id"] == by_name["Mira"]["id"]
            and relation["to_entity_id"] == by_name["Kavic"]["id"]
        ):
            patch_relation(str(relation["id"]), note=EDGE_NOTE)
    return novel_id


def _goto_graph(page: Page, novel_id: str) -> None:
    page.goto(f"{BASE}/novels/{novel_id}/knowledge/graph")
    expect(page.get_by_test_id("graph-page")).to_be_visible()


def _node_positions(page: Page) -> dict[str, str]:
    """Each node card's laid-out seat, named by the card's own text."""
    positions: dict[str, str] = page.get_by_test_id("graph-node").evaluate_all(
        "nodes => Object.fromEntries("
        "nodes.map(n => [n.textContent, n.style.left + '/' + n.style.top]))"
    )
    return positions


def test_the_graph_draws_the_deterministic_web(page: Page, installed: Stack) -> None:
    """The same canon draws the same picture across a remount — the pure
    layout pass, live — and the HUD's reset returns to the fit framing."""
    novel_id = _seed_graph()
    _goto_graph(page, novel_id)

    expect(page.get_by_test_id("graph-node")).to_have_count(3)
    expect(page.get_by_test_id("graph-edge")).to_have_count(2)
    expect(page.get_by_test_id("graph-legend")).to_contain_text("3 Entitäten • 2 Relationen")
    # The cards carry the rows' own facts: name, type, the body's first line.
    mira = page.get_by_test_id("graph-node").filter(has_text="Mira")
    expect(mira).to_contain_text("Figur")
    expect(mira).to_contain_text("Mira appears in the chapter.")
    expect(page.get_by_test_id("graph-edge").nth(0)).to_have_attribute(
        "aria-label", "Kavic → Vulkan, Verbunden mit"
    )
    expect(page.get_by_test_id("graph-edge").nth(1)).to_have_attribute(
        "aria-label", "Mira → Kavic, Verbunden mit"
    )

    # Determinism: a full remount seats every card identically.
    before = _node_positions(page)
    assert len(before) == 3
    page.reload()
    expect(page.get_by_test_id("graph-node")).to_have_count(3)
    assert _node_positions(page) == before

    # The zoom HUD scales the world; the honest reset returns to the fit.
    world = page.get_by_test_id("graph-world")
    fit = world.evaluate("el => el.style.transform")
    page.get_by_test_id("zoom-in").click()
    zoomed = world.evaluate("el => el.style.transform")
    assert zoomed != fit
    page.get_by_test_id("reset-view").click()
    assert world.evaluate("el => el.style.transform") == fit
    assert_accessible(page)


def test_the_type_filter_and_name_search_narrow_the_web(page: Page, installed: Stack) -> None:
    """Filtering hides, never re-seats: the chips and the search compose
    client-side over the loaded web, and the no-results face clears both —
    the clear button's click is its own, never a captured pan (the jsdom
    pin's live proof)."""
    novel_id = _seed_graph()
    _goto_graph(page, novel_id)
    nodes = page.get_by_test_id("graph-node")
    edges = page.get_by_test_id("graph-edge")

    # The type chip narrows to the one character; both edges lose an end.
    page.get_by_test_id("type-chip").filter(has_text="Figur").click()
    expect(nodes).to_have_count(1)
    expect(nodes).to_contain_text("Mira")
    expect(edges).to_have_count(0)
    expect(page.get_by_test_id("graph-legend")).to_contain_text("1 Entität • 0 Relationen")
    # The pressed chip toggles back to the whole web.
    page.get_by_test_id("type-chip").filter(has_text="Figur").click()
    expect(nodes).to_have_count(3)

    # The name search narrows; clearing restores.
    page.get_by_test_id("graph-search").fill("kavic")
    expect(nodes).to_have_count(1)
    expect(nodes).to_contain_text("Kavic")
    page.get_by_test_id("graph-search").fill("")
    expect(nodes).to_have_count(3)

    # A filter that matches nothing answers the no-results face; the clear
    # door resets BOTH filters (the composition is AND).
    page.get_by_test_id("type-chip").filter(has_text="Ort").click()
    page.get_by_test_id("graph-search").fill("mira")
    expect(page.get_by_test_id("graph-no-results")).to_be_visible()
    page.get_by_test_id("graph-no-results").get_by_role(
        "button", name="Filter zurücksetzen"
    ).click()
    expect(nodes).to_have_count(3)
    expect(page.get_by_test_id("graph-search")).to_have_value("")


def test_the_edge_speaks_to_the_keyboard(page: Page, installed: Stack) -> None:
    """The edge is a focusable, named button with a LIVE focus ring (the
    outline jsdom cannot lay out); Enter opens its note popover, Escape
    closes it and returns the focus, the close door returns it too."""
    novel_id = _seed_graph()
    _goto_graph(page, novel_id)

    # Keyboard navigation from the search box: the subbar's remaining doors,
    # then the canvas's edges. Tab until an edge owns the focus.
    page.get_by_test_id("graph-search").click()
    for _ in range(10):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement?.hasAttribute('data-edge') ?? false"):
            break
    else:
        pytest.fail("no edge reached the focus within ten Tabs")

    edge = page.locator("[data-edge]:focus")
    # The live focus ring: the outline the review fix drew for SVG (a
    # box-shadow ring cannot render there). Keyboard focus matches
    # :focus-visible, so the ring is laid out — style, width, offset.
    ring = edge.evaluate(
        "el => { const s = getComputedStyle(el);"
        " return [s.outlineStyle, s.outlineWidth, s.outlineOffset]; }"
    )
    assert ring == ["solid", "2px", "2px"], ring
    first_id = edge.get_attribute("data-edge-id")

    # Enter opens the popover — the first edge (Kavic → Vulkan) carries no
    # note, so the honest no-note face stands.
    page.keyboard.press("Enter")
    popover = page.get_by_test_id("edge-popover")
    expect(popover).to_be_visible()
    expect(popover).to_contain_text("Kavic → Vulkan")
    expect(popover).to_contain_text("Verbunden mit")
    expect(popover).to_contain_text("Keine Notiz hinterlegt.")

    # Escape closes and hands the focus back to the opener edge.
    page.keyboard.press("Escape")
    expect(popover).to_have_count(0)
    assert page.evaluate("document.activeElement?.getAttribute('data-edge-id')") == first_id

    # The next edge carries the seeded note; the close door returns focus too.
    page.keyboard.press("Tab")
    second_id = page.evaluate("document.activeElement?.getAttribute('data-edge-id')")
    assert second_id != first_id
    page.keyboard.press("Enter")
    expect(popover).to_contain_text("Mira → Kavic")
    expect(popover).to_contain_text(EDGE_NOTE)
    page.get_by_role("button", name="Notiz schließen").click()
    expect(popover).to_have_count(0)
    assert page.evaluate("document.activeElement?.getAttribute('data-edge-id')") == second_id


def test_a_node_opens_its_dossier_and_the_edit_is_real(page: Page, installed: Stack) -> None:
    """The node click opens the shared dossier on the row's own facts; the
    relation card's door selects the other end; the edit dialog writes
    through the real PATCH and the graph refetches the server's truth."""
    novel_id = _seed_graph()
    _goto_graph(page, novel_id)

    page.get_by_test_id("graph-node").filter(has_text="Kavic").get_by_role("button").click()
    dossier = page.get_by_test_id("entity-dossier")
    expect(dossier).to_be_visible()
    expect(dossier.get_by_role("heading", name="Kavic")).to_be_visible()
    expect(dossier).to_contain_text("Ort")
    expect(dossier).to_contain_text("Kavic appears in the chapter.")
    # The invented status stays a neutral gap row; the excerpts gap stands.
    expect(dossier).to_contain_text("Status")
    expect(dossier).to_contain_text("Fundstellen im Manuskript werden noch nicht erfasst.")
    # Both real edges, both directions — the other end named as a door. The
    # select door's name STARTS with the end's name; the edit/delete
    # affordances beside it carry „Relation …: {name}" — anchor the name so
    # the door alone answers.
    relations = dossier.locator("#dossier-relations")
    expect(relations.get_by_role("button", name=re.compile(r"^Mira"))).to_be_visible()
    expect(relations.get_by_role("button", name=re.compile(r"^Vulkan"))).to_be_visible()

    # The relation card's main door selects the other end.
    relations.get_by_role("button", name=re.compile(r"^Mira")).click()
    expect(dossier.get_by_role("heading", name="Mira")).to_be_visible()
    # The close folds the panel and clears the URL's selection.
    page.get_by_role("button", name="Dossier schließen").click()
    expect(dossier).to_have_count(0)
    expect(page).to_have_url(f"{BASE}/novels/{novel_id}/knowledge/graph")

    # The edit dialog: a real write, the graph refetches the renamed row.
    page.get_by_test_id("graph-node").filter(has_text="Vulkan").get_by_role("button").click()
    expect(dossier.get_by_role("heading", name="Vulkan")).to_be_visible()
    page.locator("#dossier-edit").click()
    dialog = page.get_by_role("dialog", name="Entität bearbeiten")
    expect(dialog).to_be_visible()
    dialog.get_by_label("Name").fill("Vulkanbund")
    dialog.get_by_role("button", name="Speichern").click()
    expect(dialog).to_have_count(0)
    expect(dossier.get_by_role("heading", name="Vulkanbund")).to_be_visible()
    expect(page.get_by_test_id("graph-node").filter(has_text="Vulkanbund")).to_be_visible()
    assert_accessible(page)


def test_the_dark_graph_face_clears_the_axe_floor(page: Page, installed: Stack) -> None:
    """The graph and its open dossier on the tokens' dark halves — the same
    WCAG A/AA floor the light face clears."""
    set_theme("dark")
    novel_id = _seed_graph()
    _goto_graph(page, novel_id)
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    page.get_by_test_id("graph-node").filter(has_text="Mira").get_by_role("button").click()
    expect(page.get_by_test_id("entity-dossier")).to_be_visible()
    assert_accessible(page)
