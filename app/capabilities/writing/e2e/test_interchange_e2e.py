"""The interchange gate: export, re-import, merge, and the two named refusals.

Four flows over the real browser, the real API and the real database — no
LLM involved beyond the embedding model's fake. Each seeds its own novel
through the shelf's import dialog from a copy of the bundled
*Im Stillen Wald* demo (unique title, so pytest-randomly may shuffle the
module), then drives the interchange dialogs a user drives:

* export as a ZIP and re-import it as a new novel — titles, types, bodies
  and relations equal in the database, row for row;
* export to a folder, revise one chapter file, drop one bare chapter and
  one bare knowledge file beside it, and merge — the receipt's counts are
  exactly what the database then holds (Review Focus 3);
* craft a chapter file whose `updated` predates the row's `updated_at` and
  merge — the conflict is named in the receipt and the stored prose is
  untouched (Review Focus 1);
* export to the same folder twice — the second attempt is refused by name
  and the first backup is not shrunk (Review Focus 2).

Every flow ends on the accessibility floor, with the receipt still on
screen where that flow's answer is.
"""

import asyncio
import json
import re
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
DATABASE = "narrare_v2_e2e"  # the stack's own database (e2e/conftest.py)

APP = Path(__file__).resolve().parents[3]
DEMO = APP / "kernel" / "interchange" / "demos" / "im-stillen-wald"
"""The bundled German demo: two chapters, six entities, three relations."""

CHAPTER_ONE = "Das Flüstern im Wald"

DEMO_CHAPTERS = 2
DEMO_ENTITIES = 6
DEMO_RELATIONS = 3


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


def _novel_ids(title: str) -> list[str]:
    """The ids carrying this title, oldest first — a re-import duplicates it."""
    return [
        str(row[0])
        for row in _rows(
            "SELECT id FROM novels WHERE title = :title ORDER BY created_at, id",
            {"title": title},
        )
    ]


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


def _chapter_body(novel_id: str, title: str) -> str:
    """One chapter's stored prose, by the novel and the chapter title."""
    [row] = _rows(
        "SELECT body FROM chapters WHERE novel_id = :novel_id AND title = :title",
        {"novel_id": novel_id, "title": title},
    )
    return str(row[0])


# ---------------------------------------------------------------------------
# Seeding and driving the shelf's dialogs
# ---------------------------------------------------------------------------


def _copy_demo(destination: Path, title: str) -> Path:
    """The demo archive on disk under a title no other test claims."""
    shutil.copytree(DEMO, destination)
    metadata_path = destination / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["title"] = title
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return destination


def _chapter_files(export: Path) -> list[Path]:
    """Every chapter file an export wrote, in archive order."""
    return sorted((export / "chapters").glob("*.md"))


def _chapter_file(export: Path, title: str) -> Path:
    """The exported chapter file carrying this title.

    The name is the server's — title slug behind the row's stored position —
    so the test asks the archive which file it is instead of pinning a
    numbering the seeding path would have to duplicate.
    """
    for path in _chapter_files(export):
        if f"\ntitle: {title}\n" in path.read_text(encoding="utf-8"):
            return path
    raise AssertionError(f"no exported chapter file carries the title {title!r}")


def _open_import(page: Page) -> Locator:
    """The shelf's import dialog, form side up."""
    page.goto(BASE + "/")
    page.get_by_role("button", name="Importieren").click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_label("Archivpfad")).to_be_visible()
    return dialog


def _expect_report(dialog: Locator, lines: list[str]) -> None:
    """The receipt's heading and one count line per class the flow meant."""
    expect(dialog.get_by_role("heading", name="Importbericht")).to_be_visible()
    for line in lines:
        expect(dialog.get_by_role("listitem").filter(has_text=line)).to_be_visible()


def _close_report(page: Page) -> None:
    """Dismiss the report; the shelf behind it shows what the import made."""
    page.get_by_role("dialog").get_by_role("button", name="Schließen").click()
    expect(page.get_by_role("dialog")).to_have_count(0)


