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

The whole-novel consistency check rides the same lane beside the chapter-
scoped extraction: one trigger, the job's row, and the findings queue —
each contradiction a card quoting both readings, acknowledged or dismissed
exactly once, with the done copy naming the check's own count.

The detail view corrects what review filed: rename, delete and merge —
each a dialog the focus contract already owns, each outcome announced,
and the entity list reflects every change at once. The rename also runs
keyboard-only: the grid's rows answer the arrow keys and Enter, and the
form dialog opens into its name field.

The list narrows twice over: the type and tag filters answer from the
novel's own rows, and the search box asks the server — a misspelt name
still finds its row, which a substring filter could never do. The edit
dialog carries every field the review filed: aliases and tags as chips
(Enter or comma files one, a case twin dedupes), the body as Markdown
source — written and shown as written — and the relations: added
against the novel's other entries with the suggested vocabulary as
autocomplete, retyped inline, deleted exactly. The card stays compact
and shows what the dialog filed: chips, the source preview, both
directions of every edge, and the mark that flags a self-relation. A
proposal card reads its suggested type and relations, and an accept
that cannot place a relation says so once, aloud.
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
# from them): Mira, Haus, See, Draußen and Leuchtturm become the five
# suggestions, types cycling the extraction vocabulary — character, location,
# faction, object, system — in order of appearance. The fake proposes up to
# eight, one per type; this chapter names five.
CHAPTER_BODY = "Mira betrat das alte Haus am See. Draußen schwieg der Leuchtturm."

# The planted contradictions: two chapters give Mira and Tom two different
# ages each. The texts steer the fake provider's derivation (a capitalized
# word given two different numbers across the chapters is one finding
# quoting both readings), the way CHAPTER_BODY steers extraction. Two names
# make two findings, so the review round has one card to acknowledge and
# one to dismiss. The chapters are created through the UI, which stores
# empty titles — the prompt's "Chapter: " headings carry no numbers.
CONTRADICTING_BODIES = (
    "Mira ist 34, und Tom ist 30.",
    "Mira ist 37, und Tom ist 33.",
)

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


def _write_chapters(page: Page, bodies: tuple[str, ...]) -> None:
    """Create one chapter per body and write it into the editor.

    The check reads every saved chapter of the novel, so each body waits
    for the save the editor itself reports before the next chapter begins
    — the check must see what the writer wrote, not a save still debouncing.
    """
    for body in bodies:
        page.get_by_role("button", name="Neues Kapitel").click()
        editor = page.locator(".ProseMirror")
        expect(editor).to_be_visible()
        editor.click()
        page.keyboard.type(body)
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
    expect(status).to_contain_text("5")
    # The settled job hands the trigger back for the next run.
    expect(extract).to_be_enabled()

    # The finished queue arrives as proposal cards: one per proposed entity.
    # Each card reads its suggested type and the relations the fake proposes,
    # so a relation line may name another card's entity — the cards below
    # are picked by their name · type line, never by a name alone.
    cards = dock.get_by_role("region", name="Vorgeschlagene Entität")
    expect(cards).to_have_count(5)

    # The proposal rides the card: the suggested type and the relation in
    # the review's words.
    mira_card = cards.filter(has_text="Mira · Figur")
    expect(mira_card).to_contain_text("Verbunden mit")
    expect(mira_card).to_contain_text("Haus")

    # Accept files the entity: Mira appears in the list beside the editor.
    mira_card.get_by_role("button", name="Übernehmen", exact=True).click()
    entities = dock.get_by_role("region", name="Entitäten")
    expect(entities).to_contain_text("Mira")
    # Her proposal points at Haus, still pending in the queue: the accept
    # cannot place it yet, and the skip is announced once, naming its
    # target — transient, heard now, persisted nowhere.
    expect(page.locator("[data-live-announcer]")).to_contain_text(
        "Eine Beziehung konnte nicht gesetzt werden: Haus"
    )

    # Discard clears: See never becomes an entity.
    cards.filter(has_text="See · Fraktion").get_by_role("button", name="Verwerfen").click()
    expect(entities).not_to_contain_text("See")

    # A second accept, the queue's other spent row: Haus is filed too —
    # and its proposal points at See, discarded one step ago, so its skip
    # names See.
    cards.filter(has_text="Haus · Ort").get_by_role("button", name="Übernehmen", exact=True).click()
    expect(entities).to_contain_text("Haus")
    expect(page.locator("[data-live-announcer]")).to_contain_text(
        "Eine Beziehung konnte nicht gesetzt werden: See"
    )

    # The chapter's other two candidates meet the same two decisions, so the
    # queue really empties: Draußen is discarded, Leuchtturm filed.
    cards.filter(has_text="Draußen · Objekt").get_by_role("button", name="Verwerfen").click()
    expect(entities).not_to_contain_text("Draußen")
    cards.filter(has_text="Leuchtturm · System").get_by_role(
        "button", name="Übernehmen", exact=True
    ).click()
    expect(entities).to_contain_text("Leuchtturm")

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

    # Selecting an entity opens its detail: the type and description of the
    # row the review filed.
    entities.get_by_text("Mira", exact=True).click()
    detail = dock.get_by_role("region", name="Mira")
    expect(detail).to_contain_text("Figur")
    expect(detail).to_contain_text("Mira appears in the chapter.")

    assert_accessible(page)


