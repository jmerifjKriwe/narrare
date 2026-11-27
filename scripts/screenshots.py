"""Capture the README's images from the real app.

Run: ``uv run python -m scripts.screenshots`` (needs Docker's Postgres — ``just
dev-services`` — and the browser once: ``uv run playwright install chromium``).
Re-run when a surface below changes: a stale image claims a UI that no longer
exists. The canonical set and its index come from ``scripts.screenshot_manifest``:
the names here are the manifest's, so the PNG directory and
``docs/screenshots/README.md`` cannot drift apart.

The call captures into a temporary sibling directory and replaces the target
set — removals included — only after every frame landed. A failed capture
leaves the previous masters and the previous index untouched;
``scripts.screenshots_publish`` owns that replacement, backing up each output
on its own filesystem and restoring both on failure.

Nothing here is mocked except the model at its boundary, the seam every E2E
suite uses: the chat stand-in answers the continuation and the interview's JSON
turn with the text this file chooses, because the kernel's fake answers every
prompt with one fixed German sentence. The README says so, in one line under the
gallery.

The demo novel is the bundled *Dead Signal* archive, loaded through the setup
door a first run takes; it is the shelf's book. The writing frames come from a
clean, API-seeded project (*The Glass Harbor*), so no archive scene heading
reaches the prose. The planted continuity error (a facility renumbered in one
chapter) lives in that project, and the check that finds it is the real one. The
sources frame is the same project's real empty archive: no notes are uploaded, so
the server-generated upload date cannot reach a frame.

Determinism is part of the recipe: the viewport, locale, timezone, reduced
motion, a fixed browser clock, the reader's stored theme and animation-free
screenshots are pinned here, and every seed is API-driven with stable order.
The graph's force layout orders nodes by the canon's own names, so its frame
runs on the same three-entity canon every capture and a fresh set of UUIDs
cannot move a card.

Two captures are byte-identical across machines, not only on this one: the
command mark is an SVG, and every captured mono glyph — keycaps, badges, code,
dates and numeric metadata — comes from the bundled IBM Plex Mono cuts under
``web/public/fonts``. The UI sans and brand serif are bundled too, but the
guard names only the mono ink: ``_assert_pinned_fonts`` loads and checks the
four mono weights, rejects a visible mono element whose first family is not
the bundled one, and refuses a rendered U+2318 before every frame.
"""

import argparse
import json
import shutil
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import httpx
from playwright.sync_api import Locator, expect, sync_playwright

from app.kernel.testing.jobs import wait_for_job
from app.kernel.testing.stack import API_PORT, WEB_PORT, run_stack, stop_shared_web
from app.kernel.testing.vendor import chat_vendor
from scripts.screenshot_fonts import MonoUse, validate_pinned_fonts
from scripts.screenshot_manifest import SHOTS, render_index, validate_shots
from scripts.screenshots_publish import publish

if TYPE_CHECKING:
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

VIEWPORT = (1600, 1000)
"""The one master viewport: the browser context and every framing bound use it."""

VIEWPORT_WIDTH, VIEWPORT_HEIGHT = VIEWPORT

TOP_BAR_HEIGHT = 56
"""Where the scrollable main begins, so a frame's content must start below it."""


CONTINUATION = " Somewhere behind the console a relay clicked, once."
"""The ghost the editor offers below the prose: the image's whole claim."""

WRITING_TITLE = "The Glass Harbor"
WRITING_SIGNAL = (
    "The console woke before the station did. A thin tone moved through the deck, "
    "steady as a pulse, and Maya counted it until the count became a question.\n\n"
    "Research Facility 7 had been sealed for six years. The file in front of her "
    "still said Research Facility 7, and the tone said otherwise.\n\n"
    'She opened the channel. "ARIA, tell me where that signal comes from."\n\n'
    'The answer arrived without a pause. "The signal comes from the place we buried."'
)
WRITING_CAST = "Mira meets Kavic at Vulcan."
"""The clean writing project the workspace, Zen and knowledge-dock frames share."""

STORYBOARD_PROSE: tuple[tuple[str, str], ...] = (
    ("Arrival", "The station woke in the dark."),
    ("The Signal", "The signal crossed the harbor twice."),
    ("The Descent", "The descent began before dawn."),
    ("The Return", "The return found the lights burning."),
    ("The Harbor", "The harbor kept its own counsel."),
)
STORYBOARD_WORDS = sum(len(body.split()) for _, body in STORYBOARD_PROSE)
"""The storyboard's written words: the progress chip's real total, no target."""

SHELF: tuple[tuple[str, str, str], ...] = (
    (
        "The Salt Road",
        "Literary",
        "A lighthouse keeper keeps a ledger of every ship that never came back.",
    ),
    (
        "Winter House",
        "Mystery",
        "Six guests, one valley, and a snowed-in road that keeps them there.",
    ),
)
"""Two more books on the shelf, so the shelf reads as a shelf and not a test row."""

