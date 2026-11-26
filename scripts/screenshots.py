"""Capture the README's images from the real app.

Run: ``uv run python -m scripts.screenshots`` (needs Docker's Postgres — ``just
dev-services`` — and the browser once: ``uv run playwright install chromium``).
Re-run when a surface below changes: a stale image claims a UI that no longer
exists. The canonical set and its index come from ``scripts.screenshot_manifest``:
the names here are the manifest's, so the PNG directory and
``docs/screenshots/README.md`` cannot drift apart.

The call captures into a temporary sibling directory and replaces the target
set — removals included — only after every frame landed. A failed capture
leaves the previous masters and the previous index untouched.

Nothing here is mocked except the model at its boundary, the seam every E2E
suite uses: the chat stand-in answers with the prose this file chooses, because
the kernel's fake answers every prompt with one German sentence. The README
says so, in one line under the gallery.

The demo novel is the bundled *Dead Signal* archive, loaded through the setup
door a first run takes. The notes are this file's own text, uploaded the way a
writer uploads research. The one planted continuity error (a facility
renumbered between chapters) is an edit a writer could make, and the check that
finds it is the real one.

Determinism is part of the recipe: the viewport, locale, timezone, reduced
motion, a fixed browser clock, the reader's stored theme and animation-free
screenshots are pinned here, and every seed is API-driven with stable order.
The graph's force layout sorts by entity id, so its frame runs on a novel with
exactly one entity; the multi-entity faces live on the dossiers page and the
interview, where creation order — not the id sort — is the truth.
"""

import argparse
import os
import shutil
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import httpx
from playwright.sync_api import expect, sync_playwright

from app.kernel.testing.jobs import wait_for_job
from app.kernel.testing.stack import API_PORT, WEB_PORT, run_stack, stop_shared_web
from app.kernel.testing.vendor import chat_vendor
from scripts.screenshot_manifest import SHOTS, render_index, validate_shots

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Literal

    from playwright.sync_api import Page

    from app.kernel.testing.vendor import ChatVendor

API = f"http://127.0.0.1:{API_PORT}"
WEB = f"http://127.0.0.1:{WEB_PORT}"
"""The ports ``run_stack`` binds — it reads ``NARRE_E2E_API_PORT`` and
``NARRE_E2E_WEB_PORT``, so a second stack on this machine needs no code edit."""
DATABASE = "narrare_v2_screenshots"
DEMO = "dead-signal"
"""The bundled English demo: seven chapters, knowledge entries and relations."""

TRANSCRIPT_TIME = "12:00 PM"
"""The one clock label the frames show. The transcript's stamp is the server
turn's, so it is pinned at the render seam; the zen pomodoro is paused before
it mounts. Every other time is relative to this run's own fresh seed, so it
reads the same on every capture."""


CONTINUATION = " Somewhere behind the console a relay clicked, once."
"""The ghost the editor offers at the caret: the image's whole claim."""

NOTES: dict[str, str] = {
    "Horizon Station — cast and places": (
        "Dr. Maya Chen is the station's chief engineer, twelve light-years from Earth. "
        "ARIA is the station's intelligence: Maya treats her as a colleague, not a tool. "
        "Director Kavic arrives from the corporation with an answer he does not give. "
        "Research Facility 7 is the Nevada site where the first device was built.\n"
    ),
    "Timeline — before the signal": (
        "Three years before the signal, Maya's sister died at Research Facility 7; the "
        "corporation called it an accident. Six months before the signal, the device was "
        "moved off the site and studied in secret. The signal arrives on Day 1.\n"
    ),
}
"""The writer's notes: plain text, chunked and embedded by the real ingestion path."""

SHELF: tuple[tuple[str, str, str], ...] = (
    (
        "The Salt Road",
        "Literary",
        "A lighthouse keeper keeps a ledger of every ship that never came back.",
    ),
    (
        "Winterhaus",
        "Mystery",
        "Six guests, one valley, and a snowed-in road that keeps them there.",
    ),
)
"""Two more books on the shelf, so the shelf reads as a shelf and not a test row."""

INTERVIEW_NAME = "Resonanz-Transponder LC-89"
"""The proposal the interview builds: the frame's real, non-mocked subject."""

