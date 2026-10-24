"""The Wissen dock: entities, review and job status beside the editor.

The tab is registry-driven: knowledge exports dockRoutes and the generated
registry carries the row, so the workspace renders the tab with zero
generator changes. Inside, extraction on the chapter the editor is showing
runs as a durable job — the panel polls the row's state, never a connection
— and the finished queue arrives as proposal cards. Both review decisions
are pinned: accept files the entity into the searchable list, discard clears
it, and the spent queue empties — the review flow also runs keyboard-only,
Tab and Enter for every step from opening the dock to both decisions. The
dock's failures are named: an unreachable backend reads as an outage, never
as an empty list — the review queue no less than the entity list, each with
its own words — and a job poll that meets a dead service reopens the
trigger instead of locking it. The extraction is idempotent against a
re-run: the same chapter filed twice holds one card set, and a consumed
suggestion files fresh on the next run. The search box reaches two tiers:
the names it filters instantly, and the corpus's passages through the
semantic search, debounced. The Titel-refusal carry rides the same
flow's book-creation step: the failed submit names the empty field with the
catalog's words.

The detail view corrects what review filed: rename, delete and merge —
each a dialog the focus contract already owns, each outcome announced,
and the entity list reflects every change at once. The rename also runs
keyboard-only: the grid's rows answer the arrow keys and Enter, and the
form dialog opens into its name field.
"""

from time import sleep
from typing import TYPE_CHECKING

import httpx
import pytest
from playwright.sync_api import Locator, Page, expect

from app.kernel.testing.a11y import assert_accessible

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

# The API the stack runs, for seeding a passage-search corpus the way the
# standalone search test's upload does — through the real service, its real
# ingestion and the E2E stack's real embedding stand-in.
API = "http://127.0.0.1:8000"

# Capitalized words steer the fake provider's extraction (it derives names
# from them): Mira, Haus and See become the three suggestions, kinds cycling
# character, place, thing in order of appearance. Draußen is fourth, beyond
# the fake's ceiling of three.
CHAPTER_BODY = "Mira betrat das alte Haus am See. Draußen schwieg der Leuchtturm."

# The passage-search corpus: one document, one chunk, its first sentence the
# needle a query shares a word with (the stand-in embeds by word, so a shared
# word is what ranks the chunk first).
PASSAGE_TEXT = (
    "Der Leuchtturm am Horizont war seit Jahren dunkel.\n\nNiemand im Dorf sprach noch über ihn."
)


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


def _write_chapter(page: Page) -> None:
    """Create a chapter and write the extraction body into the editor.

    The caret reaches the editor by Tab — the pointer has no part in this
    file's flows once the chapter exists.
    """
    page.get_by_role("button", name="Neues Kapitel").click()
    editor = page.locator(".ProseMirror")
    expect(editor).to_be_visible()
    _tab_to(page, editor)
    page.keyboard.type(CHAPTER_BODY)
    # Extraction reads the saved chapter, so the flow waits for the save
    # the editor itself reports before asking for the job.
    expect(page.get_by_text("Gespeichert")).to_be_visible()


def _tab_to(page: Page, target: Locator) -> None:
    """Walk the page's tab order until ``target`` holds focus.

    The keyboard pin's one move: a step is a Tab or an Enter, never a
    pointer. The bound is generous — the dock's tab order is a couple dozen
    stops — and a walk that exhausts it fails loudly rather than reach its
    target by accident of an already-focused element.
    """
    for _ in range(30):
        if target.evaluate("element => element === document.activeElement"):
            return
        page.keyboard.press("Tab")
    pytest.fail(f"the tab order never reaches {target}")


def _rerun_extraction_to_done(dock: Locator, extract: Locator, status: Locator) -> None:
    """Click the trigger again and wait for THAT job's row to settle done.

    The previous round's done row would satisfy any done-wait on its own,
    so the round is separated by tagging its row: the wait lands only when
    the tagged element is gone — the new job's id has no cached answer, so
    the row unmounts for a beat before the new job's first poll answers —
    and the row that answers afterwards is the new job's by construction.
    """
    status.evaluate("element => element.setAttribute('data-previous-round', '1')")
    extract.click()
    expect(dock.locator("[data-job-status][data-previous-round]")).to_have_count(0)
    expect(status).to_have_attribute("data-job-status", "done")


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


