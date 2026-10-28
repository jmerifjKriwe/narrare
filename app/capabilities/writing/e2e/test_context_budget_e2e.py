"""The budgeted continuation prompt, proven on the real stack's audited row.

Three flows over the real browser, API and database — the only fake is the
LLM provider. First, the default tier's prompt carries what the workbench
knows: the entity reached through its case-folded alias, chapter 1's tail and
the genre, each under its own heading. Second, a profile with a 2048-token
window (max output unset, so the kernel default 1024 applies) measurably
shrinks every section to its budget — room 3 584 characters, split 60/25/10/5
— and the whole prompt shrinks with it, compared against a default-tier run
of the same data pattern. Third, a zero-room pair (1024 into 1024) is
refused: the one error frame, the editor untouched, and no audit row at all —
nothing ran, so nothing was audited.

pytest-randomly shuffles this module's tests, so none leans on another's
leftovers: an autouse fixture clears the resolution state before every test,
each test builds the profiles it names through the settings form, and every
comparison a test makes happens inside that test. Every assertion on the
prompt reads ``llm_calls.prompt_text`` — the row the audit wrote, not a spy
on the provider.
"""

import asyncio
from collections.abc import Iterator  # noqa: TC003
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.db.testsupport import url_for
from app.kernel.testing.a11y import assert_accessible

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

BASE = "http://127.0.0.1:3100"
DATABASE = "narrare_v2_e2e"  # the stack's own database (e2e/conftest.py)

GENRE = "Historischer Roman"
BLURB = "Eine Erzählung über den Deich, den Nebel und ein Boot, das niemand mehr braucht."

# "Mira" is the text's first capitalized word, so the fake's derivation
# proposes her first and as a character — the one suggestion a test accepts;
# the entity then carries the description the fake proposed.
CHAPTER_ONE = (
    "Mira wohnt seit dem Herbst in der Schenke am Deich. Der Nebel zieht "
    "abends über das Wasser, und die Laterne am Steg flackert. Wanderer "
    "meiden den Weg, seit die Fähre verrostet."
)
CHAPTER_ONE_TAIL = "seit die Fähre verrostet."

# Longer than a 2048-token window's immediate slice (~1 950 characters), so
# the small prompt's tail is hard-cut, and shorter than the default tier's
# (~15 000), so the default prompt carries the whole typed text. The tail
# names the entity only by its alias — in upper case, which the ranking must
# fold to match.
_PROLOGUE = "Der Nebel hing tief über dem Deich, und die Möwen rasten auf den Pfählen. " * 30
CHAPTER_TWO = (
    _PROLOGUE + "DIE WANDERIN kehrte an den Steg zurück. Das Boot lag tief im Wasser, "
    "und der Nebel verschluckte jedes Geräusch, während draußen am Deich "
    "eine Laterne brannte."
)

ENTITY_BODY = "Mira appears in the chapter."
ALIAS = "die Wanderin"

# The prompt's section delimiters, and the pinned budgets of a 2048-token
# window whose output reserve stays the kernel default 1024 (D1's 60/25/10/5
# split over room 3 584 characters at 3.5 characters per token).
ENTITIES_HEADING = "Referenced entities:"
PREDECESSORS_HEADING = "Previous chapters:"
STYLE_HEADING = "Style notes:"
IMMEDIATE_BUDGET = 2151
ENTITIES_BUDGET = 896
PREDECESSORS_BUDGET = 358
STYLE_BUDGET = 179

DEFAULT_NOVEL = "Die Schenke im Nebel"
BASELINE_NOVEL = "Die Kette am Kai"
SMALL_NOVEL = "Die Wolke überm Deich"
REFUSED_NOVEL = "Die stille Boje"
SMALL_PROFILE = "Kontext Schmal"
REFUSED_PROFILE = "Nullraum"


def _delete_profiles() -> None:
    """Clear the resolution state, in a worker thread.

    pytest-asyncio keeps a session loop running, and asyncio.run refuses to
    start a second one in the same thread.
    """

    async def run() -> None:
        """Delete the profiles; the assignments cascade with them."""
        engine = create_async_engine(url_for(DATABASE))
        try:
            async with engine.begin() as connection:
                await connection.execute(text("DELETE FROM provider_profiles"))
        finally:
            await engine.dispose()

    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(asyncio.run, run()).result()


