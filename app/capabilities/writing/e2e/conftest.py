"""Full stack for the writing E2E: its own database, installed through the API.

The shelf only exists on an installed instance, so every shelf test opens on
a freshly installed one: ``installed`` empties the database (the setup suite's
fresh-instance pattern — pytest-randomly shuffles, and no test may inherit
another's rows) and completes setup through the real API — the blank path
with known answers, one POST, never a wizard walkthrough. The setup's own
novel is deleted again straight after: the user row is what makes the
instance installed, and every test seeds exactly the population it asserts
on through the writing API. ``installed_with_atelier`` is the same install
with the setup novel kept standing — the atelier's answers need their source
row for the dialog's inheritance face. ``uninstalled`` is the same stack's
second face: emptied and NOT set up — the pre-setup gate's precondition.

``DATABASE`` is defined here once; the tests import it and the API helpers
from this module. The helpers drive the same HTTP surface the browser uses —
real API, real Postgres, never a database insert.
"""

from collections.abc import Iterator  # noqa: TC003
from typing import Any

import httpx
import pytest

from app.kernel.db import testsupport
from app.kernel.testing.db_rows import reset
from app.kernel.testing.stack import API_URL, Stack, acquire_stack

DATABASE = testsupport.test_database("narrare_v2_writing_e2e")

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


def create_novel(
    title: str,
    *,
    genre: str | None = None,
    blurb: str | None = None,
    target_words: int | None = None,
) -> dict[str, Any]:
    """Seed one book through the writing API — the shelf's own create door."""
    body: dict[str, Any] = {"title": title}
    if genre is not None:
        body["genre"] = genre
    if blurb is not None:
        body["blurb"] = blurb
    if target_words is not None:
        body["target_words"] = target_words
    with _client() as client:
        response = client.post("/api/writing/novels", json=body)
    response.raise_for_status()
    novel: dict[str, Any] = response.json()
    return novel


def patch_novel(novel_id: str, **fields: Any) -> dict[str, Any]:
    """Correct a seeded book (status, archive stamp) — only carried fields change."""
    with _client() as client:
        response = client.patch(f"/api/writing/novels/{novel_id}", json=fields)
    response.raise_for_status()
    novel: dict[str, Any] = response.json()
    return novel


def create_chapter(novel_id: str, title: str = "") -> dict[str, Any]:
    with _client() as client:
        response = client.post(f"/api/writing/novels/{novel_id}/chapters", json={"title": title})
    response.raise_for_status()
    chapter: dict[str, Any] = response.json()
    return chapter


def write_scene(
    chapter_id: str,
    body: str,
    *,
    title: str | None = None,
    setting: str | None = None,
    story_time: str | None = None,
) -> dict[str, Any]:
    """The prose write that feeds the activity ledger — the seam's trigger.
    Prose lives on a scene now (W4 §5): the chapter is the shell, so the write
    lands a scene under it, and the scene create feeds today's ledger. The
    workspace read legs (Task 11) seed the scene's own metadata through the
    same door — only carried fields join the body."""
    payload: dict[str, Any] = {"body": body}
    if title is not None:
        payload["title"] = title
    if setting is not None:
        payload["setting"] = setting
    if story_time is not None:
        payload["story_time"] = story_time
    with _client() as client:
        response = client.post(f"/api/writing/chapters/{chapter_id}/scenes", json=payload)
    response.raise_for_status()
    scene: dict[str, Any] = response.json()
    return scene


def patch_scene(scene_id: str, **fields: Any) -> dict[str, Any]:
    """Correct a seeded scene (W4 Task 11's read legs): only carried fields
    change — a body touch advances updated_at, the last-edited rule's source."""
    with _client() as client:
        response = client.put(f"/api/writing/scenes/{scene_id}", json=fields)
    response.raise_for_status()
    scene: dict[str, Any] = response.json()
    return scene


def continue_scene(scene_id: str) -> httpx.Response:
    """Stream a scene continuation through the real stack — the SSE door (W4 §5).

    The fake provider answers deterministically, so the response carries the
    whole frame sequence (data deltas, then done or error). The response is
    returned read: status, headers and text survive the client's close. The
    request is bare — no body at all."""
    with _client() as client:
        return client.post(f"/api/writing/scenes/{scene_id}/continue")


def get_novel(novel_id: str) -> dict[str, Any]:
    with _client() as client:
        response = client.get(f"/api/writing/novels/{novel_id}")
    response.raise_for_status()
    novel: dict[str, Any] = response.json()
    return novel


def get_activity() -> dict[str, Any]:
    with _client() as client:
        response = client.get("/api/writing/activity")
    response.raise_for_status()
    activity: dict[str, Any] = response.json()
    return activity


def set_theme(theme: str) -> None:
    """The settings row's theme — the shell adopts it at boot (dark face)."""
    with _client() as client:
        response = client.patch("/api/settings/theme", json={"theme": theme})
    response.raise_for_status()


def set_daily_goal(words: int | None) -> None:
    """The atelier's daily goal — the settings PATCH the banner's aggregate
    reads (W4 row 25). The stored locale rides along untouched: absent and
    null are different answers, so the read's own value is carried back."""
    with _client() as client:
        current = client.get("/api/settings")
        current.raise_for_status()
        response = client.patch(
            "/api/settings",
            json={"locale": current.json()["locale"], "daily_goal_words": words},
        )
    response.raise_for_status()


def set_author_name(name: str | None) -> None:
    """The profile's author name (W4 D9/D22) — the chrome user block's
    label. The stored locale rides along untouched, the daily-goal rule."""
    with _client() as client:
        current = client.get("/api/settings")
        current.raise_for_status()
        response = client.patch(
            "/api/settings",
            json={"locale": current.json()["locale"], "author_name": name},
        )
    response.raise_for_status()


def word_body(count: int) -> str:
    """A body of exactly ``count`` words under the shelf's one whitespace
    rule: plain ASCII tokens, single spaces, no leading or trailing gap."""
    return " ".join(f"Silbe{index}" for index in range(count))


@pytest.fixture(scope="module")
def stack() -> Iterator[Stack]:
    running = acquire_stack("writing", database=DATABASE, seed_user=False)
    yield running


@pytest.fixture
def installed(stack: Stack) -> Stack:
    """Every shelf test starts on a freshly installed, empty shelf.

    One reset, one setup POST, one delete of the setup's own novel: the
    instance is installed (the user row exists) and the population is the
    test's own to seed.
    """
    reset(DATABASE)
    result = complete_setup()
    delete_novel(str(result["novel_id"]))
    return stack


@pytest.fixture
def installed_with_atelier(stack: Stack) -> Stack:
    """The installed instance with its first book still standing: setup's
    own novel is NOT deleted, so the atelier's answers have a source row —
    the inheritance face of the new-book dialog (spec 7). The population is
    exactly the setup book; the test seeds nothing else."""
    reset(DATABASE)
    complete_setup()
    return stack


@pytest.fixture
def uninstalled(stack: Stack) -> Stack:
    """The suite instance's second face: emptied, nobody has set up yet."""
    reset(DATABASE)
    return stack