def test_the_wissen_dock_names_an_unreachable_backend(page: Page, stack: Stack) -> None:
    """An outage in the dock reads as an outage, never as an empty list.

    A local service that is not running is a real condition of this
    product; stopping the real API produces it. The entities panel must
    name it — and must not wear its empty state as a mask, because "no
    entities" is a fact only a reachable service can claim.
    """
    _open_workspace_with_validated_title(page, "Die stille Bucht")

    # The dock opens on its tab and answers while the service runs: the
    # honest empty state of a novel without entities.
    page.get_by_role("button", name="Wissen", exact=True).click()
    dock = page.get_by_role("complementary", name="Wissen")
    expect(dock).to_be_visible()
    entities = dock.get_by_role("region", name="Entitäten")
    expect(entities.get_by_text("Noch keine Entitäten")).to_be_visible()

    # The reload is the refetch path: a fresh page asks again, and the
    # answer must be the outage's own name.
    stack.stop_api()
    try:
        page.reload()
        expect(dock).to_be_visible()
        expect(dock.get_by_role("alert").filter(has_text="konnten nicht geladen")).to_be_visible()
        # The empty-state text must not stand in for the missing answer.
        expect(entities.get_by_text("Noch keine Entitäten")).to_have_count(0)
    finally:
        stack.start_api()

    # Recovery: the same page, asked again, shows the honest empty state —
    # and no error is left standing.
    page.reload()
    expect(dock.get_by_text("Noch keine Entitäten")).to_be_visible()
    expect(dock.get_by_role("alert")).to_have_count(0)

    assert_accessible(page)


def test_the_wissen_dock_reviews_by_keyboard_alone(page: Page, stack: Stack) -> None:
    """The review flow without a pointer: Tab reaches, Enter decides.

    The dock's tab, the extraction trigger and both review decisions are
    reached through the page's own tab order and pressed with Enter — no
    click anywhere in the flow.
    """
    _open_workspace_with_validated_title(page, "Die Tastatur der Bucht")
    _write_chapter(page)

    # The keyboard opens the dock from the editor's caret.
    tab = page.get_by_role("button", name="Wissen", exact=True)
    _tab_to(page, tab)
    page.keyboard.press("Enter")
    dock = page.get_by_role("complementary", name="Wissen")
    expect(dock).to_be_visible()

    # The trigger too: Tab reaches it, Enter starts the extraction.
    extract = dock.get_by_role("button", name="Dieses Kapitel durchsuchen")
    _tab_to(page, extract)
    page.keyboard.press("Enter")
    status = dock.locator("[data-job-status]")
    expect(status).to_have_attribute("data-job-status", "done")
    expect(status).to_contain_text("3")

    cards = dock.get_by_role("region", name="Vorgeschlagene Entität")
    expect(cards).to_have_count(3)
    entities = dock.get_by_role("region", name="Entitäten")

    # Accept by keyboard: Mira is filed into the searchable list.
    accept_mira = cards.filter(has_text="Mira").get_by_role("button", name="Übernehmen", exact=True)
    _tab_to(page, accept_mira)
    page.keyboard.press("Enter")
    expect(entities).to_contain_text("Mira")

    # Discard by keyboard: See never becomes an entity.
    discard_see = cards.filter(has_text="See").get_by_role("button", name="Verwerfen")
    _tab_to(page, discard_see)
    page.keyboard.press("Enter")
    expect(entities).not_to_contain_text("See")

    # One decision each: the queue holds only Haus.
    expect(cards).to_have_count(1)
    expect(cards).to_contain_text("Haus")

    assert_accessible(page)