@pytest.fixture(autouse=True)
def clean_resolution(stack: Stack) -> Iterator[None]:
    """Every test starts on the environment tier: no profiles, no assignments.

    The shuffle turns any leftover into a coin flip — a task assignment or a
    default profile left by an earlier test would answer a later test's
    continuation, and the default tier test 1 pins would never resolve. The
    cascade takes the assignments with the profiles. Novels stay: each test
    owns a unique title and queries it by name.
    """
    _delete_profiles()
    yield


def _rows(statement: str, params: dict[str, object] | None = None) -> list[tuple[object, ...]]:
    """Rows from the stack's own database, as plain tuples."""

    async def run() -> list[tuple[object, ...]]:
        """Ask a fresh async engine; the dispose lands even on a failed query."""
        engine = create_async_engine(url_for(DATABASE))
        try:
            async with engine.connect() as connection:
                return [
                    tuple(each) for each in await connection.execute(text(statement), params or {})
                ]
        finally:
            await engine.dispose()

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, run()).result()


def _continuation_rows(title: str) -> list[tuple[str, str, str, str, str | None]]:
    """The continuation audit rows of the named novel, the prompt included.

    The review flow's extraction audits its own row for the same novel, so
    the task key scopes this to the continuation call. The audit is the only
    writer of llm_calls, so what a test asserts here is what the request
    really carried.
    """

    async def run() -> list[tuple[str, str, str, str, str | None]]:
        """Read the named novel's audit rows with a fresh async engine."""
        engine = create_async_engine(url_for(DATABASE))
        try:
            async with engine.connect() as connection:
                rows = await connection.execute(
                    text(
                        "SELECT status, task_key, prompt_text, response_text, profile_id"
                        " FROM llm_calls c JOIN novels n ON c.novel_id = n.id"
                        " WHERE n.title = :title AND c.task_key = 'writing.continuation'"
                    ),
                    {"title": title},
                )
                return [
                    (
                        str(row.status),
                        str(row.task_key),
                        str(row.prompt_text),
                        str(row.response_text),
                        None if row.profile_id is None else str(row.profile_id),
                    )
                    for row in rows
                ]
        finally:
            await engine.dispose()

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, run()).result()


def _profile_id(name: str) -> str:
    """The id of the profile the settings form created, straight from the table."""
    [row] = _rows("SELECT id FROM provider_profiles WHERE name = :name", {"name": name})
    return str(row[0])


def _sliced_sections(prompt: str) -> tuple[str, str, str, str]:
    """Split an assembled prompt back into its four budgeted sections.

    The three headings delimit the sections. The assembler places a
    two-character separator after the entities' and the predecessors' blocks;
    it is stripped here, so each returned string is exactly the slice the
    assembler was given, its heading included. The style section ends at the
    first blank line — its lines never carry one — which is where the
    instruction begins.
    """
    immediate, marker, rest = prompt.partition(ENTITIES_HEADING)
    assert marker, "the prompt carries no entities heading"
    entities, marker, rest = rest.partition(PREDECESSORS_HEADING)
    assert marker, "the prompt carries no predecessors heading"
    entities = ENTITIES_HEADING + entities.removesuffix("\n\n")
    predecessors, marker, rest = rest.partition(STYLE_HEADING)
    assert marker, "the prompt carries no style heading"
    predecessors = PREDECESSORS_HEADING + predecessors.removesuffix("\n\n")
    style = STYLE_HEADING + rest.partition("\n\n")[0]
    return immediate, entities, predecessors, style


def _open_settings(page: Page) -> None:
    """The gear's door: from the shelf's top bar to /settings."""
    page.goto(BASE + "/")
    page.get_by_role("link", name="Einstellungen").click()
    expect(page).to_have_url(f"{BASE}/settings")
    expect(page.get_by_role("heading", name="Einstellungen")).to_be_visible()


def _create_profile_and_assign(page: Page, name: str, context_window: str) -> None:
    """Create one fake profile through the form, then hand it the task.

    The window is the field's whole point here; the output cap stays empty,
    so the kernel default 1024 applies (D7: every unset limit falls back on
    its own). The assignment is the select's label option, waited out until
    the PUT's refetch moves the control — the same wait the settings flow
    uses before it leaves the page.
    """
    _open_settings(page)
    page.get_by_label("Name", exact=True).fill(name)
    page.get_by_label("Art").select_option(label="Fake (deterministisch, ohne Netzwerk)")
    page.get_by_label("Modell").fill(f"modell-{name.split()[-1].lower()}")
    page.get_by_label("Kontextfenster (Tokens)").fill(context_window)
    page.get_by_role("button", name="Profil hinzufügen").click()
    expect(page.get_by_role("listitem").filter(has_text=name)).to_be_visible()
    continuation = page.get_by_label("Weiterschreiben")
    continuation.select_option(label=name)
    expect(continuation).not_to_have_value("")


