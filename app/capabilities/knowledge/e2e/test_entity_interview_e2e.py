# The German face's own quotes and dashes are the catalog text these tests
# assert literally — intentional characters, not confusable typos.
"""The entity interview on the real stack (W9 Task 10): the graph's panel.

The canon is seeded through the real extraction → accept path, and every leg
drives the real panel against the real fake provider at its boundary: the
chooser's type decides the opening question, a key-value answer lands in the
proposal, «Keine Ahnung» offers a suggestion with its three actions, the panel
may be hidden while the model answers and returns with the reply, a reload
restores the conversation, ending it leaves the transcript read-only, and
`unparseable` reaches the named «nicht auswertbar» face for real — with the
writer's text still in the composer.
"""

import re
import time
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, Route, expect

from app.capabilities.knowledge.e2e.conftest import (
    create_chapter,
    create_novel,
    seed_canon,
    write_scene,
)
from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.stack import WEB_URL

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

BASE = WEB_URL

CAST_PROSE = "Mira trifft Kavic auf Forschungsstation."
NAME = "Resonanz-Transponder LC-89"
OPENING_OBJECT = (
    "Was möchtest du anlegen? Nenn mir den Namen des Objekts und sag in einem Satz, was es ist."
)


def _seed_canon() -> str:
    """A novel with a small canon: the interview's roster for «Alles vorschlagen»."""
    novel = create_novel("Das Signal")
    novel_id = str(novel["id"])
    chapter = create_chapter(novel_id, "Ankunft")
    write_scene(str(chapter["id"]), CAST_PROSE)
    seed_canon(novel_id, str(chapter["id"]))
    return novel_id


def _goto_graph(page: Page, novel_id: str) -> None:
    page.goto(f"{BASE}/novels/{novel_id}/knowledge/graph")
    expect(page.get_by_test_id("graph-page")).to_be_visible()


def _open_interview(page: Page, novel_id: str) -> None:
    _goto_graph(page, novel_id)
    page.get_by_test_id("graph-new-entity").click()
    expect(page.get_by_test_id("entity-interview")).to_be_visible()


def _start(page: Page, entity_type: str = "object") -> None:
    page.get_by_test_id(f"entity-interview-type-{entity_type}").click()
    page.get_by_test_id("entity-interview-start").click()
    expect(page.get_by_test_id("entity-interview-proposal")).to_be_visible()


def _composer(page: Page):
    return page.get_by_test_id("entity-interview-composer").locator("textarea")


def _say(page: Page, text: str) -> None:
    _composer(page).fill(text)
    page.get_by_test_id("entity-interview-send").click()


def test_the_interview_asks_and_collects(page: Page, installed: Stack) -> None:
    """The door opens on the chooser; «Objekt» fixes the type, the opening
    question fits it, and a key-value answer lands in the proposal."""
    novel_id = _seed_canon()
    _open_interview(page, novel_id)
    assert_accessible(page)

    page.get_by_test_id("entity-interview-type-object").click()
    page.get_by_test_id("entity-interview-start").click()
    expect(page.get_by_test_id("entity-interview-transcript")).to_contain_text(OPENING_OBJECT)
    expect(page.get_by_test_id("entity-interview-proposal")).to_contain_text("Objekt")
    assert_accessible(page)

    _say(page, f"Name: {NAME}")
    proposal = page.get_by_test_id("entity-interview-proposal")
    expect(proposal).to_contain_text(NAME)
    expect(page.get_by_test_id("entity-interview-send")).to_be_disabled()
    expect(_composer(page)).to_be_enabled()
    # The conversation survives in the URL: the panel's session is addressable.
    expect(page).to_have_url(re.compile(r"interview="))
    assert_accessible(page)

    # Hiding the panel leaves the open interview counted at the door.
    page.get_by_test_id("entity-interview-close").click()
    expect(page.get_by_test_id("entity-interview")).not_to_be_visible()
    expect(page.get_by_test_id("graph-new-entity-count")).to_have_text("1")


def test_no_idea_offers_a_suggestion_with_three_actions(page: Page, installed: Stack) -> None:
    """«Keine Ahnung» proposes an answer for the question and offers take,
    change or discard — without touching the proposal."""
    novel_id = _seed_canon()
    _open_interview(page, novel_id)
    _start(page)

    page.get_by_test_id("entity-interview-no-idea").click()
    card = page.get_by_test_id("entity-interview-suggestion")
    expect(card).to_be_visible()
    expect(card).to_contain_text("Ein Name, der zur Geschichte passt")
    expect(card.get_by_test_id("entity-interview-suggestion-accept")).to_be_visible()
    expect(card.get_by_test_id("entity-interview-suggestion-edit")).to_be_visible()
    expect(card.get_by_test_id("entity-interview-suggestion-reject")).to_be_visible()
    assert_accessible(page)

    card.get_by_test_id("entity-interview-suggestion-edit").click()
    expect(_composer(page)).to_have_value(
        "Ein Name, der zur Geschichte passt, wäre ein guter Anfang."
    )


