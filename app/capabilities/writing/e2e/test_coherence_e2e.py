"""The coherence flow, end to end — §8.6's done gate over one writer's day.

One flow over the real browser, the real API and the real database, the only
fake the LLM provider. The demo novel arrives through the shelf's import door;
the workbench opens; the Wissen dock shows an entity carrying its relation; and
two entries for the same thing fold into one — the merge dialog swept by the
accessibility floor while it stands (#369's missing axe, on the surface the
merge really runs in), the outcome heard, the survivor alone in the database,
the shelf hero naming the book under the same floor. The settings chain is
driven through its own doors: a fake provider profile on the provider page, a
novel-scoped override of ``writing.continuation`` on the prompts page — and the
continuation in the editor then answers for both, its audited row carrying the
override's marker sentence and the chosen profile's id and model. The palette
is the keyboard's way through the same day: ⌘K jumps to an entity (the dock
opens on ``?entity=``) and runs ``new-chapter`` while the editor still holds an
unsaved body — the flush gate carries the line into its own row before the
address moves, and the wire's order is the proof the gate was the mechanism:
the command's POST first, the gate's flush PUT second. The new surfaces answer
in the language the instance chose: hub, prompts page and palette re-render in
English and back to German. Every page the flow stands on is swept by axe, and
the pages it visited are measured again at 360, 768, 1024 and 1280 — the
document fits, and where the editor is on screen, the prose keeps its 320 px
floor.

Every assertion on a prompt, a profile or a chapter reads the rows the audit
and the API wrote — the stack's own database, never a spy on the request.
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
from app.kernel.testing.viewport import assert_page_fits

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.kernel.testing.stack import Stack

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(480)]
# One flow carries the whole gate — the writer's day and the four-width sweep
# in one test — so its budget is the viewport sweep's own, scaled to match.

BASE = "http://127.0.0.1:3100"
DATABASE = "narrare_v2_e2e"  # the stack's own database (e2e/conftest.py)

APP = Path(__file__).resolve().parents[3]
DEMO = APP / "kernel" / "interchange" / "demos" / "im-stillen-wald"
"""The bundled German demo: two chapters, six entities, three relations."""

NOVEL = "Der rote Faden"
CHAPTER_ONE = "Das Flüstern im Wald"
RELATION_CARRIER = "Der Waldgeist"  # the demo's relations name Johann twice over
MERGED_AWAY = "Das Dorf"
SURVIVOR = "Das Försterhaus"
UNSAVED_LINE = "Dieser Satz muss den Kapitelwechsel überleben."

DEMO_CHAPTERS = 2
DEMO_ENTITIES = 6
DEMO_RELATIONS = 3

PROSE = ".ProseMirror"
EDITOR_SECTION = "section.min-w-0"
RAIL = 'aside[aria-label="Kapitel"]'
DOCK = 'aside[aria-label="Wissen"]'
WIDTHS = [360, 768, 1024, 1280]

CONTINUATION = "writing.continuation"
PROFILE_NAME = "Die feste Stimme"
PROFILE_MODEL = "fest-eins"

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
    """The id of the one novel carrying this title — the flow owns it."""
    [row] = _rows("SELECT id FROM novels WHERE title = :title", {"title": title})
    return str(row[0])


def _profile_id(name: str) -> str:
    """The id of the profile the form created, straight from the table."""
    [row] = _rows("SELECT id FROM provider_profiles WHERE name = :name", {"name": name})
    return str(row[0])


def _entity_names(novel_id: str) -> list[str]:
    """The novel's entity names — the merge's before and after."""
    return [
        str(row[0])
        for row in _rows(
            "SELECT name FROM entities WHERE novel_id = :novel_id ORDER BY name",
            {"novel_id": novel_id},
        )
    ]


def _relation_count(novel_id: str) -> int:
    """How many edges the novel's entries carry."""
    [row] = _rows(
        "SELECT count(*) FROM entity_relations edge"
        " JOIN entities source ON source.id = edge.from_entity_id"
        " WHERE source.novel_id = :novel_id",
        {"novel_id": novel_id},
    )
    count = row[0]
    assert isinstance(count, int)
    return count


def _entity_id(novel_id: str, name: str) -> str:
    """One entity's id, by its exact name — the deep link's parameter."""
    [row] = _rows(
        "SELECT id FROM entities WHERE novel_id = :novel_id AND name = :name",
        {"novel_id": novel_id, "name": name},
    )
    return str(row[0])


