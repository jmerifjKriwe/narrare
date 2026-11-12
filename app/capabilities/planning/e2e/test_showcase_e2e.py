"""Showcase seed for the planning screens: a populated chronology and
storyboard so the timeline canvas and the scene matrix have something to
draw.

Run with ``just test-e2e planning`` and read the screenshots from
``/tmp/opencode/showcase/``.
"""

import uuid
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page  # noqa: TC002

from app.kernel.testing.stack import API_URL, WEB_URL

pytestmark = [pytest.mark.e2e, pytest.mark.showcase, pytest.mark.timeout(300)]

API = API_URL
BASE = WEB_URL
SHOTS = Path("/tmp/opencode/showcase")  # noqa: S108

EVENTS = [
    ("Der Große Bruch", "Nevada-Tiefraumarray verliert 41% der Verbindung.", "2278"),
    ("Unglück auf Station 7", "Lins Tod — offiziell Kühlmittel-Kollaps.", "14. Nov 2284"),
    ("Verlegung Transmitter L2", "Transport des Resonanzrings in den Orbit.", "Mai 2287"),
    ("Ankunft auf Horizon Station", "Dockung der Shuttle-Kapsel, Kalibrierung ARIA.", "Tag 01"),
    ("Empfang des Notfall-Codes", "Signal moduliert auf 14.2 Hz.", "Tag 03"),
]


def _seed_novel(client: httpx.Client, title: str) -> str:
    novel = client.post("/api/writing/novels", json={"title": title, "genre": "Sci-Fi"})
    novel.raise_for_status()
    novel_id = str(novel.json()["id"])

    # One chapter carrying four scenes, so the storyboard matrix has rows.
    chapter = client.post(f"/api/writing/novels/{novel_id}/chapters", json={"title": "Kapitel 1"})
    chapter.raise_for_status()
    chapter_id = str(chapter.json()["id"])
    scenes = [
        ("Ankunft auf Horizon Station", "Etablierung der Station", "planned"),
        ("Das erste Flüstern (14.2 Hz)", "Auslöser", "in_progress"),
        ("Quarantäne-Befehl von Kavic", "Eskalation", "planned"),
        ("Der verbotene Dekodier-Lauf", "Plot Point 1", "planned"),
    ]
    saved = client.put(
        f"/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes",
        json={
            "scenes": [
                {"id": str(uuid.uuid4()), "title": t, "purpose": p, "status": s}
                for (t, p, s) in scenes
            ]
        },
    )
    saved.raise_for_status()

    for index, (title_e, desc, date) in enumerate(EVENTS, start=1):
        event = client.post(
            f"/api/planning/novels/{novel_id}/timeline-events",
            json={
                "title": title_e,
                "description": desc,
                "date_label": date,
                "position": index,
                "character_names": ["Maya Chen", "ARIA"],
            },
        )
        event.raise_for_status()
    return novel_id


def test_showcase_planning_chronology(page: Page, stack) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    with httpx.Client(base_url=API, timeout=120) as client:
        novel_id = _seed_novel(client, "Dead Signal — Planung")

    page.goto(f"{BASE}/planning?novel={novel_id}")
    page.screenshot(path=str(SHOTS / "planning-chronology.png"), full_page=True)

    page.goto(f"{BASE}/planning/storyboard?novel={novel_id}")
    page.screenshot(path=str(SHOTS / "planning-storyboard.png"), full_page=True)

    page.goto(f"{BASE}/planning/structure?novel={novel_id}")
    page.screenshot(path=str(SHOTS / "planning-structure.png"), full_page=True)
