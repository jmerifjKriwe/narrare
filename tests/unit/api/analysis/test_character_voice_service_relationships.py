"""KB-relationship population tests for CharacterVoiceService (ANAL-008).

Verifies that ``CharacterVoiceService.analyze`` populates the
``kb_relationships`` variable in the ``PromptContext.extra`` dict with
real relationship data from the relationship repository, so the
character-voice profiler has character-relationship context — especially
valuable for voice profiling where character relationships are
charakterprägend (CR-AUFG-03-09).

Mirrors the ``kb_characters`` pattern from
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
from tests.unit.api.analysis._character_voice_test_helpers import (
    FakeComposer,
    consume,
    make_agent_output,
    make_chapter,
    make_kb_entry,
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


def _wire_kb_repo_for_two_characters() -> AsyncMock:
    """Wire a KB repo that returns entries for Elena and Marc."""
    kb_repo = AsyncMock()
    kb_repo.get_by_name = AsyncMock(
        side_effect=lambda _nid, name: {
            "Elena": make_kb_entry(name="Elena"),
            "Marc": make_kb_entry(name="Marc"),
        }.get(name)
    )
    kb_repo.update = AsyncMock()
    return kb_repo


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
        character-voice profiler can use character relationships as
        charakterprägend context (e.g. Elena's formal register may stem
        from her courtly alliance with the queen)."""
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
        kb_repo = _wire_kb_repo_for_two_characters()

        novel = make_novel(title="My Epic", genre="Fantasy", writing_language="en")
        chapter = make_chapter(novel_id=novel.id)

        service = make_service(
            composer, config, kb_repo=kb_repo, relationship_repo=relationship_repo
        )  # type: ignore[arg-type]
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]
        service._chapter_repo.list_by_novel = AsyncMock(return_value=[chapter])  # type: ignore[attr-defined]

        with patch_mode1() as (_MockAgent, _MockDeps, mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            _MockAgent.return_value = mock_agent

            await consume(service.analyze(novel.id, None, uuid.uuid4()))  # type: ignore[arg-type]

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
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """relationship_repo=None → graceful degradation (backward compat).

        Pre-existing tests and any caller that omits ``relationship_repo``
        must keep working: ``kb_relationships`` falls back to an empty
        string so the template's variable substitution still succeeds.
        """
        kb_repo = _wire_kb_repo_for_two_characters()

        novel = make_novel()
        chapter = make_chapter(novel_id=novel.id)

        service = make_service(composer, config, kb_repo=kb_repo)  # relationship_repo omitted
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]
        service._chapter_repo.list_by_novel = AsyncMock(return_value=[chapter])  # type: ignore[attr-defined]

        with patch_mode1() as (_MockAgent, _MockDeps, mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_agent_output())
            _MockAgent.return_value = mock_agent

            await consume(service.analyze(novel.id, None, uuid.uuid4()))  # type: ignore[arg-type]

        ctx = mock_compose.call_args.kwargs.get("prompt_context")
        assert ctx is not None
        assert ctx.extra["kb_relationships"] == "", (
            "kb_relationships must be empty when relationship_repo is None (graceful degradation)."
        )


# ---------------------------------------------------------------------------
# Constructor wiring
# ---------------------------------------------------------------------------


class TestCharacterVoiceServiceRelationshipsConstructor:
    """The constructor accepts and stores ``relationship_repo``."""

    def test_constructor_stores_relationship_repo(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        from narrare.analysis.character_voice_service import CharacterVoiceService
        from tests.unit.api.analysis._character_voice_test_helpers import FakeModelRegistry

        service = CharacterVoiceService(
            novel_repo=AsyncMock(),  # type: ignore[arg-type]
            chapter_repo=AsyncMock(),  # type: ignore[arg-type]
            kb_repo=AsyncMock(),  # type: ignore[arg-type]
            relationship_repo=AsyncMock(),  # type: ignore[arg-type]
            model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
            model_config=config,
            composer=composer,  # type: ignore[arg-type]
        )

        assert service._relationship_repo is not None, "Constructor must store relationship_repo."

    def test_constructor_defaults_relationship_repo_to_none(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        from narrare.analysis.character_voice_service import CharacterVoiceService
        from tests.unit.api.analysis._character_voice_test_helpers import FakeModelRegistry

        service = CharacterVoiceService(
            novel_repo=AsyncMock(),  # type: ignore[arg-type]
            chapter_repo=AsyncMock(),  # type: ignore[arg-type]
            kb_repo=AsyncMock(),  # type: ignore[arg-type]
            model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
            model_config=config,
            composer=composer,  # type: ignore[arg-type]
        )

        assert service._relationship_repo is None, (
            "relationship_repo must default to None (backward compatibility)."
        )
