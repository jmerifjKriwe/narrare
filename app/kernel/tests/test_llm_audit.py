"""The LlmCall audit: the table, then the writer, then what handlers record.

Plan §3.4: one row per provider call — prompt and answer capped at 64 KB,
tokens, latency, status. cost_usd stays NULL until WP2's catalog prices it
and no profile_id exists until a profile table does; the column set is pinned
here so a drift fails at its first commit instead of in WP2's evidence.
"""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.kernel.db.base import Base
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user
from app.kernel.llm.audit import CAP, record_call
from app.kernel.llm.models import LlmCall

LLM_CALL_COLUMNS = {
    "id",
    "user_id",
    "novel_id",
    "task_key",
    "prompt_key",
    "provider_kind",
    "model",
    "input_tokens",
    "output_tokens",
    "cost_usd",
    "latency_ms",
    "status",
    "error",
    "prompt_text",
    "response_text",
    "truncated",
    "created_at",
}


@pytest.mark.usefixtures("schema")
def test_the_llm_calls_table_is_registered_with_exactly_these_columns() -> None:
    table = Base.metadata.tables[LlmCall.__tablename__]
    assert set(table.columns.keys()) == LLM_CALL_COLUMNS


@pytest.mark.usefixtures("schema")
def test_the_jobs_and_contracts_tables_are_still_registered() -> None:
    tables = Base.metadata.tables
    assert "jobs" in tables
    assert "novels" in tables
    assert "chapters" in tables


OWNER = uuid4()


@pytest.fixture
async def a_user(empty_tables: None) -> None:
    """The users row a user-owned audit row needs: the key reaches users."""
    await seed_user(OWNER)


async def _record(
    prompt_text: str, response_text: str, session: AsyncSession | None = None
) -> None:
    """Record one call on the given session, or a session of the test's own."""
    if session is not None:
        await record_call(
            session,
            user_id=OWNER,
            task_key="knowledge.extract-entities",
            provider_kind="fake",
            model="fake",
            latency_ms=3,
            status="ok",
            prompt_text=prompt_text,
            response_text=response_text,
        )
        return
    async with Session() as own:
        await _record(prompt_text, response_text, own)
        await own.commit()


async def _the_row() -> LlmCall:
    """The audit's single row, fresh from the database."""
    async with Session() as session:
        rows = (await session.execute(text("SELECT id FROM llm_calls"))).scalars().all()
        assert len(rows) == 1
        row = await session.get(LlmCall, rows[0])
    assert row is not None
    return row


@pytest.mark.usefixtures("a_user")
async def test_an_over_long_prompt_is_clipped_and_the_row_is_marked_truncated() -> None:
    await _record(prompt_text="p" * (CAP + 1), response_text="[]")

    row = await _the_row()
    assert row.prompt_text == "p" * CAP
    assert row.response_text == "[]"  # the untouched column stays whole
    assert row.truncated is True


@pytest.mark.usefixtures("a_user")
async def test_an_over_long_answer_is_clipped_and_the_row_is_marked_truncated() -> None:
    await _record(prompt_text="PURPOSE: extract-entities", response_text="r" * (CAP + 1))

    row = await _the_row()
    assert row.prompt_text == "PURPOSE: extract-entities"
    assert row.response_text == "r" * CAP
    assert row.truncated is True


@pytest.mark.usefixtures("a_user")
async def test_over_long_prompt_and_answer_are_clipped_together() -> None:
    await _record(prompt_text="p" * (CAP + 1), response_text="r" * (CAP + 1))

    row = await _the_row()
    assert row.prompt_text == "p" * CAP
    assert row.response_text == "r" * CAP
    assert row.truncated is True


@pytest.mark.usefixtures("a_user")
async def test_exactly_the_cap_is_kept_whole_and_not_marked_truncated() -> None:
    # 65 536 fits; 65 537 clips. The boundary is the contract, so both
    # columns sit exactly on it.
    await _record(prompt_text="p" * CAP, response_text="r" * CAP)

    row = await _the_row()
    assert len(row.prompt_text) == CAP
    assert len(row.response_text) == CAP
    assert row.truncated is False


@pytest.mark.usefixtures("a_user")
async def test_a_short_call_is_kept_whole_with_a_null_cost() -> None:
    # D5, pinned: no catalog prices the call yet, and an unknown price is not
    # a free call — NULL, never 0.
    await _record(prompt_text="PURPOSE: extract-entities", response_text="[]")

    row = await _the_row()
    assert row.prompt_text == "PURPOSE: extract-entities"
    assert row.response_text == "[]"
    assert row.truncated is False
    assert row.cost_usd is None


@pytest.mark.usefixtures("a_user")
async def test_record_call_rides_the_callers_commit_and_never_commits_alone() -> None:
    async with Session() as writer:
        await _record("PURPOSE: check-consistency", "[]", session=writer)
        # Nothing committed: another session cannot see the row yet, which is
        # the proof that record_call did not commit inside.
        async with Session() as reader:
            before = await reader.scalar(text("SELECT count(*) FROM llm_calls"))
        assert before == 0
        await writer.commit()

    async with Session() as reader:
        after = await reader.scalar(text("SELECT count(*) FROM llm_calls"))
    assert after == 1