CONTINUATION_BODY = (
    "Maya laid her hand on the console and waited for the sign nobody had agreed on. "
    "Outside, the night was still.\n\n"
    "The frost crept through the seams. Somewhere a transformer hummed."
)
"""A short scene, so the continuation and its accept pill stay above the prompt bar."""


class WorkspaceUnavailableError(RuntimeError):
    """The explorer never rendered; a named failure beats a 30-second wait."""


def _api() -> httpx.Client:
    """A short-timeout client against the stack's own API."""
    return httpx.Client(base_url=API, timeout=30.0)


def _shot(page: Page, out: Path, name: str) -> Path:
    """Write one 1600x1000 master with motion, caret and hover pinned.

    The pointer parks in a dead corner: a surviving hover from the click that
    opened the page would otherwise paint a tooltip into one run and not the
    next. Fonts settle before the frame, so a late swap cannot change the
    text's antialiasing between captures.
    """
    page.mouse.move(1590, 990)
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(300)
    path = out / f"{name}.png"
    page.screenshot(path=str(path), animations="disabled", caret="hide")
    print(f"wrote {path}")
    return path


def _set_theme(page: Page, theme: Literal["light", "dark"]) -> None:
    """Store the reader's theme through the API, then reload onto it.

    The write is the settings surface's own endpoint; the reload is how the
    shell adopts a stored choice at boot, exactly as a reader's next visit
    does. ``light`` is explicit, so a frame never depends on the OS.
    """
    with _api() as api:
        api.patch("/api/settings/theme", json={"theme": theme}).raise_for_status()
    page.reload()
    expect(page.locator("html")).to_have_attribute("data-theme", theme)


def _open_workspace(page: Page, novel_id: str) -> None:
    """Open the workspace and wait for its explorer, never a stale label."""
    page.goto(f"{WEB}/novels/{novel_id}")
    explorer = page.get_by_test_id("explorer-tree").or_(page.get_by_test_id("explorer-empty-book"))
    try:
        expect(explorer).to_be_visible(timeout=5000)
    except AssertionError as error:
        raise WorkspaceUnavailableError(
            f"the workspace explorer did not render for novel {novel_id}"
        ) from error


def _pause_clock(page: Page) -> None:
    """Freeze timers just before a surface with a running counter mounts."""
    now = datetime.fromisoformat(page.evaluate("new Date().toISOString()").replace("Z", "+00:00"))
    page.clock.pause_at(now + timedelta(milliseconds=100))


def _resume_clock(page: Page) -> None:
    page.clock.resume()


def _seed(api: httpx.Client) -> tuple[str, list[dict[str, object]]]:
    """Set the language, load the demo, upload the notes, return ids.

    Returns the novel id and its chapters in position order.
    """
    # A demo carries its own title: the archive's metadata wins over the field.
    setup = api.post("/api/setup", json={"novel_title": "Dead Signal", "demo": DEMO})
    setup.raise_for_status()
    novel_id = str(setup.json()["novel_id"])
    # After setup: the settings row needs the user that setup creates.
    api.patch("/api/settings", json={"locale": "en"}).raise_for_status()

    for title, body in NOTES.items():
        uploaded = api.post(
            "/api/knowledge/documents",
            files={"file": (f"{title}.txt", body.encode())},
            data={"title": title},
        )
        uploaded.raise_for_status()

    for title, genre, blurb in SHELF:
        created = api.post(
            "/api/writing/novels",
            json={"title": title, "genre": genre, "blurb": blurb},
        )
        created.raise_for_status()

    chapters = api.get(f"/api/writing/novels/{novel_id}/chapters")
    chapters.raise_for_status()
    return novel_id, list(chapters.json())


def _plant_contradiction(api: httpx.Client, chapter: dict[str, object]) -> None:
    """Renumber one facility mention, so the check has a real contradiction.

    The demo names Research Facility 7 twice in the same chapter; one mention
    becomes 9. A name carrying two numbers in one checked passage is what the
    consistency contract reports, and the same-chapter edit keeps both
    readings in the group the map-reduce sends to the provider. The prose
    lives on scenes now (W4 §5) — the chapter is the grouping shell, so the
    edit finds the scene carrying the mention (the list is in position order)
    and renumbers it there, the same one-mention edit a writer makes.
    """
    listed = api.get(f"/api/writing/chapters/{chapter['id']}/scenes")
    listed.raise_for_status()
    for scene in listed.json():
        original = str(scene["body"])
        if original.count("Research Facility 7") < 2:
            continue
        body = original.replace("Research Facility 7", "Research Facility 9", 1)
        updated = api.put(f"/api/writing/scenes/{scene['id']}", json={"body": body})
        updated.raise_for_status()
        return
    raise SystemExit("the demo no longer names Research Facility 7 twice in one chapter")


