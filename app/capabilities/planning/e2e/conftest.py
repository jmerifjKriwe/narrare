"""Full stack for the planning E2E: its own database, installed through the API.

The planning surfaces only exist on an installed instance, so every test
opens on a freshly installed one (the knowledge suite's pattern): ``installed``
empties the database — pytest-randomly shuffles, and no test may inherit
another's rows — and completes setup through the real API, the blank path
with known answers. The setup's own novel is deleted again straight after:
the user row is what makes the instance installed, and every test seeds
exactly the population it asserts on through the writing and planning APIs.

The helpers drive the same HTTP surface the browser uses — real API, real
Postgres, never a database insert. No provider fake is needed here at all:
planning is pure CRUD and deterministic structure math, so the suite seeds
events, scene aggregates, stages and remaps through the product's own doors
and reads the server's truth back through the same doors after every write
the browser makes.

``DATABASE`` is defined here once; the tests import it and the API helpers
from this module.
"""

from collections.abc import Iterator  # noqa: TC003
from typing import Any
from uuid import uuid4

import httpx
import pytest
from playwright.sync_api import Page, expect

from app.kernel.db import testsupport
from app.kernel.testing.db_rows import reset
from app.kernel.testing.stack import API_URL, WEB_URL, Stack, acquire_stack

DATABASE = testsupport.test_database("narrare_v2_planning_e2e")

# The blank path's known answers — the wizard's step-1 defaults and one of
# each settings vocabulary, so the installed instance is a real, complete one.
SETUP_ANSWERS: dict[str, Any] = {
    "novel_title": "Das Atelier-Buch",
    "genre": "Literarische Belletristik",
    "target_words": 65000,
    "author_typology": "plantser",
    "dramatic_form": "three-act",
    "ai_role": "lektor",
    "canon_strictness": 3,
}


def _client() -> httpx.Client:
    """One client per call against this worker's stack — nothing to leak."""
    return httpx.Client(base_url=API_URL, timeout=30.0)


def complete_setup() -> dict[str, Any]:
    """The one POST that installs the instance; return the provisioning facts."""
    with _client() as client:
        response = client.post("/api/setup", json=SETUP_ANSWERS)
    response.raise_for_status()
    result: dict[str, Any] = response.json()
    assert result["novel_title"] == SETUP_ANSWERS["novel_title"]
    return result


def delete_novel(novel_id: str) -> None:
    with _client() as client:
        response = client.delete(f"/api/writing/novels/{novel_id}")
    response.raise_for_status()


def create_novel(title: str, *, target_words: int | None = None) -> dict[str, Any]:
    """Seed one book through the writing API — the shelf's own create door."""
    body: dict[str, Any] = {"title": title}
    if target_words is not None:
        body["target_words"] = target_words
    with _client() as client:
        response = client.post("/api/writing/novels", json=body)
    response.raise_for_status()
    novel: dict[str, Any] = response.json()
    return novel


def create_chapter(novel_id: str, title: str = "") -> dict[str, Any]:
    with _client() as client:
        response = client.post(f"/api/writing/novels/{novel_id}/chapters", json={"title": title})
    response.raise_for_status()
    chapter: dict[str, Any] = response.json()
    return chapter


def mint() -> str:
    """A client-minted scene id — the dock's own rule: an id no row owns is
    the PUT's create."""
    return str(uuid4())


def scene(
    title: str = "",
    *,
    purpose: str = "",
    conflict: str = "",
    resolution: str = "",
    beats: list[str] | None = None,
    status: str = "planned",
) -> dict[str, Any]:
    """One SceneUpsert body, the id minted here — the aggregate PUT's shape."""
    return {
        "id": mint(),
        "title": title,
        "purpose": purpose,
        "conflict": conflict,
        "resolution": resolution,
        "beats": beats if beats is not None else [],
        "status": status,
    }


def save_scenes(novel_id: str, chapter_id: str, scenes: list[dict[str, Any]]) -> dict[str, Any]:
    """Write the chapter's whole scene list through the aggregate PUT — the
    dock's own save door, and the suite's seed seam for scenes with plans."""
    with _client() as client:
        response = client.put(
            f"/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes",
            json={"scenes": scenes},
        )
    response.raise_for_status()
    aggregate: dict[str, Any] = response.json()
    return aggregate


def read_scenes(novel_id: str, chapter_id: str) -> dict[str, Any]:
    """The chapter's aggregate — the server's truth behind the dock."""
    with _client() as client:
        response = client.get(f"/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes")
    response.raise_for_status()
    aggregate: dict[str, Any] = response.json()
    return aggregate


def create_event(novel_id: str, **fields: Any) -> dict[str, Any]:
    """Seed one timeline event through the planning API."""
    with _client() as client:
        response = client.post(f"/api/planning/novels/{novel_id}/timeline-events", json=fields)
    response.raise_for_status()
    event: dict[str, Any] = response.json()
    return event


def list_events(novel_id: str) -> list[dict[str, Any]]:
    """The novel's events in the server's manual order."""
    with _client() as client:
        response = client.get(f"/api/planning/novels/{novel_id}/timeline-events")
    response.raise_for_status()
    events: list[dict[str, Any]] = response.json()
    return events


def get_storyboard(novel_id: str) -> dict[str, Any]:
    """The novel's storyboard read — structure, stages, chapter rows."""
    with _client() as client:
        response = client.get(f"/api/planning/novels/{novel_id}/storyboard")
    response.raise_for_status()
    storyboard: dict[str, Any] = response.json()
    return storyboard


def remap(novel_id: str, structure_id: str, *, confirm: bool) -> httpx.Response:
    """The raw remap call for the refusal legs — the status is the finding."""
    with _client() as client:
        return client.post(
            f"/api/planning/novels/{novel_id}/remap",
            json={"structure_id": structure_id, "confirm": confirm},
        )


def set_theme(theme: str) -> None:
    """The settings row's theme — the shell adopts it at boot (dark face)."""
    with _client() as client:
        response = client.patch("/api/settings/theme", json={"theme": theme})
    response.raise_for_status()


def goto_timeline(page: Page, novel_id: str) -> None:
    """Open the chronology and wait for its ready-state surface."""
    page.goto(f"{WEB_URL}/novels/{novel_id}/planning/timeline")
    expect(page.get_by_test_id("timeline-page")).to_be_visible()


def goto_storyboard(page: Page, novel_id: str) -> None:
    """Open the storyboard and wait for its ready-state surface."""
    page.goto(f"{WEB_URL}/novels/{novel_id}/planning/storyboard")
    expect(page.get_by_test_id("storyboard-page")).to_be_visible()


def goto_causality(page: Page, novel_id: str) -> None:
    """Open the causality strip and wait for its ready-state surface."""
    page.goto(f"{WEB_URL}/novels/{novel_id}/planning/causality")
    expect(page.get_by_test_id("causality-page")).to_be_visible()


@pytest.fixture(scope="module")
def stack() -> Iterator[Stack]:
    running = acquire_stack("planning", database=DATABASE, seed_user=False)
    yield running


@pytest.fixture
def installed(stack: Stack) -> Stack:
    """Every planning test starts on a freshly installed, empty instance.

    One reset, one setup POST, one delete of the setup's own novel: the
    instance is installed (the user row exists) and the population is the
    test's own to seed.
    """
    reset(DATABASE)
    result = complete_setup()
    delete_novel(str(result["novel_id"]))
    return stack
