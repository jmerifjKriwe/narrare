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

Every refusal in this file is the server's own: a suggestion settled by a
second request through the real API answers the real 422 `suggestion-mismatch`,
and `unparseable` makes the real extraction fail. A route may hold a request
for timing and then continue it; it never answers in the server's place.

Four legs hold a turn at the route, so a running answer is deterministic rather
than a race: the handler keeps the `Route` and returns (the request stays
pending), and the test thread releases it once. The first releases one turn while
the panel is hidden and reopens to its reply, then reopens a second turn before
its release — still thinking, composer closed — and lets the reply land. The
second hides the panel, continues the held request so the server's
own 502 `extraction-failed` lands, and reopens to the named failure with the
sent text: the hidden panel never opened itself. The third holds one turn each
in two interviews: returning to the first before either answer lands still shows
it thinking with a closed composer, and each release lands in its own
conversation. The fourth continues a held refusal while a second interview is
shown, and finds the face, the text and the retry in the first on return.
"""

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


def _interview_id(page: Page) -> str:
    """The open interview's id, from the route's `interview` parameter."""
    found = re.search(r"[?&]interview=([0-9a-f-]{36})", page.url)
    assert found is not None, f"the panel's interview parameter is missing on {page.url}"
    return found.group(1)


def _accept_suggestion(session_id: str) -> None:
    """Settle the pending suggestion through the real turn endpoint — the
    pattern ``_add_alias`` uses — so the panel's own press meets a real
    refusal instead of one this test invented."""
    with httpx.Client(base_url=API_URL, timeout=30.0) as client:
        response = client.post(
            f"/api/chat/sessions/{session_id}/turns",
            json={"text": "", "act": "accept-suggestion"},
        )
    response.raise_for_status()


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


def _resume(page: Page, entity_type: str) -> None:
    """Pick the open interview of one type from the list — the type is what
    tells two open rows apart while neither has a name. The type label is
    matched exactly: «Fortsetzen» contains an «ort»."""
    page.get_by_test_id("entity-interview-sessions").click()
    listing = page.get_by_test_id("entity-interview-list")
    row = listing.locator("div.flex.items-center.justify-between").filter(
        has=page.get_by_text(entity_type, exact=True)
    )
    expect(row).to_have_count(1)
    row.get_by_role("button", name="Fortsetzen").click()


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


def test_the_newest_standing_suggestion_alone_is_actionable(page: Page, installed: Stack) -> None:
    """Two «Keine Ahnung» presses leave two pending suggestions — the fake
    answers every press. Only the newest card carries take, change or discard:
    the server settles the newest suggestion, so an older card's action would
    settle another turn. The older one stands as the assistant's plain turn;
    once the newest is taken, the older becomes the actionable suggestion."""
    novel_id = _seed_canon()
    _open_interview(page, novel_id)
    _start(page)

    page.get_by_test_id("entity-interview-no-idea").click()
    expect(page.get_by_test_id("entity-interview-suggestion")).to_be_visible()
    page.get_by_test_id("entity-interview-no-idea").click()

    # Both answers landed: two pending turns stand on the wire.
    transcript = page.get_by_test_id("entity-interview-transcript")
    expect(transcript.get_by_text("Hier ist ein Vorschlag.")).to_have_count(2)
    # One card, one set of actions: the older suggestion is plain turn text.
    expect(page.get_by_test_id("entity-interview-suggestion")).to_have_count(1)
    expect(page.get_by_test_id("entity-interview-suggestion-accept")).to_have_count(1)
    expect(transcript).to_contain_text("Ein Name, der zur Geschichte passt")

    # The one card's press settles the newest suggestion.
    page.get_by_test_id("entity-interview-suggestion-accept").click()
    expect(transcript).to_contain_text("übernommen")
    # The suggestion that was older is the newest pending now: it carries the
    # actions, and no second card stands beside it.
    expect(page.get_by_test_id("entity-interview-suggestion")).to_have_count(1)
    expect(page.get_by_test_id("entity-interview-suggestion-accept")).to_have_count(1)
    assert_accessible(page)


def test_a_stale_suggestion_has_its_own_face(page: Page, installed: Stack) -> None:
    """A suggestion settled before the press answers the real 422
    `suggestion-mismatch`: the panel names it, offers no retry, and the
    suggestion that stands now stays on screen. The second writer is this test,
    through the real turn endpoint — one browser cannot open the second tab
    this stack would need, and a fabricated response would drive neither the
    server nor the database."""
    novel_id = _seed_canon()
    _open_interview(page, novel_id)
    _start(page)
    page.get_by_test_id("entity-interview-no-idea").click()
    expect(page.get_by_test_id("entity-interview-suggestion")).to_be_visible()

    # Another writer settles the pending suggestion first, through the API.
    _accept_suggestion(_interview_id(page))

    page.get_by_test_id("entity-interview-suggestion-accept").click()
    failure = page.get_by_test_id("entity-interview-failure")
    expect(failure).to_contain_text(
        "Der Vorschlag hat sich inzwischen geändert. Sieh dir den aktuellen Vorschlag an."
    )
    expect(page.get_by_test_id("entity-interview-retry")).not_to_be_visible()
    # The refetch brings the suggestion that stands now: settled and marked.
    expect(page.get_by_test_id("entity-interview-transcript")).to_contain_text("übernommen")


def test_hiding_the_panel_while_the_model_answers_keeps_the_turn(
    page: Page, installed: Stack
) -> None:
    """Review Focus 4: the panel may be hidden mid-turn. A turn released while
    the panel is away lands unseen: reopening shows the reply and a free
    composer. A second turn, reopened before its release, still shows it
    thinking with the composer closed, and its reply lands in the open panel.

    Each turn's request is held at the route (the handler keeps it and returns,
    which leaves it pending) and released from the test thread, so the in-flight
    state is deterministic — no dispatcher sleep, no handler that blocks."""
    novel_id = _seed_canon()
    _open_interview(page, novel_id)
    _start(page)

    held: list[Route] = []
    ready = [threading.Event(), threading.Event()]
    arrivals = 0

    def _hold(route: Route) -> None:
        nonlocal arrivals
        ready[arrivals].set()
        arrivals += 1
        held.append(route)

    page.route("**/api/chat/sessions/*/turns", _hold)
    try:
        # First half: the answer lands while the panel is hidden.
        _say(page, f"Name: {NAME}")
        expect(page.get_by_test_id("entity-interview-transcript")).to_contain_text(
            "Der Assistent überlegt ..."
        )
        page.get_by_test_id("entity-interview-close").click()
        expect(page.get_by_test_id("entity-interview")).not_to_be_visible()

        # The thinking row is drawn when the mutation starts, before the
        # handler is guaranteed to have run: wait for the handler itself.
        assert ready[0].wait(timeout=10), "the turn never reached the route handler"
        assert len(held) == 1
        with page.expect_response(
            lambda answer: answer.request.method == "POST" and "/turns" in answer.url
        ) as answered:
            held.pop(0).continue_()
        assert answered.value.status == 200

        # The reply landed while the panel was away, and it must not have
        # opened itself.
        expect(page.get_by_test_id("entity-interview")).not_to_be_visible()
        page.get_by_test_id("graph-new-entity").click()
        panel = page.get_by_test_id("entity-interview")
        expect(panel).to_be_visible()
        expect(panel).to_contain_text("Notiert.")
        expect(page.get_by_test_id("entity-interview-proposal")).to_contain_text(NAME)
        expect(_composer(page)).to_be_enabled()

        # Second half: reopening during the turn still shows it thinking.
        second = "Zweites Relais"
        _say(page, f"Name: {second}")
        expect(panel).to_contain_text("Der Assistent überlegt ...")
        page.get_by_test_id("entity-interview-close").click()
        expect(panel).not_to_be_visible()

        page.get_by_test_id("graph-new-entity").click()
        panel = page.get_by_test_id("entity-interview")
        expect(panel).to_be_visible()
        expect(panel).to_contain_text("Der Assistent überlegt ...")
        expect(_composer(page)).to_be_disabled()
        expect(page.get_by_test_id("entity-interview-save")).to_be_disabled()
        # The thinking face gets the same axe pass as every other face.
        assert_accessible(page)

        assert ready[1].wait(timeout=10), "the second turn never reached the route handler"
        assert len(held) == 1
        held.pop(0).continue_()
        expect(panel).to_contain_text("Notiert.")
        expect(page.get_by_test_id("entity-interview-proposal")).to_contain_text(second)
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
    and no error.

    The refusal is the server's own: `unparseable` makes the real extraction
    fail twice, and the held request is continued rather than answered here,
    so a real 502 lands while the panel is away."""
    novel_id = _seed_canon()
    _open_interview(page, novel_id)
    _start(page)

    sent = "unparseable"
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
        with page.expect_response(
            lambda answer: answer.request.method == "POST" and "/turns" in answer.url
        ) as answered:
            held.pop().continue_()
        assert answered.value.status == 502

        # The failure lands while the panel is hidden and must not open it.
        # The door below selects the same session, so without this assertion
        # the leg could not tell whether the panel had opened itself.
        expect(page.get_by_test_id("entity-interview")).not_to_be_visible()
        page.get_by_test_id("graph-new-entity").click()
        expect(page.get_by_test_id("entity-interview-failure")).to_contain_text(
            "Die Antwort war nicht auswertbar. Dein Text ist noch im Eingabefeld."
        )
        expect(_composer(page)).to_have_value(sent)
    finally:
        while held:
            held.pop().continue_()
        page.unroute_all(behavior="ignoreErrors")


