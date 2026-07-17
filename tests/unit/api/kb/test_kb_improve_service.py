"""Unit tests for KBImproveService.analyze — AI-assisted entry improvement analysis.

Tests analyze operations with mocked dependencies.
Uses AsyncMock(spec=...) and MagicMock(spec=...) patterns.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare.kb.improve_analyzer import KBImproveAnalyzer
from narrare.kb.improve_contracts import (
    ImproveSuggestionResponse,
    KBImproveAnalysisResponse,
)
from narrare.kb.improve_service import KBImproveService
from narrare_core.agents.kb_improve_types import (
    ImprovementSuggestion,
    KBImproveOutput,
    SuggestionType,
)
from narrare_core.shared.errors import NotFoundError

# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _make_entry(
    *,
    name: str = "John Smith",
    entity_type: str = "character",
    body: str = "A brave hero.",
) -> MagicMock:
    """Create a minimal mock KB entry with required attributes."""
    entry = MagicMock(spec=["name", "entity_type", "metadata_", "body", "tags", "id"])
    entry.name = name
    entry.entity_type = entity_type
    entry.metadata_ = {"age": 30, "role": "protagonist"}
    entry.body = body
    entry.tags = ["hero", "protagonist"]
    entry.id = uuid4()
    return entry


def _make_service(
    *,
    entry_exists: bool = True,
    suggestions_returned: bool = True,
    world_context_empty: bool = False,
    adjacency_fails: bool = False,
) -> tuple[KBImproveService, dict[str, AsyncMock]]:
    """Create a KBImproveService with all dependencies mocked.

    Returns (service, mocks_dict) where mocks_dict contains all
    mocked dependencies for assertion access.
    """
    entry_id = uuid4()

    # --- KB Repository ---
    kb_repo = AsyncMock(spec=["get_by_id", "get_by_slug", "create", "update", "delete"])
    if entry_exists:
        entry = _make_entry()
        kb_repo.get_by_id = AsyncMock(return_value=entry)
    else:
        kb_repo.get_by_id = AsyncMock(return_value=None)
    kb_repo.update = AsyncMock()

    # --- Relationship Repository ---
    rel_repo = AsyncMock(spec=["list_for_entry", "get_adjacency_map", "create", "delete"])
    rel_repo.list_for_entry = AsyncMock(return_value=[])
    if adjacency_fails:
        rel_repo.get_adjacency_map = AsyncMock(side_effect=RuntimeError("adjacency failed"))
    else:
        rel_repo.get_adjacency_map = AsyncMock(return_value={str(entry_id): {"related_id_1"}})
    rel_repo.create = AsyncMock()

    # --- KB Context Provider (single source for world context, ADR-067) ---
    # Mirrors the real provider's RULE-11 contract: returns the canonical
    # ``- name (type): brief`` aggregate, or "" when the KB is empty/unavailable.
    kb_context_provider = AsyncMock(spec=["fetch_world_context", "fetch_context", "fetch_entities"])
    if world_context_empty:
        kb_context_provider.fetch_world_context = AsyncMock(return_value="")
    else:
        kb_context_provider.fetch_world_context = AsyncMock(
            return_value="- World Context (world): A backdrop entity"
        )
    kb_context_provider.fetch_entities = AsyncMock(return_value=[])

    # --- Prompt Composer ---
    prompt_composer = AsyncMock(spec=["build"])
    composed = MagicMock(spec=["system"])
    composed.system = "System prompt for KB improve"
    prompt_composer.build = AsyncMock(return_value=composed)

    # --- Model Registry ---
    registry = AsyncMock(spec=["get_model"])
    model = MagicMock(spec=object)
    registry.get_model = AsyncMock(return_value=model)

    # --- KB Service ---
    kb_service = AsyncMock(spec=["get", "create", "update"])

    # --- KB Improve Agent ---
    if suggestions_returned:
        agent_output = KBImproveOutput(
            suggestions=[
                ImprovementSuggestion(
                    type=SuggestionType.ADD_FIELD,
                    target="personality",
                    description="Add personality trait",
                    proposed_content="Brave and cunning",
                    confidence=0.85,
                    reasoning="Notable trait missing",
                ),
                ImprovementSuggestion(
                    type=SuggestionType.CONNECT,
                    target="mentor",
                    description="Connect to mentor figure",
                    proposed_content="Gandalf",
                    related_entity_id=str(uuid4()),
                    related_entity_name="Gandalf",
                    confidence=0.75,
                    reasoning="Mentor relationship would enrich story",
                ),
            ],
            overall_assessment="Entry needs more detail",
            completeness_score=0.4,
        )
    else:
        agent_output = KBImproveOutput(
            suggestions=[],
            overall_assessment="Entry is complete",
            completeness_score=0.9,
        )

    config = MagicMock(spec=["provider_name", "model_id", "temperature", "max_tokens"])
    config.provider_name = "default"
    config.model_id = "default"
    config.temperature = 0.7
    config.max_tokens = 4096

    analyzer = KBImproveAnalyzer(
        registry=registry,
        config=config,
        kb_context_provider=kb_context_provider,
        prompt_composer=prompt_composer,
        kb_repo=kb_repo,
        rel_repo=rel_repo,
        improve_cache=None,
        kb_agent=None,
    )

    service = KBImproveService(
        analyzer=analyzer,
        kb_repo=kb_repo,
        kb_service=kb_service,
        rel_repo=rel_repo,
    )

    mocks = {
        "kb_repo": kb_repo,
        "rel_repo": rel_repo,
        "kb_context_provider": kb_context_provider,
        "prompt_composer": prompt_composer,
        "registry": registry,
        "kb_service": kb_service,
        "agent_output": agent_output,
    }

    return service, mocks


# ---------------------------------------------------------------------------
# Tests: analyze
# ---------------------------------------------------------------------------


class TestAnalyze:
    """Test KBImproveService.analyze — entry improvement analysis."""

    async def test_analyze_happy_path_returns_suggestions(self) -> None:
        """analyze with valid entry returns KBImproveAnalysisResponse with suggestions."""
        service, mocks = _make_service()
        novel_id = uuid4()
        entry_id = uuid4()

        with patch("narrare.kb.improve_analyzer.KBImproveAgent") as MockAgent:
            mock_agent_instance = MockAgent.return_value
            mock_agent_instance.run = AsyncMock(return_value=mocks["agent_output"])

            result = await service.analyze(
                novel_id=novel_id,
                entry_id=entry_id,
            )

        assert isinstance(result, KBImproveAnalysisResponse)
        assert len(result.suggestions) > 0
        assert result.overall_assessment == "Entry needs more detail"
        assert result.completeness_score == 0.4

        # Verify first suggestion has correct shape
        first = result.suggestions[0]
        assert isinstance(first, ImproveSuggestionResponse)
        assert first.type == "add_field"
        assert first.target == "personality"
        assert first.confidence == 0.85

    async def test_analyze_missing_entry_raises_not_found(self) -> None:
        """analyze with nonexistent entry raises NotFoundError."""
        service, _mocks = _make_service(entry_exists=False)
        novel_id = uuid4()
        entry_id = uuid4()

        with pytest.raises(NotFoundError):
            await service.analyze(
                novel_id=novel_id,
                entry_id=entry_id,
            )

    async def test_analyze_empty_world_context_still_works(self) -> None:
        """analyze still returns suggestions when the KB is empty (RULE-11).

        The KBContextProvider degrades to an empty world_context string on an
        empty/unavailable KB; analyze must still compose its deps and run.
        """
        service, mocks = _make_service(world_context_empty=True)
        novel_id = uuid4()
        entry_id = uuid4()

        with patch("narrare.kb.improve_analyzer.KBImproveAgent") as MockAgent:
            mock_agent_instance = MockAgent.return_value
            mock_agent_instance.run = AsyncMock(return_value=mocks["agent_output"])

            result = await service.analyze(
                novel_id=novel_id,
                entry_id=entry_id,
            )

        # Should still return suggestions (world_context is empty but not fatal)
        assert isinstance(result, KBImproveAnalysisResponse)
        assert len(result.suggestions) > 0
        # World context was sourced via the provider (single source, ADR-067).
        mocks["kb_context_provider"].fetch_world_context.assert_called_once()

    async def test_analyze_adjacency_map_fails_gracefully(self) -> None:
        """analyze still works when adjacency map is unavailable."""
        service, mocks = _make_service(adjacency_fails=True)
        novel_id = uuid4()
        entry_id = uuid4()

        with patch("narrare.kb.improve_analyzer.KBImproveAgent") as MockAgent:
            mock_agent_instance = MockAgent.return_value
            mock_agent_instance.run = AsyncMock(return_value=mocks["agent_output"])

            result = await service.analyze(
                novel_id=novel_id,
                entry_id=entry_id,
            )

        assert isinstance(result, KBImproveAnalysisResponse)
        assert len(result.suggestions) > 0
        # Verify rel_repo was still called for adjacency
        mocks["rel_repo"].get_adjacency_map.assert_called_once()

    async def test_analyze_empty_suggestions_returns_empty_list(self) -> None:
        """analyze returns empty suggestions list when agent finds no improvements."""
        service, mocks = _make_service(suggestions_returned=False)
        novel_id = uuid4()
        entry_id = uuid4()

        with patch("narrare.kb.improve_analyzer.KBImproveAgent") as MockAgent:
            mock_agent_instance = MockAgent.return_value
            mock_agent_instance.run = AsyncMock(return_value=mocks["agent_output"])

            result = await service.analyze(
                novel_id=novel_id,
                entry_id=entry_id,
            )

        assert isinstance(result, KBImproveAnalysisResponse)
        assert len(result.suggestions) == 0
        assert result.completeness_score == 0.9
