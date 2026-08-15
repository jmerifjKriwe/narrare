"""C5 / ADR-082 wiring tests — resolved budgets reach the runtime consumers.

Enforcement evidence for RULE-18b: create_pipeline is the ONLY
WritingContextAssembler construction point, and fetch_series_history is
the ONLY series-history assembly call site — pinning both proves the
resolved cascade values reach the runtime consumers.

Factory-level wiring (deps_* resolving against the model window) is
added in Tasks 3b/3c in this same file.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

from narrare.writing._helpers import fetch_series_history
from narrare_core.writing.draft_processor import DraftProcessor


class TestCreatePipelineForwardsTotalBudget:
    def test_forwards_total_budget_to_assembler(self) -> None:
        from narrare.writing.deps_pipeline import create_pipeline

        pipeline = create_pipeline(DraftProcessor(), total_budget=24_000)

        assert pipeline._context_assembler.total_budget == 24_000

    def test_without_total_budget_keeps_core_default(self) -> None:
        from narrare.writing.deps_pipeline import create_pipeline
        from narrare_core.context.budget import DEFAULT_TOTAL_BUDGET

        pipeline = create_pipeline(DraftProcessor())

        assert pipeline._context_assembler.total_budget == DEFAULT_TOTAL_BUDGET


class TestFetchSeriesHistoryBudget:
    async def test_passes_token_budget_through_to_provider(self) -> None:
        provider = AsyncMock()
        provider.assemble_series_history.return_value = "block"
        novel_id = uuid.uuid4()

        result = await fetch_series_history(provider, novel_id, token_budget=12_000)

        assert result == "block"
        provider.assemble_series_history.assert_awaited_once_with(novel_id, token_budget=12_000)

    async def test_none_budget_calls_provider_without_token_budget(self) -> None:
        """Backward-compatible default: no budget → provider default (16,000)."""
        provider = AsyncMock()
        provider.assemble_series_history.return_value = "block"
        novel_id = uuid.uuid4()

        await fetch_series_history(provider, novel_id)

        provider.assemble_series_history.assert_awaited_once_with(novel_id)

    async def test_none_provider_returns_empty(self) -> None:
        assert await fetch_series_history(None, uuid.uuid4(), token_budget=12_000) == ""
