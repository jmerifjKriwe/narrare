"""The override lifecycle, end to end — §7.5's chain and the archive boundary.

Six flows over the real browser, the real API and the real database; the only
fake is the LLM provider. The page saves a novel-scoped override of
``writing.continuation`` and the next continuation's audited prompt carries the
override's marker sentence; a broken template and a ``chat.ask`` re-voice that
drops the marked sources are refused by name and store nothing; a reset hands
the prompt back to the bundled template; and an export of an overridden novel
carries exactly the closed archive surface — ``metadata.json``, ``chapters/``,
``kb/`` — so a round-trip lands as before, without the override it must not
carry.

pytest-randomly shuffles this module's tests, so none leans on another's
leftovers: every stored override is novel-scoped to a novel the test itself
created, a refused save's emptiness is asserted against that novel's id (not
the table), and the one global refusal names a key no test ever stores. Every
assertion on a prompt reads ``llm_calls.prompt_text`` — the row the audit
wrote, not a spy on the provider.
"""

import asyncio
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Locator, Page, expect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.db.testsupport import url_for
from app.kernel.testing.a11y import assert_accessible

if TYPE_CHECKING:
    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(240)]

BASE = "http://127.0.0.1:3100"
DATABASE = "narrare_v2_prompts_e2e"  # the stack's own database (e2e/conftest.py)

APP = Path(__file__).resolve().parents[3]
DEMO = APP / "kernel" / "interchange" / "demos" / "im-stillen-wald"
"""The bundled German demo: two chapters, six entities, three relations."""

DEMO_CHAPTERS = 2
DEMO_ENTITIES = 6
DEMO_RELATIONS = 3

CONTINUATION = "writing.continuation"
CHAT = "chat.ask"

# The override's marker and the template that carries it: a working prompt —
# sections and instruction kept, so a render cannot fail for want of a
# variable — whose own line no bundled render can ever produce.
MARKER = "OVERRIDE-MARKER 4711"
OVERRIDE_TEMPLATE = (
    "Eigene Stimme für {{ novel_title }}: OVERRIDE-MARKER 4711.\n"
    "\n"
    "Text so far:\n"
    "{{ tail }}\n"
    "\n"
    "{{ entities_section }}{{ predecessors_section }}{{ style_section }}"
    "Continue the chapter in the same voice. Keep the language of the existing "
    "text. Return only the new text, without a heading or commentary."
)


# ---------------------------------------------------------------------------
# Database reads — the stack's own rows, never a spy on the request
# ---------------------------------------------------------------------------


def _rows(statement: str, params: dict[str, object] | None = None) -> list[tuple[object, ...]]:
    """Rows from the stack's database as plain tuples, in a worker thread.

    pytest-asyncio keeps a session loop running, and asyncio.run refuses to
    start a second one in the same thread.
    """

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


def _novel_id(title: str) -> str:
    """The id of the one novel carrying this title — every test owns a title."""
    [row] = _rows("SELECT id FROM novels WHERE title = :title", {"title": title})
    return str(row[0])


def _novel_ids(title: str) -> list[str]:
    """The ids carrying this title, oldest first — a re-import duplicates it."""
    return [
        str(row[0])
        for row in _rows(
            "SELECT id FROM novels WHERE title = :title ORDER BY created_at, id",
            {"title": title},
        )
    ]


def _latest_continuation(title: str) -> tuple[str, str]:
    """The novel's latest continuation audit row: status and prompt text.

    The audit is the only writer of llm_calls, so what a test asserts here is
    what the request really carried.
    """
    [row] = _rows(
        "SELECT status, prompt_text FROM llm_calls c"
        " JOIN novels n ON c.novel_id = n.id"
        " WHERE n.title = :title AND c.task_key = 'writing.continuation'"
        " ORDER BY c.created_at DESC LIMIT 1",
        {"title": title},
    )
    return str(row[0]), str(row[1])


def _override_count(novel_id: str) -> int:
    """How many override rows the novel's id carries — the archive's boundary."""
    [row] = _rows(
        "SELECT count(*) FROM prompt_templates WHERE novel_id = :novel_id",
        {"novel_id": novel_id},
    )
    count = row[0]
    assert isinstance(count, int)
    return count


