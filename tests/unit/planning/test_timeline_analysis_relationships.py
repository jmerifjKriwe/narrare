"""KB-context population tests for TimelineAnalysisService (ADR-067).

Verifies that ``TimelineAnalysisService.generate_timeline`` populates the
``kb_relationships`` variable in the ``PromptContext.extra`` dict with real
relationship data flowing through the canonical KB-context provider
(:class:`narrare.kb._context_provider.KBContextProvider`), so the timeline
planner has character-relationship context for character-arc planning
(CR-AUFG-03-09).

The provider wires the real fetch+render path (``list_entities`` /
``format_relationships``); only the repositories are faked, so this proves the
genuine service → provider → ``PromptContext.extra`` chain (no proxy padding).

See:
    ADR-067 — Reusable KB-Context Provider.
    ADR-049 — Prompt-Surface Identity & Path Contract Retrofit.
    CONSTRAINTS.md RULE-11 (graceful degradation).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare.kb._context_provider import KBContextProvider
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
    """Build a fake RelationshipRepository returning the given edges."""
    repo = AsyncMock()
    repo.get_relationships_with_names.return_value = edges
    return repo


def _make_empty_kb_repo() -> AsyncMock:
    """Fake KBRepository whose ``list_entries`` yields no entries.

    The provider only needs a non-None repo that returns an empty page so it
    proceeds past the entity-fetch guard to render relationships; the entity
    slots degrade to empty (RULE-11). ``list_entities`` calls
    ``list_entries(novel_id=..., page=..., page_size=100)`` and stops once a
    batch is shorter than the page size, so a single empty page terminates it.
    """
    repo = AsyncMock()
    repo.list_entries.return_value = ([], 0)
    return repo


# ---------------------------------------------------------------------------
# kb_relationships population (via the canonical KB-context provider)
# ---------------------------------------------------------------------------


class TestKBRelationshipsPopulation:
    """``kb_relationships`` is populated through the KB-context provider."""

    @pytest.mark.asyncio
    async def test_kb_relationships_populated_when_provider_has_edges(
        self,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_registry: AsyncMock,
        composer: FakeComposer,
        model_config: ResolvedModelConfig,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """When the provider's relationship repo has edges, the formatted
        relationship text flows into ``kb_relationships`` so the timeline
        planner can use character relationships for character-arc planning.

        The real ``KBContextProvider`` is wired (ADR-067); the empty KB repo
        makes the entity slots degrade to empty while relationships still
        render — proving the service → provider → context chain end-to-end."""
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
        kb_context_provider = KBContextProvider(
            kb_repo=_make_empty_kb_repo(),  # type: ignore[arg-type]
            relationship_repo=_make_relationship_repo(edges),  # type: ignore[arg-type]
        )

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
            kb_context_provider=kb_context_provider,  # type: ignore[arg-type]
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
    async def test_kb_relationships_empty_when_no_provider(
        self,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_registry: AsyncMock,
        composer: FakeComposer,
        model_config: ResolvedModelConfig,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """kb_context_provider=None → graceful degradation (RULE-11).

        The service falls back to ``KBContextBundle.empty()`` so every kb_*
        slot — including ``kb_relationships`` — is an empty string and the
        template's variable substitution still succeeds without an exception.
        """
        novel = make_novel_model(id=novel_id)
        mock_novel_repo.get_by_id.return_value = novel
        mock_chapter_repo.list_by_novel.return_value = [
            make_chapter(position=0, title="Ch 1"),
        ]
        mock_registry.get_model.return_value = MagicMock(spec=[])

        # kb_context_provider omitted → None (RULE-11: empty bundle)
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
            "kb_relationships must be empty when no provider is wired (RULE-11)."
        )


# ---------------------------------------------------------------------------
# Constructor wiring
# ---------------------------------------------------------------------------


class TestTimelineKbContextConstructor:
    """The constructor accepts and stores ``kb_context_provider``."""

    def test_constructor_stores_kb_context_provider(
        self,
        mock_novel_repo: AsyncMock,
        mock_chapter_repo: AsyncMock,
        mock_registry: AsyncMock,
        composer: FakeComposer,
    ) -> None:
        provider = KBContextProvider(kb_repo=None, relationship_repo=None)
        service = TimelineAnalysisService(
            novel_repo=mock_novel_repo,
            chapter_repo=mock_chapter_repo,
            model_registry=mock_registry,
            composer=composer,  # type: ignore[arg-type]
            kb_context_provider=provider,
        )
        assert service._kb_context_provider is not None, (
            "Constructor must store kb_context_provider."
        )

    def test_constructor_defaults_kb_context_provider_to_none(
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
        assert service._kb_context_provider is None, (
            "kb_context_provider must default to None (graceful degradation)."
        )
