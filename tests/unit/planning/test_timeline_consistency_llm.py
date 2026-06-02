"""Unit tests for TimelineConsistencyService — LLM checks (PLAN-004 Phase 2).

Tests LLM checks integration, combined result merging, and graceful
degradation when LLM is unavailable.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare.planning.timeline_consistency_service import TimelineConsistencyService


def _make_novel(**overrides: object) -> MagicMock:
    """Create a mock novel."""
    defaults: dict[str, object] = {
        "id": overrides.get("id", uuid.uuid4()),
        "title": overrides.get("title", "Test Novel"),
        "genre": overrides.get("genre", "fantasy"),
        "writing_language": overrides.get("writing_language", "en"),
    }
    defaults.update(overrides)
    novel = MagicMock(spec=["id", "title", "genre", "writing_language"])
    for k, v in defaults.items():
        setattr(novel, k, v)
    return novel


def _make_event(**overrides: object) -> MagicMock:
    """Create a mock TimelineEvent."""
    defaults: dict[str, object] = {
        "id": overrides.get("id", uuid.uuid4()),
        "event_name": overrides.get("event_name", "Battle"),
        "event_type": overrides.get("event_type", "plot_point"),
        "temporal_order": overrides.get("temporal_order", 1),
        "causes": overrides.get("causes", ""),
        "consequences": overrides.get("consequences", ""),
        "timestamp_raw": overrides.get("timestamp_raw", "Day 1"),
        "timestamp_normalized": overrides.get("timestamp_normalized", ""),
        "chapter_id": overrides.get("chapter_id"),
        "character_refs": overrides.get("character_refs", []),
        "location_ref": overrides.get("location_ref"),
    }
    defaults.update(overrides)
    event = MagicMock(
        spec=[
            "id",
            "event_name",
            "event_type",
            "temporal_order",
            "causes",
            "consequences",
            "timestamp_raw",
            "timestamp_normalized",
            "chapter_id",
            "character_refs",
            "location_ref",
        ]
    )
    for k, v in defaults.items():
        setattr(event, k, v)
    return event


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def novel_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_event_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_novel_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service_with_llm(
    mock_event_repo: AsyncMock,
    mock_novel_repo: AsyncMock,
) -> TimelineConsistencyService:
    """Service with LLM configured."""
    mock_registry = AsyncMock()
    mock_config = MagicMock(spec=["provider_name", "model_id"])
    return TimelineConsistencyService(
        event_repo=mock_event_repo,
        novel_repo=mock_novel_repo,
        model_registry=mock_registry,
        model_config=mock_config,
    )


class TestLLMChecks:
    """Test LLM checks integration."""

    async def test_llm_checks_skipped_when_no_provider(
        self,
        mock_novel_repo: AsyncMock,
        mock_event_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """LLM checks should be skipped when no model_config is set."""
        service = TimelineConsistencyService(
            event_repo=mock_event_repo,
            novel_repo=mock_novel_repo,
            model_registry=None,
            model_config=None,
        )
        mock_novel_repo.get_by_id.return_value = _make_novel(id=novel_id)
        mock_event_repo.list_by_novel.return_value = [
            _make_event(event_name="Event A", temporal_order=1),
        ]

        result = await service.check_consistency(novel_id, user_id)

        # Only deterministic issues, no LLM issues
        llm_issues = [i for i in result.issues if i.source == "llm"]
        assert len(llm_issues) == 0

    async def test_llm_checks_with_configured_provider(
        self,
        service_with_llm: TimelineConsistencyService,
        mock_novel_repo: AsyncMock,
        mock_event_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """LLM checks should run when model_config is set."""
        novel = _make_novel(id=novel_id)
        mock_novel_repo.get_by_id.return_value = novel
        mock_event_repo.list_by_novel.return_value = [
            _make_event(event_name="Event A", temporal_order=1, timestamp_raw="Day 1"),
        ]

        # Mock the model registry to return a model
        assert service_with_llm._registry is not None
        mock_model = AsyncMock(spec=[])
        service_with_llm._registry.get_model = AsyncMock(return_value=mock_model)

        # Mock the TimelineAgent — it's imported locally inside _run_llm_checks
        mock_agent_result = MagicMock(spec=["temporal_conflicts"])
        mock_agent_result.temporal_conflicts = ["Event A seems to happen before its cause"]

        mock_agent_instance = AsyncMock()
        mock_agent_instance.run.return_value = mock_agent_result

        with (
            patch(
                "narrare_core.agents.timeline_agent.TimelineAgent",
                return_value=mock_agent_instance,
            ),
            patch(
                "narrare_core.agents.timeline_agent.TimelineDeps",
            ),
        ):
            result = await service_with_llm.check_consistency(novel_id, user_id)

        # Should have both deterministic and LLM issues
        llm_issues = [i for i in result.issues if i.source == "llm"]
        assert len(llm_issues) == 1
        assert llm_issues[0].rule_id == "llm_temporal_conflict"

    async def test_llm_checks_empty_events_skipped(
        self,
        service_with_llm: TimelineConsistencyService,
        mock_novel_repo: AsyncMock,
        mock_event_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """LLM checks should be skipped when there are no events."""
        mock_novel_repo.get_by_id.return_value = _make_novel(id=novel_id)
        mock_event_repo.list_by_novel.return_value = []

        result = await service_with_llm.check_consistency(novel_id, user_id)

        llm_issues = [i for i in result.issues if i.source == "llm"]
        assert len(llm_issues) == 0

    async def test_llm_checks_failure_does_not_crash(
        self,
        service_with_llm: TimelineConsistencyService,
        mock_novel_repo: AsyncMock,
        mock_event_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """LLM check failure should not crash the whole consistency check."""
        mock_novel_repo.get_by_id.return_value = _make_novel(id=novel_id)
        mock_event_repo.list_by_novel.return_value = [
            _make_event(event_name="Event A", temporal_order=1),
        ]

        # Make the agent import fail — _run_llm_checks catches all exceptions
        with patch(
            "narrare_core.agents.timeline_agent.TimelineAgent",
            side_effect=ImportError("No agent"),
        ):
            result = await service_with_llm.check_consistency(novel_id, user_id)

        # Should still return deterministic results
        assert result.deterministic_pass is True


class TestCombinedResultMerging:
    """Test merging of deterministic and LLM results."""

    async def test_combined_results_include_both_sources(
        self,
        service_with_llm: TimelineConsistencyService,
        mock_novel_repo: AsyncMock,
        mock_event_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """Results should include issues from both deterministic and LLM checks."""
        novel = _make_novel(id=novel_id)
        mock_novel_repo.get_by_id.return_value = novel
        mock_event_repo.list_by_novel.return_value = [
            _make_event(
                event_name="Event A",
                temporal_order=None,  # triggers missing_temporal_order
                timestamp_raw="Day 1",
            ),
        ]

        # Mock the model registry
        assert service_with_llm._registry is not None
        mock_model = AsyncMock(spec=[])
        service_with_llm._registry.get_model = AsyncMock(return_value=mock_model)

        mock_agent_result = MagicMock(spec=["temporal_conflicts"])
        mock_agent_result.temporal_conflicts = ["LLM conflict found"]

        mock_agent_instance = AsyncMock()
        mock_agent_instance.run.return_value = mock_agent_result

        with (
            patch(
                "narrare_core.agents.timeline_agent.TimelineAgent",
                return_value=mock_agent_instance,
            ),
            patch(
                "narrare_core.agents.timeline_agent.TimelineDeps",
            ),
        ):
            result = await service_with_llm.check_consistency(novel_id, user_id)

        # Should have deterministic issues (missing_temporal_order)
        det_issues = [i for i in result.issues if i.source == "deterministic"]
        assert len(det_issues) >= 1

        # Should have LLM issues
        llm_issues = [i for i in result.issues if i.source == "llm"]
        assert len(llm_issues) == 1
