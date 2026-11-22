"""Scene continuation on the real stack (W4 §5): the SSE door, end to end.

The endpoint ``POST /api/writing/scenes/{id}/continue`` is driven on the real
server and the real Postgres, the fake provider the one permitted boundary
fake (rule 2). The frames, the done event and the audit row are already pinned
in process; this leg proves they survive a real HTTP server — the SSE framing
and the door's own content-type and cache-control headers on the wire, and the
audit row written by the deployed stack. The response is read whole, so it
does not prove incremental delivery. Everything else about the door — the
missing scene's 404, the over-long prompt's 422, the coded refusal frames
(key-unavailable, prompt-refused incl. budget), the prompt that reaches the
provider byte for byte, and the foreign-user boundary — is pinned by the
integration oracle (``tests/test_continuation.py``).

The UI legs (W4 Task 16, design G4) ride the same stack: the prompt bar's ask
streams into the ghost preview at the scene tail, Tab accepts into the
autosave chain (the PUT carries the joined body, the reload reads it back),
Esc and typing dismiss, the pills and the input round-trip their prompts, the
over-long instruction is refused client-side before the wire, and KACHEL 8's
corrected error face names a dead connection with the retry that lands after
recovery. The leave guard's stream cell (W4 Task 17) is pinned honestly: a
proposal is not an unsaved edit — the guard reads the autosave alone, so a
reload, a route leave and a scene switch with a standing ghost ask nothing
and owe no write. Every face clears the axe WCAG A/AA floor, light and dark.
"""

import json
import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Dialog, Page, Request, expect

from app.capabilities.writing.e2e.conftest import (
    DATABASE,
    continue_scene,
    create_chapter,
    create_novel,
    set_theme,
    write_scene,
)
from app.kernel.llm.fake import FakeProvider
from app.kernel.testing.a11y import assert_accessible
from app.kernel.testing.db_rows import rows
from app.kernel.testing.stack import WEB_URL

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(120)]


def _deltas(body: str) -> list[str]:
    """The text deltas of the SSE data lines, other event payloads ignored."""
    deltas: list[str] = []
    for line in body.splitlines():
        if line.startswith("data: "):
            payload = json.loads(line[len("data: ") :])
            if "delta" in payload:
                deltas.append(payload["delta"])
    return deltas


def test_the_scene_continuation_streams_and_audits(installed: object) -> None:
    """The real stack streams the fake's prose in pieces, closes with done, and
    audits the call against the scene's own novel — free, because fake."""
    novel = create_novel("Der Nebel")
    chapter = create_chapter(str(novel["id"]), "Ankunft")
    scene = write_scene(str(chapter["id"]), "Der Nebel kam von See.")

    response = continue_scene(str(scene["id"]))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    deltas = _deltas(response.text)
    assert len(deltas) > 1  # framed per chunk, not one data frame
    assert "".join(deltas) == "".join(FakeProvider.CHUNKS)
    assert "event: done" in response.text
    assert "event: error" not in response.text

    # The honest check: the call left its row, named for the scene's novel.
    audit = rows(
        DATABASE,
        "SELECT task_key, status, novel_id, response_text, cost_usd FROM llm_calls",
    )
    assert len(audit) == 1
    task_key, status, novel_id, response_text, cost_usd = audit[0]
    assert task_key == "writing.continuation"
    assert status == "ok"
    assert str(novel_id) == str(novel["id"])
    assert response_text == "".join(FakeProvider.CHUNKS)
    assert cost_usd == 0.0


# --- The UI legs (W4 Task 16): ghost text + the prompt bar -----------------
#
# The browser drives the real bar and the real ghost on the real stack; the
# fake provider's deterministic prose is the proposal the legs assert on.

BASE = WEB_URL
PROSE = "Szenenprosa"  # the editor textbox's accessible name
PROMPT_INPUT = "Anweisung für die Fortsetzung"  # the bar input's name
GHOST = "".join(FakeProvider.CHUNKS)  # the proposal the fake streams
SEED_BODY = "Der Nebel kam von See."
JOINED = f"{SEED_BODY}\n\n{GHOST}"
PILL = re.compile("Vorschlag übernehmen")


def _seed_scene() -> tuple[str, str]:
    """One book, one chapter, one scene — return (novel_id, scene_id)."""
    novel = create_novel("Das Ghost-Buch")
    chapter = create_chapter(str(novel["id"]), "Ankunft")
    scene = write_scene(str(chapter["id"]), SEED_BODY, title="Die Szene")
    return str(novel["id"]), str(scene["id"])


def _open(page: Page, novel_id: str) -> None:
    page.goto(f"{BASE}/novels/{novel_id}")
    expect(page.get_by_role("textbox", name=PROSE)).to_be_visible()