def test_a_failed_poll_reopens_the_extraction_trigger(page: Page, stack: Stack) -> None:
    """An unanswered job poll is an error with a way back, not a locked button.

    The service going down under an outstanding job leaves the poll with no
    answer. That must read as a named error — the row is the answer, and no
    answer is an error, not work still going — and the trigger must reopen:
    the retry is the same button again, starting a fresh extraction.

    Two timing windows shape the loop, and neither may cost a timeout. The
    fake provider finishes fast, so a round's job may complete between the
    read that says it is live and the service stop: its poll then answers
    done before the service dies, no poll is left to raise the outage, and
    the alert this test needs never comes — a round lost that way costs one
    more round. And the panel's swap of the previous round's status element
    for the new job's is a render that can fall between two samples, so the
    swap is waited out by the old element going away — durable once true —
    never by catching a milliseconds-wide count-zero window.
    """
    _open_workspace_with_validated_title(page, "Die unterbrochene Durchsuchung")
    _write_chapter(page)

    page.get_by_role("button", name="Wissen", exact=True).click()
    dock = page.get_by_role("complementary", name="Wissen")
    expect(dock).to_be_visible()
    extract = dock.get_by_role("button", name="Dieses Kapitel durchsuchen")
    status = dock.locator("[data-job-status]")
    alert = dock.get_by_role("alert").filter(has_text="Fortschritt")

    for _attempt in range(8):
        if _attempt > 0:
            # Tag the previous round's row: the next read must sample the
            # new job's element, and "the tagged one is gone" is exactly
            # that, durably — React unmounts the old node when the trigger
            # files a new job, and a fresh one never carries the tag.
            status.evaluate("element => element.setAttribute('data-previous-round', '1')")
        extract.click()
        if _attempt > 0:
            # The tag check retries through the enqueue's flight and lands
            # when the old element unmounts; the visible status afterwards
            # is the new job's row by construction.
            expect(dock.locator("[data-job-status][data-previous-round]")).to_have_count(0)
        expect(status).to_be_visible()
        if status.get_attribute("data-job-status") == "done":
            # Settled before the stop could land under it: a spent chance,
            # and the done row's suggestions are simply more pending queue
            # for the round that does catch live work.
            continue

        # A live row: stop the service under it. The stop settles the round
        # one of two ways within a poll tick — the unanswered poll names the
        # outage (the race won), or the row's last answer, a poll that
        # landed before the service died, flips it done and the polling
        # stops with nothing left to raise (the race lost).
        stack.stop_api()
        try:
            expect(alert.or_(dock.locator('[data-job-status="done"]'))).to_be_visible()
            if alert.count() == 0:
                # The race lost. The service comes back and the loop takes
                # another round; only the won round proceeds.
                continue
            # The poll's answer is the connection's refusal, and that is named.
            expect(alert).to_be_visible()
            # The stale row must not stand beside it: the last-known answer
            # under a dead poll is queued or running (a done row would have
            # stopped the polling before the service died), and a row still
            # promising progress the panel cannot show would outshout the
            # alert that holds the truth.
            expect(status).to_have_count(0)
            # The trigger reopens instead of locking on the unanswered job.
            expect(extract).to_be_enabled()
            break
        finally:
            stack.start_api()
    else:
        pytest.fail("never caught an outstanding job to stop the service under")

    # The retry: a click on the reopened trigger runs a fresh extraction,
    # and the panel follows it to its answer with no error left standing.
    extract.click()
    expect(status).to_have_attribute("data-job-status", "done")
    expect(status).to_contain_text("3")
    expect(dock.get_by_role("alert")).to_have_count(0)

    assert_accessible(page)


def test_the_review_queue_names_an_unreachable_backend(page: Page, stack: Stack) -> None:
    """The queue's outage is named, never worn as a spent queue.

    A queue holding three pending cards goes unreachable: a reload that
    cannot reach the service must say so in the queue's own words. The
    entity list shed this mask first (its outage test pins that alert);
    the queue's silence would read worse — as a queue already reviewed —
    and the two alerts must stay nameable apart, because both panels sit
    in the dock and both queries fail together.
    """
    _open_workspace_with_validated_title(page, "Die wartende Bucht")
    _write_chapter(page)

    page.get_by_role("button", name="Wissen", exact=True).click()
    dock = page.get_by_role("complementary", name="Wissen")
    expect(dock).to_be_visible()
    extract = dock.get_by_role("button", name="Dieses Kapitel durchsuchen")
    extract.click()
    status = dock.locator("[data-job-status]")
    expect(status).to_have_attribute("data-job-status", "done")
    cards = dock.get_by_role("region", name="Vorgeschlagene Entität")
    expect(cards).to_have_count(3)

    # The reload is the refetch path: a fresh page asks again, and the
    # queue's answer must be the outage's own name — not the silence a
    # spent queue renders exactly like.
    stack.stop_api()
    try:
        page.reload()
        expect(dock).to_be_visible()
        queue_alert = dock.get_by_role("alert").filter(has_text="lassen sich nicht laden")
        expect(queue_alert).to_be_visible()
        # The queue does not pretend beside its own alert: no last-known
        # cards stand in for the missing answer.
        expect(cards).to_have_count(0)
    finally:
        stack.start_api()

    # Recovery: the same page, asked again, shows the queue it holds —
    # and no error is left standing.
    page.reload()
    expect(cards).to_have_count(3)
    expect(dock.get_by_role("alert")).to_have_count(0)

    assert_accessible(page)