def test_returning_to_an_interview_whose_answer_is_out_keeps_it_busy(
    page: Page, installed: Stack
) -> None:
    """A turn belongs to the interview it was sent for: with A's and B's
    answers both held, returning to A shows its thinking row and a closed
    composer, and each release lands in its own conversation."""
    novel_id = _seed_canon()
    _open_interview(page, novel_id)
    _start(page)

    held: list[Route] = []
    ready = [threading.Event(), threading.Event()]

    def _hold(route: Route) -> None:
        index = len(held)
        held.append(route)
        ready[index].set()

    page.route("**/api/chat/sessions/*/turns", _hold)
    try:
        _say(page, f"Name: {NAME}")
        expect(page.get_by_test_id("entity-interview-transcript")).to_contain_text(
            "Der Assistent überlegt ..."
        )
        assert ready[0].wait(timeout=10), "A's turn never reached the route handler"

        # A second interview while A's answer is still out.
        page.get_by_test_id("entity-interview-sessions").click()
        page.get_by_test_id("entity-interview-list").get_by_role(
            "button", name="Neues Interview"
        ).click()
        _start(page, "location")
        _say(page, "Ein Ort an der Küste.")
        expect(page.get_by_test_id("entity-interview-transcript")).to_contain_text(
            "Der Assistent überlegt ..."
        )
        assert ready[1].wait(timeout=10), "B's turn never reached the route handler"

        # Back in A before its answer lands: it is still thinking, whoever
        # was answered after it; its save door and end button wait too.
        _resume(page, "Objekt")
        panel = page.get_by_test_id("entity-interview")
        expect(panel).to_contain_text("Der Assistent überlegt ...")
        expect(_composer(page)).to_be_disabled()
        expect(page.get_by_test_id("entity-interview-save")).to_be_disabled()
        expect(page.get_by_test_id("entity-interview-end")).to_be_disabled()

        assert len(held) == 2
        held.pop(0).continue_()
        expect(panel).to_contain_text("Notiert.")
        expect(_composer(page)).to_be_enabled()

        # A's settle leaves B alone: B's own answer is still out.
        _resume(page, "Ort")
        expect(page.get_by_test_id("entity-interview")).to_contain_text(
            "Der Assistent überlegt ..."
        )
        expect(_composer(page)).to_be_disabled()

        held.pop(0).continue_()
        expect(page.get_by_test_id("entity-interview")).to_contain_text("Notiert.")
        expect(_composer(page)).to_be_enabled()
    finally:
        while held:
            held.pop().continue_()
        page.unroute_all(behavior="ignoreErrors")