INTERVIEW_NAME = "Resonance Transponder LC-89"
INTERVIEW_DESCRIPTION = "A relay that answers to the pressure curve."
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


def _assert_pinned_fonts(page: Page) -> None:
    """Refuse a frame whose mono ink would come from the machine's fonts.

    The page answers three facts — which bundled weights loaded, the computed
    font stack of every mono element with its visibility, and its own text —
    and ``scripts.screenshot_fonts.validate_pinned_fonts`` owns the rule.
    Keeping the judgement pure lets the first-family order and the
    visible/hidden distinction be tested without a browser; this wrapper only
    evaluates the page and turns the errors into a failed capture.
    """
    result = page.evaluate(
        """async () => {
            const weights = [400, 500, 600, 700];
            await Promise.all(
                weights.map((weight) =>
                    document.fonts.load(`${weight} 10px "IBM Plex Mono"`, "BESbswy"),
                ),
            );
            const loaded = Object.fromEntries(
                weights.map((weight) => [
                    weight,
                    document.fonts.check(`${weight} 10px "IBM Plex Mono"`, "BESbswy"),
                ]),
            );
            const monoUses = [];
            for (const element of document.querySelectorAll("body *")) {
                const family = getComputedStyle(element).fontFamily;
                if (!/mono/i.test(family)) continue;
                const visible =
                    typeof element.checkVisibility === "function"
                        ? element.checkVisibility()
                        : element.getClientRects().length > 0;
                monoUses.push({ family, visible });
            }
            return { loaded, monoUses, text: document.body.innerText };
        }"""
    )
    errors = validate_pinned_fonts(
        loaded={int(weight): yes for weight, yes in result["loaded"].items()},
        mono_uses=[
            MonoUse(family=use["family"], visible=use["visible"]) for use in result["monoUses"]
        ],
        body_text=result["text"],
    )
    if errors:
        raise SystemExit("; ".join(errors))


def _shot(page: Page, out: Path, name: str) -> Path:
    """Write one 1600x1000 master with motion, caret and hover pinned.

    The pointer parks in a dead corner: a surviving hover from the click that
    opened the page would otherwise paint a tooltip into one run and not the
    next. Fonts settle and then prove they are the bundled ones, so a late
    swap or a system fallback cannot change the text between captures.
    """
    page.mouse.move(VIEWPORT_WIDTH - 10, VIEWPORT_HEIGHT - 10)
    page.evaluate("document.fonts.ready")
    _assert_pinned_fonts(page)
    page.wait_for_timeout(300)
    path = out / f"{name}.png"
    page.screenshot(path=str(path), animations="disabled", caret="hide")
    print(f"wrote {path}")
    return path


def _require_inside(
    locator: Locator,
    *,
    name: str,
    left: float = 0,
    top: float = 0,
    right: float = VIEWPORT_WIDTH,
    bottom: float = VIEWPORT_HEIGHT,
) -> None:
    """Fail the capture when a frame's own element leaves the viewport.

    Both axes are checked: a vertical scroll can still shove a wide card past
    the right edge, and the master's claim is that the whole element is inside
    the 1600x1000 frame. The recipe's framing claims are checked at capture
    time, where the real layout answers.
    """
    box = locator.bounding_box()
    if box is None:
        raise SystemExit(f"{name}: nothing to measure")
    start_x, end_x = box["x"], box["x"] + box["width"]
    start_y, end_y = box["y"], box["y"] + box["height"]
    if start_x < left or end_x > right or start_y < top or end_y > bottom:
        raise SystemExit(
            f"{name}: x {start_x:.1f}..{end_x:.1f} y {start_y:.1f}..{end_y:.1f} "
            f"is outside x {left:.1f}..{right:.1f} y {top:.1f}..{bottom:.1f}"
        )


def _require_small_gap(first: Locator, second: Locator, *, name: str, maximum: float = 48) -> None:
    """Fail when two stacked blocks sit farther apart than a normal group gap.

    The causality page's groups keep their own ``gap-4`` rhythm; only the
    flexible middle group absorbs the spare height. A stretched layout that
    spreads every block fails here instead of shipping four wide voids.
    """
    first_box = first.bounding_box()
    second_box = second.bounding_box()
    if first_box is None or second_box is None:
        raise SystemExit(f"{name}: nothing to measure")
    gap = second_box["y"] - (first_box["y"] + first_box["height"])
    if gap > maximum:
        raise SystemExit(f"{name}: {gap:.1f}px gap exceeds {maximum:.1f}px")


def _require_unclipped(locator: Locator, *, name: str) -> None:
    """Fail when an element's own content overflows its box.

    A wrapped status badge is fine; a badge whose text runs past its padding
    is not. The comparison is against the element's own scroll and client
    boxes, so it catches truncation without reading the rendered pixels.
    """
    metrics = locator.evaluate(
        """element => ({
            scrollWidth: element.scrollWidth,
            clientWidth: element.clientWidth,
            scrollHeight: element.scrollHeight,
            clientHeight: element.clientHeight,
        })"""
    )
    if (
        metrics["scrollWidth"] > metrics["clientWidth"] + 1
        or metrics["scrollHeight"] > metrics["clientHeight"] + 1
    ):
        raise SystemExit(
            f"{name}: content {metrics['scrollWidth']}x{metrics['scrollHeight']} overflows "
            f"its {metrics['clientWidth']}x{metrics['clientHeight']} box"
        )