def _run_check(api: httpx.Client, novel_id: str) -> None:
    """Start the whole-book check and wait for the job to finish."""
    started = api.post(f"/api/knowledge/consistency/{novel_id}")
    started.raise_for_status()
    job_id = str(started.json()["job_id"])
    with httpx.Client(base_url=API, timeout=30.0) as poll:
        for _ in range(120):
            job = poll.get(f"/api/jobs/{job_id}")
            job.raise_for_status()
            state = job.json()["status"]
            if state not in {"queued", "running"}:
                if state != "done":
                    raise SystemExit(f"the consistency job ended {state}: {job.text}")
                return
            time.sleep(0.5)
    raise SystemExit("the consistency job did not finish within a minute")


def _route_model(api: httpx.Client, vendor: ChatVendor) -> tuple[str, str]:
    """Two providers with one model each, as a user would: the stand-in, and a local endpoint.

    The knowledge jobs stay on the deterministic fake — they answer JSON, which a
    prose stand-in cannot. The continuation goes to the local endpoint, so its
    text is the demo prose instead of one canned German sentence. ``chat.ask``
    stays on the fake as well: the entity interview rides that key and needs
    the fake's structured interview answer, not prose. The provider row is the
    endpoint, so the pair is created first and the models hang off it — the way
    the settings surface stores a configuration.

    Returns the local provider and model ids: the capture removes that pair
    once the continuation frame is shot, because its endpoint URL is a
    per-run free port and a screenshot must not carry a random address.
    """
    fake = api.post(
        "/api/settings/providers", json={"name": "Deterministic stand-in", "kind": "fake"}
    )
    fake.raise_for_status()
    fake_id = str(fake.json()["id"])

    local = api.post(
        "/api/settings/providers",
        json={"name": "Local endpoint", "kind": "openai-chat", "base_url": vendor.base_url},
    )
    local.raise_for_status()
    local_id = str(local.json()["id"])

    fake_model = api.post(
        "/api/settings/models",
        json={"name": "Deterministic stand-in", "provider_id": fake_id, "model": "fake"},
    )
    fake_model.raise_for_status()
    fake_model_id = str(fake_model.json()["id"])

    local_model = api.post(
        "/api/settings/models",
        json={"name": "Local endpoint", "provider_id": local_id, "model": "vendor-max"},
    )
    local_model.raise_for_status()
    local_model_id = str(local_model.json()["id"])

    for task, profile_id in (
        ("knowledge.extract-entities", fake_model_id),
        ("knowledge.check-consistency", fake_model_id),
        ("writing.continuation", local_model_id),
    ):
        assigned = api.put(f"/api/settings/assignments/{task}", json={"profile_id": profile_id})
        assigned.raise_for_status()
    return local_id, local_model_id


def _drop_local_endpoint(api: httpx.Client, provider_id: str, model_id: str) -> None:
    """Remove the continuation endpoint once its frame is taken.

    The vendor's port is random per capture; leaving the provider row in place
    would print that address into the AI-rules frame. Deleting the model also
    clears its assignment (the cascade the settings surface documents).
    """
    api.delete(f"/api/settings/models/{model_id}").raise_for_status()
    api.delete(f"/api/settings/providers/{provider_id}").raise_for_status()


def _create_novel(api: httpx.Client, title: str) -> str:
    novel = api.post("/api/writing/novels", json={"title": title})
    novel.raise_for_status()
    return str(novel.json()["id"])


def _create_chapter(api: httpx.Client, novel_id: str, title: str) -> str:
    chapter = api.post(f"/api/writing/novels/{novel_id}/chapters", json={"title": title})
    chapter.raise_for_status()
    return str(chapter.json()["id"])


def _write_scene(api: httpx.Client, chapter_id: str, body: str) -> None:
    saved = api.post(f"/api/writing/chapters/{chapter_id}/scenes", json={"body": body})
    saved.raise_for_status()


