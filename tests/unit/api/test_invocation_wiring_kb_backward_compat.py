"""Backward-compatibility tests for KB invocation wiring (ADR-040).

Verifies that KB services behave unchanged when
``invocation_pipeline=None`` — no pipeline wired, no crash.

Split from ``test_invocation_wiring_kb.py`` (RULE-04 file-size limit).

See:
    ADR-040, INFRA-013, CONSTRAINTS.md RULE-10/RULE-11.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from tests.unit.api.kb._extraction_helpers import permissive_novel_gate


class TestBackwardCompatibility:
    """KB services work correctly when invocation_pipeline is None."""

    @pytest.mark.asyncio
    async def test_improve_service_without_pipeline(self) -> None:
        """KBImproveService works without invocation_pipeline."""
        from types import SimpleNamespace

        from narrare.kb.improve_service import KBImproveService

        mock_analyzer = MagicMock(spec=["analyze"])
        mock_analyzer.analyze = AsyncMock(return_value=MagicMock(spec=["suggestions"]))

        novel_id = uuid4()
        kb_repo = MagicMock(spec=["get_by_id"])
        kb_repo.get_by_id = AsyncMock(return_value=SimpleNamespace(novel_id=novel_id))

        service = KBImproveService(
            analyzer=mock_analyzer,
            kb_repo=kb_repo,
            kb_service=MagicMock(spec=["get"]),
            rel_repo=MagicMock(spec=["get_by_id"]),
            novel_repo=permissive_novel_gate(),
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

        service = WorldbuildingService(
            analyzer=mock_analyzer,
            rel_repo=MagicMock(spec=["get_by_id"]),
            entry_repo=MagicMock(spec=["list_entries"]),
            cache=MagicMock(spec=["get", "set"]),
            novel_repo=permissive_novel_gate(),
            invocation_pipeline=None,
        )

        result = await service.analyze(
            novel_id=uuid4(), request=WorldbuildingAnalysisRequest(), user_id=uuid4()
        )
        assert result is not None