def _seed_novel(page: Page, source: Path, title: str) -> None:
    """Import a folder as a new novel, read its receipt, and land on the shelf."""
    dialog = _open_import(page)
    dialog.get_by_label("Archivpfad").fill(str(source))
    dialog.get_by_role("button", name="Jetzt importieren").click()
    _expect_report(
        dialog,
        [
            f"{DEMO_CHAPTERS} Kapitel wurden hinzugefügt",
            f"{DEMO_ENTITIES} Wissenseinträge wurden hinzugefügt",
            f"{DEMO_RELATIONS} Beziehungen wurden angelegt",
        ],
    )
    assert_accessible(page)
    _close_report(page)
    expect(page.get_by_role("link", name=title)).to_be_visible()


def _import_zip(page: Page, archive: Path) -> Locator:
    """Import a downloaded archive file as a new novel; the report stays up."""
    dialog = _open_import(page)
    dialog.get_by_label("Archivdatei (.zip)").set_input_files(str(archive))
    expect(dialog.get_by_text(archive.name)).to_be_visible()
    dialog.get_by_role("button", name="Jetzt importieren").click()
    expect(dialog.get_by_role("heading", name="Importbericht")).to_be_visible()
    return dialog


def _import_merge(page: Page, source: Path, title: str) -> Locator:
    """Import a folder into the named novel; the report is the caller's to read."""
    dialog = _open_import(page)
    dialog.get_by_role("radio", name="In einen bestehenden Roman").check()
    dialog.get_by_label("Roman", exact=True).select_option(label=title)
    dialog.get_by_label("Archivpfad").fill(str(source))
    dialog.get_by_role("button", name="Jetzt importieren").click()
    return dialog


def _open_export(page: Page, title: str) -> Locator:
    """The export dialog of the named shelf row, its proposal prefilled."""
    page.goto(BASE + "/")
    row = page.get_by_role("listitem").filter(has_text=title)
    expect(row).to_be_visible()
    row.get_by_role("button", name="Exportieren").click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_label("Zielordner")).to_be_visible()
    return dialog


def _export_path(page: Page, title: str, target: Path) -> None:
    """Export into a folder on disk and dismiss the receipt."""
    dialog = _open_export(page, title)
    dialog.get_by_label("Zielordner").fill(str(target))
    dialog.get_by_role("button", name="Jetzt exportieren").click()
    expect(dialog.get_by_role("heading", name="Export abgeschlossen")).to_be_visible()
    expect(dialog).to_contain_text(f"Geschrieben nach {target}")
    assert_accessible(page)
    dialog.get_by_role("button", name="Schließen").click()
    expect(page.get_by_role("dialog")).to_have_count(0)


def _export_zip(page: Page, title: str, destination: Path) -> Path:
    """Export as a ZIP download and save it where the import can pick it up."""
    dialog = _open_export(page, title)
    dialog.get_by_role("radio", name="ZIP-Download").check()
    with page.expect_download() as caught:
        dialog.get_by_role("button", name="Jetzt exportieren").click()
    caught.value.save_as(str(destination))
    return destination


# ---------------------------------------------------------------------------
# The flows
# ---------------------------------------------------------------------------


