"""The LlmCall audit: the table, then the writer, then what handlers record.

Plan §3.4: one row per provider call — prompt and answer capped at 64 KB,
tokens, latency, status, and the price the catalog's truth table computes.
The column set is pinned here so a drift fails at its first commit instead
of in later work's evidence.
"""

from collections.abc import AsyncIterator  # noqa: TC003
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.kernel.db.base import Base
from app.kernel.db.session import Session
from app.kernel.db.testsupport import seed_user
from app.kernel.llm.audit import CAP, audited_stream, record_call
from app.kernel.llm.catalog import ModelInfo
from app.kernel.llm.contract import DONE, CompletionEvent, CompletionRequest, Delta, Usage
from app.kernel.llm.models import LlmCall
from app.kernel.llm.resolution import ResolvedProvider

LLM_CALL_COLUMNS = {
    "id",
    "user_id",
    "novel_id",
    "profile_id",
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
    """Verify model registration exposes exactly the audit contract's columns."""
    table = Base.metadata.tables[LlmCall.__tablename__]
    assert set(table.columns.keys()) == LLM_CALL_COLUMNS


@pytest.mark.usefixtures("schema")
def test_the_jobs_and_contracts_tables_are_still_registered() -> None:
    """Verify registering audits preserves job and domain table metadata."""
    tables = Base.metadata.tables
    assert "jobs" in tables
    assert "novels" in tables
    assert "chapters" in tables


OWNER = uuid4()
PROFILE = uuid4()
REMOTE_URL = "https://api.vendor.example/v1"


def _resolved(provider: _ScriptedProvider | _RaisingAfterDoneProvider) -> ResolvedProvider:
    """A fake-tier resolved carrier for a scripted provider, what these tests stream."""
    return ResolvedProvider(
        provider=provider,
        profile_id=PROFILE,
        kind="fake",
        model="fake",
        context_window=None,
        max_output_tokens=None,
        temperature=None,
        request_timeout=None,
        base_url=None,
        api_key=None,
    )


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
    """Verify prompt clipping sets the truncated flag without changing the response."""
    await _record(prompt_text="p" * (CAP + 1), response_text="[]")

    row = await _the_row()
    assert row.prompt_text == "p" * CAP
    assert row.response_text == "[]"  # the untouched column stays whole
    assert row.truncated is True


@pytest.mark.usefixtures("a_user")
async def test_an_over_long_answer_is_clipped_and_the_row_is_marked_truncated() -> None:
    """Verify response clipping sets the truncated flag without changing the prompt."""
    await _record(prompt_text="PURPOSE: extract-entities", response_text="r" * (CAP + 1))

    row = await _the_row()
    assert row.prompt_text == "PURPOSE: extract-entities"
    assert row.response_text == "r" * CAP
    assert row.truncated is True


@pytest.mark.usefixtures("a_user")
async def test_over_long_prompt_and_answer_are_clipped_together() -> None:
    """Verify both audit texts are capped when both exceed the limit."""
    await _record(prompt_text="p" * (CAP + 1), response_text="r" * (CAP + 1))

    row = await _the_row()
    assert row.prompt_text == "p" * CAP
    assert row.response_text == "r" * CAP
    assert row.truncated is True


@pytest.mark.usefixtures("a_user")
async def test_exactly_the_cap_is_kept_whole_and_not_marked_truncated() -> None:
    """Verify texts exactly at the cap remain intact without a truncated flag."""
    # 65 536 fits; 65 537 clips. The boundary is the contract, so both
    # columns sit exactly on it.
    await _record(prompt_text="p" * CAP, response_text="r" * CAP)

    row = await _the_row()
    assert len(row.prompt_text) == CAP
    assert len(row.response_text) == CAP
    assert row.truncated is False


@pytest.mark.usefixtures("a_user")
async def test_a_short_call_is_kept_whole_with_a_null_cost() -> None:
    """Verify short texts remain intact and a caller without info stays NULL."""
    # Pinned: the helper passes no catalog info, and an unknown price is not
    # a free call — NULL, never 0.
    await _record(prompt_text="PURPOSE: extract-entities", response_text="[]")

    row = await _the_row()
    assert row.prompt_text == "PURPOSE: extract-entities"
    assert row.response_text == "[]"
    assert row.truncated is False
    assert row.cost_usd is None


ACME_TURBO = ModelInfo(
    context_window=100_000,
    max_output_tokens=4_096,
    input_price_per_mtok=3.0,
    output_price_per_mtok=15.0,
    supports_json_schema=True,
    supports_tools=True,
    supports_vision=False,
)


async def _record_priced(base_url: str) -> None:
    """Record one priced remote-style call carrying a profile id."""
    async with Session() as session:
        await record_call(
            session,
            user_id=OWNER,
            task_key="chat.ask",
            provider_kind="openai-chat",
            model="acme/turbo-3",
            latency_ms=120,
            status="ok",
            prompt_text="Continue",
            response_text="[]",
            input_tokens=1_000,
            output_tokens=2_000,
            profile_id=PROFILE,
            base_url=base_url,
            info=ACME_TURBO,
        )
        await session.commit()


@pytest.mark.usefixtures("a_user")
async def test_record_call_prices_a_priced_remote_call() -> None:
    """Verify the catalog's Mtok sum and the profile id land on the row."""
    await _record_priced("https://api.vendor.example/v1")

    row = await _the_row()
    assert row.cost_usd == pytest.approx(0.033)  # 1 000 * 3.0 + 2 000 * 15.0
    assert row.profile_id == PROFILE


@pytest.mark.usefixtures("a_user")
async def test_record_call_prices_a_local_call_at_zero() -> None:
    """Verify a priced model on a local endpoint is recorded as free (D4)."""
    await _record_priced("http://127.0.0.1:11434/v1")

    row = await _the_row()
    assert row.cost_usd == 0.0


@pytest.mark.usefixtures("a_user")
async def test_record_call_rides_the_callers_commit_and_never_commits_alone() -> None:
    """Verify an audit becomes visible to other sessions only after the caller commits."""
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


class _ScriptedProvider:
    """A provider with scripted events, or one that raises instead of yielding."""

    def __init__(
        self, events: tuple[CompletionEvent, ...], *, fail: Exception | None = None
    ) -> None:
        """Store the script: the events to yield, or the failure to raise."""
        self.events = events
        self.fail = fail

    def describe(self) -> str:
        """Name this scripted stand-in."""
        return "scripted"

    def configuration_problems(self) -> list[str]:
        """Ready by construction."""
        return []

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Yield every scripted event, or raise the scripted failure first."""
        if self.fail is not None:
            raise self.fail
        for event in self.events:
            yield event


async def _audited_row() -> Any:
    """The single audit row every test in this group expects to find."""
    async with Session() as session:
        return (
            await session.execute(text("SELECT status, error, response_text FROM llm_calls"))
        ).one()


@pytest.mark.usefixtures("a_user")
async def test_audited_stream_audits_a_drained_call_as_ok() -> None:
    """A fully drained call records ok, no error, and the concatenated answer."""
    provider = _ScriptedProvider(
        (Delta(text="part "), Usage(input_tokens=3, output_tokens=2), DONE)
    )
    events = [
        event
        async for event in audited_stream(
            _resolved(provider),
            CompletionRequest.user("Continue"),
            user_id=OWNER,
            task_key="test.stream",
        )
    ]
    assert events[-1] is DONE
    row = await _audited_row()
    assert (row.status, row.error, row.response_text) == ("ok", None, "part ")


@pytest.mark.usefixtures("a_user")
async def test_audited_stream_records_ok_when_the_consumer_stops_at_done() -> None:
    """DONE is the terminal event: a consumer that stops there ended cleanly."""
    provider = _ScriptedProvider((Delta(text="part "), DONE))
    stream = audited_stream(
        _resolved(provider),
        CompletionRequest.user("Continue"),
        user_id=OWNER,
        task_key="test.stream",
    )
    async for event in stream:
        if event is DONE:
            break
    await stream.aclose()
    row = await _audited_row()
    assert (row.status, row.error) == ("ok", None)


@pytest.mark.usefixtures("a_user")
async def test_audited_stream_records_the_usage_refusal_in_the_error_column() -> None:
    """A malformed-usage refusal lands in the row's error text, naming the field."""
    provider = _ScriptedProvider(
        (),
        fail=ValueError(
            "reported usage field prompt_tokens is not a non-negative integer count: '12'"
        ),
    )
    stream = audited_stream(
        _resolved(provider),
        CompletionRequest.user("Continue"),
        user_id=OWNER,
        task_key="test.stream",
    )
    with pytest.raises(ValueError):
        async for _ in stream:
            pass
    row = await _audited_row()
    assert row.status == "error"
    assert "prompt_tokens" in row.error


class _RaisingAfterDoneProvider(_ScriptedProvider):
    """Breaks the provider contract: raises after its own terminal event."""

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Yield one delta and DONE, then fail."""
        yield Delta(text="part ")
        yield DONE
        raise RuntimeError("vendor died after its terminal frame")


@pytest.mark.usefixtures("a_user")
async def test_a_raise_after_done_is_an_error_row_not_a_contradiction() -> None:
    """A provider that fails after its terminal event is recorded as failed."""
    stream = audited_stream(
        _resolved(_RaisingAfterDoneProvider((), fail=None)),
        CompletionRequest.user("Continue"),
        user_id=OWNER,
        task_key="test.stream",
    )
    with pytest.raises(RuntimeError):
        async for _ in stream:
            pass
    row = await _audited_row()
    assert row.status == "error"
    assert "after its terminal frame" in row.error


# The resolved kind decides the cost tier: the fake is free, a local endpoint
# is free, and an unknown model on a remote endpoint stays NULL — design D4.


async def _cost_of_a_streamed_call(*, kind: str, model: str, base_url: str | None) -> float | None:
    """Drain one scripted call and return the cost its audit row carries."""
    resolved = ResolvedProvider(
        provider=_ScriptedProvider(
            (Delta(text="x"), Usage(input_tokens=10, output_tokens=5), DONE)
        ),
        profile_id=PROFILE,
        kind=kind,
        model=model,
        context_window=None,
        max_output_tokens=None,
        temperature=None,
        request_timeout=None,
        base_url=base_url,
        api_key=None,
    )
    events = [
        event
        async for event in audited_stream(
            resolved, CompletionRequest.user("Continue"), user_id=OWNER, task_key="test.stream"
        )
    ]
    assert events[-1] is DONE
    async with Session() as session:
        row = (await session.execute(text("SELECT cost_usd FROM llm_calls"))).one()
    return row.cost_usd


@pytest.mark.usefixtures("a_user")
async def test_a_fake_kind_costs_zero_even_on_an_unknown_model() -> None:
    """The fake's rows are free whatever its free-text model spelled."""
    cost = await _cost_of_a_streamed_call(kind="fake", model="ghost-writer", base_url=None)
    assert cost == 0.0


@pytest.mark.usefixtures("a_user")
async def test_an_unknown_model_on_a_remote_endpoint_stays_null() -> None:
    """No catalog tier reaches the model: the cost is unknown, never free."""
    cost = await _cost_of_a_streamed_call(
        kind="openai-chat", model="no-catalog-entry-for-this-test", base_url=REMOTE_URL
    )
    assert cost is None


@pytest.mark.usefixtures("a_user")
async def test_a_local_endpoint_costs_zero_even_on_an_unknown_model() -> None:
    """Locality is free whatever the catalog knows about the model."""
    cost = await _cost_of_a_streamed_call(
        kind="openai-chat", model="no-catalog-entry-for-this-test", base_url="http://127.0.0.1:9/v1"
    )
    assert cost == 0.0
