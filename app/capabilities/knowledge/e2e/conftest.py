"""Full stack for the knowledge E2E: its own database, installed through the API.

The knowledge surfaces only exist on an installed instance, so every test
opens on a freshly installed one (the writing suite's pattern): ``installed``
empties the database — pytest-randomly shuffles, and no test may inherit
another's rows — and completes setup through the real API, the blank path
with known answers. The setup's own novel is deleted again straight after:
the user row is what makes the instance installed, and every test seeds
exactly the population it asserts on through the writing and knowledge APIs.

The helpers drive the same HTTP surface the browser uses — real API, real
Postgres, never a database insert. The one permitted fake is the provider
boundary (rule 2): both the LLM tier and the embedding tier default to their
``fake`` catalog entries, so the stack needs no provider configuration — the
extraction's suggestions and the check's findings derive from the seeded
prose alone (``app/kernel/llm/fake.py``: the distinct capitalized names, one
relation to the next name, a name carrying two numbers is a contradiction),
and the semantic search orders by the fake embedding's signed feature hash
(``app/kernel/embeddings/fake.py``). ``seed_canon`` steers the whole canon
through the real extraction → accept path, so the graph and dossiers legs
browse rows only the product's own doors ever wrote.

``DATABASE`` is defined here once; the tests import it and the API helpers
from this module.
"""

from collections.abc import Iterator  # noqa: TC003
from typing import Any

import httpx
import pytest

from app.kernel.db import testsupport
from app.kernel.testing.db_rows import reset
from app.kernel.testing.jobs import wait_for_job
from app.kernel.testing.stack import API_URL, Stack, acquire_stack

DATABASE = testsupport.test_database("narrare_v2_knowledge_e2e")

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


def create_novel(title: str) -> dict[str, Any]:
    """Seed one book through the writing API — the shelf's own create door."""
    with _client() as client:
        response = client.post("/api/writing/novels", json={"title": title})
    response.raise_for_status()
    novel: dict[str, Any] = response.json()
    return novel


def create_chapter(novel_id: str, title: str = "") -> dict[str, Any]:
    with _client() as client:
        response = client.post(f"/api/writing/novels/{novel_id}/chapters", json={"title": title})
    response.raise_for_status()
    chapter: dict[str, Any] = response.json()
    return chapter


def write_scene(chapter_id: str, body: str, *, title: str | None = None) -> dict[str, Any]:
    """The prose write the extraction and the check read: the chapter's prose
    lives on its scenes (W4 §5), joined in position order by the jobs."""
    payload: dict[str, Any] = {"body": body}
    if title is not None:
        payload["title"] = title
    with _client() as client:
        response = client.post(f"/api/writing/chapters/{chapter_id}/scenes", json=payload)
    response.raise_for_status()
    scene: dict[str, Any] = response.json()
    return scene


def set_theme(theme: str) -> None:
    """The settings row's theme — the shell adopts it at boot (dark face)."""
    with _client() as client:
        response = client.patch("/api/settings/theme", json={"theme": theme})
    response.raise_for_status()


def upload_document(name: str, text: str) -> dict[str, Any]:
    """Ingest one text document through the real multipart door — the same
    ``file`` field the sources page's picker sends."""
    with _client() as client:
        response = client.post(
            "/api/knowledge/documents",
            files={"file": (name, text.encode("utf-8"), "text/plain")},
        )
    response.raise_for_status()
    document: dict[str, Any] = response.json()
    return document


def enqueue_extraction(novel_id: str, chapter_id: str) -> str:
    """Queue the chapter's extraction and return the job id (202, the lane)."""
    with _client() as client:
        response = client.post(
            f"/api/knowledge/extraction/{novel_id}", json={"chapter_id": chapter_id}
        )
    assert response.status_code == 202
    return str(response.json()["job_id"])


def enqueue_consistency(novel_id: str) -> str:
    """Queue the whole-novel check and return the job id."""
    with _client() as client:
        response = client.post(f"/api/knowledge/consistency/{novel_id}")
    assert response.status_code == 202
    return str(response.json()["job_id"])