def test_a_rerun_stacks_no_duplicate_cards(page: Page, stack: Stack) -> None:
    """The re-run files one card set, and a consumed row files fresh.

    An extraction re-run — the outage retry's shape, the trigger clicked
    again after the row settled — parses the same three entities off the
    same chapter. The pending dedupe must hold: the queue answers with
    the cards it already has, never a stacked second set. The asymmetry
    is the other half of the rule: accept consumes a row, so the next
    re-run files that entity fresh — the review is the only thing that
    reopens a filed key.
    """
    _open_workspace_with_validated_title(page, "Die wiederholte Durchsuchung")
    _write_chapter(page)

    page.get_by_role("button", name="Wissen", exact=True).click()
    dock = page.get_by_role("complementary", name="Wissen")
    expect(dock).to_be_visible()
    extract = dock.get_by_role("button", name="Dieses Kapitel durchsuchen")
    status = dock.locator("[data-job-status]")
    cards = dock.get_by_role("region", name="Vorgeschlagene Entität")

    # The first run files its three cards.
    extract.click()
    expect(status).to_have_attribute("data-job-status", "done")
    expect(cards).to_have_count(3)

    # The re-run on the same chapter: one card set, whatever the panel is
    # asked again. (The done row's count is the parse's, not the queue's —
    # the card count is the dedupe's witness.)
    _rerun_extraction_to_done(dock, extract, status)
    expect(cards).to_have_count(3)

    # The asymmetry: accept consumes Mira's row, and the re-run files her
    # fresh beside the two that never left.
    cards.filter(has_text="Mira").get_by_role("button", name="Übernehmen", exact=True).click()
    expect(cards).to_have_count(2)
    _rerun_extraction_to_done(dock, extract, status)
    expect(cards).to_have_count(3)

    assert_accessible(page)


def test_the_dock_search_reaches_passages(page: Page, stack: Stack) -> None:
    """The search box's second tier: passages from the semantic search.

    The box keeps its instant, client-side filter of the names — and while
    it carries a query, a debounced server search renders the corpus's
    passages under the entity list, each with its document's title. A
    search that meets a dead service names itself: the same named-failure
    rule the dock's other panels hold, in this tier's own words.
    """
    _open_workspace_with_validated_title(page, "Die Bucht mit den Notizen")

    # The corpus is seeded through the API the stack runs — the same path
    # the standalone search test's upload takes, embedding included.
    with httpx.Client(base_url=API, timeout=30) as api:
        seeded = api.post(
            "/api/knowledge/documents",
            files={"file": ("notizen.txt", PASSAGE_TEXT.encode("utf-8"), "text/plain")},
            data={"title": "Notizen"},
        )
        seeded.raise_for_status()

    page.get_by_role("button", name="Wissen", exact=True).click()
    dock = page.get_by_role("complementary", name="Wissen")
    expect(dock).to_be_visible()
    search = dock.get_by_label("Entitäten durchsuchen")

    # Typing asks both tiers: the names filter where they are, and past
    # the debounce the passages arrive with their document's title.
    search.fill("Leuchtturm")
    passages = dock.get_by_role("region", name="Passagen")
    expect(passages.get_by_text("Notizen")).to_be_visible()
    expect(
        passages.get_by_text("Der Leuchtturm am Horizont war seit Jahren dunkel.")
    ).to_be_visible()

    # The outage names itself in this tier's words: a failed search is an
    # answer missing, not an empty passages block.
    stack.stop_api()
    try:
        search.fill("Dorf")
        expect(dock.get_by_role("alert").filter(has_text="Passagensuche")).to_be_visible()
    finally:
        stack.start_api()

    # Recovery: the same box, asked again, finds the passage again — and
    # the error is gone with the answer that replaced it.
    search.fill("Leuchtturm")
    expect(passages.get_by_text("Notizen")).to_be_visible()
    expect(dock.get_by_role("alert")).to_have_count(0)

    assert_accessible(page)


