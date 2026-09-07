"""Unit tests for KBImproveService.apply — applying improvement suggestions.

Extracted from test_kb_improve_service.py for RULE-04 compliance.
Uses factory helpers defined here to keep tests self-contained.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare.kb.improve_contracts import KBImproveApplyResponse
from narrare_core.llm import ResolvedModelConfig
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from narrare.kb.improve_service import KBImproveService
    from narrare_core.agents.kb_improve_types import ImprovementSuggestion

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
    extra_suggestions: list[ImprovementSuggestion] | None = None,
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
    kb_context_provider = AsyncMock(spec=["fetch_world_context", "fetch_context", "fetch_entities"])
    kb_context_provider.fetch_world_context = AsyncMock(
        return_value="" if world_context_empty else "- World Context (world): A backdrop"
    )
    kb_context_provider.fetch_entities = AsyncMock(return_value=[])

    # --- Prompt Composer ---
    prompt_composer = AsyncMock(spec=["build"])
    composed = MagicMock(spec=["system"])
    composed.system = "System prompt for KB improve"
    prompt_composer.build = AsyncMock(return_value=composed)

    # --- Model Registry (Task 6c: prepare() assembly point) ---
    registry = AsyncMock(spec=["prepare"])
    registry.prepare = AsyncMock(
        return_value=SimpleNamespace(
            model=MagicMock(spec=object), model_settings=None, usage_limits=None
        )
    )

    # --- KB Service ---
    kb_service = AsyncMock(spec=["get", "create", "update"])

    # --- KB Improve Agent output ---
    if suggestions_returned:
        from narrare_core.agents.kb_improve_types import (
            ImprovementSuggestion,
            KBImproveOutput,
            SuggestionType,
        )

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
                *(extra_suggestions or []),
            ],
            overall_assessment="Entry needs more detail",
            completeness_score=0.4,
        )
    else:
        from narrare_core.agents.kb_improve_types import KBImproveOutput

        agent_output = KBImproveOutput(
            suggestions=[],
            overall_assessment="Entry is complete",
            completeness_score=0.9,
        )

    # Real config value object — the ADR-045 run-limit resolver (Task 3)
    # reads resolve_output_limit()/token_limit_profile from it.
    config = ResolvedModelConfig(
        provider_name="default", model_id="default", temperature=0.7, max_tokens=4096
    )

    from narrare.kb.improve_analyzer import KBImproveAnalyzer
    from narrare.kb.improve_service import KBImproveService

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
# Tests: apply
# ---------------------------------------------------------------------------


class TestApply:
    """Test KBImproveService.apply — applying improvement suggestions."""

    async def test_apply_happy_path_applies_suggestions(self) -> None:
        """apply with valid suggestion_ids applies changes and returns success."""
        service, mocks = _make_service()
        novel_id = uuid4()
        entry_id = uuid4()

        with patch("narrare.kb.improve_analyzer.KBImproveAgent") as MockAgent:
            mock_agent_instance = MockAgent.return_value
            mock_agent_instance.run = AsyncMock(return_value=mocks["agent_output"])

            result = await service.apply(
                novel_id=novel_id,
                entry_id=entry_id,
                suggestion_ids=[0, 1],
            )

        assert isinstance(result, KBImproveApplyResponse)
        assert result.success is True
        assert result.applied_count > 0
        assert result.entry_id is not None

    async def test_apply_no_valid_suggestions_returns_failure(self) -> None:
        """apply with no matching suggestion_ids returns success=False."""
        service, mocks = _make_service()
        novel_id = uuid4()
        entry_id = uuid4()

        with patch("narrare.kb.improve_analyzer.KBImproveAgent") as MockAgent:
            mock_agent_instance = MockAgent.return_value
            mock_agent_instance.run = AsyncMock(return_value=mocks["agent_output"])

            # Use suggestion_ids that don't match (e.g., 999)
            result = await service.apply(
                novel_id=novel_id,
                entry_id=entry_id,
                suggestion_ids=[999],
            )

        assert result.success is False
        assert result.applied_count == 0
        assert "No valid suggestions" in result.message

    async def test_apply_missing_entry_raises_not_found(self) -> None:
        """apply with nonexistent entry raises NotFoundError."""
        service, _mocks = _make_service(entry_exists=False)
        novel_id = uuid4()
        entry_id = uuid4()

        with pytest.raises(NotFoundError):
            await service.apply(
                novel_id=novel_id,
                entry_id=entry_id,
                suggestion_ids=[0],
            )

    async def test_apply_empty_suggestion_ids_returns_empty(self) -> None:
        """apply with empty suggestion_ids list returns success=False."""
        service, mocks = _make_service()
        novel_id = uuid4()
        entry_id = uuid4()

        with patch("narrare.kb.improve_analyzer.KBImproveAgent") as MockAgent:
            mock_agent_instance = MockAgent.return_value
            mock_agent_instance.run = AsyncMock(return_value=mocks["agent_output"])

            result = await service.apply(
                novel_id=novel_id,
                entry_id=entry_id,
                suggestion_ids=[],
            )

        assert result.success is False
        assert result.applied_count == 0


# ---------------------------------------------------------------------------
# Tests: reserved metadata keys (ADR-085 §5/§6 invariant)
# ---------------------------------------------------------------------------


def _reserved_target_suggestion(target: str) -> ImprovementSuggestion:
    from narrare_core.agents.kb_improve_types import ImprovementSuggestion, SuggestionType

    return ImprovementSuggestion(
        type=SuggestionType.ADD_FIELD,
        target=target,
        description="LLM forge attempt",
        proposed_content="forged by the model",
        confidence=0.9,
        reasoning="Model proposed a platform-reserved key",
    )


class TestApplyReservedKeyGuard:
    """LLM proposals can never write ``provenance``/``resolution`` keys.

    Same invariant class as the extraction apply flow: platform-reserved
    metadata keys are stripped from every proposal consumption site. The
    improve path historically wrote ``suggestion.proposed_content`` under
    ``suggestion.target`` unguarded (progress.md Task 10 binding note).
    """

    async def test_apply_reserved_target_is_not_written(self) -> None:
        """A forged ``resolution`` target is skipped; normal keys still land."""
        reserved = _reserved_target_suggestion("resolution")
        service, mocks = _make_service(extra_suggestions=[reserved])
        novel_id = uuid4()
        entry_id = uuid4()

        with patch("narrare.kb.improve_analyzer.KBImproveAgent") as MockAgent:
            mock_agent_instance = MockAgent.return_value
            mock_agent_instance.run = AsyncMock(return_value=mocks["agent_output"])

            result = await service.apply(
                novel_id=novel_id,
                entry_id=entry_id,
                suggestion_ids=[0, 2],
            )

        assert result.success is True
        metadata_updates = mocks["kb_repo"].update.await_args.args[1]["metadata_"]
        assert "resolution" not in metadata_updates
        assert metadata_updates["personality"] == "Brave and cunning"

    async def test_apply_provenance_target_is_not_written(self) -> None:
        """The ``provenance`` key is equally protected (forge guard)."""
        service, mocks = _make_service(
            extra_suggestions=[_reserved_target_suggestion("provenance")],
        )
        novel_id = uuid4()
        entry_id = uuid4()

        with patch("narrare.kb.improve_analyzer.KBImproveAgent") as MockAgent:
            mock_agent_instance = MockAgent.return_value
            mock_agent_instance.run = AsyncMock(return_value=mocks["agent_output"])

            await service.apply(
                novel_id=novel_id,
                entry_id=entry_id,
                suggestion_ids=[2],
            )

        # Only the reserved suggestion was selected → nothing else to write,
        # so kb_repo.update must not have been called at all.
        mocks["kb_repo"].update.assert_not_awaited()