def _seed_canon(api: httpx.Client, title: str, prose: str, accept_order: list[str]) -> str:
    """A novel whose canon entered through extraction → accept, through the API.

    The accept order is sorted explicitly so the rows' creation timestamps —
    the order every browsing surface reads — do not depend on the suggestion
    queue's ties. Returns the novel id.
    """
    novel_id = _create_novel(api, title)
    chapter_id = _create_chapter(api, novel_id, "Ankunft")
    _write_scene(api, chapter_id, prose)
    enqueued = api.post(f"/api/knowledge/extraction/{novel_id}", json={"chapter_id": chapter_id})
    enqueued.raise_for_status()
    job = wait_for_job(api, enqueued.json()["job_id"])
    assert job["status"] == "done", f"the extraction job ended {job['status']}"
    suggestions = api.get(f"/api/knowledge/novels/{novel_id}/suggestions")
    suggestions.raise_for_status()
    rank = {name: index for index, name in enumerate(accept_order)}
    ordered = sorted(suggestions.json(), key=lambda row: rank[str(row["name"])])
    for suggestion in ordered:
        accepted = api.post(f"/api/knowledge/suggestions/{suggestion['id']}/accept")
        accepted.raise_for_status()
    return novel_id


def _scene(
    title: str, *, conflict: str = "", resolution: str = "", status: str = "planned"
) -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "title": title,
        "purpose": "",
        "conflict": conflict,
        "resolution": resolution,
        "beats": [],
        "status": status,
    }


def _save_scenes(
    api: httpx.Client, novel_id: str, chapter_id: str, scenes: list[dict[str, object]]
) -> None:
    saved = api.put(
        f"/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes",
        json={"scenes": scenes},
    )
    saved.raise_for_status()


def _seed_causality(api: httpx.Client) -> str:
    """A two-chapter chain with one open gap, wide enough to fit the frame.

    The first chapter carries the answered scene and the gapped one, so the
    "forces" link is real; the second stands empty, the honest break the
    strip shows when no scene was planned there. Two chapters and two scenes
    fit the 1600px viewport without a horizontal crop.
    """
    novel_id = _create_novel(api, "Die verkettete Bucht")
    first = _create_chapter(api, novel_id, "Ankunft")
    _create_chapter(api, novel_id, "Der Nebel")
    _save_scenes(
        api,
        novel_id,
        first,
        [
            _scene(
                "Kalibrierung der Messsonde",
                conflict="Die Sonde schlägt bei 14.2 Hz aus.",
                resolution="Der Außenposten wird evakuiert.",
                status="complete",
            ),
            _scene("Der Ausfall", conflict="Der Strom fällt aus."),
        ],
    )
    return novel_id


def _seed_timeline(api: httpx.Client) -> str:
    """A novel with chapters and events, through the API.

    The events enter the world the way a writer would place them — through
    the real create — one dated with characters and a chapter, one ordered
    but undated, one unordered and chapterless. Returns the novel's id.
    """
    novel_id = _create_novel(api, "Die geplante Bucht")
    chapter_ids = [_create_chapter(api, novel_id, title) for title in ("Ankunft", "Abreise")]
    events: tuple[dict[str, object], ...] = (
        {
            "title": "Anfang",
            "description": "Maya erreicht die Station; das Signal ist noch ein Gerücht.",
            "date_label": "Im Frühling",
            "character_names": ["Maya Chen", "ARIA"],
            "chapter_id": chapter_ids[0],
            "position": 1,
        },
        {
            "title": "Mitte",
            "description": "Der Konzern nennt es einen Unfall.",
            "chapter_id": chapter_ids[1],
            "position": 2,
        },
        {"title": "Ausklang", "description": "Drei Jahre fehlen."},
    )
    for payload in events:
        created = api.post(f"/api/planning/novels/{novel_id}/timeline-events", json=payload)
        created.raise_for_status()
    return novel_id


