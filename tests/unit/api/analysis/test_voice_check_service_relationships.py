"""KB-relationship population tests for CharacterVoiceCheckerService (WRITE-010).

Verifies that the voice-check pipeline populates the ``kb_relationships``
variable in the ``PromptContext.extra`` dict with real relationship data
from the relationship repository, so the voice checker has
character-relationship context when checking dialogue against stored
profiles (CR-AUFG-03-09).

The wiring chain is:
``CharacterVoiceCheckerService.check()``
→ ``run_voice_checker_agent(relationship_repo=...)``
→ ``resolve_voice_check_prompt(kb_relationships=...)``
→ ``PromptContext.extra["kb_relationships"]``

See:
    ADR-057 — Voice-check checking-path contract.
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
    CONSTRAINTS.md RULE-11 (graceful degradation).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.kb.relationship_repository import RelationshipEdgeRow
from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.analysis._voice_check_test_helpers import (
    FakeVoiceProfileConsumer,
    consume,
    make_agent_output,
    make_chapter,
    make_novel,
    make_profile,
    make_service,
    patch_mode1,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
        config: ResolvedModelConfig,
    ) -> None:
        """When ``relationship_repo`` is wired and has edges, the formatted
        relationship text flows into ``kb_relationships`` so the voice
        checker can use character relationships when evaluating whether
        dialogue matches established profiles (e.g. Elena's tone toward
        her ally may differ from her tone toward her rival)."""
        edges = [
            RelationshipEdgeRow(
                source_name="Elena",
                rel_type="ally",
                label=None,
                target_name="Queen",
                direction="mutual",
            ),
            RelationshipEdgeRow(
                source_name="Marc",
                rel_type="rival",
                label=None,
                target_name="Elena",
                direction="directed",
            ),
        ]
        relationship_repo = _make_relationship_repo(edges)

        novel = make_novel()
        chapter = make_chapter(novel_id=novel.id)
        consumer = FakeVoiceProfileConsumer([make_profile("Elena"), make_profile("Marc")])
        service = make_service(
            novel=novel,
            chapter=chapter,
            consumer=consumer,
            config=config,
            relationship_repo=relationship_repo,  # type: ignore[arg-type]
        )

        with patch_mode1() as (MockAgent, mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            await consume(service.check(chapter.id, uuid.uuid4()))

        ctx = mock_compose.call_args.kwargs.get("prompt_context")
        assert ctx is not None, "prompt_context must be supplied to compose_invocation."
        kb_rels = ctx.extra["kb_relationships"]
        assert "Elena" in kb_rels, "kb_relationships must include the Elena character."
        assert "Queen" in kb_rels, "kb_relationships must include the Queen character."
        assert "Marc" in kb_rels, "kb_relationships must include the Marc character."
        assert "→" in kb_rels, (
            "kb_relationships must use the arrow format from format_relationships."
        )

    @pytest.mark.asyncio
    async def test_kb_relationships_empty_when_repo_is_none(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        """relationship_repo=None → graceful degradation (backward compat).

        Pre-existing tests and any caller that omits ``relationship_repo``
        must keep working: ``kb_relationships`` falls back to an empty
        string so the template's variable substitution still succeeds.
        """
        novel = make_novel()
        chapter = make_chapter(novel_id=novel.id)
        consumer = FakeVoiceProfileConsumer([make_profile("Elena"), make_profile("Marc")])
        service = make_service(novel=novel, chapter=chapter, consumer=consumer, config=config)

        with patch_mode1() as (MockAgent, mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            MockAgent.return_value = mock_agent

            await consume(service.check(chapter.id, uuid.uuid4()))

        ctx = mock_compose.call_args.kwargs.get("prompt_context")
        assert ctx is not None
        assert ctx.extra["kb_relationships"] == "", (
            "kb_relationships must be empty when relationship_repo is None (graceful degradation)."
        )


# ---------------------------------------------------------------------------
# Constructor wiring
# ---------------------------------------------------------------------------


class TestVoiceCheckRelationshipsConstructor:
    """The constructor accepts and stores ``relationship_repo``."""

    def test_constructor_stores_relationship_repo(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        from narrare.analysis.voice_check_service import CharacterVoiceCheckerService
        from tests.unit.api.analysis._voice_check_test_helpers import FakeModelRegistry

        async def _provider(project_id: uuid.UUID) -> object:
            return None

        service = CharacterVoiceCheckerService(
            novel_repo=AsyncMock(),  # type: ignore[arg-type]
            chapter_repo=AsyncMock(),  # type: ignore[arg-type]
            model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
            consumer_provider=_provider,  # type: ignore[arg-type]
            model_config=config,
            relationship_repo=AsyncMock(),  # type: ignore[arg-type]
        )

        assert service._relationship_repo is not None, "Constructor must store relationship_repo."

    def test_constructor_defaults_relationship_repo_to_none(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        from narrare.analysis.voice_check_service import CharacterVoiceCheckerService
        from tests.unit.api.analysis._voice_check_test_helpers import FakeModelRegistry

        async def _provider(project_id: uuid.UUID) -> object:
            return None

        service = CharacterVoiceCheckerService(
            novel_repo=AsyncMock(),  # type: ignore[arg-type]
            chapter_repo=AsyncMock(),  # type: ignore[arg-type]
            model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
            consumer_provider=_provider,  # type: ignore[arg-type]
            model_config=config,
        )

        assert service._relationship_repo is None, (
            "relationship_repo must default to None (backward compatibility)."
        )