def test_a_failure_of_the_interview_the_writer_left_waits_there(
    page: Page, installed: Stack
) -> None:
    """A turn that fails while another interview is shown keeps its face and
    its words in the interview it was sent for: returning to it, the writer
    finds the named failure, the text still in the composer and the retry —
    and the interview that stood in between took nothing of it.

    The refusal is the server's own: `unparseable` makes the real extraction
    fail twice, so the release answers a real 502 — no fabricated body."""
    novel_id = _seed_canon()
    _open_interview(page, novel_id)
    _start(page)

    held: list[Route] = []
    ready = threading.Event()

    def _hold(route: Route) -> None:
        held.append(route)
        ready.set()

    page.route("**/api/chat/sessions/*/turns", _hold)
    try:
        _say(page, "unparseable")
        expect(page.get_by_test_id("entity-interview-transcript")).to_contain_text(
            "Der Assistent überlegt ..."
        )
        assert ready.wait(timeout=10), "the turn never reached the route handler"

        # A second interview while the first answer is still out.
        page.get_by_test_id("entity-interview-sessions").click()
        page.get_by_test_id("entity-interview-list").get_by_role(
            "button", name="Neues Interview"
        ).click()
        _start(page, "location")

        # The released turn fails for real while this interview is shown.
        with page.expect_response(
            lambda answer: answer.request.method == "POST" and "/turns" in answer.url
        ) as answered:
            held.pop(0).continue_()
        assert answered.value.status == 502

        # The writer's next action is the settle marker: the interview that
        # stood in between is opened again, so the failure's queued state has
        # been written before «B unchanged» is asserted.
        _resume(page, "Ort")
        expect(page.get_by_test_id("entity-interview")).not_to_contain_text(
            "Die Antwort war nicht auswertbar."
        )
        expect(_composer(page)).to_be_enabled()

        # Back in it: the face, the words, the retry.
        _resume(page, "Objekt")
        failure = page.get_by_test_id("entity-interview-failure")
        expect(failure).to_contain_text(
            "Die Antwort war nicht auswertbar. Dein Text ist noch im Eingabefeld."
        )
        expect(_composer(page)).to_have_value("unparseable")
        expect(page.get_by_test_id("entity-interview-retry")).to_be_visible()
    finally:
        while held:
            held.pop().continue_()
        page.unroute_all(behavior="ignoreErrors")


