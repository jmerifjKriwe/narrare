"""KB-relationship population tests for CoreferenceService (ANAL-005, W4a).

Verifies that ``CoreferenceService.analyze`` populates the
``kb_relationships`` variable in the ``PromptContext.extra`` dict with real
relationship data flowing through the canonical KB-context provider
(:class:`narrare.kb._context_provider.KBContextProvider`, ADR-067), so the
coreference model has character-relationship context when resolving pronouns
and tracking mentions (CR-AUFG-03-09). Relationships now route through the
same provider as the entity slots (single KB-context source), matching the
W2 timeline pattern.

The provider wires the real fetch+render path (``format_relationships``);
only the repositories are faked, so this proves the genuine
service → provider → ``PromptContext.extra`` chain (no proxy padding).

See:
    ADR-067 — Reusable KB-Context Provider.
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
    CONSTRAINTS.md RULE-11 (graceful degradation).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.kb._context_provider import KBContextProvider
from narrare.kb.relationship_repository import RelationshipEdgeRow
from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.analysis._coreference_test_helpers import (
    FakeComposer,
    consume,
    make_agent_output,
    make_chapter,
    make_novel,
    make_service,
    patch_mode1,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def composer() -> FakeComposer:
    return FakeComposer()


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


def _make_relationship_repo(edges: list[RelationshipEdgeRow]) -> AsyncMock:
    """Build a fake RelationshipRepository returning the given edges."""
    repo = AsyncMock()
    repo.get_relationships_with_names.return_value = edges
    return repo


def _make_empty_kb_repo() -> AsyncMock:
    """Fake KBRepository whose ``list_entries`` yields no entries.

    The provider only needs a non-None repo that returns an empty page so it
    proceeds to render relationships; the entity slots degrade to empty
    (RULE-11). ``list_entities`` paginates and stops once a batch is shorter
    than the page size, so a single empty page terminates it.
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
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """When the provider's relationship repo has edges, the formatted
        relationship text flows into ``kb_relationships`` so the coreference
        model can use character relationships for pronoun resolution and
        mention tracking.

        The real ``KBContextProvider`` is wired (ADR-067); the empty KB repo
        makes the entity slots degrade to empty while relationships still
        render — proving the service → provider → context chain end-to-end."""
        edges = [
            RelationshipEdgeRow(
                source_name="Alice",
                rel_type="ally",
                label=None,
                target_name="Bob",
                direction="mutual",
            ),
            RelationshipEdgeRow(
                source_name="Alice",
                rel_type="sister_of",
                label=None,
                target_name="Carol",
                direction="mutual",
            ),
        ]
        kb_context_provider = KBContextProvider(
            kb_repo=_make_empty_kb_repo(),  # type: ignore[arg-type]
            relationship_repo=_make_relationship_repo(edges),  # type: ignore[arg-type]
        )

        service = make_service(composer, config, kb_context_provider=kb_context_provider)
        service._chapter_repo.get.return_value = make_chapter()  # type: ignore[attr-defined]
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with patch_mode1() as (_MockAgent, _MockDeps, mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            _MockAgent.return_value = mock_agent

            await consume(service.analyze(uuid.uuid4(), uuid.uuid4()))  # type: ignore[arg-type]

        ctx = mock_compose.call_args.kwargs.get("prompt_context")
        assert ctx is not None, "prompt_context must be supplied to compose_invocation."
        kb_rels = ctx.extra["kb_relationships"]
        assert "Alice" in kb_rels, "kb_relationships must include the Alice character."
        assert "Bob" in kb_rels, "kb_relationships must include the Bob character."
        assert "Carol" in kb_rels, "kb_relationships must include the Carol character."
        assert "→" in kb_rels, (
            "kb_relationships must use the arrow format from format_relationships."
        )

    @pytest.mark.asyncio
    async def test_kb_relationships_empty_when_no_provider(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """kb_context_provider=None → graceful degradation (RULE-11).

        The service falls back to ``KBContextBundle.empty()`` so
        ``kb_relationships`` is an empty string and the template's variable
        substitution still succeeds without an exception.
        """
        service = make_service(composer, config)  # provider omitted → None
        service._chapter_repo.get.return_value = make_chapter()  # type: ignore[attr-defined]
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with patch_mode1() as (_MockAgent, _MockDeps, mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            _MockAgent.return_value = mock_agent

            await consume(service.analyze(uuid.uuid4(), uuid.uuid4()))  # type: ignore[arg-type]

        ctx = mock_compose.call_args.kwargs.get("prompt_context")
        assert ctx is not None
        assert ctx.extra["kb_relationships"] == "", (
            "kb_relationships must be empty when no provider is wired (RULE-11)."
        )

    @pytest.mark.asyncio
    async def test_kb_relationships_empty_when_provider_has_no_edges(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """An empty edge list also degrades gracefully to empty text."""
        kb_context_provider = KBContextProvider(
            kb_repo=_make_empty_kb_repo(),  # type: ignore[arg-type]
            relationship_repo=_make_relationship_repo([]),  # type: ignore[arg-type]
        )

        service = make_service(composer, config, kb_context_provider=kb_context_provider)
        service._chapter_repo.get.return_value = make_chapter()  # type: ignore[attr-defined]
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with patch_mode1() as (_MockAgent, _MockDeps, mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            _MockAgent.return_value = mock_agent

            await consume(service.analyze(uuid.uuid4(), uuid.uuid4()))  # type: ignore[arg-type]

        ctx = mock_compose.call_args.kwargs.get("prompt_context")
        assert ctx is not None
        assert ctx.extra["kb_relationships"] == "", (
            "kb_relationships must be empty when the provider has no edges."
        )
