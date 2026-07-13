"""Tests for memory/session_memory_service.py — SessionMemoryService.

Service-behavior tests for cross-session writing-context recording and
retrieval via mem0.

Privacy: only structural metadata (mode, chapter_title, word_count) is
recorded — never raw chapter prose (ADR-045 Decision 8, RULE-22).

See: ADR-045 Decision 8, CONSTRAINTS.md RULE-08/RULE-11/RULE-22.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

from narrare_core.memory._null_client import NullMemoryClient
from narrare_core.memory.session_memory_service import SessionMemoryService


class TestRecordWritingSession:
    """Tests for SessionMemoryService.record_writing_session()."""

    async def test_record_calls_mem0_add_with_structural_summary(self) -> None:
        """record_writing_session() must forward a structural summary to mem0.add().

        No extra LLM call — the summary is pure string formatting of the
        structural inputs (mode, chapter_title, word_count).
        """
        mem0 = AsyncMock()
        service = SessionMemoryService(mem0_client=mem0)

        user_id = uuid4()
        project_id = uuid4()
        await service.record_writing_session(
            user_id,
            project_id,
            mode="draft",
            chapter_title="Chapter 7",
            word_count=1200,
        )

        mem0.add.assert_awaited_once()
        call_kwargs = mem0.add.call_args[1]
        assert call_kwargs["messages"] == (
            "Writing session: user wrote 'Chapter 7' in draft mode (1200 words)"
        )
        assert call_kwargs["user_id"] == str(user_id)
        assert call_kwargs["agent_id"] == str(project_id)

    async def test_record_forwards_metadata_to_mem0(self) -> None:
        """record_writing_session() must attach type/mode/title/word_count metadata."""
        mem0 = AsyncMock()
        service = SessionMemoryService(mem0_client=mem0)

        await service.record_writing_session(
            uuid4(),
            uuid4(),
            mode="rewrite",
            chapter_title="The Long Night",
            word_count=950,
        )

        call_kwargs = mem0.add.call_args[1]
        assert call_kwargs["metadata"] == {
            "type": "writing_session",
            "mode": "rewrite",
            "chapter_title": "The Long Night",
            "word_count": 950,
        }

    async def test_record_does_not_raise_on_mem0_failure(self) -> None:
        """record_writing_session() must not raise when mem0 fails (graceful degradation)."""
        mem0 = AsyncMock()
        mem0.add.side_effect = RuntimeError("mem0 down")
        service = SessionMemoryService(mem0_client=mem0)

        # Must not raise — mem0 failure is a warning, not an error.
        await service.record_writing_session(
            uuid4(),
            uuid4(),
            mode="draft",
            chapter_title="Chapter 7",
            word_count=500,
        )
        mem0.add.assert_awaited_once()

    async def test_record_does_not_include_raw_chapter_content(self) -> None:
        """record_writing_session() records only structural metadata, never prose.

        Privacy (ADR-045 Decision 8, RULE-22): the method has no content
        parameter, so chapter body cannot reach mem0. The recorded message is
        exactly the structural template — nothing beyond mode/title/word_count.
        """
        mem0 = AsyncMock()
        service = SessionMemoryService(mem0_client=mem0)

        raw_prose = "The castle doors groaned open, revealing darkness within."
        await service.record_writing_session(
            uuid4(),
            uuid4(),
            mode="draft",
            chapter_title="Chapter 7",
            word_count=500,
        )

        call_kwargs = mem0.add.call_args[1]
        # The only chapter-derived string reaching mem0 is the title; the body
        # is structurally impossible to leak (no parameter accepts it).
        assert raw_prose not in call_kwargs["messages"]
        assert raw_prose not in str(call_kwargs["metadata"])
        # Message is exactly the structural template — no extra content.
        assert call_kwargs["messages"] == (
            "Writing session: user wrote 'Chapter 7' in draft mode (500 words)"
        )

    async def test_record_with_null_memory_client_does_not_raise(self) -> None:
        """record_writing_session() with NullMemoryClient succeeds silently."""
        null_client = NullMemoryClient()
        service = SessionMemoryService(mem0_client=null_client)

        await service.record_writing_session(
            uuid4(),
            uuid4(),
            mode="draft",
            chapter_title="Chapter 1",
            word_count=100,
        )


class TestGetCrossSessionContext:
    """Tests for SessionMemoryService.get_cross_session_context()."""

    async def test_get_context_calls_mem0_search_with_correct_filters(self) -> None:
        """get_cross_session_context() must query mem0 scoped to user+project."""
        mem0 = AsyncMock()
        mem0.search.return_value = {"results": []}
        service = SessionMemoryService(mem0_client=mem0)

        user_id = uuid4()
        project_id = uuid4()
        await service.get_cross_session_context(user_id, project_id)

        mem0.search.assert_awaited_once()
        call_kwargs = mem0.search.call_args[1]
        assert call_kwargs["query"] == "writing sessions and chapter decisions"
        assert call_kwargs["filters"] == {
            "user_id": str(user_id),
            "agent_id": str(project_id),
        }

    async def test_get_context_returns_bullet_list_when_results_exist(self) -> None:
        """get_cross_session_context() formats results as a newline-joined bullet list."""
        mem0 = AsyncMock()
        mem0.search.return_value = {
            "results": [
                {"memory": "User wrote 'Chapter 7' with a cliffhanger ending"},
                {"memory": "User wrote 'Chapter 6' in rewrite mode"},
            ]
        }
        service = SessionMemoryService(mem0_client=mem0)

        context = await service.get_cross_session_context(uuid4(), uuid4())

        assert context == (
            "- User wrote 'Chapter 7' with a cliffhanger ending\n"
            "- User wrote 'Chapter 6' in rewrite mode"
        )

    async def test_get_context_returns_empty_string_when_no_results(self) -> None:
        """get_cross_session_context() returns '' when mem0 has no results."""
        mem0 = AsyncMock()
        mem0.search.return_value = {"results": []}
        service = SessionMemoryService(mem0_client=mem0)

        context = await service.get_cross_session_context(uuid4(), uuid4())
        assert context == ""

    async def test_get_context_returns_empty_string_on_mem0_failure(self) -> None:
        """get_cross_session_context() returns '' when mem0 raises (graceful degradation)."""
        mem0 = AsyncMock()
        mem0.search.side_effect = RuntimeError("mem0 down")
        service = SessionMemoryService(mem0_client=mem0)

        context = await service.get_cross_session_context(uuid4(), uuid4())
        assert context == ""

    async def test_get_context_limits_to_top_five_results(self) -> None:
        """get_cross_session_context() caps the bullet list at 5 entries."""
        mem0 = AsyncMock()
        mem0.search.return_value = {
            "results": [{"memory": f"session memory {i}"} for i in range(7)]
        }
        service = SessionMemoryService(mem0_client=mem0)

        context = await service.get_cross_session_context(uuid4(), uuid4())

        bullets = context.split("\n")
        assert len(bullets) == 5
        assert all(b.startswith("- ") for b in bullets)
        assert bullets[0] == "- session memory 0"

    async def test_get_context_with_null_memory_client_returns_empty(self) -> None:
        """get_cross_session_context() with NullMemoryClient returns ''."""
        null_client = NullMemoryClient()
        service = SessionMemoryService(mem0_client=null_client)

        context = await service.get_cross_session_context(uuid4(), uuid4())
        assert context == ""