def _create_novel(page: Page, title: str) -> None:
    """Create a novel with genre and blurb through the shelf's form, and open it."""
    page.goto(BASE + "/")
    page.get_by_role("button", name="Neues Buch").click()
    page.get_by_label("Titel").fill(title)
    page.get_by_label("Genre").fill(GENRE)
    page.get_by_label("Klappentext").fill(BLURB)
    page.get_by_role("button", name="Anlegen").click()
    page.get_by_role("link", name=title).click()
    expect(page.get_by_role("heading", name=title)).to_be_visible()


def _wait_saved(page: Page) -> None:
    """Wait for the editor's own saved status — the indicator element itself.

    Matched by element and text, not by a bare ``get_by_text``: the live
    announcer may still carry the entity editor's "…gespeichert.", which a
    substring search would take for this chapter's save.
    """
    expect(page.locator("span[role='status']").filter(has_text="Gespeichert")).to_be_visible()


def _write_chapter(page: Page, body: str) -> None:
    """Create a new chapter and type the body, waiting for the save it reports.

    The new chapter's own editor is the one that must show saved: its empty
    text proves the switch happened before a keystroke lands, so the typed
    body is the one the save carries.
    """
    page.get_by_role("button", name="Neues Kapitel").click()
    editor = page.locator(".ProseMirror")
    expect(editor).to_be_visible()
    expect(editor).to_have_text("")
    editor.click()
    page.keyboard.type(body)
    _wait_saved(page)


def _accept_mira_and_file_alias(page: Page) -> None:
    """Extraction over the open chapter, the Mira card accepted, the alias filed.

    The knowledge dock's own flow: the job settles done, the queue holds the
    proposal cards, one accept files the entity — and the entity editor's
    alias field takes ``die Wanderin`` as a chip, announced by the save.
    """
    page.get_by_role("button", name="Wissen", exact=True).click()
    dock = page.get_by_role("complementary", name="Wissen")
    expect(dock).to_be_visible()

    dock.get_by_role("button", name="Dieses Kapitel durchsuchen").click()
    status = dock.locator("[data-job-status]")
    expect(status).to_have_attribute("data-job-status", "done")

    entities = dock.get_by_role("region", name="Entitäten")
    dock.get_by_role("region", name="Vorgeschlagene Entität").filter(
        has_text="Mira · Figur"
    ).get_by_role("button", name="Übernehmen", exact=True).click()
    row = entities.get_by_role("gridcell", name="Mira", exact=True)
    expect(row).to_be_visible()

    # The detail shows the body the entity editor keeps — the description the
    # fake proposed and the prompt will carry. The alias rides the editor's
    # chips field: typed, filed with Enter, saved with the dialog's button.
    row.click()
    detail = dock.get_by_role("region", name="Mira")
    expect(detail).to_contain_text(ENTITY_BODY)
    detail.get_by_role("button", name="Bearbeiten").click()
    dialog = page.get_by_role("dialog")
    aliases = dialog.get_by_label("Aliase")
    aliases.fill(ALIAS)
    aliases.press("Enter")
    dialog.get_by_role("button", name="Speichern").click()
    expect(dialog).not_to_be_visible()
    expect(detail.get_by_text(ALIAS, exact=True)).to_be_visible()


def _continue_and_take(page: Page) -> None:
    """Run the continuation, wait for the whole ghost, take it with Tab."""
    page.get_by_role("button", name="Weiterschreiben").click()
    # The stream becomes a ghost at the caret; waiting for its last words
    # proves the whole answer arrived before the row is read.
    ghost = page.locator(".ProseMirror .ghost")
    expect(ghost).to_contain_text("über die Straße.")
    page.keyboard.press("Tab")
    expect(page.locator(".ProseMirror .ghost")).to_have_count(0)
    _wait_saved(page)