def _chapter_id(novel_id: str, title: str) -> str:
    """One chapter's id, by its exact title — the selection's address."""
    [row] = _rows(
        "SELECT id FROM chapters WHERE novel_id = :novel_id AND title = :title",
        {"novel_id": novel_id, "title": title},
    )
    return str(row[0])


def _latest_chapter_position(novel_id: str) -> int:
    """The reading order's last position — where the command's chapter lands."""
    [row] = _rows(
        "SELECT max(position) FROM chapters WHERE novel_id = :novel_id",
        {"novel_id": novel_id},
    )
    position = row[0]
    assert isinstance(position, int)
    return position


def _chapter_body(novel_id: str, title: str) -> str:
    """One chapter's stored prose, by the novel and the chapter title."""
    [row] = _rows(
        "SELECT body FROM chapters WHERE novel_id = :novel_id AND title = :title",
        {"novel_id": novel_id, "title": title},
    )
    body = row[0]
    return "" if body is None else str(body)


def _latest_continuation(title: str) -> tuple[str, str, str, str]:
    """The novel's latest continuation audit row: what the call really was.

    The audit is the only writer of llm_calls, so status, prompt text,
    profile and model read here are what the request carried.
    """
    [row] = _rows(
        "SELECT status, prompt_text, c.profile_id, c.model FROM llm_calls c"
        " JOIN novels n ON c.novel_id = n.id"
        " WHERE n.title = :title AND c.task_key = 'writing.continuation'"
        " ORDER BY c.created_at DESC LIMIT 1",
        {"title": title},
    )
    return str(row[0]), str(row[1]), str(row[2]), str(row[3])


# ---------------------------------------------------------------------------
# Driving the shelf, the dock and the palette
# ---------------------------------------------------------------------------


def _copy_demo(destination: Path, title: str) -> Path:
    """The demo archive on disk under the title the flow owns."""
    shutil.copytree(DEMO, destination)
    metadata_path = destination / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["title"] = title
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return destination


def _import_demo(page: Page, source: Path) -> None:
    """Import the archive as a new novel through the shelf, read the receipt.

    The receipt stays up for the floor: a dialog the flow stands in is a page
    the flow visited, and #369's lesson is that a flow's end state is swept,
    not stepped over.
    """
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
    assert_accessible(page)
    dialog.get_by_role("button", name="Schließen").click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(page.get_by_role("link", name=NOVEL)).to_be_visible()


def _row_named(entities: Locator, name: str) -> Locator:
    """The entity list's cell for one exact name."""
    return entities.get_by_role("gridcell", name=name, exact=True)


def _open_palette(page: Page, title: str = "Springen zu") -> Locator:
    """⌘K opens the palette over whatever the page holds; the dialog answers."""
    page.keyboard.press("Control+k")
    palette = page.get_by_role("dialog", name=title)
    expect(palette).to_be_visible()
    return palette


def _palette_group(palette: Locator, label: str) -> Locator:
    """One labelled group — the palette's structure is part of the pin."""
    return palette.get_by_role("group", name=label)


def _jump_to_entity(page: Page, name: str) -> None:
    """⌘K, the entity's words, its row: the jump is the whole gesture."""
    palette = _open_palette(page)
    palette.get_by_role("textbox").fill(name)
    _palette_group(palette, "Entitäten").get_by_role("button", name=name).click()


def _run_new_chapter(page: Page) -> None:
    """⌘K, the command's words, its row — the gesture the flush gate answers."""
    palette = _open_palette(page)
    palette.get_by_role("textbox").fill("Neues Kap")
    _palette_group(palette, "Befehle").get_by_role("button", name="Neues Kapitel").click()


def _create_fake_profile(page: Page) -> None:
    """The one provider the day needs, through the form; it is the default.

    A fresh stack holds no profiles, so the first fake becomes the default on
    its own — and the continuation later must name exactly this row.
    """
    page.get_by_label("Name", exact=True).fill(PROFILE_NAME)
    page.get_by_label("Art").select_option(label="Fake (deterministisch, ohne Netzwerk)")
    page.get_by_label("Modell").fill(PROFILE_MODEL)
    page.get_by_role("button", name="Profil hinzufügen").click()
    row = page.get_by_role("listitem").filter(has_text=PROFILE_NAME)
    expect(row).to_be_visible()
    expect(row.get_by_text("Standard", exact=True)).to_have_count(1)