def _require_dock_badge(page: Page) -> None:
    """The dock's status badge is painted, readable and not clipped."""
    badge = page.get_by_test_id("dock-soon-badge")
    expect(badge).to_be_visible()
    expect(badge).to_have_text("Not available yet.")
    _require_inside(badge, name="dock status badge")
    _require_unclipped(badge, name="dock status badge")


def _scroll_to_show_bottom(container: Locator, target: Locator, *, margin: float = 8) -> None:
    """Scroll a real container just enough that the target's bottom is inside."""
    box = target.bounding_box()
    if box is None:
        raise SystemExit("the scroll target has no box")
    delta = box["y"] + box["height"] - (VIEWPORT_HEIGHT - margin)
    if delta > 0:
        container.evaluate("(element, by) => { element.scrollTop += by; }", delta)


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
    """Set the language, load the demo and the two shelf books, return ids.

    The demo is the shelf's hero; no notes are uploaded, so the sources archive
    stays genuinely empty. Returns the novel id and its chapters in position
    order.
    """
    # A demo carries its own title: the archive's metadata wins over the field.
    setup = api.post("/api/setup", json={"novel_title": "Dead Signal", "demo": DEMO})
    setup.raise_for_status()
    novel_id = str(setup.json()["novel_id"])
    # After setup: the settings row needs the user that setup creates.
    api.patch("/api/settings", json={"locale": "en"}).raise_for_status()

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

    The seed names Research Facility 7 twice in the same chapter; one mention
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
    raise SystemExit("the seed no longer names Research Facility 7 twice in one chapter")


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

    The knowledge jobs stay on the deterministic fake — they answer the
    JSON extraction and consistency shapes. The continuation and ``chat.ask``
    go to the local endpoint, so their text is this file's own prose and the
    interview gets a canned English JSON turn instead of the kernel fake's
    German sentence. The provider row is the endpoint, so the pair is created
    first and the models hang off it — the way the settings surface stores a
    configuration.

    Returns the local provider and model ids: the capture removes that pair
    after the interview, because its endpoint URL is a per-run free port and a
    screenshot must not carry a random address.
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
        ("chat.ask", local_model_id),
    ):
        assigned = api.put(f"/api/settings/assignments/{task}", json={"profile_id": profile_id})
        assigned.raise_for_status()
    return local_id, local_model_id