def _continue(page: Page) -> None:
    """The bare ask — the bar's primary with an empty input."""
    page.get_by_role("button", name="Weiterschreiben").click()
    expect(page.get_by_role("button", name=PILL)).to_be_visible(timeout=10_000)


def _watch_scene_puts(page: Page) -> list[str]:
    """The scene PUT urls the page sends — the „no write is owed" oracle.
    The continue ask is a POST and the order PUTs name chapters, so a PUT
    under the scenes door is the body save alone."""
    writes: list[str] = []

    def record(request: Request) -> None:
        if request.method == "PUT" and "/api/writing/scenes/" in request.url:
            writes.append(request.url)

    page.on("request", record)
    return writes


def test_continue_streams_into_the_ghost_and_tab_inserts_and_saves(
    page: Page, installed: Stack
) -> None:
    """continue → the pending ghost at the tail → Tab inserts the proposal
    as a new paragraph and the autosave chain lands it: the PUT carries the
    joined body, the foot rests green, the reload reads the row back."""
    novel_id, scene_id = _seed_scene()
    _open(page, novel_id)

    with page.expect_response(
        lambda r: f"/api/writing/scenes/{scene_id}/continue" in r.url and r.request.method == "POST"
    ) as streamed:
        _continue(page)
    assert streamed.value.ok
    # The ghost stands OUTSIDE the document — the textbox holds the scene's
    # own words until Tab accepts.
    expect(page.get_by_role("textbox", name=PROSE)).to_have_text(SEED_BODY)

    # Tab accepts (the streaming start seated the caret in the prose).
    with page.expect_response(
        lambda r: f"/api/writing/scenes/{scene_id}" in r.url and r.request.method == "PUT"
    ) as saved:
        page.keyboard.press("Tab")
    assert saved.value.ok
    payload = saved.value.request.post_data_json
    assert payload is not None
    assert payload["body"] == JOINED
    expect(page.get_by_role("button", name=PILL)).to_have_count(0)
    expect(page.get_by_text("Automatisch gesichert")).to_be_visible()
    # The live foot count moved with the acceptance (5 + 12 words).
    expect(page.get_by_text("17 Wörter im Gesamtabschnitt")).to_be_visible()
    assert_accessible(page)

    # The row, not the in-memory body: a reload carries the accepted words.
    page.reload()
    expect(page.get_by_role("textbox", name=PROSE)).to_contain_text(GHOST)
    assert_accessible(page)


def test_esc_dismisses_the_ghost_and_the_body_stays(page: Page, installed: Stack) -> None:
    """Esc drops the proposal — the scene's own words stand untouched and
    no write is owed (the ghost was never an edit)."""
    novel_id, _scene_id = _seed_scene()
    _open(page, novel_id)
    _continue(page)

    page.keyboard.press("Escape")
    expect(page.get_by_role("button", name=PILL)).to_have_count(0)
    expect(page.get_by_role("textbox", name=PROSE)).to_have_text(SEED_BODY)
    expect(page.get_by_text("Automatisch gesichert")).to_be_visible()
    assert_accessible(page)


def test_typing_dismisses_the_ghost(page: Page, installed: Stack) -> None:
    """The writer's own words win over the proposal: a keystroke drops the
    ghost and stands in the prose."""
    novel_id, _scene_id = _seed_scene()
    _open(page, novel_id)
    _continue(page)

    page.keyboard.type(" Eigene Worte.")
    expect(page.get_by_role("button", name=PILL)).to_have_count(0)
    expect(page.get_by_role("textbox", name=PROSE)).to_contain_text("Eigene Worte.")
    expect(page.get_by_role("textbox", name=PROSE)).not_to_contain_text(GHOST)


