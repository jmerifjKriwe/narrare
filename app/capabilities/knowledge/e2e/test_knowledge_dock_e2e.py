"""The Wissen dock: entities, review and job status beside the editor.

The tab is registry-driven: knowledge exports dockRoutes and the generated
registry carries the row, so the workspace renders the tab with zero
generator changes. Inside, extraction on the chapter the editor is showing
runs as a durable job — the panel polls the row's state, never a connection
— and the finished queue arrives as proposal cards. Both review decisions
are pinned: accept files the entity into the searchable list, discard clears
it, and the spent queue empties. The Titel-refusal carry rides the same
flow's book-creation step: the failed submit names the empty field with the
catalog's words.
"""

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

from app.kernel.testing.a11y import assert_accessible

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

# Capitalized words steer the fake provider's extraction (it derives names
# from them): Mira, Haus and See become the three suggestions, kinds cycling
# character, place, thing in order of appearance. Draußen is fourth, beyond
# the fake's ceiling of three.
CHAPTER_BODY = "Mira betrat das alte Haus am See. Draußen schwieg der Leuchtturm."


def _open_workspace_with_validated_title(page: Page, title: str) -> None:
    """Create a novel the only way a user can — refusing an empty Titel first.

    The refusal is the Titel-validation carry: the failed submit names the
    empty field instead of silently doing nothing.
    """
    page.goto("http://127.0.0.1:3100/")
    page.get_by_role("button", name="Neues Buch").click()
    page.get_by_role("button", name="Anlegen").click()
    expect(page.get_by_text("Bitte gib einen Titel ein.")).to_be_visible()
    page.get_by_label("Titel").fill(title)
    page.get_by_role("button", name="Anlegen").click()
    page.get_by_role("link", name=title).click()
    expect(page.get_by_role("heading", name=title)).to_be_visible()


def test_the_wissen_dock_reviews_extraction_beside_the_editor(page: Page, stack: Stack) -> None:
    _open_workspace_with_validated_title(page, "Das Wissen der Bucht")

    page.get_by_role("button", name="Neues Kapitel").click()
    editor = page.locator(".ProseMirror")
    expect(editor).to_be_visible()
    editor.click()
    page.keyboard.type(CHAPTER_BODY)
    # Extraction reads the saved chapter, so the test waits for the save the
    # editor itself reports before asking for the job.
    expect(page.get_by_text("Gespeichert")).to_be_visible()

    # The tab comes from the generated dock registry; the keyboard opens it.
    tab = page.get_by_role("button", name="Wissen", exact=True)
    expect(tab).to_be_visible()
    tab.focus()
    page.keyboard.press("Enter")
    dock = page.get_by_role("complementary", name="Wissen")
    expect(dock).to_be_visible()
    expect(editor).to_be_visible()

    # Extraction runs on the chapter the editor is showing — the active
    # chapter reaches the dock through the shell seam, not the URL. The
    # trigger closes while its job is outstanding: a second click could not
    # stack a duplicate job — and a duplicate review queue — behind the first.
    extract = dock.get_by_role("button", name="Dieses Kapitel durchsuchen")
    extract.click()
    expect(extract).to_be_disabled()
    status = dock.locator("[data-job-status]")
    expect(status).to_be_visible()
    # The row is the answer (spec §9 D10): whatever the first poll sees —
    # queued, running, done — it settles done with the result count.
    expect(status).to_have_attribute("data-job-status", "done")
    expect(status).to_contain_text("3")
    # The settled job hands the trigger back for the next run.
    expect(extract).to_be_enabled()

    # The finished queue arrives as proposal cards: one per proposed entity.
    cards = dock.get_by_role("region", name="Vorgeschlagene Entität")
    expect(cards).to_have_count(3)

    # Accept files the entity: Mira appears in the list beside the editor.
    cards.filter(has_text="Mira").get_by_role("button", name="Übernehmen", exact=True).click()
    entities = dock.get_by_role("region", name="Entitäten")
    expect(entities).to_contain_text("Mira")

    # Discard clears: See never becomes an entity.
    cards.filter(has_text="See").get_by_role("button", name="Verwerfen").click()
    expect(entities).not_to_contain_text("See")

    # A second accept, the queue's other spent row: Haus is filed too.
    cards.filter(has_text="Haus").get_by_role("button", name="Übernehmen", exact=True).click()
    expect(entities).to_contain_text("Haus")

    # The queue is spent. A consumed suggestion cannot be reviewed again —
    # the backend's 409 is pinned in tests/test_entities.py; here the UI's
    # side of that contract is the emptied queue.
    expect(cards).to_have_count(0)

    # The status stays the result, not a spinner: polling stopped with the
    # done row. No /api/jobs request may leave the page for the next turns
    # of the poll's own clock.
    poll_silence: list[str] = []
    page.on(
        "request",
        lambda request: poll_silence.append(request.url) if "/api/jobs/" in request.url else None,
    )
    page.wait_for_timeout(2500)
    assert poll_silence == [], f"the done job is still polled: {poll_silence}"

    # The chapter-scoped search: typing narrows the list it sits above.
    dock.get_by_label("Entitäten durchsuchen").fill("Mira")
    expect(entities.get_by_text("Mira", exact=True)).to_be_visible()
    expect(entities.get_by_text("Haus", exact=True)).to_have_count(0)
    dock.get_by_label("Entitäten durchsuchen").press("Escape")

    # Selecting an entity opens its detail: the kind and description of the
    # row the review filed.
    entities.get_by_text("Mira", exact=True).click()
    detail = dock.get_by_role("region", name="Mira")
    expect(detail).to_contain_text("Figur")
    expect(detail).to_contain_text("Mira appears in the chapter.")

    assert_accessible(page)
