"""The LlmCall audit: the table, then the writer, then what handlers record.

Plan §3.4: one row per provider call — prompt and answer capped at 64 KB,
tokens, latency, status. cost_usd stays NULL until WP2's catalog prices it
and no profile_id exists until a profile table does; the column set is pinned
here so a drift fails at its first commit instead of in WP2's evidence.
"""

import pytest

from app.kernel.db.base import Base
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
