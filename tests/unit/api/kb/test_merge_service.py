"""Unit tests for KBMergeService — invocation composition (ADR-048 Mode 2).

Verifies that ``analyze_merge_candidates`` routes through ``compose_invocation``
with the correct Mode 2 (agent-internal) declaration, replacing the
deprecated ``safe_record_evidence()`` placeholder path.

See:
    ADR-048, ADR-045 Decision 7,
    CONSTRAINTS.md RULE-02a/RULE-03/RULE-11.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from narrare.kb.merge_service import _MERGE_MANUAL_INJECTION, KBMergeService
from narrare.kb.schemas_merge import MergeRequest
from narrare_core.agents.merge_types import MergeOutput
from narrare_core.llm import ResolvedModelConfig

# ---------------------------------------------------------------------------
# Fake dependency classes (avoid bare MagicMock for domain contracts — RULE-TEST-01)
# ---------------------------------------------------------------------------


class FakeNovelRepo:
    """Fake NovelRepository for KBMergeService tests."""

    def __init__(self) -> None:
        self.get_by_id: AsyncMock = AsyncMock()


class FakeModelRegistry:
    """Fake ModelRegistry returning a stub Model."""

    def __init__(self) -> None:
        self.get_model: AsyncMock = AsyncMock(return_value=MagicMock(spec=object))


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def make_novel() -> MagicMock:
    """Create a mock novel with the attributes KBMergeService reads."""
    novel = MagicMock(spec=["id", "title", "genre", "writing_language"])
    novel.id = uuid4()
    novel.title = "Test Novel"
    novel.genre = "Fantasy"
    novel.writing_language = "en"
    return novel


def make_merge_output() -> MagicMock:
    """Create a mock KBMergeAgent output (MergeOutput-shaped)."""
    return MagicMock(
        spec=MergeOutput,
        merge_decisions=[],
        overall_notes="No merge candidates found.",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(
        provider_name="test", model_id="test-model", temperature=0.7, max_tokens=4096
    )


@pytest.fixture
def novel_repo() -> FakeNovelRepo:
    repo = FakeNovelRepo()
    repo.get_by_id.return_value = make_novel()
    return repo


@pytest.fixture
def registry() -> FakeModelRegistry:
    return FakeModelRegistry()


# ---------------------------------------------------------------------------
# Invocation composition — ADR-048 Mode 2 (agent-internal)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_merge_candidates_calls_compose_invocation_mode2(
    config: ResolvedModelConfig,
    novel_repo: FakeNovelRepo,
    registry: FakeModelRegistry,
) -> None:
    """analyze_merge_candidates routes through compose_invocation (Mode 2) per ADR-048.

    Replaces the deprecated safe_record_evidence() placeholder path. The
    service must call compose_invocation with the KBMergeAgent's
    ManualInjectionDeclaration and the kb_merge feature_id.
    """
    novel_id: UUID = uuid4()

    service = KBMergeService(
        novel_repo=novel_repo,  # type: ignore[arg-type]
        model_registry=registry,  # type: ignore[arg-type]
        model_config=config,
    )

    request = MergeRequest(
        entity_type="character",
        candidate_pairs=[{"a": "Anna", "b": "Ana"}],
    )

    with (
        patch("narrare_core.agents.merge_agent.KBMergeAgent") as MockAgent,
        patch("narrare_core.ai_invocation.compose_invocation", new=AsyncMock()) as mock_compose,
    ):
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=make_merge_output())
        MockAgent.return_value = mock_agent

        await service.analyze_merge_candidates(
            novel_id=novel_id,
            user_id=uuid4(),
            request=request,
        )

    mock_compose.assert_awaited_once()
    kwargs = mock_compose.call_args.kwargs
    assert kwargs["manual_injection"] is _MERGE_MANUAL_INJECTION
    assert kwargs["invocation_context"].feature_id == "kb_merge"


@pytest.mark.asyncio
async def test_analyze_merge_candidates_compose_invocation_failure_is_graceful(
    config: ResolvedModelConfig,
    novel_repo: FakeNovelRepo,
    registry: FakeModelRegistry,
) -> None:
    """compose_invocation failure is caught and logged (RULE-11), extraction continues."""
    service = KBMergeService(
        novel_repo=novel_repo,  # type: ignore[arg-type]
        model_registry=registry,  # type: ignore[arg-type]
        model_config=config,
    )

    request = MergeRequest(
        entity_type="character",
        candidate_pairs=[],
    )

    with (
        patch("narrare_core.agents.merge_agent.KBMergeAgent") as MockAgent,
        patch(
            "narrare_core.ai_invocation.compose_invocation",
            new=AsyncMock(side_effect=RuntimeError("pipeline offline")),
        ),
    ):
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=make_merge_output())
        MockAgent.return_value = mock_agent

        # Must not raise — failure is logged, not propagated.
        result = await service.analyze_merge_candidates(
            novel_id=uuid4(),
            user_id=uuid4(),
            request=request,
        )

    assert result.merge_decisions == []
