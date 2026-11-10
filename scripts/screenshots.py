"""Capture the README's images from the real app.

Run: ``uv run python -m scripts.screenshots`` (needs Docker's Postgres — ``just
dev-services`` — and the browser once: ``uv run playwright install chromium``).
Re-run when a surface below changes: a stale image claims a UI that no longer
exists.

Nothing here is mocked except the model at its boundary, the seam every E2E suite
uses: the chat stand-in answers with the prose this file chooses, because the
kernel's fake answers every prompt with one German sentence. The README says so, in
one line under the gallery.

The demo novel is the bundled *Dead Signal* archive, loaded through the setup door
a first run takes. The notes are this file's own text, uploaded the way a writer
uploads research. The one planted continuity error (a facility renumbered between
chapters) is an edit a writer could make, and the check that finds it is the real
one.
"""

import argparse
import re
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from playwright.sync_api import FloatRect, expect, sync_playwright

from app.kernel.testing.jobs import wait_for_job
from app.kernel.testing.stack import API_PORT, WEB_PORT, run_stack
from app.kernel.testing.vendor import chat_vendor

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from app.kernel.testing.vendor import ChatVendor

API = f"http://127.0.0.1:{API_PORT}"
WEB = f"http://127.0.0.1:{WEB_PORT}"
"""The ports ``run_stack`` binds — it reads ``NARRE_E2E_API_PORT`` and
``NARRE_E2E_WEB_PORT``, so a second stack on this machine needs no code edit."""
DATABASE = "narrare_v2_screenshots"
DEMO = "dead-signal"
"""The bundled English demo: three chapters, eight knowledge entries, relations."""


CHAT_ANSWER = (
    "The signal arrives at Research Facility 7, in Nevada: Maya's sister's last post, "
    "years after the accident that killed her."
)
"""What the stand-in says when the writer asks about the signal."""

CONTINUATION = (
    " Somewhere behind the console a relay clicked, once, and the hum of the deck went "
    "quiet — the sound of a system deciding, on its own, to answer."
)
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

QUESTION = "Where does the signal come from?"

SHOTS = (
    "01-workspace-continuation.png",
    "02-chat-sources.png",
    "03-knowledge-dock.png",
    "04-knowledge-search.png",
    "05-shelf.png",
    "06-shelf-dark.png",
    "07-workspace-dark.png",
    "08-design.png",
    "09-design-dark.png",
    "10-graph.png",
    "11-graph-dark.png",
)


def _api() -> httpx.Client:
    """A short-timeout client against the stack's own API."""
    return httpx.Client(base_url=API, timeout=30.0)


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

    The demo names Research Facility 7 in two chapters; one of them becomes 9.
    A name carrying two numbers is what the consistency contract reports.
    """
    original = str(chapter["body"])
    body = original.replace("Research Facility 7", "Research Facility 9", 1)
    if body == original:
        raise SystemExit("the demo no longer names Research Facility 7")
    updated = api.put(f"/api/writing/chapters/{chapter['id']}", json={"body": body})
    updated.raise_for_status()


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


def _route_model(api: httpx.Client, vendor: ChatVendor) -> None:
    """Two providers with one model each, as a user would: the stand-in, and a local endpoint.

    The knowledge jobs stay on the deterministic fake — they answer JSON, which a
    prose stand-in cannot. Chat and the continuation go to the local endpoint, so
    their text is the demo prose instead of one canned German sentence. The
    provider row is the endpoint, so the pair is created first and the models
    hang off it — the way the settings surface stores a configuration.
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
        ("chat.ask", local_model_id),
        ("writing.continuation", local_model_id),
    ):
        assigned = api.put(f"/api/settings/assignments/{task}", json={"profile_id": profile_id})
        assigned.raise_for_status()


def _seed_graph(api: httpx.Client) -> tuple[str, str, str]:
    """A novel with two accepted entities joined by one edge, through the API.

    The entities enter the world the only way they can — the extraction
    job over a real chapter, and the review's accept — and the edge rides
    the real relation create. Returns the novel's id and the two entity
    names, the words the canvas must then show. Mirrors the knowledge E2E's
    graph seed; the screenshots stack runs the same fake providers.
    """
    novel = api.post("/api/writing/novels", json={"title": "Die graphische Bucht"})
    novel.raise_for_status()
    novel_id = str(novel.json()["id"])
    chapter = api.post(f"/api/writing/novels/{novel_id}/chapters", json={"title": "Ankunft"})
    chapter.raise_for_status()
    chapter_id = str(chapter.json()["id"])
    saved = api.put(
        f"/api/writing/chapters/{chapter_id}",
        json={"body": "Mira betrat das alte Haus am See. Draußen schwieg der Leuchtturm."},
    )
    saved.raise_for_status()
    enqueued = api.post(f"/api/knowledge/extraction/{novel_id}", json={"chapter_id": chapter_id})
    enqueued.raise_for_status()
    job = wait_for_job(api, enqueued.json()["job_id"])
    assert job["status"] == "done", f"the extraction job ended {job['status']}"
    suggestions = api.get(f"/api/knowledge/novels/{novel_id}/suggestions")
    suggestions.raise_for_status()
    assert len(suggestions.json()) >= 2
    first = api.post(f"/api/knowledge/suggestions/{suggestions.json()[0]['id']}/accept")
    first.raise_for_status()
    second = api.post(f"/api/knowledge/suggestions/{suggestions.json()[1]['id']}/accept")
    second.raise_for_status()
    listed = api.get(f"/api/knowledge/novels/{novel_id}/entities")
    listed.raise_for_status()
    names = [str(row["name"]) for row in listed.json()]
    assert len(names) == 2
    edge = api.post(
        f"/api/knowledge/entities/{listed.json()[0]['id']}/relations",
        json={"to_entity_id": listed.json()[1]["id"], "relation_type": "friend_of"},
    )
    edge.raise_for_status()
    return novel_id, names[0], names[1]