def _save_novel_override(page: Page) -> None:
    """The prompts page's novel tier: the override saved, the card in force."""
    page.get_by_label("Roman").select_option(label=NOVEL)
    card = page.get_by_role("listitem").filter(has_text=CONTINUATION)
    card.get_by_role("button", name="Überschreibung für diesen Roman anlegen").click()
    card.get_by_label("Vorlage").fill(OVERRIDE_TEMPLATE)
    card.get_by_role("button", name="Speichern").click()
    expect(card.get_by_label("Vorlage")).to_have_count(0)
    expect(card.get_by_text("Eine Überschreibung dieses Romans ist in Kraft.")).to_be_visible()


def _sweep_face(page: Page, url: str, witness: Callable[[], None], *, prose: bool) -> None:
    """One face at the current width: the witness proves arrival, the floor measures.

    A face that measures prose waits for the editor itself. Its own witness can
    arrive while the book is still loading on the dock route — the workspace
    renders the dock and the toolbar independently of the novel's row — and a
    measurement taken then reads a page that has no editor to measure.
    """
    page.goto(url)
    witness()
    if prose:
        expect(page.locator(PROSE)).to_be_visible()
    assert_page_fits(page, prose_selector=PROSE if prose else None)


# ---------------------------------------------------------------------------
# The flow
# ---------------------------------------------------------------------------