def test_export_reimport_identical(page: Page, stack: Stack, tmp_path: Path) -> None:
    """A ZIP of a novel, imported as a new one, is the same novel."""
    title = "Die Waldprobe"
    _seed_novel(page, _copy_demo(tmp_path / "quelle", title), title)
    [source_id] = _novel_ids(title)

    archive = _export_zip(page, title, tmp_path / "die-waldprobe.zip")

    dialog = _import_zip(page, archive)
    # A new novel: every item is a birth, nothing refused, and the receipt
    # says exactly the counts the source archive carried.
    _expect_report(
        dialog,
        [
            f"{DEMO_CHAPTERS} Kapitel wurden hinzugefügt",
            f"{DEMO_ENTITIES} Wissenseinträge wurden hinzugefügt",
            f"{DEMO_RELATIONS} Beziehungen wurden angelegt",
        ],
    )
    assert_accessible(page)

    source_row, copy_id = _novel_ids(title)
    assert source_row == source_id
    assert copy_id != source_id

    # Titles, positions and bodies; names, types, bodies, aliases and tags;
    # both ends and the note of every edge — equal row for row.
    assert _chapters_of(copy_id) == _chapters_of(source_id)
    assert _entities_of(copy_id) == _entities_of(source_id)
    assert _relations_of(copy_id) == _relations_of(source_id)
    # And the source carries what was compared: a comparison of empty lists
    # would prove nothing.
    assert len(_chapters_of(source_id)) == DEMO_CHAPTERS
    assert len(_entities_of(source_id)) == DEMO_ENTITIES
    assert len(_relations_of(source_id)) == DEMO_RELATIONS


def test_merge_outside_work(page: Page, stack: Stack, tmp_path: Path) -> None:
    """A revised chapter, a bare chapter and a bare entry merge in, counted."""
    title = "Der Nachtrag"
    _seed_novel(page, _copy_demo(tmp_path / "quelle", title), title)
    [novel_id] = _novel_ids(title)

    export = tmp_path / "export"
    _export_path(page, title, export)

    # The outside-the-app gesture: one chapter revised in place, one bare
    # chapter added with no frontmatter and no index entry, one bare
    # knowledge file beside it.
    chapter = _chapter_file(export, CHAPTER_ONE)
    revised = chapter.read_text(encoding="utf-8")
    chapter.write_text(revised + "\nEin Satz aus der Schreibwerkstatt.\n", encoding="utf-8")
    (export / "chapters" / "nachtrag.md").write_text(
        "Der Nachtrag wurde am Küchentisch geschrieben.\n", encoding="utf-8"
    )
    (export / "kb" / "eintrag.md").write_text(
        "# Eintrag\n\nEin Eintrag ohne Frontmatter.\n", encoding="utf-8"
    )

    dialog = _import_merge(page, export, title)
    _expect_report(
        dialog,
        [
            "1 Kapitel wurde überarbeitet",
            "1 Kapitel war bereits aktuell",
            "1 Kapitel wurde hinzugefügt",
            "1 Wissenseintrag wurde hinzugefügt",
            "6 Wissenseinträge waren bereits aktuell",
            "3 Beziehungen bestanden bereits",
        ],
    )
    # Nothing was refused: all three changes are legal by the rules.
    expect(dialog).not_to_contain_text("wurde abgelehnt")
    assert_accessible(page)

    # The receipt's counts are the database's deltas, checked row by row.
    chapters = _chapters_of(novel_id)
    assert len(chapters) == DEMO_CHAPTERS + 1
    # The bare file has no title of its own: the format's rule is the
    # de-slugged file stem, which is exactly what it says it is.
    assert [row[0] for row in chapters] == [
        CHAPTER_ONE,
        "Die Grenze zwischen Welten",
        "nachtrag",
    ]
    revised_body = str(chapters[0][2])
    assert "Ein Satz aus der Schreibwerkstatt." in revised_body
    assert revised_body.startswith("Anna Müller kannte das Försterhaus")
    # The bare chapter appended after the stock's last position, body verbatim.
    assert chapters[2][1] == DEMO_CHAPTERS
    assert chapters[2][2] == "Der Nachtrag wurde am Küchentisch geschrieben.\n"

    entities = _entities_of(novel_id)
    assert len(entities) == DEMO_ENTITIES + 1
    # Same rule for a bare knowledge file: its name is the file stem, its
    # type the forgiving default, its body the whole file.
    added = next(row for row in entities if row[0] == "eintrag")
    assert added[1] == "generic"
    assert added[2] == "# Eintrag\n\nEin Eintrag ohne Frontmatter.\n"
    # Edges are create-only and these three were already there: no fourth.
    assert len(_relations_of(novel_id)) == DEMO_RELATIONS