def _capture(
    page: Page,
    out: Path,
    novel_id: str,
    chapters: list[dict[str, object]],
    vendor: ChatVendor,
    api: httpx.Client,
) -> list[Path]:
    """Shoot the frames in the order the page tells them."""
    written: list[Path] = []
    first = chapters[0]

    def shot(name: str, *, height: int | None = None) -> None:
        path = out / name
        clip: FloatRect | None = (
            {"x": 0, "y": 0, "width": 1600, "height": height} if height else None
        )
        page.screenshot(path=str(path), clip=clip)
        written.append(path)
        print(f"wrote {path}")

    def gallery_height() -> int:
        """Tall enough for the whole gallery in one frame.

        The shell is exactly one viewport tall and `main` owns the page
        scroll, so a capture at the shared 1600x1000 would stop at the
        fold: the viewport grows by the scroller's overflow for these two
        frames, then returns to the shared size.
        """
        return int(
            page.evaluate(
                """() => {
                    const main = document.querySelector("main");
                    if (!main) return document.documentElement.scrollHeight;
                    return Math.ceil(
                        main.scrollHeight + (window.innerHeight - main.clientHeight),
                    );
                }"""
            )
        )

    def gallery_shot(name: str) -> None:
        page.set_viewport_size({"width": 1600, "height": gallery_height()})
        try:
            shot(name)
        finally:
            page.set_viewport_size({"width": 1600, "height": 1000})

    # 1. The workspace, a chapter open, a suggestion waiting and uncommitted.
    page.goto(f"{WEB}/novels/{novel_id}")
    page.get_by_role("complementary", name="Chapters").get_by_role(
        "button", name=str(first["title"])
    ).click()
    editor = page.locator(".ProseMirror")
    expect(editor).to_be_visible()
    # The suggestion lands at the caret, so the caret goes where a writer
    # stopped: the end of the chapter's opening paragraph. Placed through the
    # DOM because End walks the visual line, not the paragraph.
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
    vendor.set_answer(CONTINUATION)
    page.get_by_role("button", name="Continue writing").click()
    ghost = page.locator(".ProseMirror .ghost")
    expect(ghost).to_contain_text("relay clicked")
    # The caret sits at the end of a long chapter; bring the offer into frame.
    ghost.scroll_into_view_if_needed()
    shot(SHOTS[0])

    # 2. The chat dock beside the chapter: a streamed answer with its sources.
    page.keyboard.press("Escape")
    page.get_by_role("button", name="Chat", exact=True).click()
    dock = page.get_by_role("complementary", name="Chat")
    vendor.set_answer(CHAT_ANSWER)
    dock.get_by_label("Question").fill(QUESTION)
    dock.get_by_role("button", name="Ask").click()
    expect(dock.get_by_role("region", name="Answer")).to_contain_text(
        "Horizon Station — cast and places"
    )
    # The answer is offered to the editor as a variant; the offer is not what
    # this frame claims, and it covers the sources.
    dock.get_by_role("button", name="Discard").click()
    shot(SHOTS[1])

    # 3. The knowledge dock: extraction, the whole-book check, the cast.
    page.get_by_role("button", name="Knowledge", exact=True).click()
    knowledge = page.get_by_role("complementary", name="Knowledge")
    expect(knowledge.get_by_role("button", name="Check the whole book")).to_be_visible()
    expect(knowledge.get_by_text("Research Facility")).to_be_visible()
    # The entity list and the findings arrive on separate requests, and the
    # entity one is not this frame's subject: wait for the finding itself. The
    # frame claims a pair of readings, not their order, so both are accepted.
    expect(knowledge.get_by_text(re.compile(r"Facility: (?:7 vs\. 9|9 vs\. 7)"))).to_be_visible()
    # The dock's content area is half the viewport and the extraction panel
    # sits above the check: the frame opens on the check button it names,
    # whole, with the finding and the entities under it. The dock scrolls
    # alone — `scrollIntoView` would take the workbench with it.
    knowledge.get_by_role("button", name="Check the whole book").evaluate(
        """button => {
            const area = button.closest("div.overflow-y-auto");
            const shift = button.getBoundingClientRect().top - area.getBoundingClientRect().top;
            area.scrollTop += shift;
        }"""
    )
    shot(SHOTS[2])

    # 4. The knowledge page: the notes on file, and a search that finds them.
    page.goto(f"{WEB}/knowledge")
    expect(page.get_by_text("Horizon Station — cast and places")).to_be_visible()
    page.get_by_label("Search term").fill("facility built the device")
    page.get_by_role("button", name="Search").click()
    # A hit is a row in the Hits panel, not a list item: the row renders as a
    # plain element (the panel groups it), so the frame waits for the passage.
    expect(page.get_by_role("heading", name="Hits")).to_be_visible()
    expect(page.get_by_text("the device was moved off the site")).to_be_visible()
    shot(SHOTS[3])

    # 5. The shelf: the books, and the door out of the app.
    page.goto(f"{WEB}/")
    expect(page.get_by_role("heading", name="Novels")).to_be_visible()
    shot(SHOTS[4], height=700)

    # 6. The chosen dark: the reader's setting, proven against a light OS.
    #    Shot with the setting, not `color_scheme="dark"` — the claim is that
    #    the stored choice beats the system.
    api.patch("/api/settings/theme", json={"theme": "dark"})
    page.goto(f"{WEB}/")
    expect(page.get_by_role("heading", name="Novels")).to_be_visible()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    shot(SHOTS[5], height=700)

    # 7. The workbench in the same light: the prose surface is the object.
    page.goto(f"{WEB}/novels/{novel_id}")
    expect(page.locator(".ProseMirror")).to_be_visible()
    shot(SHOTS[6])

    # 8. The design gallery in the default light: every primitive and token
    #    plus the Target drafts and the dock-and-palette specimens on one
    #    page, outside the settings hub's nav.
    #    Full page — the claim is the six sections together, not one viewport
    #    of them.
    api.patch("/api/settings/theme", json={"theme": None})
    page.goto(f"{WEB}/design")
    expect(page.get_by_role("heading", name="Design gallery")).to_be_visible()
    gallery_shot(SHOTS[7])

    # 9. The same gallery in the reader's chosen dark, proven against a
    #    light OS like the shelf's dark frame.
    api.patch("/api/settings/theme", json={"theme": "dark"})
    page.goto(f"{WEB}/design")
    expect(page.get_by_role("heading", name="Design gallery")).to_be_visible()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    gallery_shot(SHOTS[8])

    # 10. The graph canvas in the default light: the novel's entities as
    #     named nodes, the one relation as the line between them, and the
    #     selected node's glance below — the canvas owns the page, shot at
    #     the shared viewport.
    api.patch("/api/settings/theme", json={"theme": None})
    graph_novel, first, second = _seed_graph(api)
    page.goto(f"{WEB}/knowledge/graph?novel={graph_novel}")
    expect(page.get_by_role("button", name=first)).to_be_visible()
    expect(page.get_by_role("button", name=second)).to_be_visible()
    expect(page.locator("svg line")).to_have_count(1)
    page.get_by_role("button", name=first).click()
    expect(page.get_by_role("region", name=first)).to_be_visible()
    shot(SHOTS[9])

    # 11. The same canvas in the reader's chosen dark, proven against a
    #     light OS — the tokens resolve, the selection keeps its focus
    #     fill, the glance stays readable.
    api.patch("/api/settings/theme", json={"theme": "dark"})
    page.goto(f"{WEB}/knowledge/graph?novel={graph_novel}")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    expect(page.get_by_role("button", name=first)).to_be_visible()
    expect(page.locator("svg line")).to_have_count(1)
    page.get_by_role("button", name=first).click()
    expect(page.get_by_role("region", name=first)).to_be_visible()
    shot(SHOTS[10])

    api.patch("/api/settings/theme", json={"theme": None})
    return written


