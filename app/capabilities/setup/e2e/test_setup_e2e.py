"""A fresh database must open on setup and end on the novel it created.

Three first runs over the real stack: the blank path creates one empty
novel and opens its workbench; the demo path loads a bundled archive's
chapters, entities and relations into the novel it names; and the blank
path again, checked against the database, proves it still writes nothing
but the novel. Every run starts on an uninstalled instance
(``e2e/conftest.py`` empties the database before each test).
"""

import asyncio
import re
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
DATABASE = "narrare_v2_setup_e2e"  # the stack's own database (e2e/conftest.py)

DEMO_TITLE = "Im Stillen Wald"
"""The demo's own title, from the archive's metadata — never the typed one."""

DEMO_CHAPTERS = ["Das Flüstern im Wald", "Die Grenze zwischen Welten"]
DEMO_ENTITIES = ["Anna Müller", "Johann Bauer", "Der Waldgeist"]
DEMO_ENTITY_COUNT = 6
DEMO_RELATION_COUNT = 3


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


def test_a_fresh_database_opens_on_setup(page: Page, stack: Stack) -> None:
    page.goto(BASE + "/")

    # The root sends an uninstalled instance to setup instead of showing an empty list.
    expect(page).to_have_url(re.compile(r"/setup$"))
    expect(page.get_by_role("heading", name="Willkommen bei Narrare")).to_be_visible()

    page.get_by_label("Titel des Romans").fill("Der Nebel")
    page.get_by_role("button", name="Los geht's").click()

    expect(page.get_by_role("heading", name="Der Nebel")).to_be_visible()
    page.reload()
    expect(page.get_by_role("heading", name="Der Nebel")).to_be_visible()

    # Setup is closed: the root now lists the novel instead of redirecting.
    page.goto(BASE + "/")
    expect(page.get_by_role("link", name="Der Nebel")).to_be_visible()

    assert_accessible(page)


def test_setup_with_a_demo_loads_its_content(page: Page, stack: Stack) -> None:
    """First run from the bundled demo: its novel, chapters and knowledge."""
    page.goto(BASE + "/")
    expect(page).to_have_url(re.compile(r"/setup$"))
    assert_accessible(page)

    # The demo brings its own title, so the field is parked — visibly
    # disabled, never silently dropped.
    page.get_by_role("radio", name=DEMO_TITLE).check()
    expect(page.get_by_label("Titel des Romans")).to_be_disabled()
    page.get_by_role("button", name="Los geht's").click()

    # Straight into the demo's own novel, its chapters on the rail.
    expect(page.get_by_role("heading", name=DEMO_TITLE)).to_be_visible()
    rail = page.get_by_role("complementary", name="Kapitel")
    for chapter in DEMO_CHAPTERS:
        expect(rail.get_by_role("button", name=chapter)).to_be_visible()
    assert_accessible(page)

    # The knowledge the archive carried is in the dock, and the archive's
    # own relation reads on the entity card.
    page.get_by_role("button", name="Wissen", exact=True).click()
    dock = page.get_by_role("complementary", name="Wissen")
    entities = dock.get_by_role("region", name="Entitäten")
    for name in DEMO_ENTITIES:
        expect(entities.get_by_role("gridcell", name=name, exact=True)).to_be_visible()
    entities.get_by_role("gridcell", name="Anna Müller", exact=True).click()
    detail = dock.get_by_role("region", name="Anna Müller")
    expect(detail).to_contain_text("→ Johann Bauer · Verbunden mit")
    assert_accessible(page)

    # The screen and the database agree on what first run created.
    assert _rows("SELECT title, author, genre, language FROM novels") == [
        (DEMO_TITLE, "Narrare Demo", "Literary", "de")
    ]
    assert _rows("SELECT title, position FROM chapters ORDER BY position") == [
        (DEMO_CHAPTERS[0], 0),
        (DEMO_CHAPTERS[1], 1),
    ]
    assert len(_rows("SELECT id FROM entities")) == DEMO_ENTITY_COUNT
    assert len(_rows("SELECT id FROM entity_relations")) == DEMO_RELATION_COUNT


def test_blank_path_unchanged(page: Page, stack: Stack) -> None:
    """First run without a demo: one empty novel, and the workbench opens."""
    page.goto(BASE + "/")
    expect(page).to_have_url(re.compile(r"/setup$"))
    assert_accessible(page)

    # Blank is the default; the title is the only input the path takes.
    expect(page.get_by_role("radio", name="Leer beginnen")).to_be_checked()
    page.get_by_label("Titel des Romans").fill("Die Leere")
    page.get_by_role("button", name="Los geht's").click()

    expect(page.get_by_role("heading", name="Die Leere")).to_be_visible()
    rail = page.get_by_role("complementary", name="Kapitel")
    expect(rail.get_by_text("Noch kein Kapitel")).to_be_visible()
    # No chapter, so no editor: the empty rail's copy is the page's truth.
    expect(page.locator(".ProseMirror")).to_have_count(0)
    assert_accessible(page)

    # One novel, and nothing else: no chapters, no knowledge, no metadata
    # the demo path would have brought.
    assert _rows("SELECT title, author, genre, blurb, language FROM novels") == [
        ("Die Leere", None, None, None, None)
    ]
    assert _rows("SELECT id FROM chapters") == []
    assert _rows("SELECT id FROM entities") == []
    assert _rows("SELECT id FROM entity_relations") == []

    # Setup is closed: the root lists the novel instead of redirecting.
    page.goto(BASE + "/")
    expect(page.get_by_role("link", name="Die Leere")).to_be_visible()
    assert_accessible(page)
