# The German face's own quotes and dashes are the catalog text these tests
# assert literally — intentional characters, not confusable typos.
"""The entity interview on the real stack (W9 Task 10): the graph's panel.

The canon is seeded through the real extraction → accept path, and every leg
drives the real panel against the real fake provider at its boundary: the
chooser's type decides the opening question, a key-value answer lands in the
proposal, «Keine Ahnung» offers a suggestion with its three actions, a reload
restores the conversation, ending it leaves the transcript read-only, and
`unparseable` reaches the named «nicht auswertbar» face for real — with the
writer's text still in the composer.

Two legs hold the turn at the route, so the panel's hidden state is
deterministic rather than a race: the handler keeps the `Route` and returns
(the request stays pending), and the test thread releases it once. The first
reopens the panel before that release — still thinking, composer closed — and
then lets the reply land. The second hides the panel, fulfils the held request
with the 502 `provider-error` body, and reopens to the named failure with the
sent text: the hidden panel never opened itself.
"""

import json
import re
import threading
from typing import TYPE_CHECKING

import httpx
import pytest
from playwright.sync_api import Page, Route, expect

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


def _add_alias(entity_id: str, alias: str) -> None:
    """Give an existing row one alias through the real correction path — the
    ambiguous-target leg's second match."""
    with httpx.Client(base_url=API_URL, timeout=30.0) as client:
        response = client.patch(f"/api/knowledge/entities/{entity_id}", json={"aliases": [alias]})
    response.raise_for_status()


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


def test_a_stale_suggestion_has_its_own_face(page: Page, installed: Stack) -> None:
    """A suggestion settled in a second tab answers 422 `suggestion-mismatch`:
    the panel names it, offers no retry, and the current suggestion stays. The
    refusal is forced at the network boundary — one browser cannot open the
    second tab this stack would need."""
    novel_id = _seed_canon()
    _open_interview(page, novel_id)
    _start(page)
    page.get_by_test_id("entity-interview-no-idea").click()
    expect(page.get_by_test_id("entity-interview-suggestion")).to_be_visible()

    def _stale(route: Route) -> None:
        route.fulfill(
            status=422,
            content_type="application/json",
            body=json.dumps(
                {
                    "detail": {
                        "code": "suggestion-mismatch",
                        "detail": "there is no pending suggestion",
                    }
                }
            ),
        )

    page.route("**/api/chat/sessions/*/turns", _stale)
    page.get_by_test_id("entity-interview-suggestion-accept").click()
    failure = page.get_by_test_id("entity-interview-failure")
    expect(failure).to_contain_text(
        "Der Vorschlag hat sich inzwischen geändert. Sieh dir den aktuellen Vorschlag an."
    )
    expect(page.get_by_test_id("entity-interview-retry")).not_to_be_visible()
    # The refetch brings the suggestion that stands now.
    expect(page.get_by_test_id("entity-interview-suggestion")).to_be_visible()
    page.unroute("**/api/chat/sessions/*/turns")


def test_hiding_the_panel_while_the_model_answers_keeps_the_turn(
    page: Page, installed: Stack
) -> None:
    """Review Focus 4: the panel may be hidden mid-turn. Reopening before the
    answer lands still shows it thinking with the composer closed; releasing
    the held request lets the reply land in the open panel.

    The turn's request is held at the route (the handler keeps it and returns,
    which leaves it pending) and released from the test thread, so the in-flight
    state is deterministic — no dispatcher sleep, no handler that blocks."""
    novel_id = _seed_canon()
    _open_interview(page, novel_id)
    _start(page)

    held: list[Route] = []
    held_ready = threading.Event()

    def _hold(route: Route) -> None:
        held.append(route)
        held_ready.set()

    page.route("**/api/chat/sessions/*/turns", _hold)
    try:
        _say(page, f"Name: {NAME}")
        expect(page.get_by_test_id("entity-interview-transcript")).to_contain_text(
            "Der Assistent überlegt ..."
        )
        page.get_by_test_id("entity-interview-close").click()
        expect(page.get_by_test_id("entity-interview")).not_to_be_visible()

        page.get_by_test_id("graph-new-entity").click()
        panel = page.get_by_test_id("entity-interview")
        expect(panel).to_be_visible()
        expect(panel).to_contain_text("Der Assistent überlegt ...")
        expect(_composer(page)).to_be_disabled()
        expect(page.get_by_test_id("entity-interview-save")).to_be_disabled()

        # The thinking row is drawn when the mutation starts, before the
        # handler is guaranteed to have run: wait for the handler itself.
        assert held_ready.wait(timeout=10), "the turn never reached the route handler"
        assert len(held) == 1
        held.pop().continue_()
        expect(panel).to_contain_text("Notiert.")
        expect(page.get_by_test_id("entity-interview-proposal")).to_contain_text(NAME)
        expect(_composer(page)).to_be_enabled()
    finally:
        while held:
            held.pop().continue_()
        page.unroute_all(behavior="ignoreErrors")