def test_the_wissen_dock_reviews_the_novels_findings(page: Page, stack: Stack) -> None:
    """The whole-novel check: the planted contradictions, reviewed to empty.

    Two chapters give Mira and Tom two different ages each; the check —
    novel-wide, its section beside the chapter-scoped extraction — files
    one finding per name, each a card quoting both readings. Acknowledge
    and dismiss consume exactly once: each card leaves the queue, each
    outcome is heard, and the job's done copy names the check's own count
    — the kind-aware row, not the extraction's words. The row settling is
    also the poll's end: no /api/jobs request may leave the page after it.
    """
    _open_workspace_with_validated_title(page, "Die widersprüchliche Bucht")
    _write_chapters(page, CONTRADICTING_BODIES)

    page.get_by_role("button", name="Wissen", exact=True).click()
    dock = page.get_by_role("complementary", name="Wissen")
    expect(dock).to_be_visible()
    checks = dock.get_by_role("region", name="Konsistenz")

    # The check is novel-wide: one trigger beside the extraction's chapter
    # one, closed while its job is outstanding — the same single-shot rule,
    # because a second click would stack a duplicate job behind the first.
    check = checks.get_by_role("button", name="Ganzes Buch prüfen")
    check.click()
    expect(check).to_be_disabled()
    status = checks.locator("[data-job-status]")
    expect(status).to_be_visible()
    # The row is the answer (spec §9 D10): it settles done, and the done
    # copy speaks the check's kind — the findings found, not the
    # extraction's suggestions.
    expect(status).to_have_attribute("data-job-status", "done")
    expect(status).to_contain_text("2 Widersprüche gefunden")
    # The settled job hands the trigger back for the next run.
    expect(check).to_be_enabled()

    # The findings arrive as cards: one per contradiction, the summary and
    # the detail quoting both readings on the card.
    cards = dock.get_by_role("region", name="Widerspruch")
    expect(cards).to_have_count(2)
    mira = cards.filter(has_text="Mira")
    expect(mira).to_contain_text("Mira: 34 vs. 37")
    expect(mira).to_contain_text('"Mira ist 34" vs. "Mira ist 37"')
    tom = cards.filter(has_text="Tom")
    expect(tom).to_contain_text("Tom: 30 vs. 33")
    expect(tom).to_contain_text('"Tom ist 30" vs. "Tom ist 33"')

    # Acknowledge consumes Mira's finding exactly once: the card leaves the
    # queue and the outcome is heard, not only seen.
    mira.get_by_role("button", name="Übernehmen", exact=True).click()
    expect(mira).to_have_count(0)
    expect(page.locator("[data-live-announcer]")).to_contain_text(
        "Der Widerspruch wurde zur Kenntnis genommen"
    )

    # Dismiss consumes Tom's: the queue is spent, and the done row stays
    # the parse's count — two found, whatever the review decided.
    tom.get_by_role("button", name="Verwerfen").click()
    expect(cards).to_have_count(0)
    expect(page.locator("[data-live-announcer]")).to_contain_text("Der Widerspruch wurde verworfen")
    expect(status).to_contain_text("2 Widersprüche gefunden")

    # The status stays the result, not a spinner: polling stopped with the
    # done row. No /api/jobs request may leave the page for the next turns
    # of the poll's own clock.
    poll_silence: list[str] = []
    page.on(
        "request",
        lambda request: poll_silence.append(request.url) if "/api/jobs/" in request.url else None,
    )
    page.wait_for_timeout(2500)
    assert poll_silence == [], f"the done check job is still polled: {poll_silence}"

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
    expect(status).to_contain_text("5")

    cards = dock.get_by_role("region", name="Vorgeschlagene Entität")
    expect(cards).to_have_count(5)
    entities = dock.get_by_role("region", name="Entitäten")

    # Accept by keyboard: Mira is filed into the searchable list.
    accept_mira = cards.filter(has_text="Mira · Figur").get_by_role(
        "button", name="Übernehmen", exact=True
    )
    _tab_to(page, accept_mira)
    page.keyboard.press("Enter")
    expect(entities).to_contain_text("Mira")

    # Discard by keyboard: See never becomes an entity.
    discard_see = cards.filter(has_text="See · Fraktion").get_by_role("button", name="Verwerfen")
    _tab_to(page, discard_see)
    page.keyboard.press("Enter")
    expect(entities).not_to_contain_text("See")

    # One decision each: the queue holds the chapter's other three cards.
    expect(cards).to_have_count(3)
    expect(cards.filter(has_text="Haus · Ort")).to_be_visible()

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
    expect(status).to_contain_text("5")
    expect(dock.get_by_role("alert")).to_have_count(0)

    assert_accessible(page)