def _chapters_of(novel_id: str) -> list[tuple[object, ...]]:
    """A novel's chapters in reading order: title, position, body."""
    return _rows(
        "SELECT title, position, body FROM chapters WHERE novel_id = :novel_id"
        " ORDER BY position, id",
        {"novel_id": novel_id},
    )


def _entities_of(novel_id: str) -> list[tuple[object, ...]]:
    """A novel's entities by name: name, type, body, aliases, tags."""
    return _rows(
        "SELECT name, type, content, aliases, tags FROM entities WHERE novel_id = :novel_id"
        " ORDER BY name",
        {"novel_id": novel_id},
    )


def _relations_of(novel_id: str) -> list[tuple[object, ...]]:
    """A novel's edges by end names: from, type, to, note."""
    return _rows(
        "SELECT source.name, edge.relation_type, target.name, edge.note"
        " FROM entity_relations edge"
        " JOIN entities source ON source.id = edge.from_entity_id"
        " JOIN entities target ON target.id = edge.to_entity_id"
        " WHERE source.novel_id = :novel_id"
        " ORDER BY edge.created_at, edge.id",
        {"novel_id": novel_id},
    )


# ---------------------------------------------------------------------------
# Driving the page, the workbench and the shelf's dialogs
# ---------------------------------------------------------------------------


def _continuation_card(page: Page) -> Locator:
    """The writing.continuation card on the prompts page, by its key code."""
    return page.get_by_role("listitem").filter(has_text=CONTINUATION)


def _prompts_for_novel(page: Page, title: str) -> Locator:
    """The prompts page with the novel selected; the continuation card back.

    Selecting in the filter is what makes the novel tier visible and triggers
    the novel-scoped refetch; waiting for the tier's own button is the caller's
    proof the refetch landed, so a click never reaches a stale global view.
    """
    page.goto(BASE + "/prompts")
    page.get_by_label("Roman").select_option(label=title)
    return _continuation_card(page)


def _save_override(page: Page, card: Locator, content: str) -> None:
    """Fill the open editor and save; the editor closing is the save landing."""
    card.get_by_label("Vorlage").fill(content)
    card.get_by_role("button", name="Speichern").click()
    expect(card.get_by_label("Vorlage")).to_have_count(0)


def _create_novel_with_chapter(page: Page, title: str, line: str) -> None:
    """Create a novel the only way a user can, open it, and write a line.

    The module's database is shared, so every test owns a title no other uses.
    """
    page.goto(BASE + "/")
    page.get_by_role("button", name="Neues Buch").click()
    page.get_by_label("Titel").fill(title)
    page.get_by_role("button", name="Anlegen").click()
    page.get_by_role("link", name=title).click()
    page.get_by_role("button", name="Neues Kapitel").click()
    editor = page.locator(".ProseMirror")
    editor.click()
    page.keyboard.type(line)
    expect(page.locator("span[role='status']").filter(has_text="Gespeichert")).to_be_visible()


def _run_continuation(page: Page) -> None:
    """Run the continuation, wait for the whole ghost, take it with Tab.

    The ghost's last words prove the stream finished; the audit row lands in
    the stream finalizer's own commit by the time the ghost is taken.
    """
    page.get_by_role("button", name="Weiterschreiben").click()
    ghost = page.locator(".ProseMirror .ghost")
    expect(ghost).to_contain_text("über die Straße.")
    page.keyboard.press("Tab")
    expect(page.locator(".ProseMirror .ghost")).to_have_count(0)


def _import_as_new_novel(page: Page, source: Path, title: str) -> None:
    """Import a folder as a new novel through the shelf, and read the receipt."""
    page.goto(BASE + "/")
    page.get_by_role("button", name="Importieren").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Archivpfad").fill(str(source))
    dialog.get_by_role("button", name="Jetzt importieren").click()
    expect(dialog.get_by_role("heading", name="Importbericht")).to_be_visible()
    for line in (
        f"{DEMO_CHAPTERS} Kapitel wurden hinzugefügt",
        f"{DEMO_ENTITIES} Wissenseinträge wurden hinzugefügt",
        f"{DEMO_RELATIONS} Beziehungen wurden angelegt",
    ):
        expect(dialog.get_by_role("listitem").filter(has_text=line)).to_be_visible()
    dialog.get_by_role("button", name="Schließen").click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    # A round-trip's title is already on the shelf, so the row is matched by
    # first: the receipt's counts above are the proof the import landed.
    expect(page.get_by_role("link", name=title).first).to_be_visible()