def test_the_writer_s_day_holds_together_end_to_end(
    page: Page, stack: Stack, tmp_path: Path
) -> None:
    """Setup to the narrow window: every surface the day touches, pinned in order."""
    page.set_viewport_size({"width": 1280, "height": 720})

    # --- Setup, the demo novel through the shelf's import door. The receipt
    # named the counts; the rows are what the rest of the flow walks, so the
    # merge's arithmetic below stands on checked ground.
    _import_demo(page, _copy_demo(tmp_path / "quelle", NOVEL))
    novel_id = _novel_id(NOVEL)
    assert sorted(_entity_names(novel_id)) == sorted(
        [
            "Anna Müller",
            "Das Dorf",
            "Das Försterhaus",
            "Der Stille Wald",
            "Der Waldgeist",
            "Johann Bauer",
        ]
    )
    assert _relation_count(novel_id) == DEMO_RELATIONS
    chapter_one_id = _chapter_id(novel_id, CHAPTER_ONE)

    # --- The workspace: the rail beside the editor, the selection addressed.
    page.get_by_role("link", name=NOVEL).click()
    expect(page.get_by_role("heading", name=NOVEL)).to_be_visible()
    expect(page.locator(RAIL)).to_be_visible()
    assert_accessible(page)
    page.get_by_role("button", name=CHAPTER_ONE).click()
    expect(page).to_have_url(re.compile(f"chapter={chapter_one_id}"))

    # --- The dock: an entity with a relation. The card names its edge, both
    # ends — the day's knowledge is not a list of names but a web.
    page.get_by_role("button", name="Wissen", exact=True).click()
    dock = page.get_by_role("complementary", name="Wissen")
    expect(dock).to_be_visible()
    entities = dock.get_by_role("region", name="Entitäten")
    expect(_row_named(entities, RELATION_CARRIER)).to_be_visible()
    _row_named(entities, RELATION_CARRIER).click()
    detail = dock.get_by_role("region", name=RELATION_CARRIER)
    expect(detail).to_be_visible()
    expect(detail).to_contain_text("→ Johann Bauer")
    assert_accessible(page)

    # --- The merge: two entries for the same thing fold into one. The floor
    # stands on the open dialog — the hero of the merge, the surface #369
    # found unswept — then the outcome is heard, the list reflects it, and
    # the database holds the survivor's rows alone.
    _row_named(entities, MERGED_AWAY).click()
    detail = dock.get_by_role("region", name=MERGED_AWAY)
    expect(detail).to_be_visible()
    detail.get_by_role("button", name="Zusammenführen").click()
    dialog = page.get_by_role("dialog")
    picker = dialog.get_by_label("Zusammenführen mit")
    expect(picker).to_be_visible()
    assert_accessible(page)
    picker.fill("Försterhaus")
    picker.press("ArrowDown")
    picker.press("Enter")
    expect(picker).to_have_value(SURVIVOR)
    dialog.get_by_role("button", name="Jetzt zusammenführen").click()
    expect(dialog).not_to_be_visible()
    expect(page.locator("[data-live-announcer]")).to_contain_text(
        f"{MERGED_AWAY} wurde mit {SURVIVOR} zusammengeführt"
    )
    expect(_row_named(entities, MERGED_AWAY)).to_have_count(0)
    expect(_row_named(entities, SURVIVOR)).to_be_visible()
    assert len(_entity_names(novel_id)) == DEMO_ENTITIES - 1
    assert MERGED_AWAY not in _entity_names(novel_id)
    # The merged-away entry carried no edge of its own: the web is untouched.
    assert _relation_count(novel_id) == DEMO_RELATIONS
    assert_accessible(page)

    # --- The shelf hero after a merge, under the floor: a merge is a write,
    # the hero's truth is the novel's touched time, and #369's gap was
    # exactly this state standing unswept at the end of a merge flow.
    page.get_by_role("link", name="Alle Romane").click()
    expect(page).to_have_url(f"{BASE}/")
    hero = page.get_by_role("region", name="Mach weiter")
    expect(hero).to_contain_text(NOVEL)
    assert_accessible(page)

    # --- The settings chain, through its own doors: the hub, then the
    # provider page, then the prompts page.
    page.get_by_role("link", name="Einstellungen").click()
    expect(page).to_have_url(f"{BASE}/settings")
    expect(page.get_by_role("heading", name="Einstellungen")).to_be_visible()
    assert_accessible(page)
    page.get_by_role("region", name="Anbieter").get_by_role("link", name="Anbieter").click()
    expect(page.get_by_role("heading", name="Aufgaben")).to_be_visible()
    _create_fake_profile(page)
    assert_accessible(page)
    profile_id = _profile_id(PROFILE_NAME)

    # The prompts door is the frame's own cluster nav, which every page of
    # the settings area carries — the hub is not the only way through.
    page.get_by_role("navigation", name="Einstellungen").get_by_role("link", name="Prompts").click()
    expect(page.get_by_role("heading", name="Prompts")).to_be_visible()
    _save_novel_override(page)
    assert_accessible(page)

    # --- The continuation, and the audit that answers for the chain: the
    # marker rode the override's template, and the call is the profile's own
    # row — its id and its free-text model, not the bundled default's.
    page.goto(f"{BASE}/novels/{novel_id}")
    expect(page.get_by_role("heading", name=NOVEL)).to_be_visible()
    page.get_by_role("button", name=CHAPTER_ONE).click()
    expect(page.locator(PROSE)).to_be_visible()
    page.get_by_role("button", name="Weiterschreiben").click()
    ghost = page.locator(f"{PROSE} .ghost")
    expect(ghost).to_contain_text("über die Straße.")
    page.keyboard.press("Tab")
    expect(page.locator(f"{PROSE} .ghost")).to_have_count(0)
    expect(page.locator("span[role='status']").filter(has_text="Gespeichert")).to_be_visible()
    assert_accessible(page)
    status, prompt_text, used_profile, used_model = _latest_continuation(NOVEL)
    assert status == "ok"
    assert MARKER in prompt_text
    assert used_profile == profile_id
    assert used_model == PROFILE_MODEL

    # --- ⌘K jumps to an entity: the palette steps aside, the dock opens on
    # the named card, and the address says so — the selection's URL is the
    # deep link the rail writes too.
    waldgeist_id = _entity_id(novel_id, RELATION_CARRIER)
    _jump_to_entity(page, RELATION_CARRIER)
    expect(page).to_have_url(re.compile(f"entity={waldgeist_id}"))
    expect(page.locator(DOCK)).to_be_visible()
    expect(page.locator(DOCK).get_by_role("region", name=RELATION_CARRIER)).to_be_visible()
    assert_accessible(page)

    # --- ⌘K runs new-chapter while the editor holds an unsaved body. The
    # debounce is still counting — the save indicator quiet, nothing on the
    # wire — so the PUT the gate awaits can only be the flush. The wire's
    # order is the proof the gate was the mechanism: the command's POST
    # creates the chapter first, and the gate's flush PUT follows it — a
    # debounce that had fired on its own clock would read PUT before POST.
    editor = page.locator(PROSE)
    editor.click()
    page.keyboard.type(UNSAVED_LINE)
    expect(page.locator(EDITOR_SECTION).get_by_role("status")).to_have_count(0)
    wire: list[str] = []
    page.on(
        "request",
        lambda request: (
            wire.append(f"{request.method} {request.url}")
            if (
                request.method == "POST" and request.url.endswith("/chapters")
            )  # the command's create
            or ("/api/writing/chapters/" in request.url and request.method == "PUT")
            else None
        ),
    )
    with page.expect_response(
        lambda response: (
            "/api/writing/chapters/" in response.url and response.request.method == "PUT"
        )
    ) as flushed:
        _run_new_chapter(page)
    assert flushed.value.ok
    assert [each.split(" ", 1)[0] for each in wire] == ["POST", "PUT"], (
        f"the flush did not ride the command's navigation: {wire}"
    )
    assert chapter_one_id in wire[1]
    # The rail gained the chapter, the address moved to it, the editor shows
    # the empty chapter the command made — and the row holds the line.
    new_position = _latest_chapter_position(novel_id)
    expect(
        page.get_by_role("button", name=f"Kapitel {new_position + 1}", exact=True)
    ).to_be_visible()
    [new_chapter_id] = [
        str(row[0])
        for row in _rows(
            "SELECT id FROM chapters WHERE novel_id = :novel_id AND position = :position",
            {"novel_id": novel_id, "position": new_position},
        )
    ]
    expect(page).to_have_url(re.compile(f"chapter={new_chapter_id}"))
    expect(editor).to_have_text("")
    assert UNSAVED_LINE in _chapter_body(novel_id, CHAPTER_ONE)
    assert_accessible(page)

    # --- The language switch, on each new surface: the hub, the prompts page
    # and the palette answer in the chosen language, not the browser's.
    page.goto(f"{BASE}/settings")
    expect(page.get_by_role("heading", name="Einstellungen")).to_be_visible()
    assert_accessible(page)
    switcher = page.get_by_role("banner").get_by_role("combobox")
    switcher.select_option("en")
    expect(page.get_by_role("heading", name="Settings")).to_be_visible()
    for region in ("Providers", "Prompts", "Language"):
        expect(page.get_by_role("region", name=region)).to_be_visible()
    assert_accessible(page)
    # The palette is a surface of its own: its words re-render with the page.
    palette = _open_palette(page, title="Jump to")
    expect(palette.get_by_role("textbox")).to_have_attribute(
        "placeholder", "Search chapters, entities, pages and commands"
    )
    expect(_palette_group(palette, "Novels").get_by_role("button", name=NOVEL)).to_be_visible()
    expect(_palette_group(palette, "Docks & pages")).to_be_visible()
    assert_accessible(page)
    page.keyboard.press("Escape")

    page.goto(f"{BASE}/settings/prompts")
    expect(page.get_by_role("heading", name="Prompts")).to_be_visible()
    page.get_by_label("Novel").select_option(label=NOVEL)
    card = page.get_by_role("listitem").filter(has_text=CONTINUATION)
    expect(card.get_by_text("An override of this novel is in force.")).to_be_visible()
    assert_accessible(page)
    # Back to German, on the page the switch left: the stored choice drives
    # every surface, and the flow hands the sweep a German app again.
    page.get_by_role("banner").get_by_role("combobox").select_option("de")
    expect(page.get_by_label("Roman")).to_be_visible()
    expect(page.get_by_text("Eine Überschreibung dieses Romans ist in Kraft.")).to_be_visible()
    assert_accessible(page)

    # --- The widths, over the pages the day visited. Each face proves its
    # arrival, then answers the mechanical floor: the document fits, and
    # where the editor is on screen the prose keeps its 320 px content box.
    novel_url = f"{BASE}/novels/{novel_id}"
    dock_url = f"{novel_url}/wissen?entity={waldgeist_id}"

    def workbench_open() -> None:
        """Both halves of the desktop face: the prose and the rail beside it."""
        expect(page.locator(PROSE)).to_be_visible()
        expect(page.locator(RAIL)).to_be_visible()

    faces: list[tuple[str, str, Callable[[], None], bool]] = [
        (
            "shelf",
            f"{BASE}/",
            lambda: expect(page.get_by_role("link", name=NOVEL)).to_be_visible(),
            False,
        ),
        ("workspace, rail open", novel_url, workbench_open, True),
        (
            "workspace, dock open",
            dock_url,
            lambda: expect(page.locator(DOCK)).to_be_visible(),
            True,
        ),
        (
            "settings hub",
            f"{BASE}/settings",
            lambda: expect(page.get_by_role("heading", name="Einstellungen")).to_be_visible(),
            False,
        ),
        (
            "provider page",
            f"{BASE}/settings/provider",
            lambda: expect(page.get_by_role("heading", name="Aufgaben")).to_be_visible(),
            False,
        ),
        (
            "prompts page",
            f"{BASE}/settings/prompts",
            lambda: expect(page.get_by_role("heading", name="Prompts")).to_be_visible(),
            False,
        ),
    ]
    for width in WIDTHS:
        page.set_viewport_size({"width": width, "height": 720})
        for _label, url, witness, prose in faces:
            _sweep_face(page, url, witness, prose=prose)