def _seed_storyboard(api: httpx.Client) -> str:
    """A novel with chapters wearing three different sync badges, through the API."""
    novel_id = _create_novel(api, "Die aufgestellte Bucht")
    chapter_ids = [
        _create_chapter(api, novel_id, title) for title in ("Ankunft", "Abreise", "Heimkehr")
    ]
    ankunft, _, heimkehr = chapter_ids
    seeded: tuple[tuple[str, list[dict[str, object]]], ...] = (
        (ankunft, [{"id": str(uuid4()), "title": "Sturm", "status": "planned"}]),
        (heimkehr, [{"id": str(uuid4()), "title": "Rückblick", "status": "complete"}]),
    )
    for chapter_id, scenes in seeded:
        _save_scenes(api, novel_id, chapter_id, scenes)
    _write_scene(api, heimkehr, "Erste Worte im Manuskript.")
    return novel_id


def _seed_continuation(api: httpx.Client) -> tuple[str, str]:
    """A short book for the continuation frame: one chapter, one scene."""
    novel_id = _create_novel(api, "The Quiet Channel")
    chapter_id = _create_chapter(api, novel_id, "Arrival")
    _write_scene(api, chapter_id, CONTINUATION_BODY)
    return novel_id, chapter_id


def _goto_graph(page: Page, novel_id: str) -> None:
    page.goto(f"{WEB}/novels/{novel_id}/knowledge/graph")
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


def _caret_at_first_paragraph_end(page: Page) -> None:
    """Place the caret where a writer stopped: the opening paragraph's end."""
    page.evaluate(
        """() => {
            const paragraph = document.querySelector(".ProseMirror p");
            if (!paragraph) return;
            const range = document.createRange();
            range.selectNodeContents(paragraph);
            range.collapse(false);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
        }"""
    )


