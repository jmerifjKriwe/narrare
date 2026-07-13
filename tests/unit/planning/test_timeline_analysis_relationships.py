"""KB-relationship population tests for TimelineAnalysisService.

Verifies that ``TimelineAnalysisService.generate_timeline`` populates the
``kb_relationships`` variable in the ``PromptContext.extra`` dict with real
relationship data from the relationship repository, so the timeline
planner has character-relationship context for character-arc planning
(CR-AUFG-03-09).

See:
    ADR-049 — Prompt-Surface Identity & Path Contract Retrofit.
    CONSTRAINTS.md RULE-11 (graceful degradation).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare.kb.relationship_repository import RelationshipEdgeRow
from narrare.planning.timeline_analysis_service import TimelineAnalysisService
from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.planning._timeline_test_helpers import (
    FakeComposer,
    make_chapter,
    make_mock_agent,
    make_novel_model,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def novel_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_novel_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_chapter_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_registry() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def composer() -> FakeComposer:
    return FakeComposer()


@pytest.fixture
def model_config() -> ResolvedModelConfig:
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


def _make_relationship_repo(edges: list[RelationshipEdgeRow]) -> AsyncMock:
    """Build a mock RelationshipRepository returning the given edges."""
    repo = AsyncMock()
    repo.get_relationships_with_names.return_value = edges
    return repo


# ---------------------------------------------------------------------------
# kb_relationships population
# ---------------------------------------------------------------------------


class TestKBRelationshipsPopulation:
    """``kb_relationships`` is populated from the relationship repository."""

    @pytest.mark.asyncio
    async def test_kb_relationships_populated_when_repo_has_edges(
        self,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_registry: AsyncMock,
        composer: FakeComposer,
        model_config: ResolvedModelConfig,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """When ``relationship_repo`` is wired and has edges, the formatted
        relationship text flows into ``kb_relationships`` so the timeline
        planner can use character relationships for character-arc planning."""
        edges = [
            RelationshipEdgeRow(
                source_name="Alice",
                rel_type="mentor",
                label=None,
                target_name="Bob",
                direction="directed",
            ),
            RelationshipEdgeRow(
                source_name="Alice",
                rel_type="rival",
                label=None,
                target_name="Carol",
                direction="mutual",
            ),
        ]
        relationship_repo = _make_relationship_repo(edges)

        novel = make_novel_model(id=novel_id, title="My Epic", genre="fantasy")
        mock_novel_repo.get_by_id.return_value = novel
        mock_chapter_repo.list_by_novel.return_value = [
            make_chapter(position=0, title="Ch 1"),
        ]
        mock_registry.get_model.return_value = MagicMock(spec=[])

        service = TimelineAnalysisService(
            novel_repo=mock_novel_repo,
            chapter_repo=mock_chapter_repo,
            model_registry=mock_registry,
            model_config=model_config,
            composer=composer,  # type: ignore[arg-type]
            relationship_repo=relationship_repo,  # type: ignore[arg-type]
        )

        with (
            patch("narrare_core.agents.timeline_agent.TimelineAgent") as MockAgent,
            patch("narrare_core.agents.timeline_agent.TimelineDeps"),
        ):
            MockAgent.return_value = make_mock_agent()
            await service.generate_timeline(novel_id, user_id)

        ctx = composer.last_context
        assert ctx is not None, "PromptComposer.build must receive a context."
        kb_rels = getattr(ctx, "extra", {}).get("kb_relationships", "MISSING")
        assert "Alice" in kb_rels, "kb_relationships must include the Alice character."
        assert "Bob" in kb_rels, "kb_relationships must include the Bob character."
        assert "Carol" in kb_rels, "kb_relationships must include the Carol character."
        assert "→" in kb_rels, (
            "kb_relationships must use the arrow format from format_relationships."
        )

    @pytest.mark.asyncio
    async def test_kb_relationships_empty_when_repo_is_none(
        self,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_registry: AsyncMock,
        composer: FakeComposer,
        model_config: ResolvedModelConfig,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """relationship_repo=None → graceful degradation (backward compat).

        Pre-existing tests and any caller that omits ``relationship_repo``
        must keep working: ``kb_relationships`` falls back to an empty
        string so the template's variable substitution still succeeds.
        """
        novel = make_novel_model(id=novel_id)
        mock_novel_repo.get_by_id.return_value = novel
        mock_chapter_repo.list_by_novel.return_value = [
            make_chapter(position=0, title="Ch 1"),
        ]
        mock_registry.get_model.return_value = MagicMock(spec=[])

        # relationship_repo omitted → None (backward compat)
        service = TimelineAnalysisService(
            novel_repo=mock_novel_repo,
            chapter_repo=mock_chapter_repo,
            model_registry=mock_registry,
            model_config=model_config,
            composer=composer,  # type: ignore[arg-type]
        )

        with (
            patch("narrare_core.agents.timeline_agent.TimelineAgent") as MockAgent,
            patch("narrare_core.agents.timeline_agent.TimelineDeps"),
        ):
            MockAgent.return_value = make_mock_agent()
            await service.generate_timeline(novel_id, user_id)

        ctx = composer.last_context
        assert ctx is not None
        assert getattr(ctx, "extra", {}).get("kb_relationships", "MISSING") == "", (
            "kb_relationships must be empty when relationship_repo is None (graceful degradation)."
        )


# ---------------------------------------------------------------------------
# Constructor wiring
# ---------------------------------------------------------------------------


class TestTimelineRelationshipsConstructor:
    """The constructor accepts and stores ``relationship_repo``."""

    def test_constructor_stores_relationship_repo(
        self,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_registry: AsyncMock,
        composer: FakeComposer,
    ) -> None:
        service = TimelineAnalysisService(
            novel_repo=mock_novel_repo,
            chapter_repo=mock_chapter_repo,
            model_registry=mock_registry,
            composer=composer,  # type: ignore[arg-type]
            relationship_repo=AsyncMock(),  # type: ignore[arg-type]
        )
        assert service._relationship_repo is not None, "Constructor must store relationship_repo."

    def test_constructor_defaults_relationship_repo_to_none(
        self,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_registry: AsyncMock,
        composer: FakeComposer,
    ) -> None:
        service = TimelineAnalysisService(
            novel_repo=mock_novel_repo,
            chapter_repo=mock_chapter_repo,
            model_registry=mock_registry,
            composer=composer,  # type: ignore[arg-type]
        )
        assert service._relationship_repo is None, (
            "relationship_repo must default to None (backward compatibility)."
        )