def capture(out: Path) -> list[Path]:
    """Boot the stack, seed a writer's novel, and write every frame."""
    out.mkdir(parents=True, exist_ok=True)
    with (
        chat_vendor() as vendor,
        run_stack(
            database=DATABASE,
            seed_user=False,
            env={"NARRE_LLM_PROVIDER": "fake", "NARRE_EMBEDDING_PROVIDER": "fake"},
        ),
        _api() as api,
        sync_playwright() as playwright,
        playwright.chromium.launch() as browser,
        browser.new_context(
            viewport={"width": 1600, "height": 1000},
            device_scale_factor=1,
            locale="en-US",
            color_scheme="light",
        ) as context,
    ):
        novel_id, chapters = _seed(api)
        _plant_contradiction(api, chapters[-1])
        _route_model(api, vendor)
        _run_check(api, novel_id)

        page = context.new_page()
        vendor.set_answer(CHAT_ANSWER)
        written = _capture(page, out, novel_id, chapters, vendor, api)
    return written


def main(argv: list[str] | None = None) -> int:
    """Write the README's images; exit non-zero when fewer than SHOTS were."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("assets/screenshots"),
        help="directory the PNGs are written to",
    )
    args = parser.parse_args(argv)
    written = capture(args.out)
    if len(written) < len(SHOTS):
        print(f"only {len(written)} of {len(SHOTS)} images were written", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