def _capture(
    page: Page,
    out: Path,
    novel_id: str,
    chapters: list[dict[str, object]],
    vendor: ChatVendor,
    api: httpx.Client,
    local_endpoint: tuple[str, str],
) -> list[Path]:
    """Shoot the frames in the order the page tells them."""
    written: list[Path] = []
    first_chapter = str(chapters[0]["id"])

    def open_chapter(book: str, chapter: str) -> None:
        _open_workspace(page, book)
        # The chapter title button, not the chevron beside it: selecting the
        # chapter opens its first scene, the deterministic entry point.
        page.get_by_test_id(f"tree-chapter-{chapter}").get_by_role("button").nth(1).click()
        expect(page.locator(".ProseMirror")).to_be_visible()

    # 20/21. The rebuilt workspace in the default light and the reader's
    #     stored dark: the same demo scene, so the pair is the same desk.
    _set_theme(page, "light")
    open_chapter(novel_id, first_chapter)
    written.append(_shot(page, out, "20-workspace-rebuilt"))
    _set_theme(page, "dark")
    open_chapter(novel_id, first_chapter)
    written.append(_shot(page, out, "21-workspace-rebuilt-dark"))

    # 37/38. The shelf, before the planning and interview books exist, so it
    #     really is the writer's three books.
    _set_theme(page, "light")
    page.goto(f"{WEB}/")
    expect(page.get_by_role("heading", name="The Bookshelf", exact=True)).to_be_visible()
    written.append(_shot(page, out, "37-shelf"))
    _set_theme(page, "dark")
    page.goto(f"{WEB}/")
    expect(page.get_by_role("heading", name="The Bookshelf", exact=True)).to_be_visible()
    written.append(_shot(page, out, "38-shelf-dark"))

    # 35. A short scene with the continuation waiting at the caret; the short
    #     book leaves the accept pill above the prompt bar.
    _set_theme(page, "light")
    continuation_novel, continuation_chapter = _seed_continuation(api)
    open_chapter(continuation_novel, continuation_chapter)
    _caret_at_first_paragraph_end(page)
    vendor.set_answer(CONTINUATION)
    page.get_by_role("button", name="Continue writing").click()
    ghost = page.get_by_test_id("ghost-preview")
    expect(ghost).to_contain_text("relay clicked")
    ghost.scroll_into_view_if_needed()
    written.append(_shot(page, out, "35-workspace-continuation"))

    # 22. Zen: the prose alone. The clock pauses before the room mounts, so
    #     the pomodoro's digits never tick between the two captures.
    open_chapter(novel_id, first_chapter)
    _pause_clock(page)
    page.keyboard.press("F9")
    expect(page.get_by_test_id("zen-mode")).to_be_visible()
    written.append(_shot(page, out, "22-zen"))
    _resume_clock(page)

    # 23. Zen in the reader's stored dark.
    _set_theme(page, "dark")
    open_chapter(novel_id, first_chapter)
    _pause_clock(page)
    page.keyboard.press("F9")
    expect(page.get_by_test_id("zen-mode")).to_be_visible()
    written.append(_shot(page, out, "23-zen-dark"))
    _resume_clock(page)

    # The continuation frame is shot; the per-run vendor address must not
    # reach the AI-rules frame, so its provider and model go now.
    _drop_local_endpoint(api, *local_endpoint)

    # 36. The knowledge dock beside the prose: the check, its finding, the cast.
    _set_theme(page, "light")
    open_chapter(novel_id, first_chapter)
    page.get_by_role("button", name="Knowledge", exact=True).click()
    expect(page.get_by_test_id("knowledge-dock")).to_be_visible()
    # The demo's own scene headings carry numbers too; this frame claims the
    # planted Facility contradiction, so wait for that finding and bring it
    # into the dock's own scroll area.
    finding = page.get_by_test_id("knowledge-finding").filter(has_text="Facility")
    expect(finding).to_be_visible(timeout=15000)
    finding.evaluate(
        """element => {
            const area = element.closest("div.overflow-y-auto");
            if (!area) return;
            const shift = element.getBoundingClientRect().top - area.getBoundingClientRect().top;
            area.scrollTop += shift - 8;
        }"""
    )
    written.append(_shot(page, out, "36-knowledge-dock"))

    # 25. The dossiers on a three-entity canon, accepted in a fixed order.
    _set_theme(page, "light")
    dossiers_novel = _seed_canon(
        api,
        "Das Signal",
        "Mira trifft Kavic auf Vulkan.",
        ["Mira", "Kavic", "Vulkan"],
    )
    page.goto(f"{WEB}/novels/{dossiers_novel}/knowledge/dossiers")
    expect(page.get_by_test_id("dossiers-page")).to_be_visible()
    cards = page.get_by_test_id("dossier-card")
    expect(cards).to_have_count(3)
    cards.filter(has_text="Mira").click()
    expect(page.get_by_test_id("dossier-overview")).to_be_visible()
    written.append(_shot(page, out, "25-dossiers"))

    # 26. The sources archive: the uploaded notes and a semantic search.
    page.goto(f"{WEB}/novels/{novel_id}/knowledge/sources")
    expect(page.get_by_test_id("sources-page")).to_be_visible()
    expect(page.get_by_test_id("sources-document")).to_have_count(len(NOTES))
    page.get_by_test_id("sources-search").fill("facility built the device")
    page.get_by_test_id("sources-search-button").click()
    expect(page.get_by_test_id("sources-hit").first).to_be_visible()
    written.append(_shot(page, out, "26-sources"))

    # 28. The settings hub.
    page.goto(f"{WEB}/settings")
    expect(page.get_by_test_id("settings-page")).to_be_visible()
    expect(page.locator("#settings-author-name")).to_be_visible()
    written.append(_shot(page, out, "28-settings-hub"))

    # 29. AI rules: providers, models and the task assignments.
    page.goto(f"{WEB}/settings/ai-regeln")
    expect(page.get_by_test_id("ai-rules-page")).to_be_visible()
    expect(page.get_by_role("heading", name="AI rules & model architecture")).to_be_visible()
    expect(page.get_by_role("heading", name="1. Providers & interfaces")).to_be_visible()
    written.append(_shot(page, out, "29-ai-rules"))

    # 30. Prompts: the five bundled cards and the live editor.
    page.goto(f"{WEB}/settings/prompts")
    expect(page.get_by_test_id("prompts-page")).to_be_visible()
    expect(page.get_by_test_id("prompt-card")).to_have_count(5)
    expect(page.get_by_test_id("prompts-editor")).to_be_visible()
    written.append(_shot(page, out, "30-prompts"))

    # 27. Causality: the seeded chain with its one open gap.
    causality_novel = _seed_causality(api)
    page.goto(f"{WEB}/novels/{causality_novel}/planning/causality")
    expect(page.get_by_test_id("causality-page")).to_be_visible()
    expect(page.get_by_test_id("causality-chain")).to_contain_text("1 open gap")
    written.append(_shot(page, out, "27-causality"))

    # 41/42. The timeline.
    timeline_novel = _seed_timeline(api)
    page.goto(f"{WEB}/novels/{timeline_novel}/planning/timeline")
    expect(page.get_by_test_id("timeline-page")).to_be_visible()
    expect(page.get_by_text("Im Frühling")).to_be_visible()
    written.append(_shot(page, out, "41-timeline"))
    _set_theme(page, "dark")
    page.goto(f"{WEB}/novels/{timeline_novel}/planning/timeline")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    expect(page.get_by_text("Im Frühling")).to_be_visible()
    written.append(_shot(page, out, "42-timeline-dark"))

    # 43/44. The storyboard, reading the storyboard seed's aggregate.
    _set_theme(page, "light")
    storyboard_novel = _seed_storyboard(api)
    page.goto(f"{WEB}/novels/{storyboard_novel}/planning/storyboard")
    expect(page.get_by_test_id("storyboard-page")).to_be_visible()
    expect(page.get_by_test_id("storyboard-stage").first).to_be_visible()
    expect(page.get_by_test_id("storyboard-card")).to_have_count(3)
    expect(page.get_by_test_id("storyboard-progress")).to_contain_text("4 words")
    written.append(_shot(page, out, "43-storyboard"))
    _set_theme(page, "dark")
    page.goto(f"{WEB}/novels/{storyboard_novel}/planning/storyboard")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    expect(page.get_by_test_id("storyboard-stage").first).to_be_visible()
    expect(page.get_by_test_id("storyboard-card")).to_have_count(3)
    written.append(_shot(page, out, "44-storyboard-dark"))

    # 39/40. The lore graph. One entity: the force layout sorts by id, so a
    #     one-node web is the only shape whose pixels do not depend on UUIDs.
    _set_theme(page, "light")
    canon_novel = _seed_canon(api, "Die stille Bucht", "Mira.", ["Mira"])
    _goto_graph(page, canon_novel)
    node = page.get_by_test_id("graph-node").get_by_role("button")
    expect(page.get_by_test_id("graph-node")).to_have_count(1)
    node.click()
    expect(page.get_by_test_id("entity-dossier")).to_be_visible()
    written.append(_shot(page, out, "39-graph"))
    _set_theme(page, "dark")
    _goto_graph(page, canon_novel)
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    page.get_by_test_id("graph-node").get_by_role("button").click()
    expect(page.get_by_test_id("entity-dossier")).to_be_visible()
    written.append(_shot(page, out, "40-graph-dark"))

    # 31/32. The manual create dialog, reached through the interview door.
    _set_theme(page, "light")
    _open_interview(page, canon_novel)
    page.get_by_test_id("entity-interview-manual").click()
    expect(page.get_by_test_id("entity-create-dialog")).to_be_visible()
    written.append(_shot(page, out, "31-entity-create"))
    _set_theme(page, "dark")
    _open_interview(page, canon_novel)
    page.get_by_test_id("entity-interview-manual").click()
    expect(page.get_by_test_id("entity-create-dialog")).to_be_visible()
    written.append(_shot(page, out, "32-entity-create-dark"))

    # 33/34. The interview: a chosen type, two real answers and the proposal
    #     the fake provider builds from them.
    _set_theme(page, "light")
    _open_interview(page, canon_novel)
    _start(page, "object")
    _say(page, f"Name: {INTERVIEW_NAME}")
    proposal = page.get_by_test_id("entity-interview-proposal")
    expect(proposal).to_contain_text(INTERVIEW_NAME)
    _say(
        page,
        "Beschreibung: Ein Relais, das auf die Druckkurve seiner Fingerkuppen reagiert.",
    )
    expect(proposal).to_contain_text("Druckkurve")
    written.append(_shot(page, out, "33-entity-interview"))
    _set_theme(page, "dark")
    expect(page.get_by_test_id("entity-interview")).to_be_visible()
    expect(page.get_by_test_id("entity-interview-proposal")).to_contain_text(INTERVIEW_NAME)
    written.append(_shot(page, out, "34-entity-interview-dark"))

    return written