def test_a_leave_with_a_standing_ghost_asks_nothing(page: Page, installed: Stack) -> None:
    """The ghost is not an unsaved edit: the guard reads the autosave alone,
    and a proposal never feeds it. A reload with the standing ghost meets no
    unload prompt, a route leave lands on the shelf without the
    Abschiedsschutz, and no write is owed — the row keeps the scene's own
    words. The running stream asks the same question (the guard never reads
    the continuation); its mid-flight face is #899's boundary, so the resting
    face pins the semantics on the real stack here."""
    novel_id, scene_id = _seed_scene()
    _open(page, novel_id)

    writes = _watch_scene_puts(page)
    seen: list[str] = []

    def accept(dialog: Dialog) -> None:
        seen.append(dialog.type)
        dialog.accept()

    page.on("dialog", accept)

    _continue(page)
    # The proposal stands OUTSIDE the document — the scene's own words are
    # the textbox's alone, so there is nothing for a guard to protect.
    expect(page.get_by_role("textbox", name=PROSE)).to_have_text(SEED_BODY)

    # The unload face of the same question: a reload asks nothing, and the
    # proposal retires with the page that asked it.
    page.reload()
    expect(page.get_by_role("textbox", name=PROSE)).to_be_visible()
    expect(page.get_by_role("button", name=PILL)).to_have_count(0)
    expect(page.get_by_role("textbox", name=PROSE)).to_have_text(SEED_BODY)
    assert seen == []

    # The route leave: the shelf lands, no Abschiedsschutz stands between.
    _continue(page)
    page.locator("header").get_by_role("link", name="Manuscripts").click()
    expect(page).to_have_url(BASE + "/")
    expect(page.get_by_role("heading", name="Das Bücherregal")).to_be_visible()
    expect(page.get_by_role("alertdialog")).to_have_count(0)
    assert seen == []
    assert writes == []
    assert rows(DATABASE, "SELECT body FROM scenes WHERE id = :id", {"id": scene_id}) == [
        (SEED_BODY,)
    ]

    # Back in the book, the scene's own words stand — no ghost survived.
    _open(page, novel_id)
    expect(page.get_by_role("textbox", name=PROSE)).to_have_text(SEED_BODY)
    expect(page.get_by_role("button", name=PILL)).to_have_count(0)
    assert writes == []


def test_a_scene_switch_retires_the_ghost_without_asking(page: Page, installed: Stack) -> None:
    """A scene switch is a leave too: with no draft the flush gate passes
    clean, no Abschiedsschutz stands, and the ghost retires with the tail it
    was asked for — the target scene's own words stand, and neither row was
    written."""
    novel = create_novel("Das Ghost-Buch")
    chapter = create_chapter(str(novel["id"]), "Ankunft")
    first = write_scene(str(chapter["id"]), "Worte der ersten Szene.", title="Die erste")
    second = write_scene(str(chapter["id"]), SEED_BODY, title="Die zweite")
    _open(page, str(novel["id"]))
    # The last-created scene leads — „Die zweite".
    expect(page.get_by_role("heading", name="Die zweite", exact=True)).to_be_visible()

    writes = _watch_scene_puts(page)

    _continue(page)
    expect(page.get_by_role("textbox", name=PROSE)).to_have_text(SEED_BODY)

    page.get_by_role("button", name=re.compile("Szene 1 · Die erste")).click()
    expect(page.get_by_role("heading", name="Die erste", exact=True)).to_be_visible()
    expect(page.get_by_role("alertdialog")).to_have_count(0)
    expect(page.get_by_role("button", name=PILL)).to_have_count(0)
    expect(page.get_by_role("textbox", name=PROSE)).to_have_text("Worte der ersten Szene.")
    assert_accessible(page)

    # Back to the asked tail: its own words, no ghost — the retirement was
    # the switch's, not a dismissal the writer chose.
    page.get_by_role("button", name=re.compile("Szene 2 · Die zweite")).click()
    expect(page.get_by_role("heading", name="Die zweite", exact=True)).to_be_visible()
    expect(page.get_by_role("textbox", name=PROSE)).to_have_text(SEED_BODY)
    expect(page.get_by_role("button", name=PILL)).to_have_count(0)
    expect(page.get_by_role("alertdialog")).to_have_count(0)

    assert writes == []
    assert rows(DATABASE, "SELECT body FROM scenes WHERE id = :id", {"id": str(first["id"])}) == [
        ("Worte der ersten Szene.",)
    ]
    assert rows(DATABASE, "SELECT body FROM scenes WHERE id = :id", {"id": str(second["id"])}) == [
        (SEED_BODY,)
    ]


def test_a_quick_pill_round_trips_its_prompt(page: Page, installed: Stack) -> None:
    """The pill's localized label rides the prompt parameter on the wire —
    and the proposal it returns accepts like any other."""
    novel_id, scene_id = _seed_scene()
    _open(page, novel_id)

    with page.expect_request(
        lambda r: f"/api/writing/scenes/{scene_id}/continue" in r.url and r.method == "POST"
    ) as asked:
        page.get_by_role("button", name="Spannungsspitze einbauen").click()
    assert asked.value.post_data_json == {"prompt": "Spannungsspitze einbauen"}
    expect(page.get_by_role("button", name=PILL)).to_be_visible(timeout=10_000)

    with page.expect_response(
        lambda r: f"/api/writing/scenes/{scene_id}" in r.url and r.request.method == "PUT"
    ) as saved:
        page.keyboard.press("Tab")
    payload = saved.value.request.post_data_json
    assert payload is not None
    assert payload["body"] == JOINED
    # The call left its audit row — the prompt changed the prompt alone.
    audit = rows(DATABASE, "SELECT task_key, status FROM llm_calls")
    assert audit == [("writing.continuation", "ok")]


