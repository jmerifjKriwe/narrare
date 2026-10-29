"""The prompts surface: list, inspect, override, reset — broken templates named at save.

Every save-time refusal comes back named: the render's own reason
(``syntax``, ``undefined-variable``, ``include-cycle``, …), the contract's
``contract``, the scope rules' ``novel-scope``, and ``unknown-novel`` — a
``novel_id`` naming another user's novel is refused by name, never trusted.
The PUT path upserts atomically: two saves racing on an empty scope both
land, the loser as the update, never a 500.
"""

import asyncio
from contextlib import suppress
from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.main import app
from app.capabilities.prompts.service import PromptRefusedError, PromptService
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.models import Novel
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user
from app.kernel.prompts import get_registry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.timeout(30)

CONTINUATION = "writing.continuation"
CHAT = "chat.ask"
EXTRACT = "knowledge.extract-entities"
CONSISTENCY = "knowledge.check-consistency"


def _client() -> AsyncClient:
    """An HTTP client that drives the real application through ASGI."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _novel(user_id: UUID = LOCAL_USER_ID, title: str = "Der Nebel") -> UUID:
    """One novel row, its id back."""
    async with Session() as session:
        novel = Novel(user_id=user_id, title=title)
        session.add(novel)
        await session.commit()
        return novel.id


async def _rows() -> list[tuple[str, UUID | None, str]]:
    """Every stored override row: key, novel tier, content."""
    async with Session() as session:
        found = (
            await session.execute(
                text("SELECT prompt_key, novel_id, content FROM prompt_templates")
            )
        ).all()
    return [(row.prompt_key, row.novel_id, row.content) for row in found]


# --- the happy paths -------------------------------------------------------


async def test_a_valid_override_saves_and_shows_in_the_detail() -> None:
    """PUT stores the row in the global tier; GET detail shows it in force."""
    async with _client() as client:
        saved = await client.put(
            f"/api/prompts/{CONTINUATION}",
            json={"content": "Novel: {{ novel_title }} — write on."},
        )
        assert saved.status_code == 200, saved.text
        body = saved.json()
        assert body["override"] == {
            "scope": "global",
            "content": "Novel: {{ novel_title }} — write on.",
        }
        assert body["effective_content"] == "Novel: {{ novel_title }} — write on."

        fetched = await client.get(f"/api/prompts/{CONTINUATION}")
        assert fetched.status_code == 200
        assert fetched.json()["override"]["scope"] == "global"
        assert fetched.json()["effective_content"] == "Novel: {{ novel_title }} — write on."

    rows = await _rows()
    assert len(rows) == 1
    assert rows[0][0] == CONTINUATION
    assert rows[0][1] is None  # the global tier


async def test_a_second_put_replaces_the_row_instead_of_stacking_one() -> None:
    """The upsert: the scope's row is rewritten in place, one row total."""
    async with _client() as client:
        first = await client.put(
            f"/api/prompts/{CONTINUATION}", json={"content": "First: {{ tail }}"}
        )
        second = await client.put(
            f"/api/prompts/{CONTINUATION}", json={"content": "Second: {{ tail }}"}
        )
        assert (first.status_code, second.status_code) == (200, 200)

    rows = await _rows()
    assert len(rows) == 1
    assert rows[0][2] == "Second: {{ tail }}"