def test_stale_import_is_refused(page: Page, stack: Stack, tmp_path: Path) -> None:
    """An archive that predates the prose it names is refused, prose intact."""
    title = "Die alte Fassung"
    _seed_novel(page, _copy_demo(tmp_path / "quelle", title), title)
    [novel_id] = _novel_ids(title)

    # The stock moves on through the editor, the way the user moves it.
    page.goto(BASE + "/")
    page.get_by_role("link", name=title).click()
    expect(page.get_by_role("heading", name=title)).to_be_visible()
    page.get_by_role("button", name=CHAPTER_ONE).click()
    editor = page.locator(".ProseMirror")
    expect(editor).to_be_visible()
    editor.click()
    page.keyboard.type(" Der Förster sah ihr nach.")
    expect(page.locator("span[role='status']").filter(has_text="Gespeichert")).to_be_visible()
    assert_accessible(page)

    stock_body = _chapter_body(novel_id, CHAPTER_ONE)
    assert "Der Förster sah ihr nach." in stock_body

    export = tmp_path / "export"
    _export_path(page, title, export)

    # The crafted archive: older than the row it would overwrite, and
    # different prose — the exact shape Review Focus 1 names.
    chapter = _chapter_file(export, CHAPTER_ONE)
    archive_path = f"chapters/{chapter.name}"
    crafted = chapter.read_text(encoding="utf-8")
    crafted = re.sub(
        r"^updated:.*$",
        "updated: 2000-01-01T00:00:00+00:00",
        crafted,
        count=1,
        flags=re.MULTILINE,
    )
    chapter.write_text(crafted + "\nDiese Zeile darf nicht ankommen.\n", encoding="utf-8")

    dialog = _import_merge(page, export, title)
    expect(dialog.get_by_role("heading", name="Importbericht")).to_be_visible()
    # The refusal is named where the retry is: the file, and why.
    expect(dialog).to_contain_text("Ein Eintrag wurde abgelehnt:")
    refused = dialog.get_by_role("listitem").filter(has_text="stale revision")
    expect(refused).to_be_visible()
    expect(refused).to_contain_text(archive_path)
    expect(
        dialog.get_by_role("listitem").filter(has_text="1 Kapitel war bereits aktuell")
    ).to_be_visible()
    assert_accessible(page)

    # And the prose is exactly what it was before the import ran.
    assert _chapter_body(novel_id, CHAPTER_ONE) == stock_body
    assert "Diese Zeile darf nicht ankommen." not in stock_body


def test_non_empty_export_target_refused(page: Page, stack: Stack, tmp_path: Path) -> None:
    """A second export into the same folder is refused by name, backup intact."""
    title = "Die Sicherung"
    _seed_novel(page, _copy_demo(tmp_path / "quelle", title), title)

    backup = tmp_path / "sicherung"
    _export_path(page, title, backup)
    assert len(_chapter_files(backup)) == DEMO_CHAPTERS
    assert (backup / "metadata.json").is_file()

    # The same folder again: the refusal names the folder, in the dialog,
    # where the retry is one edit away.
    dialog = _open_export(page, title)
    dialog.get_by_label("Zielordner").fill(str(backup))
    dialog.get_by_role("button", name="Jetzt exportieren").click()
    refusal = dialog.get_by_role("alert")
    expect(refusal).to_contain_text("existiert und ist nicht leer")
    expect(refusal).to_contain_text(str(backup))
    assert_accessible(page)

    # Nothing was written over: the first backup still carries the archive.
    assert (backup / "metadata.json").is_file()
    assert len(list((backup / "kb").glob("*.md"))) == DEMO_ENTITIES
