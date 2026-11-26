"""Full stack for the prompts E2E: its own database, installed through the API.

The Prompts surface is a post-setup surface behind the same setup gate as the
shelf and the settings pages, so every test opens on a freshly installed
instance (the settings suite's pattern): ``installed`` empties the database —
pytest-randomly shuffles, and no test may inherit another's rows — and
completes setup through the real API, the blank path with known answers. The
setup's own novel is deleted again straight after: every test seeds exactly
the population it asserts on through the APIs.

The helpers drive the same HTTP surface the browser uses — real API, real
Postgres, never a database insert. The LLM boundary holds the suite's one
permitted fake: a provider row of kind ``fake`` whose models answer locally,
so the live test leg runs against the wire without a network call — the fake
is configuration, never a test branch (rule 2).

``DATABASE`` is defined here once; the tests import it and the API helpers
from this module.
"""

from typing import TYPE_CHECKING, Any

import httpx
import pytest
from playwright.sync_api import Page, expect

from app.kernel.db import testsupport
from app.kernel.testing.db_rows import reset
from app.kernel.testing.stack import API_URL, WEB_URL, Stack, acquire_stack

if TYPE_CHECKING:
    from collections.abc import Iterator

DATABASE = testsupport.test_database("narrare_v2_prompts_e2e")

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


def create_novel(title: str = "Dead Signal") -> str:
    """One book through the writing API; return its id."""
    with _client() as client:
        response = client.post("/api/writing/novels", json={"title": title})
    assert response.status_code == 201, response.text
    novel: dict[str, Any] = response.json()
    return str(novel["id"])


def create_chapter(novel_id: str, title: str = "") -> str:
    """One chapter under the book; return its id."""
    with _client() as client:
        response = client.post(f"/api/writing/novels/{novel_id}/chapters", json={"title": title})
    assert response.status_code == 201, response.text
    chapter: dict[str, Any] = response.json()
    return str(chapter["id"])


def write_scene(chapter_id: str, body: str, title: str | None = None) -> str:
    """One prose scene under the chapter — the writer's latest-touched scene
    the live test's assembly rides; return its id."""
    payload: dict[str, Any] = {"body": body}
    if title is not None:
        payload["title"] = title
    with _client() as client:
        response = client.post(f"/api/writing/chapters/{chapter_id}/scenes", json=payload)
    assert response.status_code == 201, response.text
    scene: dict[str, Any] = response.json()
    return str(scene["id"])


def create_fake_provider(name: str = "Lokal-E2E") -> str:
    """One fake-kind provider: no endpoint, no key — its models answer
    locally (the live test's honest mark)."""
    with _client() as client:
        response = client.post("/api/settings/providers", json={"name": name, "kind": "fake"})
    assert response.status_code == 201, response.text
    provider: dict[str, Any] = response.json()
    return str(provider["id"])


def create_model(
    provider_id: str, name: str = "Lokal-Schreiber", model_id: str = "llama3:8b"
) -> str:
    """One model under the provider; the first is the default, so the whole
    cascade — the live test's tier ride included — answers through it."""
    with _client() as client:
        response = client.post(
            "/api/settings/models",
            json={"name": name, "provider_id": provider_id, "model": model_id},
        )
    assert response.status_code == 201, response.text
    model: dict[str, Any] = response.json()
    return str(model["id"])


def set_theme(theme: str | None) -> None:
    """The settings row's theme — the shell adopts it at boot (dark face)."""
    with _client() as client:
        response = client.patch("/api/settings/theme", json={"theme": theme})
    response.raise_for_status()


def save_override(key: str, content: str, novel_id: str | None = None) -> httpx.Response:
    """The raw PUT — the seeding legs read the marks it moves; the refusal
    legs read the status. ``novel_id`` absent saves the global tier."""
    with _client() as client:
        return client.put(
            f"/api/prompts/{key}",
            json={"content": content, "novel_id": novel_id},
        )


def goto_prompts(page: Page) -> Page:
    """Open the Prompts surface and wait for its ready-state surface: the
    page's testid, then the catalog's cards, then the editor — the reads
    only render once they answered."""
    page.goto(f"{WEB_URL}/settings/prompts")
    expect_prompts(page)
    return page


def expect_prompts(page: Page) -> None:
    """The page's own ready face: the testid stood, the catalog answered
    (five bundled keys), the editor opened on the first key."""
    expect(page.get_by_test_id("prompts-page")).to_be_visible()
    expect(page.get_by_test_id("prompt-card")).to_have_count(5)
    expect(page.get_by_test_id("prompts-editor")).to_be_visible()


@pytest.fixture(scope="module")
def stack() -> Iterator[Stack]:
    running = acquire_stack("prompts", database=DATABASE, seed_user=False)
    yield running


@pytest.fixture
def installed(stack: Stack) -> Stack:
    """Every prompts test starts on a freshly installed, empty instance."""
    reset(DATABASE)
    result = complete_setup()
    delete_novel(str(result["novel_id"]))
    return stack