def _drop_local_endpoint(api: httpx.Client, provider_id: str, model_id: str) -> None:
    """Remove the local endpoint once its frames are taken.

    The vendor's port is random per capture; leaving the provider row in place
    would print that address into the AI-rules frame. Deleting the model also
    clears its assignments (the cascade the settings surface documents).
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


def _write_scene(
    api: httpx.Client, chapter_id: str, body: str, *, title: str | None = None
) -> None:
    payload: dict[str, object] = {"body": body}
    if title is not None:
        payload["title"] = title
    saved = api.post(f"/api/writing/chapters/{chapter_id}/scenes", json=payload)
    saved.raise_for_status()


def _seed_canon(api: httpx.Client, title: str, prose: str, accept_order: list[str]) -> str:
    """A novel whose canon entered through extraction → accept, through the API.

    The accept order is sorted explicitly so the rows' creation timestamps —
    the order every browsing surface reads — do not depend on the suggestion
    queue's ties. Returns the novel id.
    """
    novel_id = _create_novel(api, title)
    chapter_id = _create_chapter(api, novel_id, "Arrival")
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
    title: str,
    *,
    purpose: str = "",
    conflict: str = "",
    resolution: str = "",
    beats: list[str] | None = None,
    status: str = "planned",
) -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "title": title,
        "purpose": purpose,
        "conflict": conflict,
        "resolution": resolution,
        "beats": list(beats or ()),
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
    """A three-chapter chain with exactly one open gap, all of it in frame.

    The first chapter carries the gapped scene and the third the answered
    one; the second stands empty, the honest break the strip shows when no
    scene was planned there. The two scene cards and three label cards fit
    the 1600px track without a horizontal crop, and the chip and the
    methodology footer both read one open gap.
    """
    novel_id = _create_novel(api, "The Chained Bay")
    first = _create_chapter(api, novel_id, "Arrival")
    _create_chapter(api, novel_id, "The Fog")
    third = _create_chapter(api, novel_id, "The Descent")
    _save_scenes(
        api,
        novel_id,
        first,
        [_scene("The outage", conflict="The power fails at the worst moment.")],
    )
    _save_scenes(
        api,
        novel_id,
        third,
        [
            _scene(
                "The signal returns",
                conflict="The relay stays silent through the night.",
                resolution="Mara answers it herself.",
                status="complete",
            )
        ],
    )
    return novel_id


def _seed_timeline(api: httpx.Client) -> str:
    """A novel with six placed events and three unordered notes.

    The events enter the world the way a writer would place them — through
    the real create. Three chapters give the chapter chips real names; four
    placed rows carry free-text dates while two are ordered without one, and
    the unordered register holds three fragments without a position. Returns
    the novel's id.
    """
    novel_id = _create_novel(api, "The Planned Bay")
    arrival, departure, homecoming = [
        _create_chapter(api, novel_id, title) for title in ("Arrival", "Departure", "Homecoming")
    ]
    events: tuple[dict[str, object], ...] = (
        {
            "title": "Beginning",
            "description": "Maya reaches the station; the signal is still a rumour.",
            "date_label": "In spring",
            "character_names": ["Maya Chen", "ARIA"],
            "chapter_id": arrival,
            "position": 1,
        },
        {
            "title": "The sealed file",
            "description": "The archive names Research Facility 7.",
            "date_label": "Three days later",
            "chapter_id": arrival,
            "position": 2,
        },
        {
            "title": "The corporation calls",
            "description": "The corporation calls it an accident.",
            "chapter_id": departure,
            "position": 3,
        },
        {
            "title": "The missing years",
            "description": "Six years vanish from the station log.",
            "date_label": "In the following winter",
            "chapter_id": departure,
            "position": 4,
        },
        {
            "title": "The return",
            "description": "The crew comes back to a deck that remembers them.",
            "chapter_id": homecoming,
            "position": 5,
        },
        {
            "title": "The last signal",
            "description": "The tone stops at the moment of arrival.",
            "date_label": "At first light",
            "chapter_id": homecoming,
            "position": 6,
        },
        {"title": "Coda", "description": "Three years are missing."},
        {
            "title": "Alternate opening",
            "description": "A different first chapter, kept as a note.",
        },
        {
            "title": "Epilogue idea",
            "description": "The harbor closes in the fog.",
        },
    )
    for payload in events:
        created = api.post(f"/api/planning/novels/{novel_id}/timeline-events", json=payload)
        created.raise_for_status()
    return novel_id


def _seed_storyboard(api: httpx.Client) -> str:
    """Eight chapters with four sync faces, real scenes and words, through the API.

    Position ratios put two chapters in Setup, four in Confrontation and two
    in Resolution. The first chapter carries three planned scenes, so its
    drill-in shows real purpose, conflict, resolution and beats. The four
    sync faces — planned, on track, completed, empty — all derive from the
    seeded scenes and words, never from a capture-only override.
    """
    novel_id = _create_novel(api, "The Staged Bay")
    titles = (
        "Arrival",
        "The Watch",
        "The Signal",
        "The Descent",
        "The Outage",
        "The Return",
        "The Harbor",
        "Coda",
    )
    chapters = {title: _create_chapter(api, novel_id, title) for title in titles}
    planned: tuple[tuple[str, list[dict[str, object]]], ...] = (
        (
            "Arrival",
            [
                _scene(
                    "First light",
                    purpose="Show the station waking.",
                    conflict="The console answers before anyone speaks.",
                    resolution="Mara answers the tone.",
                    beats=["A thin tone crosses the deck.", "Mara counts it."],
                    status="complete",
                ),
                _scene(
                    "The sealed file",
                    purpose="Introduce the contradiction.",
                    conflict="The file still says Facility 7.",
                    beats=["The file opens on the old number."],
                    status="in_progress",
                ),
                _scene(
                    "The channel",
                    purpose="Open the question.",
                    conflict="ARIA answers from the buried place.",
                ),
            ],
        ),
        (
            "The Watch",
            [_scene("The long watch", conflict="Nothing moves on the scope.")],
        ),
        (
            "The Signal",
            [
                _scene(
                    "The carrier",
                    conflict="The tone repeats in the same breath.",
                    resolution="Mara records it.",
                    status="in_progress",
                ),
                _scene("The triangulation", conflict="Two bearings disagree."),
            ],
        ),
        (
            "The Descent",
            [
                _scene(
                    "The stairwell",
                    conflict="The lights fail below deck.",
                    resolution="She keeps the rail.",
                    status="complete",
                )
            ],
        ),
        (
            "The Return",
            [
                _scene(
                    "The threshold",
                    conflict="The airlock will not cycle.",
                    resolution="Kavic forces it.",
                    status="complete",
                ),
                _scene(
                    "The empty deck",
                    conflict="No one answers the hail.",
                    resolution="They go in anyway.",
                    status="complete",
                ),
            ],
        ),
        (
            "The Harbor",
            [_scene("The waterline", conflict="The tide is wrong.")],
        ),
    )
    for title, scenes in planned:
        _save_scenes(api, novel_id, chapters[title], scenes)
    for title, body in STORYBOARD_PROSE:
        _write_scene(api, chapters[title], body, title=title)
    return novel_id


def _seed_writing(api: httpx.Client) -> tuple[str, str, str]:
    """The clean project the workspace, Zen, continuation and dock share.

    Three chapters: a short arrival scene for the continuation, a longer
    signal scene with the planted facility pair, and a cast sentence the
    extraction turns into the dock's three entities. The prose carries no
    archive scene headings. Returns the novel id, the arrival chapter and the
    signal chapter.
    """
    novel_id = _create_novel(api, WRITING_TITLE)
    arrival = _create_chapter(api, novel_id, "Arrival")
    _write_scene(api, arrival, CONTINUATION_BODY, title="Arrival")
    signal = _create_chapter(api, novel_id, "The Signal")
    _write_scene(api, signal, WRITING_SIGNAL, title="The Signal")
    cast = _create_chapter(api, novel_id, "The Cast")
    _write_scene(api, cast, WRITING_CAST, title="The Cast")
    enqueued = api.post(f"/api/knowledge/extraction/{novel_id}", json={"chapter_id": cast})
    enqueued.raise_for_status()
    job = wait_for_job(api, enqueued.json()["job_id"])
    assert job["status"] == "done", f"the extraction job ended {job['status']}"
    suggestions = api.get(f"/api/knowledge/novels/{novel_id}/suggestions")
    suggestions.raise_for_status()
    rank = {name: index for index, name in enumerate(["Mira", "Kavic", "Vulcan"])}
    for suggestion in sorted(suggestions.json(), key=lambda row: rank[str(row["name"])]):
        accepted = api.post(f"/api/knowledge/suggestions/{suggestion['id']}/accept")
        accepted.raise_for_status()
    return novel_id, arrival, signal


def _interview_answer(name: str, content: str | None = None) -> str:
    """The English JSON turn the interview vendor returns for one writer turn."""
    slots: dict[str, object] = {"name": name}
    if content is not None:
        slots["content"] = content
    return json.dumps({"reply": "Noted.", "slots": slots, "relations": []})


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


def _settle_interview(page: Page) -> None:
    """Show the proposal's last row and the newest answer, not a cut edge."""
    page.get_by_test_id("entity-interview-proposal-body").evaluate(
        "element => { element.scrollTop = element.scrollHeight; }"
    )
    page.get_by_test_id("entity-interview-transcript").evaluate(
        "element => { element.scrollTop = element.scrollHeight; }"
    )


