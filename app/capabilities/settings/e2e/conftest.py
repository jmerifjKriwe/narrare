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
a configured endpoint, because the driver read is pure resolution — a provider
and a default model created through the API are enough for the cascade to
answer ``configured``, and no network call ever leaves.

The one exception is the update check: the stack's ``NARRA_UPDATE_CHECK_URL``
points at the session's ``ReleaseVendor`` (a real local server), so the banner
leg exercises the browser, the API and the release source without GitHub. The
vendor's default tag is the running version — every other test sees no banner.

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
from app.kernel.testing.release_vendor import ReleaseVendor
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


def dismiss_update(version: str) -> None:
    """Stop announcing ``version`` through the API, as the shell's dialog does.

    The update leg's cleanup uses this: the suite shares one settings database,
    and a later module must start on a row that announces nothing.
    """
    with _client() as client:
        response = client.post("/api/updates/dismiss", json={"version": version})
    response.raise_for_status()


def read_driver() -> dict[str, Any]:
    """The instance's driver kind as one word — the offline card's truth."""
    with _client() as client:
        response = client.get("/api/settings/driver")
    response.raise_for_status()
    driver: dict[str, Any] = response.json()
    return driver


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


def create_fake_provider(name: str = "Lokal-E2E") -> str:
    """One fake-kind provider: no endpoint, no key — the gate passes it, and
    its models answer locally (the honest 100%-lokal tile's own fact)."""
    with _client() as client:
        response = client.post("/api/settings/providers", json={"name": name, "kind": "fake"})
    assert response.status_code == 201, response.text
    provider: dict[str, Any] = response.json()
    assert provider["api_key_mask"] is None
    return str(provider["id"])


def create_model(
    provider_id: str,
    name: str = "Cloud-Schreiber",
    model_id: str = "test-model",
    **tunables: Any,
) -> str:
    """One model with stored tunables (``max_output_tokens`` and friends) —
    the stored ceiling is the only one resolution caps a profile at."""
    with _client() as client:
        response = client.post(
            "/api/settings/models",
            json={"name": name, "provider_id": provider_id, "model": model_id, **tunables},
        )
    assert response.status_code == 201, response.text
    model: dict[str, Any] = response.json()
    return str(model["id"])


def read_providers() -> list[dict[str, Any]]:
    """The provider rows as every read shows them — the mask, never a key."""
    with _client() as client:
        response = client.get("/api/settings/providers")
    response.raise_for_status()
    providers: list[dict[str, Any]] = response.json()
    return providers


def read_tasks() -> list[dict[str, Any]]:
    """The effective view: one row per known task key, the cascade's answer."""
    with _client() as client:
        response = client.get("/api/settings/tasks")
    response.raise_for_status()
    tasks: list[dict[str, Any]] = response.json()
    return tasks


def read_assignments() -> list[dict[str, Any]]:
    """The stored assignment rows: the model and the profile choice."""
    with _client() as client:
        response = client.get("/api/settings/assignments")
    response.raise_for_status()
    assignments: list[dict[str, Any]] = response.json()
    return assignments


def _task_row(task_key: str) -> dict[str, Any]:
    for row in read_tasks():
        if row["task_key"] == task_key:
            return row
    raise AssertionError(f"no tasks row for {task_key}")


def await_tasks(task_key: str, **fields: Any) -> dict[str, Any]:
    """Poll the tasks read until one task's row answers ``fields`` — a
    browser write's landing on the cascade, not a sleep-and-hope. The last
    read rides the failure so a wrong expectation names itself."""
    deadline = time.monotonic() + 10.0
    row = _task_row(task_key)
    while time.monotonic() < deadline:
        if all(row[key] == value for key, value in fields.items()):
            return row
        time.sleep(0.1)
        row = _task_row(task_key)
    raise AssertionError(f"the tasks row {task_key} never answered {fields!r}; last: {row!r}")


def create_novel(title: str = "Das Atelier-Buch") -> str:
    """One book through the writing API — the pointer door's target."""
    with _client() as client:
        response = client.post("/api/writing/novels", json={"title": title})
    assert response.status_code == 201, response.text
    novel: dict[str, Any] = response.json()
    return str(novel["id"])


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


# The AI page's hero heading (de-DE context) — the ready face leans on it.
AI_HEADING_DE = "KI-Regeln & Modell-Architektur"


def goto_ai_rules(page: Page) -> Page:
    """Open the AI-Regeln surface and wait for its ready-state surface: the
    page's testid, then the hero heading, then the provider section's — the
    sections only render once the five strict reads answered."""
    page.goto(f"{WEB_URL}/settings/ai-regeln")
    expect_ai_rules(page)
    return page


def expect_ai_rules(page: Page) -> None:
    """The AI page's own ready face: the testid stood, the reads answered
    (the provider section's heading is behind the read gate)."""
    expect(page.get_by_test_id("ai-rules-page")).to_be_visible()
    expect(page.get_by_role("heading", name=AI_HEADING_DE)).to_be_visible()
    expect(page.get_by_role("heading", name="1. Provider & Schnittstellen")).to_be_visible()


def expect_settings(page: Page) -> None:
    """The page's own testid, then the form: the row stood, the fields open.
    The submit button is the language-independent ready face — the form only
    renders once the strict read answered (the isolation leg boots in
    English, every other leg in German)."""
    expect(page.get_by_test_id("settings-page")).to_be_visible()
    expect(page.locator('form button[type="submit"]')).to_be_visible()


@pytest.fixture(scope="session")
def release_vendor() -> Iterator[ReleaseVendor]:
    """The update check's release source for this worker: a real local server.

    The settings stack is the one suite that points ``NARRA_UPDATE_CHECK_URL``
    at a stand-in, so the browser's banner can be exercised without GitHub. The
    default tag is the running version, so every other settings test sees no
    banner; the update leg changes the mutable ``state`` for its own walk.
    """
    with ReleaseVendor() as vendor:
        yield vendor


@pytest.fixture(scope="module")
def stack(release_vendor: ReleaseVendor) -> Iterator[Stack]:
    running = acquire_stack(
        "settings",
        database=DATABASE,
        seed_user=False,
        env={
            "NARRA_UPDATE_CHECK_URL": release_vendor.base_url,
            "NARRA_UPDATE_CHECK_CACHE_SECONDS": "0",
        },
    )
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