def test_a_long_proposal_keeps_the_conversation_reachable(page: Page, installed: Stack) -> None:
    """A long description and twelve relations stay bounded: the proposal's
    body scrolls inside the card, and the collapse control, the composer, the
    save door and the end button stay in the viewport — in the wide column and
    on the small-screen overlay, without collapsing the proposal first. The
    transcript never shrinks to nothing.

    The writer's turn carries at most 4,000 characters and a model's answer
    may fill the description to 10,000; the leg walks the longest description
    a turn can carry, and the card's bound does not depend on the length."""
    novel_id = _seed_canon()
    _open_interview(page, novel_id)
    _start(page)

    # A short proposal draws its content: the bound must not collapse the
    # body to nothing before a long one ever arrives.
    body = page.get_by_test_id("entity-interview-proposal-body")
    short = body.evaluate("element => element.getBoundingClientRect().height")
    assert short > 40, f"the short proposal's body collapsed to {short}px"

    description = ("Ein Relais, das den Puls der Station misst. " * 100)[:3_960]
    _say(page, f"Beschreibung: {description}")
    proposal = page.get_by_test_id("entity-interview-proposal")
    expect(proposal).to_contain_text("Ein Relais, das den Puls der Station misst.")
    for index in range(12):
        _say(page, f"Beziehung: Ziel {index}|kennt")
        expect(proposal).to_contain_text(f"Ziel {index}")

    def _bounded() -> None:
        expect(page.get_by_test_id("entity-interview-proposal-toggle")).to_be_in_viewport()
        expect(page.get_by_test_id("entity-interview-composer")).to_be_in_viewport()
        expect(page.get_by_test_id("entity-interview-save")).to_be_in_viewport()
        expect(page.get_by_test_id("entity-interview-end")).to_be_in_viewport()
        # The conversation keeps a readable share of the panel.
        transcript = page.get_by_test_id("entity-interview-transcript")
        height = transcript.evaluate("element => element.getBoundingClientRect().height")
        assert height >= 80, f"the transcript collapsed to {height}px"
        # The proposal's own body scrolls inside its bound.
        body = page.get_by_test_id("entity-interview-proposal-body")
        measured = body.evaluate(
            """(element) => ({
                scrollHeight: element.scrollHeight,
                clientHeight: element.clientHeight,
                overflowY: getComputedStyle(element).overflowY,
            })"""
        )
        assert measured["scrollHeight"] > measured["clientHeight"], measured
        assert measured["overflowY"] in ("auto", "scroll"), measured

    _bounded()
    assert_accessible(page)
    # The small-screen overlay holds the same bound.
    page.set_viewport_size({"width": 390, "height": 844})
    _bounded()
    assert_accessible(page)
    page.set_viewport_size({"width": 1280, "height": 720})


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