async def test_a_novel_override_writes_the_novel_row_and_leaves_the_global_tier() -> None:
    """PUT with ``novel_id`` writes the novel row; the global tier stays empty."""
    novel_id = await _novel()
    async with _client() as client:
        saved = await client.put(
            f"/api/prompts/{CONTINUATION}",
            json={"content": "Weiter: {{ tail }}", "novel_id": str(novel_id)},
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["override"]["scope"] == "novel"

        listed = (await client.get("/api/prompts", params={"novel_id": str(novel_id)})).json()
        by_key = {row["key"]: row for row in listed}
        assert by_key[CONTINUATION]["override_novel"] is True
        assert by_key[CONTINUATION]["override_global"] is False

        plain = (await client.get("/api/prompts")).json()
        assert {row["key"]: row for row in plain}[CONTINUATION]["override_novel"] is False
        assert {row["key"]: row for row in plain}[CONTINUATION]["override_global"] is False


async def test_the_detail_shows_the_sample_variables_and_the_bundled_template() -> None:
    """The editor's inputs: the bundled source, the sample factory's legend."""
    async with _client() as client:
        detail = (await client.get(f"/api/prompts/{CONTINUATION}")).json()

    assert detail["bundled_content"] == get_registry().spec(CONTINUATION).template
    assert detail["override"] is None
    assert detail["effective_content"] == detail["bundled_content"]
    variables = {variable["name"]: variable["example"] for variable in detail["variables"]}
    assert set(variables) >= {"novel_title", "chapter_title", "tail"}
    assert all(variables.values())  # every example is a non-empty string


async def test_the_diff_shows_the_bundled_against_the_override() -> None:
    """No override: the diff names ``None``. After a save: the override's text."""
    content = "Q: {{ question }}\n{{ sources }}"
    async with _client() as client:
        clean = await client.get(f"/api/prompts/{CHAT}/diff")
        assert clean.status_code == 200
        assert clean.json()["override_content"] is None
        assert clean.json()["bundled_content"] == get_registry().spec(CHAT).template

        saved = await client.put(f"/api/prompts/{CHAT}", json={"content": content})
        assert saved.status_code == 200, saved.text

        changed = await client.get(f"/api/prompts/{CHAT}/diff")
        assert changed.json()["override_content"] == content


async def test_the_list_shows_all_four_keys_with_their_facts() -> None:
    """Four bundled keys; ``chat.ask`` alone carries no novel scope."""
    async with _client() as client:
        listed = (await client.get("/api/prompts")).json()

    by_key = {row["key"]: row for row in listed}
    assert set(by_key) == {CONTINUATION, CHAT, EXTRACT, CONSISTENCY}
    assert by_key[CONTINUATION]["novel_scopable"] is True
    assert by_key[EXTRACT]["novel_scopable"] is True
    assert by_key[CONSISTENCY]["novel_scopable"] is True
    assert by_key[CHAT]["novel_scopable"] is False
    for row in listed:
        assert row["override_global"] is False
        assert row["override_novel"] is False
        assert 0 < len(row["bundled_summary"]) <= 120
    assert by_key[CONTINUATION]["bundled_summary"].startswith("Novel:")


async def test_deleting_the_global_tier_leaves_the_novel_row_in_place() -> None:
    """DELETE removes exactly its scope; the other tier survives."""
    novel_id = await _novel()
    async with _client() as client:
        await client.put(
            f"/api/prompts/{CONTINUATION}",
            json={"content": "Pro Roman: {{ tail }}", "novel_id": str(novel_id)},
        )
        await client.put(f"/api/prompts/{CONTINUATION}", json={"content": "Global: {{ tail }}"})

        deleted = await client.delete(f"/api/prompts/{CONTINUATION}")
        assert deleted.status_code == 204

        detail = await client.get(
            f"/api/prompts/{CONTINUATION}", params={"novel_id": str(novel_id)}
        )
        assert detail.json()["override"]["scope"] == "novel"

    rows = await _rows()
    assert len(rows) == 1
    assert rows[0][1] is not None  # the novel tier


async def test_deleting_an_absent_override_is_still_a_204() -> None:
    """The reset is idempotent: a scope with no row deletes to no content."""
    async with _client() as client:
        deleted = await client.delete(f"/api/prompts/{CONTINUATION}")
        assert deleted.status_code == 204


# --- the save-time gate ----------------------------------------------------


async def test_an_unknown_variable_is_refused_by_name() -> None:
    """A template naming a variable the render does not carry is a 422."""
    async with _client() as client:
        saved = await client.put(
            f"/api/prompts/{CONTINUATION}", json={"content": "Hello {{ nope }}"}
        )
        assert saved.status_code == 422
        body = saved.json()["detail"]
        assert body["reason"] == "undefined-variable"
        assert "nope" in body["detail"]
        assert await _rows() == []  # nothing half-valid was stored


async def test_a_syntax_error_is_refused_by_name() -> None:
    """A broken ``{% %}`` is refused ``syntax`` before anything renders."""
    async with _client() as client:
        saved = await client.put(
            f"/api/prompts/{CONTINUATION}", json={"content": "{% if %} broken"}
        )
        assert saved.status_code == 422
        assert saved.json()["detail"]["reason"] == "syntax"
        assert await _rows() == []


async def test_an_override_that_drops_the_chat_contract_is_refused() -> None:
    """A re-voice that loses the marked sources fails ``chat.ask``'s contract."""
    async with _client() as client:
        saved = await client.put(
            f"/api/prompts/{CHAT}", json={"content": "Question only: {{ question }}"}
        )
        assert saved.status_code == 422
        body = saved.json()["detail"]
        assert body["reason"] == "contract"
        assert "contract" in body["detail"]
        assert await _rows() == []


async def test_a_novel_scoped_save_on_a_global_only_key_names_the_key() -> None:
    """``chat.ask`` carries no novel scope; the refusal names it."""
    novel_id = await _novel()
    async with _client() as client:
        saved = await client.put(
            f"/api/prompts/{CHAT}",
            json={"content": "Q: {{ question }}\n{{ sources }}", "novel_id": str(novel_id)},
        )
        assert saved.status_code == 422
        body = saved.json()["detail"]
        assert body["reason"] == "novel-scope"
        assert CHAT in body["detail"]
        assert await _rows() == []


async def test_an_include_cycle_is_refused_by_name() -> None:
    """A template that includes itself is refused before it can loop forever."""
    async with _client() as client:
        saved = await client.put(
            f"/api/prompts/{CONTINUATION}",
            json={"content": "{% include 'writing.continuation' %}"},
        )
        assert saved.status_code == 422
        assert saved.json()["detail"]["reason"] == "include-cycle"
        assert await _rows() == []


async def test_an_unknown_key_is_a_404_on_every_route() -> None:
    """The key set is closed: users override keys, they never invent them."""
    async with _client() as client:
        saved = await client.put("/api/prompts/nope.nope", json={"content": "anything at all"})
        assert saved.status_code == 404
        fetched = await client.get("/api/prompts/nope.nope")
        assert fetched.status_code == 404
        deleted = await client.delete("/api/prompts/nope.nope")
        assert deleted.status_code == 404


async def test_a_novel_id_of_another_user_is_a_named_422() -> None:
    """A foreign novel's id is never trusted: the authorized read refuses it."""
    await seed_user(UUID("00000000-0000-0000-0000-000000000002"))
    foreign = await _novel(UUID("00000000-0000-0000-0000-000000000002"), "Fremd")
    async with _client() as client:
        saved = await client.put(
            f"/api/prompts/{CONTINUATION}",
            json={"content": "Weiter: {{ tail }}", "novel_id": str(foreign)},
        )
        assert saved.status_code == 422
        body = saved.json()["detail"]
        assert body["reason"] == "unknown-novel"
        assert str(foreign) in body["detail"]
        assert await _rows() == []


# --- the atomic upsert ------------------------------------------------------


async def test_two_saves_racing_on_an_empty_scope_both_land(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The stale-read window: the loser of the read lands as the update, never a 500.

    The loser's scope read is held on its empty result — provably, before the
    sibling may save — and released only after the sibling's commit; the save
    must then still land, one row, no ``IntegrityError``. The atomic upsert
    issues no scope read at all, so on it the hold never engages (the wait
    times out quietly) and the two saves simply land one after the other —
    the assertion is theirs either way. Real ASGI requests serialize too
    narrowly to hit this window on demand, so the read is held, the way the
    settings suite freezes its create race.
    """

    from app.kernel.prompts.models import PromptTemplateRepository

    original_row = PromptTemplateRepository._row  # pyright: ignore[reportPrivateUsage]  the frozen read is the seam the old save read through
    stale_sessions: list[AsyncSession] = []
    read_held = asyncio.Event()
    sibling_done = asyncio.Event()

    async def held_row(
        self: PromptTemplateRepository,
        prompt_key: str,
        novel_id: UUID | None,
        **_: object,
    ) -> object:
        snapshot = await original_row(self, prompt_key, novel_id)
        if stale_sessions and self.session is stale_sessions[0] and snapshot is None:
            # Only the stale read waits: the atomic save's re-read after its
            # upsert already sees a row and must pass through untouched.
            read_held.set()
            await sibling_done.wait()
        return snapshot

    monkeypatch.setattr(PromptTemplateRepository, "_row", held_row)

    async with Session() as stale, Session() as sibling:
        stale_sessions.append(stale)
        stale_save = asyncio.create_task(
            PromptService(stale, LOCAL_USER_ID).save(CONTINUATION, "the stale save", None)
        )
        # No read, no window: on the atomic upsert the hold never engages
        # and the wait times out quietly.
        with suppress(TimeoutError):
            await asyncio.wait_for(read_held.wait(), 1)
        await PromptService(sibling, LOCAL_USER_ID).save(CONTINUATION, "the fresh save", None)
        sibling_done.set()
        await asyncio.wait_for(stale_save, 10)

    rows = await _rows()
    assert len(rows) == 1
    assert rows[0][2] in ("the stale save", "the fresh save")


async def test_the_service_vocabulary_stays_closed() -> None:
    """The refusal reasons the API can answer are exactly these."""
    from app.capabilities.prompts.service import REFUSAL_REASONS

    assert set(REFUSAL_REASONS) == {"novel-scope", "unknown-novel", "contract"}


def test_the_refusal_error_keeps_reason_and_detail() -> None:
    """``PromptRefusedError`` carries what the 422 body answers with."""
    error = PromptRefusedError("novel-scope", "'chat.ask' carries no novel scope")
    assert error.reason == "novel-scope"
    assert str(error) == "'chat.ask' carries no novel scope"
