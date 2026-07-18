"""Tests for ConsistencyFeedbackService.find_similar_dismissals() — retrieve path.

Retrieve-path (semantic suppression) tests for the cross-run consistency-
dismissal learning layer (CR-AUFG-03-10). Split out of
``test_consistency_feedback_service.py`` to respect RULE-04.

Covers: mem0 query/filters, threshold filtering, type + novel-id post-filters,
score normalisation, faithful DismissalMatch reconstruction, and graceful
degradation (RULE-11) when mem0 fails / is disabled.

See: ADR-045 Decision 8, CONSTRAINTS.md RULE-08/RULE-11/RULE-22.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from narrare_core.memory.consistency_feedback_service import (
    ConsistencyFeedbackService,
)
from narrare_core.memory.consistency_models import DismissalMatch

_DISMISSAL_TYPE = "consistency_dismissal"


def _dismissal_memory(
    *,
    score: float,
    project_id: object,
    fingerprint: str = "fp-1",
    finding_description: str = "Past dismissed finding.",
    reason: str | None = None,
    memory_type: str = _DISMISSAL_TYPE,
) -> dict[str, object]:
    """Build a mem0-shaped search result for a dismissal memory."""
    return {
        "id": "mem-id",
        "memory": finding_description,
        "score": score,
        "metadata": {
            "type": memory_type,
            "novel_id": str(project_id),
            "fingerprint": fingerprint,
            "finding_description": finding_description,
            "reason": reason,
        },
    }


class TestFindSimilarDismissals:
    """Tests for ConsistencyFeedbackService.find_similar_dismissals()."""

    async def test_find_calls_mem0_search_with_correct_query_and_filters(
        self,
    ) -> None:
        """find_similar_dismissals() queries mem0 with the description + scope."""
        mem0 = AsyncMock()
        mem0.search.return_value = {"results": []}
        service = ConsistencyFeedbackService(mem0_client=mem0)

        user_id = uuid4()
        project_id = uuid4()
        await service.find_similar_dismissals(
            user_id,
            project_id,
            finding_description="new finding text",
        )

        mem0.search.assert_awaited_once()
        call_kwargs = mem0.search.call_args[1]
        assert call_kwargs["query"] == "new finding text"
        assert call_kwargs["filters"] == {
            "user_id": str(user_id),
            "agent_id": str(project_id),
        }
        assert call_kwargs["top_k"] == 10  # protocol default limit

    async def test_find_passes_custom_limit_as_top_k(self) -> None:
        """A custom ``limit`` is forwarded to mem0 as ``top_k``."""
        mem0 = AsyncMock()
        mem0.search.return_value = {"results": []}
        service = ConsistencyFeedbackService(mem0_client=mem0)

        await service.find_similar_dismissals(
            uuid4(),
            uuid4(),
            finding_description="x",
            limit=25,
        )

        assert mem0.search.call_args[1]["top_k"] == 25

    async def test_find_returns_matches_above_threshold(self) -> None:
        """Only results scoring >= similarity_threshold are returned, best-first."""
        mem0 = AsyncMock()
        project_id = uuid4()
        mem0.search.return_value = {
            "results": [
                _dismissal_memory(
                    score=0.95,
                    project_id=project_id,
                    finding_description="high match",
                    fingerprint="fp-high",
                ),
                _dismissal_memory(
                    score=0.5,
                    project_id=project_id,
                    finding_description="low match",
                    fingerprint="fp-low",
                ),
                _dismissal_memory(
                    score=0.85,
                    project_id=project_id,
                    finding_description="boundary match",
                    fingerprint="fp-boundary",
                ),
            ]
        }
        service = ConsistencyFeedbackService(mem0_client=mem0)

        matches = await service.find_similar_dismissals(
            uuid4(),
            project_id,
            finding_description="query",
            similarity_threshold=0.85,
        )

        # 0.95 and 0.85 pass (>=); 0.5 dropped. mem0 best-first order preserved.
        assert [m.fingerprint for m in matches] == ["fp-high", "fp-boundary"]
        assert all(m.similarity >= 0.85 for m in matches)
        assert {m.finding_description for m in matches} == {"high match", "boundary match"}

    async def test_find_reconstructs_match_fields_from_metadata(self) -> None:
        """DismissalMatch pulls description/reason/fingerprint from metadata (lossless)."""
        mem0 = AsyncMock()
        project_id = uuid4()
        mem0.search.return_value = {
            "results": [
                _dismissal_memory(
                    score=0.9,
                    project_id=project_id,
                    finding_description="Authoritative description.",
                    reason="False positive.",
                    fingerprint="fp-1",
                ),
            ]
        }
        service = ConsistencyFeedbackService(mem0_client=mem0)

        matches = await service.find_similar_dismissals(
            uuid4(), project_id, finding_description="q"
        )

        assert len(matches) == 1
        match = matches[0]
        assert isinstance(match, DismissalMatch)
        assert match.fingerprint == "fp-1"
        assert match.finding_description == "Authoritative description."
        assert match.reason == "False positive."
        assert match.similarity == 0.9

    async def test_find_filters_out_non_dismissal_memories(self) -> None:
        """Memories whose metadata type != consistency_dismissal are excluded."""
        mem0 = AsyncMock()
        project_id = uuid4()
        mem0.search.return_value = {
            "results": [
                _dismissal_memory(
                    score=0.99,
                    project_id=project_id,
                    memory_type="writing_session",
                    finding_description="a writing session",
                ),
                _dismissal_memory(
                    score=0.9,
                    project_id=project_id,
                    finding_description="a real dismissal",
                    fingerprint="fp-real",
                ),
            ]
        }
        service = ConsistencyFeedbackService(mem0_client=mem0)

        matches = await service.find_similar_dismissals(
            uuid4(), project_id, finding_description="q"
        )

        assert [m.fingerprint for m in matches] == ["fp-real"]

    async def test_find_filters_out_different_novel_dismissals(self) -> None:
        """Dismissals scoped to a different novel_id are excluded (within-novel)."""
        mem0 = AsyncMock()
        this_project = uuid4()
        other_project = uuid4()
        mem0.search.return_value = {
            "results": [
                _dismissal_memory(
                    score=0.95,
                    project_id=other_project,  # different novel
                    finding_description="other-novel dismissal",
                    fingerprint="fp-other",
                ),
                _dismissal_memory(
                    score=0.9,
                    project_id=this_project,
                    finding_description="this-novel dismissal",
                    fingerprint="fp-this",
                ),
            ]
        }
        service = ConsistencyFeedbackService(mem0_client=mem0)

        matches = await service.find_similar_dismissals(
            uuid4(), this_project, finding_description="q"
        )

        assert [m.fingerprint for m in matches] == ["fp-this"]

    async def test_find_falls_back_to_memory_text_when_description_missing(
        self,
    ) -> None:
        """Without a metadata description, the mem0 memory text is used."""
        mem0 = AsyncMock()
        project_id = uuid4()
        mem0.search.return_value = {
            "results": [
                {
                    "memory": "Rephrased memory text from mem0.",
                    "score": 0.9,
                    "metadata": {
                        "type": _DISMISSAL_TYPE,
                        "novel_id": str(project_id),
                        "fingerprint": "fp-fallback",
                        # finding_description intentionally absent
                    },
                },
            ]
        }
        service = ConsistencyFeedbackService(mem0_client=mem0)

        matches = await service.find_similar_dismissals(
            uuid4(), project_id, finding_description="q"
        )

        assert len(matches) == 1
        assert matches[0].finding_description == "Rephrased memory text from mem0."

    @pytest.mark.parametrize(
        ("raw_score", "expected", "threshold"),
        [
            (1.5, 1.0, 0.0),  # out-of-range high -> clamped to 1.0
            (-0.3, 0.0, 0.0),  # negative -> clamped to 0.0
            ("not-a-number", 0.0, 0.0),  # non-numeric -> defensive 0.0
        ],
    )
    async def test_find_normalises_out_of_range_scores(
        self,
        raw_score: Any,
        expected: float,
        threshold: float,
    ) -> None:
        """Out-of-range / non-numeric mem0 scores are clamped to the 0..1 contract."""
        mem0 = AsyncMock()
        project_id = uuid4()
        mem0.search.return_value = {
            "results": [
                {
                    "memory": "scored",
                    "score": raw_score,
                    "metadata": {
                        "type": _DISMISSAL_TYPE,
                        "novel_id": str(project_id),
                        "fingerprint": "fp-score",
                        "finding_description": "scored",
                    },
                },
            ]
        }
        service = ConsistencyFeedbackService(mem0_client=mem0)

        matches = await service.find_similar_dismissals(
            uuid4(),
            project_id,
            finding_description="q",
            similarity_threshold=threshold,
        )

        assert len(matches) == 1
        assert matches[0].similarity == expected