# ---------------------------------------------------------------------------
# The flows
# ---------------------------------------------------------------------------


def test_the_prompts_page_opens_over_the_real_stack(page: Page, stack: Stack) -> None:
    """The nav's own door: every bundled key, and the novel tiers say wait."""
    page.goto(BASE + "/")
    page.get_by_role("link", name="Prompts").click()
    expect(page).to_have_url(f"{BASE}/prompts")
    expect(page.get_by_role("heading", name="Prompts")).to_be_visible()

    for key in (CONTINUATION, CHAT, "knowledge.extract-entities", "knowledge.check-consistency"):
        expect(page.get_by_role("listitem").filter(has_text=key)).to_be_visible()
    # Without a novel selected, the novel scope names what it needs instead of
    # offering controls that could only guess at a target.
    expect(page.get_by_text("Wähle oben einen Roman").first).to_be_visible()

    assert_accessible(page)


def test_a_novel_override_reaches_the_continuation_prompt(page: Page, stack: Stack) -> None:
    """Saved through the page, carried by the call: §7.5's chain, audited."""
    title = "Die ferne Stimme"
    _create_novel_with_chapter(page, title, "Die ferne Stimme kam über den Deich.")

    card = _prompts_for_novel(page, title)
    card.get_by_role("button", name="Überschreibung für diesen Roman anlegen").click()
    _save_override(page, card, OVERRIDE_TEMPLATE)
    # The refetched list names the novel tier's state: the row is in force.
    expect(card.get_by_text("Eine Überschreibung dieses Romans ist in Kraft.")).to_be_visible()
    assert_accessible(page)

    page.goto(BASE + "/")
    page.get_by_role("link", name=title).click()
    _run_continuation(page)

    # The marker is in the audited prompt: the novel's override was the source
    # the chain rendered — not the bundled template, not the global tier.
    status, prompt_text = _latest_continuation(title)
    assert status == "ok"
    assert MARKER in prompt_text

    assert_accessible(page)


def test_a_broken_template_is_refused_by_name_and_stores_nothing(page: Page, stack: Stack) -> None:
    """The save gate's 422 is the page's named refusal; the novel keeps no row."""
    title = "Die steile These"
    _create_novel_with_chapter(page, title, "Die steile These stand im ersten Satz.")

    card = _prompts_for_novel(page, title)
    card.get_by_role("button", name="Überschreibung für diesen Roman anlegen").click()
    card.get_by_label("Vorlage").fill("Hallo {{ nope }}")
    card.get_by_role("button", name="Speichern").click()

    # The refusal names the reason and the variable, where the retry is.
    refusal = card.get_by_role("alert")
    expect(refusal).to_contain_text("Das Speichern wurde abgelehnt")
    expect(refusal).to_contain_text("Unbekannte Variable")
    expect(refusal).to_contain_text("nope")
    assert_accessible(page)

    # Refused means stored nothing: this novel's id carries no row at all.
    assert _override_count(_novel_id(title)) == 0


def test_a_chat_override_without_the_sources_is_refused_by_the_contract(
    page: Page, stack: Stack
) -> None:
    """A re-voice that drops the marked sources fails the contract, named."""
    page.goto(BASE + "/prompts")
    card = page.get_by_role("listitem").filter(has_text=CHAT)
    card.get_by_role("button", name="Überschreibung bearbeiten", exact=True).click()
    card.get_by_label("Vorlage").fill("Question only: {{ question }}")
    card.get_by_role("button", name="Speichern").click()

    refusal = card.get_by_role("alert")
    expect(refusal).to_contain_text("Das Speichern wurde abgelehnt")
    expect(refusal).to_contain_text("Vertrag verletzt")
    # The refusal names the key whose contract the render broke.
    expect(refusal).to_contain_text(CHAT)
    assert_accessible(page)

    # Nothing stored, in either tier: no test ever saves this key.
    assert (
        _rows("SELECT count(*) FROM prompt_templates WHERE prompt_key = :key", {"key": CHAT})[0][0]
        == 0
    )