def test_hiding_the_panel_when_the_answer_fails_keeps_its_explanation(
    page: Page, installed: Stack
) -> None:
    """A turn that fails while the panel is hidden keeps its named face and
    the writer's text: reopening shows the explanation, not an empty composer
    and no error."""
    novel_id = _seed_canon()
    _open_interview(page, novel_id)
    _start(page)

    sent = "Es stammt aus dem Labor von Lin."
    held: list[Route] = []
    held_ready = threading.Event()

    def _hold(route: Route) -> None:
        held.append(route)
        held_ready.set()

    page.route("**/api/chat/sessions/*/turns", _hold)
    try:
        _say(page, sent)
        expect(page.get_by_test_id("entity-interview-transcript")).to_contain_text(
            "Der Assistent überlegt ..."
        )
        page.get_by_test_id("entity-interview-close").click()
        expect(page.get_by_test_id("entity-interview")).not_to_be_visible()

        # As above: the thinking row predates the handler, so wait for it.
        assert held_ready.wait(timeout=10), "the turn never reached the route handler"
        assert len(held) == 1
        held.pop().fulfill(
            status=502,
            content_type="application/json",
            body=json.dumps(
                {
                    "detail": {
                        "code": "provider-error",
                        "detail": "the provider is offline",
                    }
                }
            ),
        )

        # The failure lands while the panel is hidden and must not open it.
        # The door below selects the same session, so without this assertion
        # the leg could not tell whether the panel had opened itself.
        expect(page.get_by_test_id("entity-interview")).not_to_be_visible()
        page.get_by_test_id("graph-new-entity").click()
        expect(page.get_by_test_id("entity-interview-failure")).to_contain_text(
            "Die Antwort kam nicht. Dein Text ist noch im Eingabefeld."
        )
        expect(_composer(page)).to_have_value(sent)
    finally:
        while held:
            held.pop().continue_()
        page.unroute_all(behavior="ignoreErrors")


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
    assert_accessible(page)


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


def test_the_interview_ends_in_an_entity_with_relations(page: Page, installed: Stack) -> None:
    """The handover: «Alles vorschlagen lassen» fills and marks the proposal,
    «Als Entität speichern» opens the create dialog prefilled with the locked
    type and the resolved relation, and saving puts the entity and its edge
    into the graph, closes the interview and selects the new row. The fake
    proposes one ``related_to`` to the first roster entry, name-ordered:
    «Forschungsstation»."""
    novel_id = _seed_canon()
    entities = {row["name"]: row for row in list_entities(novel_id)}
    # «Kavic» names the location and is also Mira's alias: one word, two rows.
    _add_alias(str(entities["Mira"]["id"]), "Kavic")
    _open_interview(page, novel_id)
    _start(page)
    _say(page, f"Name: {NAME}")
    expect(page.get_by_test_id("entity-interview-proposal")).to_contain_text(NAME)

    page.get_by_test_id("entity-interview-fill-all").click()
    proposal = page.get_by_test_id("entity-interview-proposal")
    expect(proposal).to_contain_text("vorgeschlagen")
    expect(proposal).to_contain_text("Forschungsstation")
    expect(proposal).to_contain_text("Verbunden mit")

    save_door = page.get_by_test_id("entity-interview-save")
    expect(save_door).to_be_enabled()
    save_door.click()

    dialog = page.get_by_test_id("entity-create-dialog")
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text("Aus dem Interview")
    # The session fixed the type: a locked chip, no select.
    expect(dialog.get_by_test_id("entity-create-type")).to_have_count(0)
    locked = dialog.get_by_test_id("entity-create-type-locked")
    expect(locked).to_contain_text("Objekt")
    expect(locked).to_contain_text("Fixiert")
    # The proposed parts keep their mark; the relation resolves to the real row.
    expect(dialog).to_contain_text("vorgeschlagen")
    expect(dialog.get_by_test_id("entity-create-relation-0-entity")).to_have_value(
        "Forschungsstation"
    )
    expect(dialog.get_by_test_id("entity-create-relation-0-suggested")).to_be_visible()
    assert_accessible(page)

    # Review Focus 3: a target that names one row and aliases another offers
    # both and blocks nothing. The writer picks the location before saving.
    target = dialog.get_by_test_id("entity-create-relation-0-entity")
    target.fill("Kavic")
    many = dialog.get_by_test_id("entity-create-relation-0-many")
    expect(many).to_contain_text("Mehrere Treffer — wählen")
    expect(many).to_contain_text("Kavic")
    expect(many).to_contain_text("Mira")
    assert_accessible(page)
    dialog.get_by_test_id(f"entity-create-relation-0-choice-{entities['Kavic']['id']}").click()
    expect(dialog.get_by_test_id("entity-create-relation-0-many")).to_have_count(0)
    expect(target).to_have_value("Kavic")

    dialog.get_by_test_id("entity-create-save").click()
    expect(dialog).not_to_be_visible()
    expect(page.get_by_test_id("toast")).to_contain_text("Entität angelegt · 1 Beziehung verknüpft")

    # The save selects the new row and the edge stands in its dossier.
    dossier = page.get_by_test_id("entity-dossier")
    expect(dossier).to_be_visible()
    expect(dossier).to_contain_text(NAME)
    expect(dossier).to_contain_text("Kavic")
    expect(dossier).to_contain_text("Verbunden mit")
    assert_accessible(page)

    # The interview is closed; its row moved to «Beendet» in the list.
    page.get_by_test_id("graph-new-entity").click()
    expect(page.get_by_test_id("entity-interview")).to_be_visible()
    page.get_by_test_id("entity-interview-sessions").click()
    listing = page.get_by_test_id("entity-interview-list")
    expect(listing).to_contain_text("Beendet")
    expect(listing).to_contain_text(NAME)
    assert_accessible(page)