def test_the_review_queue_names_an_unreachable_backend(page: Page, stack: Stack) -> None:
    """The queue's outage is named, never worn as a spent queue.

    A queue holding five pending cards goes unreachable: a reload that
    cannot reach the service must say so in the queue's own words. The
    entity list shed this mask first (its outage test pins that alert);
    the queue's silence would read worse — as a queue already reviewed —
    and the alerts must stay nameable apart, because every panel of the
    dock sits in the same outage and every query fails together (the
    findings queue's alert shares this phrasing's tail, so the filter
    carries the queue's own noun).
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
    expect(cards).to_have_count(5)

    # The reload is the refetch path: a fresh page asks again, and the
    # queue's answer must be the outage's own name — not the silence a
    # spent queue renders exactly like.
    stack.stop_api()
    try:
        page.reload()
        expect(dock).to_be_visible()
        queue_alert = dock.get_by_role("alert").filter(
            has_text="Vorschläge lassen sich nicht laden"
        )
        expect(queue_alert).to_be_visible()
        # The queue does not pretend beside its own alert: no last-known
        # cards stand in for the missing answer.
        expect(cards).to_have_count(0)
    finally:
        stack.start_api()

    # Recovery: the same page, asked again, shows the queue it holds —
    # and no error is left standing.
    page.reload()
    expect(cards).to_have_count(5)
    expect(dock.get_by_role("alert")).to_have_count(0)

    assert_accessible(page)


def test_a_rerun_stacks_no_duplicate_cards(page: Page, stack: Stack) -> None:
    """The re-run files one card set, and a consumed row files fresh.

    An extraction re-run — the outage retry's shape, the trigger clicked
    again after the row settled — parses the same entities off the same
    chapter. The pending dedupe must hold: the queue answers with the cards
    it already has, never a stacked second set. The asymmetry is the other
    half of the rule: accept consumes a row, so the next re-run files that
    entity fresh — the review is the only thing that reopens a filed key.
    """
    _open_workspace_with_validated_title(page, "Die wiederholte Durchsuchung")
    _write_chapter(page)

    page.get_by_role("button", name="Wissen", exact=True).click()
    dock = page.get_by_role("complementary", name="Wissen")
    expect(dock).to_be_visible()
    extract = dock.get_by_role("button", name="Dieses Kapitel durchsuchen")
    status = dock.locator("[data-job-status]")
    cards = dock.get_by_role("region", name="Vorgeschlagene Entität")

    # The first run files its five cards.
    extract.click()
    expect(status).to_have_attribute("data-job-status", "done")
    expect(cards).to_have_count(5)

    # The re-run on the same chapter: one card set, whatever the panel is
    # asked again. (The done row's count is the parse's, not the queue's —
    # the card count is the dedupe's witness.)
    _rerun_extraction_to_done(dock, extract, status)
    expect(cards).to_have_count(5)

    # The asymmetry: accept consumes Mira's row, and the re-run files her
    # fresh beside the four that never left.
    cards.filter(has_text="Mira · Figur").get_by_role(
        "button", name="Übernehmen", exact=True
    ).click()
    expect(cards).to_have_count(4)
    _rerun_extraction_to_done(dock, extract, status)
    expect(cards).to_have_count(5)

    assert_accessible(page)


def test_the_dock_search_reaches_passages(page: Page, stack: Stack) -> None:
    """The search box's second tier: passages from the semantic search.

    While the box carries a query, a debounced server search renders the
    corpus's passages under the entity list, each with its document's
    title. A search that meets a dead service names itself: the same
    named-failure rule the dock's other panels hold, in this tier's own
    words.
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
    """A novel with the chapter's five candidates filed as entities, through
    the API.

    The correction flows start where review leaves the story: five accepted
    entities and no chapter to write first. The API is the
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
        assert len(suggestions.json()) == 5
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
    # only See went: the merge's survivor and the two untouched candidates stay
    expect(entities.get_by_role("row")).to_have_count(3)
    expect(_row_named(entities, "Haus")).to_be_visible()
    expect(_row_named(entities, "Draußen")).to_be_visible()
    expect(_row_named(entities, "Leuchtturm")).to_be_visible()
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


def _label_entities(novel_id: str, labels: dict[str, dict[str, list[str]]]) -> None:
    """Alias and tag the seeded entities through the correction API.

    The filter flows need a list whose tags differ per row, and the list
    grows only through review — so the labels ride the same PATCH the
    edit dialog drives. Seeding is a faster driver, not another door.
    """
    with httpx.Client(base_url=API, timeout=30) as api:
        listed = api.get(f"/api/knowledge/novels/{novel_id}/entities")
        listed.raise_for_status()
        by_name = {row["name"]: row["id"] for row in listed.json()}
        for name, changes in labels.items():
            patched = api.patch(f"/api/knowledge/entities/{by_name[name]}", json=changes)
            patched.raise_for_status()


def test_the_entity_list_filters_by_type_tag_and_searches_the_server(
    page: Page, stack: Stack
) -> None:
    """The filters narrow where the rows are; the search asks the server.

    The type filter and the tag filter answer from the novel's own rows —
    the tag picker offers exactly the tags the novel's entities carry —
    and both compose. A combo with no answers names the empty result
    rather than wearing the unfiltered list. The search box's tier is the
    server's trigram search: a misspelt name still finds its row, which
    the substring filter it replaced could never do, and clearing the box
    answers unfiltered again.
    """
    novel_id = _seed_entities("Die gefilterte Bucht")
    _label_entities(
        novel_id,
        {
            "Mira": {"aliases": ["Miri"], "tags": ["Hauptfigur"]},
            "Haus": {"tags": ["Hauptfigur", "Gebäude"]},
            "See": {"tags": ["Natur"]},
        },
    )
    page.goto(f"http://127.0.0.1:3100/novels/{novel_id}")
    expect(page.get_by_role("heading", name="Die gefilterte Bucht")).to_be_visible()
    page.get_by_role("button", name="Wissen", exact=True).click()
    dock = page.get_by_role("complementary", name="Wissen")
    entities = dock.get_by_role("region", name="Entitäten")
    expect(_row_named(entities, "Mira")).to_be_visible()
    expect(entities.get_by_role("row")).to_have_count(5)

    # The type filter narrows to the characters.
    dock.get_by_label("Nach Typ filtern").select_option(label="Figur")
    expect(_row_named(entities, "Mira")).to_be_visible()
    expect(_row_named(entities, "Haus")).to_have_count(0)
    expect(entities.get_by_role("row")).to_have_count(1)
    # The narrowed answer's identity, after the settling count: while the
    # narrowed ask refetches, the list keeps its previous page, so the
    # presence above can pass against the unfiltered rows.
    expect(_row_named(entities, "Mira")).to_have_count(1)

    # The tag filter composes: Mira carries Hauptfigur, but not Natur.
    dock.get_by_label("Nach Tag filtern").select_option(label="Hauptfigur")
    expect(_row_named(entities, "Mira")).to_be_visible()
    dock.get_by_label("Nach Typ filtern").select_option(label="Alle Typen")
    expect(_row_named(entities, "Haus")).to_be_visible()
    expect(_row_named(entities, "See")).to_have_count(0)
    expect(entities.get_by_role("row")).to_have_count(2)

    # A combo with no answers is named, not masked: no character carries
    # the tag Natur.
    dock.get_by_label("Nach Typ filtern").select_option(label="Figur")
    dock.get_by_label("Nach Tag filtern").select_option(label="Natur")
    expect(entities.get_by_text("Keine Treffer")).to_be_visible()

    # Reset, and ask the server for a misspelt name: "Leuchturm" shares
    # enough of the word to find the row — a substring filter would have
    # answered with nothing.
    dock.get_by_label("Nach Typ filtern").select_option(label="Alle Typen")
    dock.get_by_label("Nach Tag filtern").select_option(label="Alle Tags")
    expect(entities.get_by_role("row")).to_have_count(5)
    # Escape closes the box's popup: while it stands open the rest of the
    # dock is aria-hidden, and the rows below must answer their role.
    dock.get_by_label("Entitäten durchsuchen").fill("Leuchturm")
    dock.get_by_label("Entitäten durchsuchen").press("Escape")
    expect(_row_named(entities, "Leuchtturm")).to_be_visible()
    expect(_row_named(entities, "Mira")).to_have_count(0)

    # An empty box is no filter: the list answers whole again.
    dock.get_by_label("Entitäten durchsuchen").fill("")
    dock.get_by_label("Entitäten durchsuchen").press("Escape")
    expect(_row_named(entities, "Mira")).to_be_visible()
    expect(entities.get_by_role("row")).to_have_count(5)

    assert_accessible(page)


def test_the_edit_dialog_edits_aliases_tags_and_the_markdown_body(page: Page, stack: Stack) -> None:
    """The dialog carries every field, and the card shows what it filed.

    Enter files an alias chip, a comma files a tag chip, and a case twin
    dedupes against the chip list — whose remove button answers the
    keyboard too: Shift+Tab reaches it, Enter presses it. The body edits
    as rich text and stores Markdown (F-26): the card previews the stored
    source — the heading stays characters there — and reopening the dialog
    shows the saved document as the editor renders it.
    """
    novel_id = _seed_entities("Die bearbeitete Bucht")
    page.goto(f"http://127.0.0.1:3100/novels/{novel_id}")
    expect(page.get_by_role("heading", name="Die bearbeitete Bucht")).to_be_visible()
    page.get_by_role("button", name="Wissen", exact=True).click()
    dock = page.get_by_role("complementary", name="Wissen")
    entities = dock.get_by_role("region", name="Entitäten")
    expect(_row_named(entities, "Mira")).to_be_visible()
    _row_named(entities, "Mira").click()
    detail = dock.get_by_role("region", name="Mira")
    expect(detail).to_contain_text("Mira appears in the chapter.")

    dock.get_by_role("region", name="Mira").get_by_role("button", name="Bearbeiten").click()
    dialog = page.get_by_role("dialog")

    # Enter files an alias chip; a comma files a tag chip.
    aliases = dialog.get_by_label("Aliase")
    aliases.fill("Miri")
    aliases.press("Enter")
    expect(dialog.get_by_text("Miri", exact=True)).to_be_visible()
    tags = dialog.get_by_label("Tags", exact=True)
    tags.fill("Hauptfigur")
    tags.press(",")
    expect(dialog.get_by_text("Hauptfigur", exact=True)).to_be_visible()

    # A case twin dedupes: the chip list keeps one Mira.
    aliases.fill("MIRI")
    aliases.press("Enter")
    expect(dialog.get_by_text("MIRI", exact=True)).to_have_count(0)
    expect(dialog.get_by_text("Miri", exact=True)).to_have_count(1)

    # The remove button answers the keyboard: Shift+Tab reaches it from the
    # field, Enter presses it. The chips wrapper's keydown serves the text
    # field only, so the button keeps its own activation.
    aliases.fill("Kathi")
    aliases.press("Enter")
    expect(dialog.get_by_text("Kathi", exact=True)).to_be_visible()
    aliases.press("Shift+Tab")  # back onto the chip's remove button
    expect(dialog.get_by_role("button", name="Kathi entfernen")).to_be_focused()
    page.keyboard.press("Enter")
    expect(dialog.get_by_text("Kathi", exact=True)).to_have_count(0)

    # The body is prose edited as rich text and stored as Markdown (F-26);
    # the card keeps previewing the stored source.
    dialog.get_by_label("Inhalt (Markdown)").fill("## Herkunft\n\nMira wuchs an der Bucht auf.")
    dialog.get_by_role("button", name="Speichern").click()
    expect(dialog).not_to_be_visible()
    expect(page.locator("[data-live-announcer]")).to_contain_text(
        "Änderungen an Mira wurden gespeichert"
    )

    # The card reads the new fields: the chips, and the body's source —
    # the preview is the Markdown, not a rendering of it.
    expect(detail.get_by_text("Miri", exact=True)).to_be_visible()
    expect(detail.get_by_text("Hauptfigur", exact=True)).to_be_visible()
    expect(detail.get_by_text("## Herkunft")).to_be_visible()
    expect(detail).to_contain_text("Mira wuchs an der Bucht auf.")

    # The save kept the document as Markdown source — the heading is there
    # as written, and no HTML serialization of the document went out instead
    # (a rendering-only check alone would pass an editor that dropped the
    # content or stored `<p>` padding).
    with httpx.Client(base_url=API, timeout=30) as api:
        stored = api.get(f"/api/knowledge/novels/{novel_id}/entities").json()
        mira = next(entity for entity in stored if entity["name"] == "Mira")
        assert "## Herkunft" in mira["content"]
        assert "<p>" not in mira["content"]

    # Reopening shows what the save kept: chip and body persist — the body
    # as the editor holds it now, rich text: the heading is a real heading,
    # the sentence the paragraph under it.
    dock.get_by_role("region", name="Mira").get_by_role("button", name="Bearbeiten").click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_text("Miri", exact=True)).to_be_visible()
    body_field = dialog.get_by_label("Inhalt (Markdown)")
    expect(body_field.get_by_role("heading", name="Herkunft")).to_be_visible()
    expect(body_field.get_by_text("Mira wuchs an der Bucht auf.", exact=True)).to_be_visible()

    assert_accessible(page)


def _entity_id(novel_id: str, name: str) -> str:
    """One seeded entity's id, by its exact name."""
    with httpx.Client(base_url=API, timeout=30) as api:
        listed = api.get(f"/api/knowledge/novels/{novel_id}/entities")
        listed.raise_for_status()
        return next(row["id"] for row in listed.json() if row["name"] == name)