def test_resetting_the_novel_scope_returns_the_bundled_prompt(page: Page, stack: Stack) -> None:
    """Reset through the page, and the next continuation speaks the bundled text."""
    title = "Die offene Rechnung"
    _create_novel_with_chapter(page, title, "Die offene Rechnung hing über dem Tisch.")

    card = _prompts_for_novel(page, title)
    card.get_by_role("button", name="Überschreibung für diesen Roman anlegen").click()
    _save_override(page, card, OVERRIDE_TEMPLATE)

    # The override bites before the reset means anything: the marker rode.
    page.goto(BASE + "/")
    page.get_by_role("link", name=title).click()
    _run_continuation(page)
    _, prompt_text = _latest_continuation(title)
    assert MARKER in prompt_text

    # The card names the tier's own override; the editor offers its reset, and
    # resetting closes the editor back onto the inherited state.
    card = _prompts_for_novel(page, title)
    card.get_by_role("button", name="Überschreibung dieses Romans bearbeiten").click()
    card.get_by_role("button", name="Zurücksetzen").click()
    expect(card.get_by_label("Vorlage")).to_have_count(0)
    expect(card.get_by_text("erbt: die mitgelieferte Vorlage")).to_be_visible()
    assert_accessible(page)

    # The row is gone — the reset deleted the novel's own tier, nothing else.
    assert _override_count(_novel_id(title)) == 0

    page.goto(BASE + "/")
    page.get_by_role("link", name=title).click()
    _run_continuation(page)
    status, prompt_text = _latest_continuation(title)
    assert status == "ok"
    # The bundled template's own header lines, and no marker anywhere.
    assert f"Novel: {title}" in prompt_text
    assert "Chapter: " in prompt_text
    assert MARKER not in prompt_text


def test_an_export_carries_the_closed_surface_and_no_override(
    page: Page, stack: Stack, tmp_path: Path
) -> None:
    """The archive's files are exactly the format's surface, marker in none."""
    title = "Die Archivprobe"
    source = tmp_path / "quelle"
    shutil.copytree(DEMO, source)
    metadata_path = source / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["title"] = title
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _import_as_new_novel(page, source, title)

    # An override stored before the export: the boundary has something to hold.
    card = _prompts_for_novel(page, title)
    card.get_by_role("button", name="Überschreibung für diesen Roman anlegen").click()
    _save_override(page, card, OVERRIDE_TEMPLATE)

    export = tmp_path / "export"
    page.goto(BASE + "/")
    row = page.get_by_role("listitem").filter(has_text=title)
    expect(row).to_be_visible()
    row.get_by_role("button", name="Exportieren").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Zielordner").fill(str(export))
    dialog.get_by_role("button", name="Jetzt exportieren").click()
    expect(dialog.get_by_role("heading", name="Export abgeschlossen")).to_be_visible()
    dialog.get_by_role("button", name="Schließen").click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    assert_accessible(page)

    # The closed set, exactly — the metadata, the chapters, the knowledge —
    # and every file in the tree inside it, the override's marker in none.
    assert {entry.name for entry in export.iterdir()} == {"metadata.json", "chapters", "kb"}
    files = [path for path in export.rglob("*") if path.is_file()]
    assert len([path for path in files if path.parent.name == "chapters"]) == DEMO_CHAPTERS
    assert len([path for path in files if path.parent.name == "kb"]) == DEMO_ENTITIES
    for path in files:
        relative = path.relative_to(export).as_posix()
        assert relative == "metadata.json" or relative.startswith(("chapters/", "kb/"))
        assert MARKER not in path.read_text(encoding="utf-8")

    # The round-trip as before: the folder comes back as a new novel, rows
    # equal to the source's — and the override stays behind, because nothing
    # in the archive carried it.
    _import_as_new_novel(page, export, title)

    source_id, copy_id = _novel_ids(title)
    assert source_id != copy_id
    assert _chapters_of(copy_id) == _chapters_of(source_id)
    assert _entities_of(copy_id) == _entities_of(source_id)
    assert _relations_of(copy_id) == _relations_of(source_id)
    # The comparison proved something: the source really carries the stock.
    assert len(_chapters_of(source_id)) == DEMO_CHAPTERS
    assert len(_entities_of(source_id)) == DEMO_ENTITIES
    assert _override_count(source_id) == 1
    assert _override_count(copy_id) == 0
