"""KB-relationship population tests for CoreferenceService (ANAL-005).

Verifies that ``CoreferenceService.analyze`` populates the
``kb_relationships`` variable in the ``PromptContext.extra`` dict with
real relationship data from the relationship repository, so the
coreference model has character-relationship context when resolving
pronouns and tracking mentions (the gap described in CR-AUFG-03-09).

Mirrors the ``kb_characters`` population tests in
``test_coreference_service_kb.py`` (same graceful-degradation contract).

See:
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
    CONSTRAINTS.md RULE-11 (graceful degradation).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

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
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """When ``relationship_repo`` is wired and has edges, the formatted
        relationship text flows into ``kb_relationships`` so the
        coreference model can use character relationships for pronoun
        resolution and mention tracking."""
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
        relationship_repo = _make_relationship_repo(edges)

        service = make_service(composer, config, relationship_repo=relationship_repo)  # type: ignore[arg-type]
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
    async def test_kb_relationships_empty_when_repo_is_none(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """relationship_repo=None → graceful degradation (backward compat).

        Pre-existing tests and any caller that omits ``relationship_repo``
        must keep working: ``kb_relationships`` falls back to an empty
        string so the template's variable substitution still succeeds.
        """
        service = make_service(composer, config)  # relationship_repo omitted → None
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
            "kb_relationships must be empty when relationship_repo is None (graceful degradation)."
        )

    @pytest.mark.asyncio
    async def test_kb_relationships_empty_when_repo_has_no_edges(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """An empty edge list also degrades gracefully to empty text."""
        relationship_repo = _make_relationship_repo([])

        service = make_service(composer, config, relationship_repo=relationship_repo)  # type: ignore[arg-type]
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
            "kb_relationships must be empty when the repo has no edges."
        )


# ---------------------------------------------------------------------------
# Constructor wiring
# ---------------------------------------------------------------------------


class TestCoreferenceServiceRelationshipsConstructor:
    """The constructor accepts and stores the optional ``relationship_repo``."""

    def test_constructor_stores_relationship_repo(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        from narrare.analysis.coreference_service import CoreferenceService
        from tests.unit.api.analysis._coreference_test_helpers import FakeModelRegistry

        service = CoreferenceService(
            novel_repo=AsyncMock(),  # type: ignore[arg-type]
            chapter_repo=AsyncMock(),  # type: ignore[arg-type]
            model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
            model_config=config,
            composer=composer,  # type: ignore[arg-type]
            relationship_repo=AsyncMock(),  # type: ignore[arg-type]
        )

        assert service._relationship_repo is not None, "Constructor must store relationship_repo."

    def test_constructor_defaults_relationship_repo_to_none(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        from narrare.analysis.coreference_service import CoreferenceService
        from tests.unit.api.analysis._coreference_test_helpers import FakeModelRegistry

        service = CoreferenceService(
            novel_repo=AsyncMock(),  # type: ignore[arg-type]
            chapter_repo=AsyncMock(),  # type: ignore[arg-type]
            model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
            model_config=config,
            composer=composer,  # type: ignore[arg-type]
        )

        assert service._relationship_repo is None, (
            "relationship_repo must default to None (backward compatibility)."
        )
