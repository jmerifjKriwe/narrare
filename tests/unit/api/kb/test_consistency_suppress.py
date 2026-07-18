"""Unit tests for the consistency-issue suppression helper (CR-AUFG-03-10).

Tests :func:`narrare.kb._consistency_suppress.suppress_dismissed_issues` —
the pure orchestration that filters out freshly-produced consistency issues
matching a past dismissal in mem0.

Best-effort (RULE-11): when mem0 is unavailable, the caller did not
authenticate a user, or a query raises, suppression is skipped (fails open
— over-suppression is the higher-cost error). Covers happy path, no-match,
disabled (None), and flaky-mem0 cases.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from narrare.kb._consistency_suppress import suppress_dismissed_issues
from narrare.kb.worldbuilding_contracts import (
    ConsistencyCategory,
    ConsistencyIssue,
)


def _make_issue(
    *,
    description: str = "Test inconsistency",
    finding_index: int = 0,
) -> ConsistencyIssue:
    """Build a ConsistencyIssue with only the fields the helper reads."""
    return ConsistencyIssue(
        finding_index=finding_index,
        category=ConsistencyCategory.ENTRY_INTERNAL,
        entity_ids=["e1"],
        entity_names=["Entity"],
        description=description,
        contradiction="A vs B",
        confidence=0.9,
    )


class TestSuppressDismissedIssues:
    """Tests for suppress_dismissed_issues()."""

    async def test_suppress_filters_issue_with_matching_dismissal(self) -> None:
        """An issue with a similar past dismissal is filtered out."""
        feedback_memory = AsyncMock()
        feedback_memory.find_similar_dismissals = AsyncMock(
            return_value=["a-match"],  # truthy -> suppress
        )
        issues = [_make_issue(description="Eye colour mismatch.")]

        kept, suppressed_count = await suppress_dismissed_issues(
            issues, feedback_memory, user_id="user-1", project_id=uuid4()
        )

        assert kept == []
        assert suppressed_count == 1
        feedback_memory.find_similar_dismissals.assert_awaited_once()

    async def test_suppress_keeps_issue_without_match(self) -> None:
        """An issue with no matching dismissal stays visible."""
        feedback_memory = AsyncMock()
        feedback_memory.find_similar_dismissals = AsyncMock(return_value=[])
        issues = [_make_issue(description="Real new finding.")]

        kept, suppressed_count = await suppress_dismissed_issues(
            issues, feedback_memory, user_id="user-1", project_id=uuid4()
        )

        assert kept == issues
        assert suppressed_count == 0

    async def test_suppress_with_none_feedback_memory_returns_all(self) -> None:
        """feedback_memory=None disables suppression (passthrough)."""
        issues = [_make_issue(), _make_issue(description="another")]

        kept, suppressed_count = await suppress_dismissed_issues(
            issues, None, user_id="user-1", project_id=uuid4()
        )

        assert kept == issues
        assert suppressed_count == 0

    async def test_suppress_with_none_user_id_returns_all(self) -> None:
        """user_id=None disables suppression (no identity to scope by)."""
        feedback_memory = AsyncMock()
        issues = [_make_issue()]

        kept, suppressed_count = await suppress_dismissed_issues(
            issues, feedback_memory, user_id=None, project_id=uuid4()
        )

        assert kept == issues
        assert suppressed_count == 0
        feedback_memory.find_similar_dismissals.assert_not_awaited()

    async def test_suppress_with_empty_issues_returns_empty(self) -> None:
        """No issues in -> no issues out, no mem0 calls made."""
        feedback_memory = AsyncMock()

        kept, suppressed_count = await suppress_dismissed_issues(
            [], feedback_memory, user_id="user-1", project_id=uuid4()
        )

        assert kept == []
        assert suppressed_count == 0
        feedback_memory.find_similar_dismissals.assert_not_awaited()

    async def test_suppress_treats_mem0_failure_as_no_match(self) -> None:
        """A raising mem0 query leaves the issue visible (RULE-11 fail-open)."""
        feedback_memory = AsyncMock()
        feedback_memory.find_similar_dismissals = AsyncMock(
            side_effect=RuntimeError("mem0 down"),
        )
        issues = [_make_issue(description="Flaky query finding.")]

        kept, suppressed_count = await suppress_dismissed_issues(
            issues, feedback_memory, user_id="user-1", project_id=uuid4()
        )

        assert kept == issues
        assert suppressed_count == 0

    async def test_suppress_counts_mixed_batch_correctly(self) -> None:
        """A mix of matching/non-matching issues: only matches counted."""
        feedback_memory = AsyncMock()
        feedback_memory.find_similar_dismissals = AsyncMock(
            side_effect=[
                ["match"],  # issue 1 -> suppressed
                [],  # issue 2 -> kept
                ["match"],  # issue 3 -> suppressed
            ],
        )
        issues = [
            _make_issue(description="suppressed-1", finding_index=0),
            _make_issue(description="kept", finding_index=1),
            _make_issue(description="suppressed-2", finding_index=2),
        ]

        kept, suppressed_count = await suppress_dismissed_issues(
            issues, feedback_memory, user_id="user-1", project_id=uuid4()
        )

        assert [i.description for i in kept] == ["kept"]
        assert suppressed_count == 2

    async def test_suppress_passes_finding_description_to_query(self) -> None:
        """The issue's description is forwarded as finding_description."""
        feedback_memory = AsyncMock()
        feedback_memory.find_similar_dismissals = AsyncMock(return_value=[])
        project_id = uuid4()

        await suppress_dismissed_issues(
            [_make_issue(description="The exact description.")],
            feedback_memory,
            user_id="user-42",
            project_id=project_id,
        )

        call = feedback_memory.find_similar_dismissals.call_args
        # Protocol: (user_id, project_id, *, finding_description, ...)
        assert call.args[0] == "user-42"
        assert call.args[1] == project_id
        assert call.kwargs["finding_description"] == "The exact description."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
