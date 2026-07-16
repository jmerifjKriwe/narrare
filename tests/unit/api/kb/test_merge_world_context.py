"""Runtime-wiring tests for KBMergeService world_context (quality-debt item 1).

Verifies that ``analyze_merge_candidates`` populates the ``{{world_context}}``
prompt variable (system channel) with real curated KB context sourced from the
project's existing entities — not a stubbed empty string. Mirrors the kb
assist/improve world-context mechanism and degrades gracefully (RULE-11) when
the KB repository is unavailable.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare_core.llm.model_config import ResolvedModelConfig

from ._merge_test_helpers import (
    FakeComposedInvocation,
    FakeComposer,
    FakeModelRegistry,
    make_merge_output,
    make_novel,
    make_request,
)


def _entry(name: str, entity_type: str = "character") -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        entity_type=entity_type,
        metadata_={"role": "protagonist"},
        body="",
    )


class _FakeKBRepo:
    def __init__(self, entries: list[SimpleNamespace]) -> None:
        self.list_entries = AsyncMock(return_value=(entries, len(entries)))


def _make_service(kb_repo: object | None) -> object:
    from narrare.kb.merge_service import KBMergeService

    novel_repo = AsyncMock()
    novel_repo.get_by_id = AsyncMock(return_value=make_novel())
    return KBMergeService(
        novel_repo=novel_repo,  # type: ignore[arg-type]
        model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
        model_config=ResolvedModelConfig(provider_name="test", model_id="m"),
        composer=FakeComposer(),  # type: ignore[arg-type]
        kb_repo=kb_repo,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_world_context_populated_from_existing_entities() -> None:
    """merge must populate world_context with curated project KB context."""
    repo = _FakeKBRepo([_entry("Elara"), _entry("Alaric")])
    service = _make_service(repo)

    with (
        patch("narrare_core.agents.merge_agent.KBMergeAgent") as MockAgent,
        patch("narrare_core.agents.merge_agent.KBMergeDeps"),
        patch(
            "narrare_core.ai_invocation.compose_invocation",
            new=AsyncMock(return_value=FakeComposedInvocation()),
        ) as mock_compose,
    ):
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=make_merge_output())
        MockAgent.return_value = mock_agent

        await service.analyze_merge_candidates(  # type: ignore[attr-defined]
            uuid.uuid4(), uuid.uuid4(), make_request()
        )

    extra = mock_compose.call_args.kwargs["prompt_context"].extra
    assert extra["world_context"] != "", (
        "world_context must be populated with real curated KB context, not stubbed empty."
    )
    assert "Elara" in extra["world_context"]


@pytest.mark.asyncio
async def test_world_context_filters_by_entity_type() -> None:
    """merge scopes world_context to the entity type under analysis."""
    repo = _FakeKBRepo([_entry("Elara", "character")])
    service = _make_service(repo)

    with (
        patch("narrare_core.agents.merge_agent.KBMergeAgent") as MockAgent,
        patch("narrare_core.agents.merge_agent.KBMergeDeps"),
        patch(
            "narrare_core.ai_invocation.compose_invocation",
            new=AsyncMock(return_value=FakeComposedInvocation()),
        ),
    ):
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=make_merge_output())
        MockAgent.return_value = mock_agent

        await service.analyze_merge_candidates(  # type: ignore[attr-defined]
            uuid.uuid4(), uuid.uuid4(), make_request(entity_type="character")
        )

    kwargs = repo.list_entries.call_args.kwargs
    assert kwargs.get("entity_type") == "character"


@pytest.mark.asyncio
async def test_world_context_degrades_gracefully_when_repo_unavailable() -> None:
    """RULE-11: a KB repo failure must not crash merge."""
    repo = MagicMock(spec=["list_entries"])
    repo.list_entries = AsyncMock(side_effect=RuntimeError("offline"))
    service = _make_service(repo)

    with (
        patch("narrare_core.agents.merge_agent.KBMergeAgent") as MockAgent,
        patch("narrare_core.agents.merge_agent.KBMergeDeps"),
        patch(
            "narrare_core.ai_invocation.compose_invocation",
            new=AsyncMock(return_value=FakeComposedInvocation()),
        ) as mock_compose,
    ):
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=make_merge_output())
        MockAgent.return_value = mock_agent

        result = await service.analyze_merge_candidates(  # type: ignore[attr-defined]
            uuid.uuid4(), uuid.uuid4(), make_request()
        )

    # Merge still completes; world_context degrades to empty.
    assert result is not None
    assert mock_compose.call_args.kwargs["prompt_context"].extra["world_context"] == ""
