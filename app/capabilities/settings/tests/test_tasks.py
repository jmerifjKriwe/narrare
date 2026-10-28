"""The effective task list: which provider serves each known key.

The page's task list no longer mirrors the kernel's keys; it renders one row
per ``KNOWN_TASK_KEYS`` entry and names the tier that actually serves it — the
exact assignment, a sibling's segment assignment, the default profile, or the
environment. The list is a read: resolving never writes, audits nothing, and
leaves the assignments untouched.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.main import app
from app.kernel.db.session import Session
from app.kernel.llm.resolution import KNOWN_TASK_KEYS

pytestmark = pytest.mark.timeout(30)


def _client() -> AsyncClient:
    """An HTTP client that drives the real application through ASGI."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _create_fake(client: AsyncClient, name: str) -> dict[str, object]:
    """Create one fake profile through the API, requiring the 201."""
    response = await client.post("/api/settings/profiles", json={"name": name, "kind": "fake"})
    assert response.status_code == 201, response.text
    return dict(response.json())


def _row(rows: list[dict[str, object]], task_key: str) -> dict[str, object]:
    """The one row of a task key, so a reordering shows up as a failed lookup."""
    [row] = [row for row in rows if row["task_key"] == task_key]
    return row


async def test_every_known_key_has_exactly_one_row() -> None:
    """The list is the kernel's keys, in their order — no mirror to drift."""
    async with _client() as client:
        response = await client.get("/api/settings/tasks")

    assert response.status_code == 200
    rows = response.json()
    assert [row["task_key"] for row in rows] == list(KNOWN_TASK_KEYS)
    assert len(rows) == len(KNOWN_TASK_KEYS)


async def test_the_environment_tier_reports_the_fake_and_names_no_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no profile and no environment choice the fake serves."""
    monkeypatch.delenv("NARRE_LLM_PROVIDER", raising=False)
    async with _client() as client:
        rows = (await client.get("/api/settings/tasks")).json()

    routed = [row for row in rows if row["assignable"]]
    assert {row["kind"] for row in routed} == {"fake"}
    assert all(row["profile_id"] is None and row["profile_name"] is None for row in routed)


async def test_the_environment_tier_reports_its_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``NARRE_LLM_PROVIDER`` names the serving adapter when no profile does."""
    monkeypatch.setenv("NARRE_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("NARRE_LLM_MODEL", "env-model")
    async with _client() as client:
        rows = (await client.get("/api/settings/tasks")).json()

    routed = [row for row in rows if row["assignable"]]
    assert {row["kind"] for row in routed} == {"openai-chat"}
    assert all(row["profile_id"] is None and row["profile_name"] is None for row in routed)


async def test_an_exact_assignment_names_that_profile() -> None:
    """The task's own assignment is the first tier, and the row names it."""
    async with _client() as client:
        await _create_fake(client, "Default")
        second = await _create_fake(client, "Second")
        await client.put("/api/settings/assignments/chat.ask", json={"profile_id": second["id"]})
        rows = (await client.get("/api/settings/tasks")).json()

    assert _row(rows, "chat.ask") == {
        "task_key": "chat.ask",
        "profile_id": second["id"],
        "profile_name": "Second",
        "kind": "fake",
        "assignable": True,
    }
    # The keys without an assignment still follow the default profile.
    assert _row(rows, "writing.continuation")["profile_name"] == "Default"


async def test_the_audit_only_key_is_not_routed_and_not_assignable() -> None:
    """``settings.test`` is audited by the probe, never served by the cascade."""
    async with _client() as client:
        await _create_fake(client, "Default")
        rows = (await client.get("/api/settings/tasks")).json()

    assert _row(rows, "settings.test") == {
        "task_key": "settings.test",
        "profile_id": None,
        "profile_name": None,
        "kind": "audit",
        "assignable": False,
    }
    assert all(row["assignable"] is True for row in rows if row["task_key"] != "settings.test")


async def test_a_task_inherits_the_segment_prefix_assignment() -> None:
    """A sibling's assignment stands in for the segment, visibly."""
    async with _client() as client:
        await _create_fake(client, "Default")
        second = await _create_fake(client, "Second")
        await client.put(
            "/api/settings/assignments/knowledge.check-consistency",
            json={"profile_id": second["id"]},
        )
        rows = (await client.get("/api/settings/tasks")).json()

    inherited = _row(rows, "knowledge.extract-entities")
    assert inherited["profile_id"] == second["id"]
    assert inherited["profile_name"] == "Second"


async def test_a_task_without_an_assignment_inherits_the_default() -> None:
    """The default profile is the third tier; every row names it."""
    async with _client() as client:
        default = await _create_fake(client, "Default")
        await _create_fake(client, "Second")
        rows = (await client.get("/api/settings/tasks")).json()

    for row in rows:
        if not row["assignable"]:
            continue
        assert row["profile_id"] == default["id"]
        assert row["profile_name"] == "Default"


async def test_listing_tasks_writes_nothing_and_audits_nothing() -> None:
    """Resolution is a read: no assignment is created, no call is recorded."""
    async with _client() as client:
        await _create_fake(client, "Default")
        assert (await client.get("/api/settings/tasks")).status_code == 200
        assignments = (await client.get("/api/settings/assignments")).json()

    assert assignments == []
    async with Session() as session:
        calls = await session.scalar(text("SELECT count(*) FROM llm_calls"))
    assert calls == 0