def _row_named(entities: Locator, name: str) -> Locator:
    """The entity list's cell for one exact name.

    The detail heading shares the name with the row it opened, so the
    list's own witness is the grid cell, and the exact match keeps a
    renamed name ("Miralam") from standing in for the old one ("Mira").
    """
    return entities.get_by_role("gridcell", name=name, exact=True)


def _seed_entities(novel_title: str) -> str:
    """A novel with Mira, Haus and See filed as entities, through the API.

    The correction flows start where review leaves the story: three
    accepted entities and no chapter to write first. The API is the
    stack's own, the worker runs inside it, and the accepts ride the real
    review path — the seeding is a faster driver, not a shortcut around
    the product. Returns the novel's id, the workspace URL's parameter.
    """
    with httpx.Client(base_url=API, timeout=30) as api:
        novel = api.post("/api/writing/novels", json={"title": novel_title})
        novel.raise_for_status()
        novel_id = novel.json()["id"]
        chapter = api.post(f"/api/writing/novels/{novel_id}/chapters", json={"title": "Ankunft"})
        chapter.raise_for_status()
        chapter_id = chapter.json()["id"]
        saved = api.put(f"/api/writing/chapters/{chapter_id}", json={"body": CHAPTER_BODY})
        saved.raise_for_status()
        enqueued = api.post(
            f"/api/knowledge/extraction/{novel_id}", json={"chapter_id": chapter_id}
        )
        enqueued.raise_for_status()
        # The worker rides the API process: poll the row it settles.
        for _ in range(120):
            job = api.get(f"/api/jobs/{enqueued.json()['job_id']}")
            job.raise_for_status()
            if job.json()["status"] in ("done", "failed"):
                break
            sleep(0.25)
        else:
            pytest.fail("the seeded extraction never settled")
        assert job.json()["status"] == "done"
        suggestions = api.get(f"/api/knowledge/novels/{novel_id}/suggestions")
        suggestions.raise_for_status()
        assert len(suggestions.json()) == 3
        for suggestion in suggestions.json():
            accepted = api.post(f"/api/knowledge/suggestions/{suggestion['id']}/accept")
            accepted.raise_for_status()
    return novel_id