def test_the_relations_are_maintained_in_the_dialog(page: Page, stack: Stack) -> None:
    """Add, retype, delete — and the card shows both directions.

    The add row picks the target from the novel's other entries and the
    type from the suggested vocabulary (free text stays welcome); the row
    edits inline, the ends immutable. The compact card reads the same
    edges from both sides and flags a self-relation, which only a
    re-pointed edge can be — the add row never offers the row itself.
    Exactly one edge leaves when its delete is pressed.
    """
    novel_id = _seed_entities("Die verbundene Bucht")
    # The seeded accept chain left Leuchtturm → Mira (the one proposal
    # whose target existed). The self-loop rides the API: the add row
    # offers only the other entries, so the loop is a merge's leftover —
    # seeded here as the faster driver.
    leuchtturm = _entity_id(novel_id, "Leuchtturm")
    with httpx.Client(base_url=API, timeout=30) as api:
        looped = api.post(
            f"/api/knowledge/entities/{leuchtturm}/relations",
            json={"to_entity_id": leuchtturm, "relation_type": "related_to"},
        )
        looped.raise_for_status()

    page.goto(f"http://127.0.0.1:3100/novels/{novel_id}")
    expect(page.get_by_role("heading", name="Die verbundene Bucht")).to_be_visible()
    page.get_by_role("button", name="Wissen", exact=True).click()
    dock = page.get_by_role("complementary", name="Wissen")
    entities = dock.get_by_role("region", name="Entitäten")
    expect(_row_named(entities, "Leuchtturm")).to_be_visible()
    _row_named(entities, "Leuchtturm").click()
    detail = dock.get_by_role("region", name="Leuchtturm")
    # The compact card: the seeded edge, and the loop with its mark.
    expect(detail).to_contain_text("→ Mira")
    expect(detail).to_contain_text("Verbunden mit")
    expect(detail).to_contain_text("Selbstbezug")

    # Haus's card first, so its relations answer sits in the cache: an
    # edge always has two ends, and the other end's card below must
    # follow the edit without waiting out the answer's freshness.
    _row_named(entities, "Haus").click()
    haus_before = dock.get_by_role("region", name="Haus")
    expect(haus_before).to_be_visible()
    expect(haus_before).not_to_contain_text("Leuchtturm")

    _row_named(entities, "Leuchtturm").click()
    detail = dock.get_by_role("region", name="Leuchtturm")
    detail.get_by_role("button", name="Bearbeiten").click()
    dialog = page.get_by_role("dialog")

    # Add: the target from the novel's other entries, the type from the
    # vocabulary, the note optional.
    target = dialog.get_by_label("Verbinden mit")
    target.fill("Haus")
    target.press("ArrowDown")
    target.press("Enter")
    expect(target).to_have_value("Haus")
    kind = dialog.get_by_label("Beziehungsart")
    kind.fill("Verbündet")
    kind.press("ArrowDown")
    kind.press("Enter")
    expect(kind).to_have_value("Verbündet mit")
    dialog.get_by_label("Notiz (optional)").fill("Seit dem Sturm")
    dialog.get_by_role("button", name="Beziehung hinzufügen").click()
    row = dialog.get_by_role("listitem").filter(has_text="Haus")
    expect(row).to_contain_text("Verbündet mit")
    expect(row).to_contain_text("Seit dem Sturm")
    expect(page.locator("[data-live-announcer]")).to_contain_text("Die Beziehung wurde hinzugefügt")

    # Inline edit: the type retypes, the ends never move.
    row.get_by_role("button", name="Beziehung bearbeiten").click()
    row_kind = row.get_by_label("Beziehungsart")
    row_kind.fill("Verfeindet")
    row_kind.press("ArrowDown")
    row_kind.press("Enter")
    row.get_by_role("button", name="Speichern").click()
    expect(row).to_contain_text("Verfeindet mit")
    expect(page.locator("[data-live-announcer]")).to_contain_text("Die Beziehung wurde gespeichert")

    dialog.get_by_role("button", name="Speichern").click()
    expect(dialog).not_to_be_visible()

    # The card keeps what the dialog filed, and Haus reads the same edge
    # from the other side — a revisit, so the cached answer from before
    # the edit must not be what the card serves.
    expect(detail).to_contain_text("→ Haus · Verfeindet mit")
    _row_named(entities, "Haus").click()
    haus = dock.get_by_role("region", name="Haus")
    expect(haus).to_contain_text("← Leuchtturm · Verfeindet mit")

    # Deleting takes exactly the one edge: the loop and the seeded edge
    # survive on the same card.
    _row_named(entities, "Leuchtturm").click()
    dock.get_by_role("region", name="Leuchtturm").get_by_role("button", name="Bearbeiten").click()
    dialog = page.get_by_role("dialog")
    row = dialog.get_by_role("listitem").filter(has_text="Verfeindet")
    row.get_by_role("button", name="Beziehung löschen").click()
    expect(row).to_have_count(0)
    expect(page.locator("[data-live-announcer]")).to_contain_text("Die Beziehung wurde gelöscht")
    dialog.get_by_role("button", name="Abbrechen").click()
    expect(dialog).not_to_be_visible()
    expect(dock.get_by_role("region", name="Leuchtturm")).not_to_contain_text("Verfeindet mit")
    expect(dock.get_by_role("region", name="Leuchtturm")).to_contain_text("Selbstbezug")
    expect(dock.get_by_role("region", name="Leuchtturm")).to_contain_text("→ Mira")

    assert_accessible(page)