def test_slices_land_in_the_prompt(page: Page, stack: Stack) -> None:
    """The default tier's prompt carries entity, predecessor tail and genre."""
    _create_novel(page, DEFAULT_NOVEL)
    _write_chapter(page, CHAPTER_ONE)
    _accept_mira_and_file_alias(page)
    _write_chapter(page, CHAPTER_TWO)

    _continue_and_take(page)
    assert_accessible(page)

    [(status, task_key, prompt_text, response_text, profile_id)] = _continuation_rows(DEFAULT_NOVEL)
    assert (status, task_key) == ("ok", "writing.continuation")
    assert "über die Straße." in response_text
    # The environment tier answered: no profile exists, so none is audited.
    assert profile_id is None

    immediate, entities, predecessors, style = _sliced_sections(prompt_text)
    # Chapter 2 never names Mira — only her alias, in upper case. Her entry
    # under the entities heading is the case-folded match working.
    assert "### Mira" in entities
    assert ENTITY_BODY in entities
    # Chapter 1's tail rides its own section, the genre its own.
    assert CHAPTER_ONE_TAIL in predecessors
    assert f"Genre: {GENRE}" in style
    assert "DIE WANDERIN" in immediate


def test_a_small_window_shrinks_the_prompt(page: Page, stack: Stack) -> None:
    """Every section of the 2048-window prompt stays inside its pinned budget."""
    # The comparison's own baseline: the same data pattern on the default
    # tier, before any profile exists to answer instead of the environment.
    _create_novel(page, BASELINE_NOVEL)
    _write_chapter(page, CHAPTER_ONE)
    _accept_mira_and_file_alias(page)
    _write_chapter(page, CHAPTER_TWO)
    _continue_and_take(page)

    baseline_rows = _continuation_rows(BASELINE_NOVEL)
    [(baseline_status, _, _, _, baseline_profile)] = baseline_rows
    assert baseline_status == "ok"
    assert baseline_profile is None

    # Then the small window: the profile is created once, here, through the
    # UI, and the assignment points the task at it.
    _create_profile_and_assign(page, SMALL_PROFILE, "2048")
    assert_accessible(page)

    page.get_by_role("link", name="Alle Romane").click()
    _create_novel(page, SMALL_NOVEL)
    _write_chapter(page, CHAPTER_ONE)
    _accept_mira_and_file_alias(page)
    _write_chapter(page, CHAPTER_TWO)

    _continue_and_take(page)
    assert_accessible(page)

    [(status, task_key, prompt_text, _, profile_id)] = _continuation_rows(SMALL_NOVEL)
    assert (status, task_key) == ("ok", "writing.continuation")
    # The assignment tier served: the audit names the small-window profile.
    assert profile_id == _profile_id(SMALL_PROFILE)

    immediate, entities, predecessors, style = _sliced_sections(prompt_text)
    assert len(immediate) <= IMMEDIATE_BUDGET
    assert len(entities) <= ENTITIES_BUDGET
    assert len(predecessors) <= PREDECESSORS_BUDGET
    assert len(style) <= STYLE_BUDGET
    # Small is not empty: each section still carries its content.
    assert ENTITY_BODY in entities
    assert CHAPTER_ONE_TAIL in predecessors
    assert f"Genre: {GENRE}" in style

    # And the window's mark is on the whole prompt: it is measurably shorter
    # than the default tier's prompt for the same data pattern.
    assert len(prompt_text) < len(baseline_rows[0][2])


def test_a_zero_room_pair_is_refused(page: Page, stack: Stack) -> None:
    """A window its output reserve fills is refused — quietly, and unaudited."""
    _create_profile_and_assign(page, REFUSED_PROFILE, "1024")
    assert_accessible(page)

    page.get_by_role("link", name="Alle Romane").click()
    _create_novel(page, REFUSED_NOVEL)
    _write_chapter(page, "Die stille Boje lag im Schilf.")

    page.get_by_role("button", name="Weiterschreiben").click()

    # The refusal is the stream's one error frame, named where the button
    # sits. No ghost ever appears, and the typed text is all the editor owns.
    expect(page.get_by_role("alert")).to_contain_text("Die Fortsetzung ist fehlgeschlagen.")
    expect(page.locator(".ProseMirror .ghost")).to_have_count(0)
    expect(page.locator(".ProseMirror")).to_contain_text("Die stille Boje lag im Schilf.")
    expect(page.locator(".ProseMirror")).not_to_contain_text("Der Nebel")

    assert_accessible(page)

    # Nothing ran: no provider call, no audit row — a row of any task would
    # count, so the query carries no task filter and no profile filter.
    assert (
        _rows(
            "SELECT * FROM llm_calls c JOIN novels n ON c.novel_id = n.id WHERE n.title = :title",
            {"title": REFUSED_NOVEL},
        )
        == []
    )