def test_the_detail_view_corrects_entities_by_hand(page: Page, stack: Stack) -> None:
    """Rename, delete and merge: the detail view's three corrections.

    Entities enter the world through review, but the review's answer is
    not the last word — a typo no longer lives forever. The rename shows
    in the list the moment it lands; the merge leaves the target and not
    the source; the delete leaves the row gone. Every outcome is
    announced, so the change is heard as well as seen.
    """
    _seed_entities("Die korrigierte Bucht")
    page.goto("http://127.0.0.1:3100/")
    page.get_by_role("link", name="Die korrigierte Bucht").click()
    expect(page.get_by_role("heading", name="Die korrigierte Bucht")).to_be_visible()

    page.get_by_role("button", name="Wissen", exact=True).click()
    dock = page.get_by_role("complementary", name="Wissen")
    entities = dock.get_by_role("region", name="Entitäten")
    expect(_row_named(entities, "Mira")).to_be_visible()

    # Rename: the typo dies. The list shows the new name the moment the
    # save lands, the old one is gone, and the detail follows the row it
    # opened.
    _row_named(entities, "Mira").click()
    dock.get_by_role("region", name="Mira").get_by_role("button", name="Bearbeiten").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Name").fill("Miralam")
    dialog.get_by_role("button", name="Speichern").click()
    expect(dialog).not_to_be_visible()
    expect(_row_named(entities, "Miralam")).to_be_visible()
    expect(_row_named(entities, "Mira")).to_have_count(0)
    expect(dock.get_by_role("region", name="Miralam")).to_be_visible()
    # the outcome is heard, not only seen
    expect(page.locator("[data-live-announcer]")).to_contain_text(
        "Änderungen an Miralam wurden gespeichert"
    )

    # Merge: two entries for the same thing fold into one — the target
    # survives, the source is deleted. The picker offers the novel's other
    # entities; the source itself is not among them. The detail is still
    # open on the renamed row: the selection followed it through the save.
    dock.get_by_role("region", name="Miralam").get_by_role("button", name="Zusammenführen").click()
    dialog = page.get_by_role("dialog")
    picker = dialog.get_by_label("Zusammenführen mit")
    picker.fill("Haus")
    picker.press("ArrowDown")
    picker.press("Enter")
    expect(picker).to_have_value("Haus")
    dialog.get_by_role("button", name="Jetzt zusammenführen").click()
    expect(dialog).not_to_be_visible()
    expect(_row_named(entities, "Haus")).to_be_visible()
    expect(_row_named(entities, "Miralam")).to_have_count(0)
    expect(page.locator("[data-live-announcer]")).to_contain_text(
        "Miralam wurde mit Haus zusammengeführt"
    )

    # Delete: the row goes, and only the row — the confirm dialog names
    # what it will take before it takes it.
    _row_named(entities, "See").click()
    dock.get_by_role("region", name="See").get_by_role("button", name="Löschen").click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_text("Willst du See wirklich löschen?")).to_be_visible()
    dialog.get_by_role("button", name="Endgültig löschen").click()
    expect(dialog).not_to_be_visible()
    expect(_row_named(entities, "See")).to_have_count(0)
    # what remains is exactly the merge's survivor
    expect(entities.get_by_role("row")).to_have_count(1)
    expect(_row_named(entities, "Haus")).to_be_visible()
    expect(page.locator("[data-live-announcer]")).to_contain_text("See wurde gelöscht")

    assert_accessible(page)


def test_an_entity_can_be_renamed_by_keyboard_alone(page: Page, stack: Stack) -> None:
    """The rename without a pointer: Tab reaches, Enter decides.

    The corrections are dialogs, so the focus contract is the shell's:
    opening lands in the form, the buttons answer the keyboard, and the
    save closes back out. The grid's rows are reached through the page's
    own tab order and selected with Enter. No click anywhere in the flow.
    """
    novel_id = _seed_entities("Die Tastatur der Korrektur")
    page.goto(f"http://127.0.0.1:3100/novels/{novel_id}")
    expect(page.get_by_role("heading", name="Die Tastatur der Korrektur")).to_be_visible()

    tab = page.get_by_role("button", name="Wissen", exact=True)
    _tab_to(page, tab)
    page.keyboard.press("Enter")
    dock = page.get_by_role("complementary", name="Wissen")
    expect(dock).to_be_visible()
    entities = dock.get_by_role("region", name="Entitäten")
    expect(_row_named(entities, "Mira")).to_be_visible()

    # The list is a real grid: Tab reaches it, the arrows walk it, Enter
    # selects the row the detail opens on.
    row = entities.get_by_role("row").filter(has_text="Mira")
    _tab_to(page, row)
    page.keyboard.press("Enter")
    detail = dock.get_by_role("region", name="Mira")
    expect(detail).to_be_visible()

    # Bearbeiten opens the form; the modal holds the focus, and one Tab
    # reaches the name field — the typing corrects the row from the
    # keyboard, no pointer involved.
    _tab_to(page, detail.get_by_role("button", name="Bearbeiten"))
    page.keyboard.press("Enter")
    dialog = page.get_by_role("dialog")
    name_field = dialog.get_by_label("Name")
    _tab_to(page, name_field)
    page.keyboard.type("Miralam")
    _tab_to(page, dialog.get_by_role("button", name="Speichern"))
    page.keyboard.press("Enter")
    expect(dialog).not_to_be_visible()
    expect(_row_named(entities, "Miralam")).to_be_visible()
    expect(_row_named(entities, "Mira")).to_have_count(0)
    expect(page.locator("[data-live-announcer]")).to_contain_text(
        "Änderungen an Miralam wurden gespeichert"
    )

    assert_accessible(page)
