"""Full stack for the settings E2E: its own database, installed through the API.

The Allgemein surface is a post-setup surface behind the same setup gate as the
shelf, so every test opens on a freshly installed instance (the planning
suite's pattern): ``installed`` empties the database — pytest-randomly
shuffles, and no test may inherit another's rows — and completes setup through
the real API, the blank path with known answers. The setup's own novel is
deleted again straight after: settings edits the user row, and every test
seeds exactly the population it asserts on through the settings API.

The helpers drive the same HTTP surface the browser uses — real API, real
Postgres, never a database insert. Settings is pure CRUD (no LLM tier), so no
provider fake is needed at all; even the offline card's hide path runs without
a configured endpoint, because the tasks read is pure resolution — a provider
and a default model created through the API are enough for the cascade to
answer a non-fake driver, and no network call ever leaves.

``DATABASE`` is defined here once; the tests import it and the API helpers
from this module.
"""

import time
from collections.abc import Iterator  # noqa: TC003
from typing import Any

import httpx
import pytest
from playwright.sync_api import Page, expect

from app.kernel.db import testsupport
from app.kernel.testing.db_rows import reset
from app.kernel.testing.stack import API_URL, WEB_URL, Stack, acquire_stack

DATABASE = testsupport.test_database("narrare_v2_settings_e2e")

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


def read_settings() -> dict[str, Any]:
    """The preference row as the server keeps it — the browser's read, asked
    directly."""
    with _client() as client:
        response = client.get("/api/settings")
    response.raise_for_status()
    row: dict[str, Any] = response.json()
    return row


def patch_settings(payload: dict[str, Any]) -> httpx.Response:
    """The raw PATCH — the refusal legs read the status, the seed legs the row."""
    with _client() as client:
        return client.patch("/api/settings", json=payload)


def seed_settings(**fields: Any) -> dict[str, Any]:
    """Seed the row through the PATCH, the locale always carried (the
    schema's own rule); a ``None`` value is the carried null."""
    payload: dict[str, Any] = {"locale": None}
    payload.update(fields)
    response = patch_settings(payload)
    response.raise_for_status()
    row: dict[str, Any] = response.json()
    return row


def set_theme(theme: str | None) -> None:
    """The settings row's theme — the shell adopts it at boot (dark face)."""
    with _client() as client:
        response = client.patch("/api/settings/theme", json={"theme": theme})
    response.raise_for_status()


def read_tasks() -> list[dict[str, Any]]:
    """The cascade's answer per known task key — the offline card's truth."""
    with _client() as client:
        response = client.get("/api/settings/tasks")
    response.raise_for_status()
    tasks: list[dict[str, Any]] = response.json()
    return tasks


def create_provider(name: str = "Cloud", api_key: str = "sk-e2e-hide-key") -> str:
    """One provider endpoint through the create door; return its id."""
    with _client() as client:
        response = client.post(
            "/api/settings/providers",
            json={
                "name": name,
                "kind": "openai-chat",
                "base_url": "https://llm.example.com/v1",
                "api_key": api_key,
            },
        )
    assert response.status_code == 201, response.text
    provider: dict[str, Any] = response.json()
    return str(provider["id"])


def create_default_model(provider_id: str, name: str = "Cloud-Schreiber") -> str:
    """One model under the provider; the first is the default, so the whole
    cascade answers through it — no assignment needed."""
    with _client() as client:
        response = client.post(
            "/api/settings/models",
            json={"name": name, "provider_id": provider_id, "model": "test-model"},
        )
    assert response.status_code == 201, response.text
    model: dict[str, Any] = response.json()
    return str(model["id"])


def await_settings(**fields: Any) -> dict[str, Any]:
    """Poll the settings read until the row answers ``fields`` — a browser
    write's landing on the wire, not a sleep-and-hope. The last read rides
    the failure so a wrong expectation names itself."""
    deadline = time.monotonic() + 10.0
    row = read_settings()
    while time.monotonic() < deadline:
        if all(row[key] == value for key, value in fields.items()):
            return row
        time.sleep(0.1)
        row = read_settings()
    raise AssertionError(f"the settings row never answered {fields!r}; last read: {row!r}")


def goto_settings(page: Page) -> Page:
    """Open the Allgemein surface and wait for its ready-state surface."""
    page.goto(f"{WEB_URL}/settings")
    expect_settings(page)
    return page


def expect_settings(page: Page) -> None:
    """The page's own testid, then the form: the row stood, the fields open."""
    expect(page.get_by_test_id("settings-page")).to_be_visible()
    expect(page.get_by_label("Autorenname")).to_be_visible()


@pytest.fixture(scope="module")
def stack() -> Iterator[Stack]:
    running = acquire_stack("settings", database=DATABASE, seed_user=False)
    yield running


@pytest.fixture
def installed(stack: Stack) -> Stack:
    """Every settings test starts on a freshly installed, empty instance.

    One reset, one setup POST, one delete of the setup's own novel: the
    instance is installed (the user row exists) and the population is the
    test's own to seed.
    """
    reset(DATABASE)
    result = complete_setup()
    delete_novel(str(result["novel_id"]))
    return stack