def test_the_input_instruction_round_trips(page: Page, installed: Stack) -> None:
    """A typed instruction rides Enter through the same parameter."""
    novel_id, scene_id = _seed_scene()
    _open(page, novel_id)

    instruction = "Lass Mira am Ufer zögern."
    page.get_by_role("textbox", name=PROMPT_INPUT).fill(instruction)
    with page.expect_request(
        lambda r: f"/api/writing/scenes/{scene_id}/continue" in r.url and r.method == "POST"
    ) as asked:
        page.get_by_role("textbox", name=PROMPT_INPUT).press("Enter")
    assert asked.value.post_data_json == {"prompt": instruction}
    expect(page.get_by_role("button", name=PILL)).to_be_visible(timeout=10_000)
    assert_accessible(page)


def test_an_overlong_instruction_is_refused_before_the_wire(page: Page, installed: Stack) -> None:
    """The client mirrors the schema's bound: 2001 characters name the
    refusal on the field, and no continue request leaves the browser."""
    novel_id, scene_id = _seed_scene()
    _open(page, novel_id)

    continues: list[str] = []
    page.on(
        "request",
        lambda r: continues.append(r.url) if "/continue" in r.url else None,
    )
    field = page.get_by_role("textbox", name=PROMPT_INPUT)
    field.fill("X" * 2001)
    refusal = page.get_by_role("alert")
    expect(refusal).to_be_visible()
    expect(refusal).to_contain_text("2000")
    page.get_by_role("button", name="Weiterschreiben").click()
    expect(refusal).to_be_visible()
    expect(page.get_by_role("button", name=PILL)).to_have_count(0)
    assert continues == []
    assert rows(DATABASE, "SELECT count(*) FROM llm_calls") == [(0,)]
    assert_accessible(page)

    # Back within the bound, the same field sends — the refusal was honest.
    field.fill("Kurze Anweisung.")
    expect(page.get_by_role("alert")).to_have_count(0)
    with page.expect_request(
        lambda r: f"/api/writing/scenes/{scene_id}/continue" in r.url and r.method == "POST"
    ) as asked:
        page.get_by_role("button", name="Weiterschreiben").click()
    assert asked.value.post_data_json == {"prompt": "Kurze Anweisung."}


def test_the_error_face_names_the_failure_and_retry_lands(page: Page, installed: Stack) -> None:
    """A dead connection raises KACHEL 8's corrected face — the Grund chip,
    the calm title, the reassurance — and Erneut versuchen lands the ghost
    after recovery; Verwerfen clears it without a write."""
    novel_id, scene_id = _seed_scene()
    _open(page, novel_id)

    installed.stop_api()
    try:
        page.get_by_role("button", name="Weiterschreiben").click()
        face = page.get_by_role("alert")
        expect(face).to_be_visible(timeout=10_000)
        expect(face).to_contain_text("ARIA konnte nicht weiterschreiben.")
        expect(face).to_contain_text("KI-Partner nicht erreichbar")
        expect(face).to_contain_text("Die Verbindung zur Schreib-Assistenz wurde unterbrochen.")
        # The reassurance is true: the scene's own words stand untouched.
        expect(page.get_by_role("textbox", name=PROSE)).to_have_text(SEED_BODY)
        assert_accessible(page)
    finally:
        installed.start_api()

    # Verwerfen clears the face — no write, no ghost.
    page.get_by_role("button", name="Verwerfen", exact=True).click()
    expect(page.get_by_role("alert")).to_have_count(0)
    expect(page.get_by_role("textbox", name=PROSE)).to_have_text(SEED_BODY)

    # The retry re-runs the very ask against the recovered service.
    page.get_by_role("button", name="Weiterschreiben").click()
    expect(page.get_by_role("button", name=PILL)).to_be_visible(timeout=10_000)
    with page.expect_response(
        lambda r: f"/api/writing/scenes/{scene_id}" in r.url and r.request.method == "PUT"
    ) as saved:
        page.keyboard.press("Tab")
    payload = saved.value.request.post_data_json
    assert payload is not None
    assert payload["body"] == JOINED
    expect(page.get_by_text("Automatisch gesichert")).to_be_visible()


def test_the_dark_faces_clear_the_axe_floor(page: Page, installed: Stack) -> None:
    """The dark bar, the pending ghost and the error face ride the tokens'
    dark halves and clear the same floor the light faces ride."""
    set_theme("dark")
    novel_id, _scene_id = _seed_scene()
    _open(page, novel_id)
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")

    _continue(page)
    assert_accessible(page)

    installed.stop_api()
    try:
        page.keyboard.press("Escape")  # drop the pending ghost
        page.get_by_role("button", name="Weiterschreiben").click()
        expect(page.get_by_role("alert")).to_be_visible(timeout=10_000)
        assert_accessible(page)
    finally:
        installed.start_api()
