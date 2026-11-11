"""Showcase seed for the knowledge screens: a populated entity graph so the
canvas, the dossier list and the atlas have something to draw.

The entities come through the real extraction path (the fake provider), so
their names are whatever the chapter text's capitalized words yield — this
is a layout smoke, not a curated replica of the Stitch graph. Hold the
screenshots next to ``docs/design/stitch/screens/knowledge/*.webp`` and read
them for drift in chrome, density and spacing, not for exact node labels.

Run with ``just test-e2e knowledge`` and read the screenshots from
``/tmp/opencode/showcase/``.
"""

from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

from app.kernel.testing.jobs import wait_for_job
from app.kernel.testing.stack import API_URL, WEB_URL

pytestmark = [pytest.mark.e2e, pytest.mark.showcase, pytest.mark.timeout(300)]

API = API_URL
BASE = WEB_URL
SHOTS = Path("/tmp/opencode/showcase")  # noqa: S108

# Capitalized words the fake provider turns into entities (up to eight).
BODY = (
    "Maya Chen traf ARIA auf der Horizon Station. Director Kavic sandte Lin "
    "nach Nevada. Forschungsstation Sieben blieb verlassen."
)


def _seed_graph_novel(client: httpx.Client, title: str) -> str:
    novel = client.post("/api/writing/novels", json={"title": title, "genre": "Sci-Fi"})
    novel.raise_for_status()
    novel_id = str(novel.json()["id"])
    chapter = client.post(f"/api/writing/novels/{novel_id}/chapters", json={"title": "Kapitel 1"})
    chapter.raise_for_status()
    chapter_id = str(chapter.json()["id"])
    saved = client.put(f"/api/writing/chapters/{chapter_id}", json={"body": BODY})
    saved.raise_for_status()
    enqueued = client.post(f"/api/knowledge/extraction/{novel_id}", json={"chapter_id": chapter_id})
    enqueued.raise_for_status()
    job = wait_for_job(client, enqueued.json()["job_id"])
    assert job["status"] == "done", job
    suggestions = client.get(f"/api/knowledge/novels/{novel_id}/suggestions")
    suggestions.raise_for_status()
    for suggestion in suggestions.json():
        accepted = client.post(f"/api/knowledge/suggestions/{suggestion['id']}/accept")
        accepted.raise_for_status()
    return novel_id


def test_showcase_knowledge_graph(page: Page, stack, vendor) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    with httpx.Client(base_url=API, timeout=120) as client:
        novel_id = _seed_graph_novel(client, "Dead Signal — Showcase")

    page.goto(f"{BASE}/knowledge/graph?novel={novel_id}")
    canvas = page.get_by_role("group", name="Entitätengraph")
    expect(canvas).to_be_visible()
    page.screenshot(path=str(SHOTS / "knowledge-graph.png"), full_page=True)
