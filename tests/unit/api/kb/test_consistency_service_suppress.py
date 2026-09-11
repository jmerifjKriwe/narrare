"""Integration tests for the mem0 suppression hook inside KBConsistencyService.

Split out of ``test_consistency_service.py`` to respect the RULE-04 300-line
file-size limit and improve cohesion: the suppression behaviour (CR-AUFG-03-10)
is a distinct concern from the base three-source orchestration.

These tests exercise the full ``KBConsistencyService.check`` path with a
fake ``ConsistencyFeedbackCollector`` to verify that:
- issues with a matching past dismissal are filtered out and counted in
  ``suppressed_count``;
- issues without a match stay visible;
- ``feedback_memory=None`` / ``user_id=None`` disable suppression (passthrough);
- a raising mem0 query leaves all issues visible (RULE-11 fail-open).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from narrare.kb.consistency_contracts import ConsistencyCheckRequest
from narrare.kb.consistency_service import KBConsistencyService
from narrare.kb.worldbuilding_contracts import (
    ConsistencyCategory,
    ConsistencyIssue,
)


def _make_issue(
    *,
    description: str = "Test inconsistency",
    finding_index: int = 0,
) -> ConsistencyIssue:
    """Create a test ConsistencyIssue with defaults."""
    return ConsistencyIssue(
        finding_index=finding_index,
        category=ConsistencyCategory.ENTRY_INTERNAL,
        entity_ids=[str(uuid4())],
        entity_names=["Entity"],
        description=description,
        contradiction="A vs B",
        confidence=0.9,
    )


def _make_service_with_feedback(
    feedback_memory: object | None,
) -> tuple[KBConsistencyService, dict[str, AsyncMock | Mock]]:
    """Create a KBConsistencyService with a feedback_memory injected."""
    analyzer = AsyncMock()
    asymmetry_checker = AsyncMock()
    worldbuilding_analyzer = AsyncMock()
    cache = AsyncMock()
    cache.hash_entity_types = Mock(return_value="")
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()

    novel_repo = AsyncMock()
    novel_repo.get_by_id = AsyncMock(return_value=object())  # permissive gate (IDOR S9)

    service = KBConsistencyService(
        analyzer=analyzer,
        asymmetry_checker=asymmetry_checker,
        worldbuilding_analyzer=worldbuilding_analyzer,
        kb_repo=AsyncMock(),
        rel_repo=AsyncMock(),
        cache=cache,
        novel_repo=novel_repo,
        feedback_memory=feedback_memory,  # type: ignore[arg-type]
    )
    service._run_cross_entity = AsyncMock(return_value=[])  # type: ignore[assignment]
    return service, {
        "analyzer": analyzer,
        "asymmetry_checker": asymmetry_checker,
        "cache": cache,
    }


class TestSemanticSuppression:
    """Integration tests for the mem0 suppression hook inside check()."""

    async def test_check_with_matching_dismissal_suppresses_issue(self) -> None:
        """An issue with a similar past dismissal is filtered out + counted."""
        feedback_memory = AsyncMock()
        feedback_memory.find_similar_dismissals = AsyncMock(
            return_value=["a-match"],  # truthy -> suppress
        )
        service, mocks = _make_service_with_feedback(feedback_memory)
        novel_id = uuid4()

        mocks["asymmetry_checker"].check = AsyncMock(return_value=[])
        issue = _make_issue(description="Eye colour mismatch.")
        mocks["analyzer"].analyze_entries = AsyncMock(return_value=([issue], 1))

        result = await service.check(
            novel_id=novel_id,
            request=ConsistencyCheckRequest(),
            user_id=str(uuid4()),
        )

        assert result.issues == []
        assert result.suppressed_count == 1

    async def test_check_without_match_keeps_issue(self) -> None:
        """An issue with no matching dismissal stays visible."""
        feedback_memory = AsyncMock()
        feedback_memory.find_similar_dismissals = AsyncMock(return_value=[])
        service, mocks = _make_service_with_feedback(feedback_memory)
        novel_id = uuid4()

        mocks["asymmetry_checker"].check = AsyncMock(return_value=[])
        issue = _make_issue(description="Genuine new finding.")
        mocks["analyzer"].analyze_entries = AsyncMock(return_value=([issue], 1))

        result = await service.check(
            novel_id=novel_id,
            request=ConsistencyCheckRequest(),
            user_id=str(uuid4()),
        )

        assert len(result.issues) == 1
        assert result.suppressed_count == 0

    async def test_check_with_none_feedback_memory_suppresses_nothing(self) -> None:
        """feedback_memory=None = passthrough (no suppression, count=0)."""
        service, mocks = _make_service_with_feedback(None)
        novel_id = uuid4()

        mocks["asymmetry_checker"].check = AsyncMock(return_value=[])
        issue = _make_issue()
        mocks["analyzer"].analyze_entries = AsyncMock(return_value=([issue], 1))

        result = await service.check(
            novel_id=novel_id,
            request=ConsistencyCheckRequest(),
            user_id=str(uuid4()),
        )

        assert len(result.issues) == 1
        assert result.suppressed_count == 0

    async def test_check_with_mem0_failure_suppresses_nothing(self) -> None:
        """A raising mem0 query leaves all issues visible (RULE-11 fail-open)."""
        feedback_memory = AsyncMock()
        feedback_memory.find_similar_dismissals = AsyncMock(
            side_effect=RuntimeError("mem0 down"),
        )
        service, mocks = _make_service_with_feedback(feedback_memory)
        novel_id = uuid4()

        mocks["asymmetry_checker"].check = AsyncMock(return_value=[])
        issue = _make_issue(description="Flaky query finding.")
        mocks["analyzer"].analyze_entries = AsyncMock(return_value=([issue], 1))

        result = await service.check(
            novel_id=novel_id,
            request=ConsistencyCheckRequest(),
            user_id=str(uuid4()),
        )

        assert len(result.issues) == 1
        assert result.suppressed_count == 0

    async def test_check_threads_user_id_into_suppression_query(self) -> None:
        """IDOR S9: ``user_id`` is required at the service boundary (a gate
        that can be skipped via ``None`` is not a gate) and is threaded —
        not dropped — into the mem0 suppression query. Helper-level
        ``None`` behaviour stays covered by ``test_consistency_suppress.py``."""
        feedback_memory = AsyncMock()
        feedback_memory.find_similar_dismissals = AsyncMock(return_value=[])
        service, mocks = _make_service_with_feedback(feedback_memory)
        novel_id = uuid4()
        user_id = str(uuid4())

        mocks["asymmetry_checker"].check = AsyncMock(return_value=[])
        issue = _make_issue()
        mocks["analyzer"].analyze_entries = AsyncMock(return_value=([issue], 1))

        result = await service.check(
            novel_id=novel_id,
            request=ConsistencyCheckRequest(),
            user_id=user_id,
        )

        assert len(result.issues) == 1
        assert result.suppressed_count == 0
        feedback_memory.find_similar_dismissals.assert_awaited_once_with(
            user_id, novel_id, finding_description=issue.description
        )