def capture(out: Path) -> list[Path]:
    """Boot the stack, seed a writer's novel, and write every frame.

    The caller owns the target's atomic replacement; this function only fills
    the directory it is given, and a failure leaves whatever stood there
    untouched.
    """
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    try:
        with (
            chat_vendor() as vendor,
            run_stack(
                database=DATABASE,
                seed_user=False,
                env={
                    "NARRE_LLM_PROVIDER": "fake",
                    "NARRE_EMBEDDING_PROVIDER": "fake",
                    # The capture contract: no update check and no banner, and
                    # no attached process whose environment the caller cannot set.
                    "NARRE_UPDATE_CHECK_URL": "off",
                },
            ),
            _api() as api,
            sync_playwright() as playwright,
            playwright.chromium.launch(
                args=[
                    "--force-color-profile=srgb",
                    "--font-render-hinting=none",
                    "--disable-lcd-text",
                    "--disable-font-subpixel-positioning",
                    "--disable-gpu",
                    "--run-all-compositor-stages-before-draw",
                    "--num-raster-threads=1",
                    "--disable-partial-raster",
                    "--disable-threaded-animation",
                    "--disable-threaded-scrolling",
                ]
            ) as browser,
            browser.new_context(
                viewport={"width": 1600, "height": 1000},
                device_scale_factor=1,
                locale="en-US",
                timezone_id="UTC",
                color_scheme="light",
                reduced_motion="reduce",
            ) as context,
        ):
            page = context.new_page()
            # The transcript's stamp is the server's turn time, so the
            # browser clock alone cannot pin it; the fixed label is the one
            # clock the frame shows. The clock itself runs one hour ahead of
            # this run's own seed, so the shelf's relative "last edited"
            # reads one hour ago — a stable, plausible label, not seconds.
            page.add_init_script(f'Date.prototype.toLocaleTimeString = () => "{TRANSCRIPT_TIME}";')
            page.clock.install(time=datetime.now(UTC) + timedelta(hours=1))

            # 24. The welcome, before setup closes its door.
            page.goto(f"{WEB}/setup")
            expect(
                page.get_by_role("heading", name="Step in. Your unwritten work awaits.")
            ).to_be_visible()
            written.append(_shot(page, out, "24-welcome-setup"))

            novel_id, chapters = _seed(api)
            _plant_contradiction(api, chapters[2])
            local_endpoint = _route_model(api, vendor)
            _run_check(api, novel_id)

            written.extend(_capture(page, out, novel_id, chapters, vendor, api, local_endpoint))
    finally:
        # The shared Vite server outlives a pytest module by design; this
        # one-shot recipe must not leave it behind when a frame fails.
        stop_shared_web()
    return written


