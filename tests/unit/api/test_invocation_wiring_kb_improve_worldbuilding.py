"""Invocation evidence wiring tests for KBImproveService/WorldbuildingService.

Split from ``test_invocation_wiring_kb.py`` for RULE-04 compliance
(file-size hard limit); the remaining services (extraction, consistency,
assist, merge) stay there.

Verifies that the improve/worldbuilding services delegate LLM evidence
recording to their analyzers (ADR-048 Mode 1) and that behavior is
unchanged when ``invocation_pipeline=None`` (backward compatibility).

See:
    ADR-040, INFRA-013, CONSTRAINTS.md RULE-10/RULE-11.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

# ===========================================================================
# 1. KBImproveService invocation wiring
# ===========================================================================


class TestImproveInvocationWiring:
    """KBImproveService delegates to analyzer (evidence recorded there)."""

    @pytest.mark.asyncio
    async def test_analyze_delegates_to_analyzer(self) -> None:
        from narrare.kb.improve_service import KBImproveService

        novel_id, entry_id = uuid4(), uuid4()
        mock_analyzer = MagicMock(spec=["analyze"])
        mock_analyzer.analyze = AsyncMock(return_value=MagicMock(spec=["suggestions"]))

        entry = MagicMock(spec=["novel_id"])
        entry.novel_id = novel_id
        kb_repo = MagicMock(spec=["get_by_id"])
        kb_repo.get_by_id = AsyncMock(return_value=entry)
        novel_repo = MagicMock(spec=["get_by_id"])
        novel_repo.get_by_id = AsyncMock(return_value=object())

        service = KBImproveService(
            analyzer=mock_analyzer,
            kb_repo=kb_repo,
            kb_service=MagicMock(spec=["get"]),
            rel_repo=MagicMock(spec=["get_by_id"]),
            novel_repo=novel_repo,
        )

        await service.analyze(novel_id=novel_id, entry_id=entry_id, user_id=uuid4())

        # Evidence recording has moved to the analyzer (ADR-048 Mode 1).
        # The service is now a thin delegation layer.
        mock_analyzer.analyze.assert_awaited_once()


# ===========================================================================
# 2. WorldbuildingService invocation wiring
# ===========================================================================


class TestWorldbuildingInvocationWiring:
    """WorldbuildingService delegates to analyzer (evidence recorded there)."""

    @pytest.mark.asyncio
    async def test_analyze_delegates_to_analyzer(self) -> None:
        from narrare.kb.worldbuilding_contracts import WorldbuildingAnalysisRequest
        from narrare.kb.worldbuilding_service import WorldbuildingService

        mock_analyzer = MagicMock(spec=["analyze"])
        mock_analyzer.analyze = AsyncMock(return_value=MagicMock(spec=["connections"]))
        novel_repo = MagicMock(spec=["get_by_id"])
        novel_repo.get_by_id = AsyncMock(return_value=object())

        service = WorldbuildingService(
            analyzer=mock_analyzer,
            rel_repo=MagicMock(spec=["get_by_id"]),
            entry_repo=MagicMock(spec=["filter_ids_in_novel"]),
            cache=MagicMock(spec=["get", "set"]),
            novel_repo=novel_repo,
        )

        request = WorldbuildingAnalysisRequest()
        await service.analyze(novel_id=uuid4(), request=request, user_id=uuid4())

        # Evidence recording has moved to the analyzer (ADR-048 Mode 1).
        # The service is now a thin delegation layer.
        mock_analyzer.analyze.assert_awaited_once()


# ===========================================================================
# Backward compatibility — no pipeline = no crash
# ===========================================================================


class TestBackwardCompatibility:
    """KB services work correctly when invocation_pipeline is None."""

    @pytest.mark.asyncio
    async def test_improve_service_without_pipeline(self) -> None:
        """KBImproveService works without invocation_pipeline."""
        from narrare.kb.improve_service import KBImproveService

        novel_id = uuid4()
        mock_analyzer = MagicMock(spec=["analyze"])
        mock_analyzer.analyze = AsyncMock(return_value=MagicMock(spec=["suggestions"]))

        entry = MagicMock(spec=["novel_id"])
        entry.novel_id = novel_id
        kb_repo = MagicMock(spec=["get_by_id"])
        kb_repo.get_by_id = AsyncMock(return_value=entry)
        novel_repo = MagicMock(spec=["get_by_id"])
        novel_repo.get_by_id = AsyncMock(return_value=object())

        service = KBImproveService(
            analyzer=mock_analyzer,
            kb_repo=kb_repo,
            kb_service=MagicMock(spec=["get"]),
            rel_repo=MagicMock(spec=["get_by_id"]),
            novel_repo=novel_repo,
            invocation_pipeline=None,
        )

        result = await service.analyze(novel_id=novel_id, entry_id=uuid4(), user_id=uuid4())
        assert result is not None

    @pytest.mark.asyncio
    async def test_worldbuilding_service_without_pipeline(self) -> None:
        """WorldbuildingService works without invocation_pipeline."""
        from narrare.kb.worldbuilding_contracts import WorldbuildingAnalysisRequest
        from narrare.kb.worldbuilding_service import WorldbuildingService

        mock_analyzer = MagicMock(spec=["analyze"])
        mock_analyzer.analyze = AsyncMock(return_value=MagicMock(spec=["connections"]))
        novel_repo = MagicMock(spec=["get_by_id"])
        novel_repo.get_by_id = AsyncMock(return_value=object())

        service = WorldbuildingService(
            analyzer=mock_analyzer,
            rel_repo=MagicMock(spec=["get_by_id"]),
            entry_repo=MagicMock(spec=["filter_ids_in_novel"]),
            cache=MagicMock(spec=["get", "set"]),
            novel_repo=novel_repo,
            invocation_pipeline=None,
        )

        result = await service.analyze(
            novel_id=uuid4(), request=WorldbuildingAnalysisRequest(), user_id=uuid4()
        )
        assert result is not None