def _capture(
    page: Page,
    out: Path,
    vendor: ChatVendor,
    api: httpx.Client,
    local_endpoint: tuple[str, str],
) -> list[Path]:
    """Shoot the frames in the order the page tells them."""
    written: list[Path] = []

    def open_chapter(book: str, chapter: str, expected_chapter: int) -> None:
        _open_workspace(page, book)
        # The chapter title button, not the chevron beside it: selecting the
        # chapter opens its first scene, the deterministic entry point.
        page.get_by_test_id(f"tree-chapter-{chapter}").get_by_role("button").nth(1).click()
        expect(page.locator(".ProseMirror")).to_be_visible()
        # The ribbon names the selected chapter, so a reordered explorer fails
        # here instead of silently capturing a different chapter.
        expect(page.get_by_test_id("workspace-ribbon")).to_contain_text(
            f"Chapter {expected_chapter}"
        )

    # 37/38. The shelf, before the clean writing project exists, so it really
    #     is the writer's three books. The scroll lands the last grid card
    #     (title, genre and blurb) above the fold, and the hero card starts
    #     below the top bar with the banner just past the fold — no edge cuts
    #     a card, a sentence or the banner.
    def shelf_frame(name: str) -> None:
        page.goto(f"{WEB}/")
        heading = page.get_by_role("heading", name="The Bookshelf", exact=True)
        expect(heading).to_be_visible()
        main = page.locator("main#main")
        last_card = main.locator("article").last
        _scroll_to_show_bottom(main, last_card, margin=32)
        hero = main.locator("section").first
        _require_inside(last_card, name=f"{name} last shelf card", bottom=VIEWPORT_HEIGHT - 2)
        _require_inside(hero, name=f"{name} shelf hero", top=TOP_BAR_HEIGHT)
        written.append(_shot(page, out, name))

    _set_theme(page, "light")
    shelf_frame("37-shelf")
    _set_theme(page, "dark")
    shelf_frame("38-shelf-dark")

    # The clean writing project: no archive headings, English prose, and the
    # planted facility pair the real consistency check reports.
    _set_theme(page, "light")
    writing_novel, arrival_chapter, signal_chapter = _seed_writing(api)
    _plant_contradiction(api, {"id": signal_chapter})
    _run_check(api, writing_novel)

    # 20/21. The rebuilt workspace in the default light and the reader's
    #     stored dark: the same signal scene, so the pair is the same desk.
    open_chapter(writing_novel, signal_chapter, 2)
    _require_dock_badge(page)
    written.append(_shot(page, out, "20-workspace-rebuilt"))
    _set_theme(page, "dark")
    open_chapter(writing_novel, signal_chapter, 2)
    _require_dock_badge(page)
    written.append(_shot(page, out, "21-workspace-rebuilt-dark"))

    # 35. The short arrival scene with the continuation offered below the prose.
    _set_theme(page, "light")
    open_chapter(writing_novel, arrival_chapter, 1)
    _caret_at_first_paragraph_end(page)
    vendor.set_answer(CONTINUATION)
    page.get_by_role("button", name="Continue writing").click()
    ghost = page.get_by_test_id("ghost-preview")
    expect(ghost).to_contain_text("relay clicked")
    ghost.scroll_into_view_if_needed()
    _require_dock_badge(page)
    written.append(_shot(page, out, "35-workspace-continuation"))

    # 22. Zen: the prose alone. The clock pauses before the room mounts, so
    #     the pomodoro's digits never tick between the two captures.
    open_chapter(writing_novel, signal_chapter, 2)
    _pause_clock(page)
    page.keyboard.press("F9")
    expect(page.get_by_test_id("zen-mode")).to_be_visible()
    written.append(_shot(page, out, "22-zen"))
    _resume_clock(page)

    # 23. Zen in the reader's stored dark.
    _set_theme(page, "dark")
    open_chapter(writing_novel, signal_chapter, 2)
    _pause_clock(page)
    page.keyboard.press("F9")
    expect(page.get_by_test_id("zen-mode")).to_be_visible()
    written.append(_shot(page, out, "23-zen-dark"))
    _resume_clock(page)

    # 36. The knowledge dock: the finding and the extracted cast beside the
    #     clean prose. The finding is scrolled into the dock's own area.
    _set_theme(page, "light")
    open_chapter(writing_novel, signal_chapter, 2)
    page.get_by_role("button", name="Knowledge", exact=True).click()
    expect(page.get_by_test_id("knowledge-dock")).to_be_visible()
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
    dossiers_novel = _seed_canon(
        api,
        "The Signal",
        "Mira meets Kavic at Vulcan.",
        ["Mira", "Kavic", "Vulcan"],
    )
    page.goto(f"{WEB}/novels/{dossiers_novel}/knowledge/dossiers")
    expect(page.get_by_test_id("dossiers-page")).to_be_visible()
    cards = page.get_by_test_id("dossier-card")
    expect(cards).to_have_count(3)
    cards.filter(has_text="Mira").click()
    expect(page.get_by_test_id("dossier-overview")).to_be_visible()
    # The gap areas carry the reader-facing note, never the retired wave copy.
    expect(page.get_by_test_id("dossier-psych-gap")).to_contain_text("Not available yet.")
    expect(page.get_by_test_id("dossier-ai-gap")).to_contain_text("Not available yet.")
    written.append(_shot(page, out, "25-dossiers"))

    # 26. The real empty sources archive: no documents, so no upload date.
    page.goto(f"{WEB}/novels/{writing_novel}/knowledge/sources")
    expect(page.get_by_test_id("sources-page")).to_be_visible()
    expect(page.get_by_test_id("sources-empty")).to_be_visible()
    expect(page.get_by_test_id("sources-empty-upload")).to_be_visible()
    expect(page.get_by_test_id("sources-upload")).to_be_visible()
    expect(page.get_by_test_id("sources-document")).to_have_count(0)
    written.append(_shot(page, out, "26-sources"))

    # 28. The settings hub. The page's own main scrolls; the profile section
    #     lands its whole card above the fold, so the daily-goal field is
    #     fully visible and the next section is not cut mid-row.
    page.goto(f"{WEB}/settings")
    settings = page.get_by_test_id("settings-page")
    expect(settings).to_be_visible()
    profile = page.locator("#profil-sektion")
    goal = page.locator("#settings-daily-goal")
    expect(goal).to_be_visible()
    _scroll_to_show_bottom(settings, profile, margin=20)
    _require_inside(goal, name="settings daily goal", top=TOP_BAR_HEIGHT)
    _require_inside(profile, name="settings profile section", top=TOP_BAR_HEIGHT)
    expect(page.locator("#settings-author-name")).to_be_visible()
    written.append(_shot(page, out, "28-settings-hub"))

    # 30. Prompts: the catalog and the selected prompt's editor. The page
    #     scrolls its own main; the fifth card's bottom lands above the fold,
    #     so all five cards stand complete rather than as a sliver.
    page.goto(f"{WEB}/settings/prompts")
    prompts = page.get_by_test_id("prompts-page")
    expect(prompts).to_be_visible()
    cards = page.get_by_test_id("prompt-card")
    expect(cards).to_have_count(5)
    expect(page.get_by_test_id("prompts-editor")).to_be_visible()
    _scroll_to_show_bottom(prompts, cards.nth(4), margin=2)
    _require_inside(cards.nth(0), name="first prompt card", top=TOP_BAR_HEIGHT)
    _require_inside(cards.nth(4), name="fifth prompt card", top=TOP_BAR_HEIGHT)
    written.append(_shot(page, out, "30-prompts"))

    # 27. Causality: the seeded three-chapter chain with its one open gap,
    #     all three chapter groups inside the track's own width.
    causality_novel = _seed_causality(api)
    page.goto(f"{WEB}/novels/{causality_novel}/planning/causality")
    expect(page.get_by_test_id("causality-page")).to_be_visible()
    expect(page.get_by_test_id("causality-chapter")).to_have_count(3)
    expect(page.get_by_test_id("causality-scene")).to_have_count(2)
    expect(page.get_by_test_id("causality-scene").filter(has_text="—")).to_have_count(1)
    expect(page.get_by_test_id("causality-chain")).to_contain_text("1 open gap")
    track = page.get_by_test_id("causality-track")
    track_box = track.bounding_box()
    last_chapter_box = page.get_by_test_id("causality-chapter").last.bounding_box()
    if track_box is None or last_chapter_box is None:
        raise SystemExit("the causality track or its last chapter has no box")
    if last_chapter_box["x"] + last_chapter_box["width"] > track_box["x"] + track_box["width"] + 1:
        raise SystemExit("the last causality chapter is cropped by the track")
    # The content column groups its five real blocks into three visual groups:
    # the subline, header+track and methodology+footnote keep their normal
    # 16px rhythm, and only the middle group's flex-1 share is the one large
    # gap; the footnote lands near the foot and the counts stay reachable.
    subline = page.get_by_test_id("causality-subline")
    header = page.get_by_test_id("causality-track-header")
    bento = page.get_by_test_id("causality-bento")
    counts = page.get_by_test_id("causality-counts")
    note = page.get_by_test_id("causality-note")
    _require_inside(subline, name="causality subline", top=TOP_BAR_HEIGHT)
    _require_inside(counts, name="causality counts", top=TOP_BAR_HEIGHT)
    _require_inside(note, name="causality footnote", top=TOP_BAR_HEIGHT)
    _require_small_gap(subline, header, name="subline to track header")
    _require_small_gap(header, track, name="track header to track")
    _require_small_gap(bento, note, name="methodology to footnote")
    note_box = note.bounding_box()
    if note_box is None:
        raise SystemExit("the causality footnote has no box")
    note_bottom = note_box["y"] + note_box["height"]
    if note_bottom < VIEWPORT_HEIGHT - 64:
        raise SystemExit(
            f"the causality footnote ends {VIEWPORT_HEIGHT - note_bottom:.0f}px above "
            "the viewport foot; the content column does not fill the page height"
        )
    written.append(_shot(page, out, "27-causality"))

    # 41/42. The timeline: six placed events and three unordered notes.
    timeline_novel = _seed_timeline(api)
    page.goto(f"{WEB}/novels/{timeline_novel}/planning/timeline")
    expect(page.get_by_test_id("timeline-page")).to_be_visible()
    expect(page.get_by_text("In spring")).to_be_visible()
    ordered = page.get_by_test_id("timeline-ordered").get_by_test_id("timeline-card")
    unordered = page.get_by_test_id("timeline-unordered").get_by_test_id("timeline-card")
    expect(ordered).to_have_count(6)
    expect(unordered).to_have_count(3)
    _require_inside(unordered.last, name="last timeline note", bottom=VIEWPORT_HEIGHT)
    sequence_note = page.get_by_test_id("timeline-sequence-gap").get_by_text("Not available yet.")
    expect(sequence_note).to_be_visible()
    _require_inside(sequence_note, name="timeline status note", top=TOP_BAR_HEIGHT)
    written.append(_shot(page, out, "41-timeline"))
    _set_theme(page, "dark")
    page.goto(f"{WEB}/novels/{timeline_novel}/planning/timeline")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    expect(page.get_by_text("In spring")).to_be_visible()
    expect(page.get_by_test_id("timeline-ordered").get_by_test_id("timeline-card")).to_have_count(6)
    expect(page.get_by_test_id("timeline-unordered").get_by_test_id("timeline-card")).to_have_count(
        3
    )
    sequence_note = page.get_by_test_id("timeline-sequence-gap").get_by_text("Not available yet.")
    expect(sequence_note).to_be_visible()
    _require_inside(sequence_note, name="timeline status note", top=TOP_BAR_HEIGHT)
    written.append(_shot(page, out, "42-timeline-dark"))

    # 43/44. The storyboard reading the eight-chapter seed's aggregate. The
    #     first card is opened so the drill-in shows its real scenes rather
    #     than the "choose a chapter" placeholder.
    def storyboard_frame(name: str) -> None:
        page.goto(f"{WEB}/novels/{storyboard_novel}/planning/storyboard")
        expect(page.get_by_test_id("storyboard-page")).to_be_visible()
        expect(page.get_by_test_id("storyboard-stage").first).to_be_visible()
        expect(page.get_by_test_id("storyboard-card")).to_have_count(8)
        expect(page.get_by_test_id("storyboard-progress")).to_contain_text(
            f"{STORYBOARD_WORDS} words"
        )
        page.get_by_test_id("storyboard-card").first.get_by_role("button").first.click()
        expect(page.get_by_test_id("drill-in")).to_be_visible()
        expect(page.get_by_test_id("drill-in-scene")).to_have_count(3)
        written.append(_shot(page, out, name))

    _set_theme(page, "light")
    storyboard_novel = _seed_storyboard(api)
    storyboard_frame("43-storyboard")
    _set_theme(page, "dark")
    storyboard_frame("44-storyboard-dark")

    # 39/40. The lore graph. The canonical three-node/two-edge cast: the
    #     layout orders by name, so the frame is the same picture every
    #     capture even though the API mints fresh UUIDs.
    _set_theme(page, "light")
    canon_novel = _seed_canon(
        api,
        "The Still Bay",
        "Mira meets Kavic at Vulcan.",
        ["Vulcan", "Kavic", "Mira"],
    )
    _goto_graph(page, canon_novel)
    expect(page.get_by_test_id("graph-node")).to_have_count(3)
    expect(page.get_by_test_id("graph-edge")).to_have_count(2)
    page.get_by_test_id("graph-node").filter(has_text="Mira").get_by_role("button").click()
    expect(page.get_by_test_id("entity-dossier")).to_be_visible()
    written.append(_shot(page, out, "39-graph"))
    _set_theme(page, "dark")
    _goto_graph(page, canon_novel)
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    page.get_by_test_id("graph-node").filter(has_text="Mira").get_by_role("button").click()
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

    # 33. The interview in light: a chosen type, two English answers and the
    #     proposal the local vendor builds from them. The transcript and the
    #     proposal's last row are scrolled into view before the frame.
    _set_theme(page, "light")
    _open_interview(page, canon_novel)
    _start(page, "object")
    vendor.set_answer(_interview_answer(INTERVIEW_NAME))
    _say(page, f"Name: {INTERVIEW_NAME}")
    proposal = page.get_by_test_id("entity-interview-proposal")
    expect(proposal).to_contain_text(INTERVIEW_NAME)
    vendor.set_answer(_interview_answer(INTERVIEW_NAME, INTERVIEW_DESCRIPTION))
    _say(page, f"Description: {INTERVIEW_DESCRIPTION}")
    expect(proposal).to_contain_text(INTERVIEW_DESCRIPTION)
    expect(page.get_by_test_id("entity-interview-transcript").get_by_text("Noted.")).to_have_count(
        2
    )
    _settle_interview(page)
    written.append(_shot(page, out, "33-entity-interview"))

    # End that session so the dark frame opens a fresh one through the same
    # sequence, with the same graph badge, proposal, transcript and composer.
    page.get_by_test_id("entity-interview-end").click()
    expect(page.get_by_test_id("entity-interview-new")).to_be_visible()

    # 34. The same interview in the reader's stored dark.
    _set_theme(page, "dark")
    _open_interview(page, canon_novel)
    _start(page, "object")
    vendor.set_answer(_interview_answer(INTERVIEW_NAME))
    _say(page, f"Name: {INTERVIEW_NAME}")
    proposal = page.get_by_test_id("entity-interview-proposal")
    expect(proposal).to_contain_text(INTERVIEW_NAME)
    vendor.set_answer(_interview_answer(INTERVIEW_NAME, INTERVIEW_DESCRIPTION))
    _say(page, f"Description: {INTERVIEW_DESCRIPTION}")
    expect(proposal).to_contain_text(INTERVIEW_DESCRIPTION)
    expect(page.get_by_test_id("entity-interview-transcript").get_by_text("Noted.")).to_have_count(
        2
    )
    _settle_interview(page)
    written.append(_shot(page, out, "34-entity-interview-dark"))

    # The local vendor is no longer needed; its random port must not reach
    # the AI-rules frame.
    _drop_local_endpoint(api, *local_endpoint)

    # 29. AI rules after the local endpoint is gone: the configured provider
    #     card and the create-provider form.
    _set_theme(page, "light")
    page.goto(f"{WEB}/settings/ai-regeln")
    expect(page.get_by_test_id("ai-rules-page")).to_be_visible()
    expect(page.get_by_role("heading", name="AI rules & model architecture")).to_be_visible()
    expect(page.get_by_role("heading", name="1. Providers & interfaces")).to_be_visible()
    written.append(_shot(page, out, "29-ai-rules"))

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
                viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
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

            _, chapters = _seed(api)
            # Bump the demo so it stays the shelf hero; the clean writing
            # project is created after the shelf frame.
            _plant_contradiction(api, chapters[2])
            local_endpoint = _route_model(api, vendor)

            written.extend(_capture(page, out, vendor, api, local_endpoint))
    finally:
        # The shared Vite server outlives a pytest module by design; this
        # one-shot recipe must not leave it behind when a frame fails.
        stop_shared_web()
    return written


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
        capture(staging / "masters")
        staged_index = staging / args.index.name
        staged_index.write_text(render_index(SHOTS), encoding="utf-8", newline="\n")
        publish(out, args.index, staging / "masters", staged_index)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