def _write_index_temp(index: Path, text: str) -> Path:
    """Write the overview beside its target; the caller replaces atomically."""
    index.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{index.name}-", dir=index.parent)
    path = Path(name)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


def _replace_directory(staged: Path, target: Path) -> None:
    """Swap the staged masters in, removals included, and keep a rollback."""
    backup_dir: Path | None = None
    previous: Path | None = None
    if target.exists():
        backup_dir = Path(tempfile.mkdtemp(prefix=f".{target.name}-old-", dir=target.parent))
        previous = backup_dir / "previous"
        target.rename(previous)
    try:
        staged.rename(target)
    except BaseException:
        if previous is not None and previous.exists():
            previous.rename(target)
        raise
    finally:
        if backup_dir is not None:
            shutil.rmtree(backup_dir, ignore_errors=True)


def _publish(staged: Path, out: Path, index: Path, written: Iterable[Path]) -> None:
    """Replace the canonical set and the overview only after a full capture."""
    expected = {shot.filename for shot in SHOTS}
    actual = {path.name for path in written}
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise SystemExit(
            f"the capture set does not match the manifest: missing={missing} extra={extra}"
        )
    staged_index = _write_index_temp(index, render_index(SHOTS))
    try:
        _replace_directory(staged, out)
        staged_index.replace(index)
    finally:
        staged_index.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    """Write the README's images; exit non-zero when the capture is incomplete."""
    validate_shots(SHOTS)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("assets/screenshots"),
        help="directory the PNGs are written to",
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=Path("docs/screenshots/README.md"),
        help="the generated overview path",
    )
    args = parser.parse_args(argv)

    out: Path = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{out.name}-", dir=out.parent))
    try:
        written = capture(staging)
        _publish(staging, out, args.index, written)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