def test_hiding_the_panel_while_the_model_answers_keeps_the_reply(
    page: Page, installed: Stack
) -> None:
    """Review Focus 4: the panel may be hidden mid-turn; the reply still lands,
    reopening shows it, and the composer is free again."""
    novel_id = _seed_canon()
    _open_interview(page, novel_id)
    _start(page)

    # Shape the network so the turn is observably in flight: the request is
    # the same real one, just delivered with a pause.
    def _slow(route: Route) -> None:
        time.sleep(0.8)
        route.continue_()

    page.route("**/api/chat/sessions/*/turns", _slow)
    with page.expect_response(re.compile(r"/api/chat/sessions/.*/turns")):
        _say(page, f"Name: {NAME}")
        expect(page.get_by_test_id("entity-interview-transcript")).to_contain_text(
            "Der Assistent überlegt ..."
        )
        page.get_by_test_id("entity-interview-close").click()
        expect(page.get_by_test_id("entity-interview")).not_to_be_visible()
    page.unroute("**/api/chat/sessions/*/turns")

    page.get_by_test_id("graph-new-entity").click()
    panel = page.get_by_test_id("entity-interview")
    expect(panel).to_be_visible()
    expect(panel).to_contain_text("Notiert.")
    expect(page.get_by_test_id("entity-interview-proposal")).to_contain_text(NAME)
    expect(_composer(page)).to_be_enabled()


def test_the_interview_survives_a_reload(page: Page, installed: Stack) -> None:
    """The session and its transcript ride the route's parameter: a reload
    restores the conversation, not a fresh panel."""
    novel_id = _seed_canon()
    _open_interview(page, novel_id)
    _start(page)
    _say(page, f"Name: {NAME}")
    expect(page.get_by_test_id("entity-interview-proposal")).to_contain_text(NAME)

    page.reload()
    panel = page.get_by_test_id("entity-interview")
    expect(panel).to_be_visible()
    expect(page.get_by_test_id("entity-interview-proposal")).to_contain_text(NAME)
    expect(page.get_by_test_id("entity-interview-transcript")).to_contain_text(NAME)
    expect(page.get_by_test_id("entity-interview-transcript")).to_contain_text("Notiert.")


def test_ending_makes_the_interview_read_only_and_keeps_it_savable(
    page: Page, installed: Stack
) -> None:
    """Ending is explicit: the composer disappears, the conversation and the
    proposal stay readable, and the list files the row under «Beendet»."""
    novel_id = _seed_canon()
    _open_interview(page, novel_id)
    _start(page)
    _say(page, f"Name: {NAME}")
    expect(page.get_by_test_id("entity-interview-proposal")).to_contain_text(NAME)

    page.get_by_test_id("entity-interview-end").click()
    expect(page.get_by_test_id("entity-interview")).to_contain_text(
        "Dieses Interview ist beendet. Das Gespräch bleibt lesbar."
    )
    expect(page.get_by_test_id("entity-interview-composer")).not_to_be_visible()
    expect(page.get_by_test_id("entity-interview-proposal")).to_contain_text(NAME)
    assert_accessible(page)

    page.get_by_test_id("entity-interview-sessions").click()
    listing = page.get_by_test_id("entity-interview-list")
    expect(listing).to_contain_text("Beendet")
    expect(listing).to_contain_text(NAME)


def test_rejecting_a_suggestion_returns_to_the_question(page: Page, installed: Stack) -> None:
    """«Verwerfen» settles the suggestion silently and leaves the question's
    conversation open for the writer's own answer."""
    novel_id = _seed_canon()
    _open_interview(page, novel_id)
    _start(page)
    page.get_by_test_id("entity-interview-no-idea").click()
    expect(page.get_by_test_id("entity-interview-suggestion")).to_be_visible()

    page.get_by_test_id("entity-interview-suggestion-reject").click()
    expect(page.get_by_test_id("entity-interview-suggestion")).not_to_be_visible()
    expect(page.get_by_test_id("entity-interview-transcript")).to_contain_text("Verwerfen")
    expect(_composer(page)).to_be_enabled()
    expect(page.get_by_test_id("entity-interview-no-idea")).to_be_enabled()


def test_suggestions_can_be_discarded(page: Page, installed: Stack) -> None:
    """«Alles vorschlagen lassen» fills what is open and marks it; «Vorschläge
    verwerfen» takes every suggested part out and keeps the writer's own."""
    novel_id = _seed_canon()
    _open_interview(page, novel_id)
    _start(page)
    _say(page, f"Name: {NAME}")
    expect(page.get_by_test_id("entity-interview-proposal")).to_contain_text(NAME)

    page.get_by_test_id("entity-interview-fill-all").click()
    proposal = page.get_by_test_id("entity-interview-proposal")
    expect(proposal).to_contain_text("vorgeschlagen")
    expect(proposal).to_contain_text("Ein Vorschlag des Fake-Treibers.")
    expect(page.get_by_test_id("entity-interview-drop-suggestions")).to_be_visible()

    page.get_by_test_id("entity-interview-drop-suggestions").click()
    expect(proposal).not_to_contain_text("vorgeschlagen")
    # The writer's own name stays; the open slots are open again.
    expect(proposal).to_contain_text(NAME)
    expect(proposal).to_contain_text("noch offen")
    expect(page.get_by_test_id("entity-interview-drop-suggestions")).not_to_be_visible()


def test_unparseable_shows_the_named_face_and_keeps_the_text(page: Page, installed: Stack) -> None:
    """The wire's repair attempt fails twice on prose: the named «nicht
    auswertbar» face stands and the writer's words are still in the field."""
    novel_id = _seed_canon()
    _open_interview(page, novel_id)
    _start(page)

    _say(page, "unparseable")
    failure = page.get_by_test_id("entity-interview-failure")
    expect(failure).to_be_visible()
    expect(failure).to_contain_text(
        "Die Antwort war nicht auswertbar. Dein Text ist noch im Eingabefeld."
    )
    expect(_composer(page)).to_have_value("unparseable")
    expect(page.get_by_test_id("entity-interview-retry")).to_be_visible()
    assert_accessible(page)