def list_suggestions(novel_id: str) -> list[dict[str, Any]]:
    with _client() as client:
        response = client.get(f"/api/knowledge/novels/{novel_id}/suggestions")
    response.raise_for_status()
    suggestions: list[dict[str, Any]] = response.json()
    return suggestions


def accept_suggestion(suggestion_id: str) -> dict[str, Any]:
    with _client() as client:
        response = client.post(f"/api/knowledge/suggestions/{suggestion_id}/accept")
    response.raise_for_status()
    accepted: dict[str, Any] = response.json()
    return accepted


def list_entities(novel_id: str) -> list[dict[str, Any]]:
    with _client() as client:
        response = client.get(f"/api/knowledge/novels/{novel_id}/entities")
    response.raise_for_status()
    entities: list[dict[str, Any]] = response.json()
    return entities


def list_relations(novel_id: str) -> list[dict[str, Any]]:
    with _client() as client:
        response = client.get(f"/api/knowledge/novels/{novel_id}/relations")
    response.raise_for_status()
    relations: list[dict[str, Any]] = response.json()
    return relations


def patch_relation(relation_id: str, **fields: Any) -> dict[str, Any]:
    """Correct a seeded edge (type, note) — only carried fields change."""
    with _client() as client:
        response = client.patch(f"/api/knowledge/relations/{relation_id}", json=fields)
    response.raise_for_status()
    relation: dict[str, Any] = response.json()
    return relation


def create_entity(
    novel_id: str, *, name: str, entity_type: str, content: str = ""
) -> dict[str, Any]:
    """Create one entity by hand through the product's own create door."""
    with _client() as client:
        response = client.post(
            "/api/knowledge/entities",
            json={"novel_id": novel_id, "name": name, "type": entity_type, "content": content},
        )
    response.raise_for_status()
    entity: dict[str, Any] = response.json()
    return entity


def add_relation(
    entity_id: str, to_entity_id: str, relation_type: str, note: str | None = None
) -> dict[str, Any]:
    """Create one directed edge through the entity's own relation door."""
    with _client() as client:
        response = client.post(
            f"/api/knowledge/entities/{entity_id}/relations",
            json={"to_entity_id": to_entity_id, "relation_type": relation_type, "note": note},
        )
    response.raise_for_status()
    relation: dict[str, Any] = response.json()
    return relation


def seed_canon(
    novel_id: str, chapter_id: str, *, accept_order: list[str] | None = None
) -> list[dict[str, Any]]:
    """Extraction → accept, through the real API: the canon the graph and the
    dossiers browse. The fake derives the proposals from the chapter's prose;
    the accept order steers which proposed relations land (a proposal whose
    target is still pending skips, D8) — the default is the queue's own order.
    Returns the entities, oldest first (the accept order)."""
    job_id = enqueue_extraction(novel_id, chapter_id)
    with _client() as client:
        job = wait_for_job(client, job_id)
    assert job["status"] == "done", job
    suggestions = list_suggestions(novel_id)
    if accept_order is not None:
        rank = {name: index for index, name in enumerate(accept_order)}
        suggestions = sorted(suggestions, key=lambda row: rank[row["name"]])
    for suggestion in suggestions:
        accept_suggestion(str(suggestion["id"]))
    return list_entities(novel_id)


@pytest.fixture(scope="module")
def stack() -> Iterator[Stack]:
    running = acquire_stack("knowledge", database=DATABASE, seed_user=False)
    yield running


@pytest.fixture
def installed(stack: Stack) -> Stack:
    """Every knowledge test starts on a freshly installed, empty instance.

    One reset, one setup POST, one delete of the setup's own novel: the
    instance is installed (the user row exists) and the population is the
    test's own to seed.
    """
    reset(DATABASE)
    result = complete_setup()
    delete_novel(str(result["novel_id"]))
    return stack
