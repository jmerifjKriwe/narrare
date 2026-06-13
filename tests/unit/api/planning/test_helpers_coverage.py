"""Tests for planning/_helpers.py — uncovered branches and error paths.

Covers:
1. find_position when chapter_id is not found (line 106)
2. ensure_outlines with non-StructureAdapter (line 163)
3. ai_suggest_stage with non-StructureAdapter fallback (lines 215, 234)
"""

from __future__ import annotations

import uuid
from typing import cast
from unittest.mock import AsyncMock, MagicMock

from narrare.chapters.models import Chapter
from narrare.planning._helpers import (
    ai_suggest_stage,
    ensure_outlines,
    find_position,
)


class TestFindPosition:
    """find_position coverage."""

    def test_find_position_not_found_returns_one(self) -> None:
        """find_position returns 1 when chapter_id not in list (line 106)."""
        chapter = MagicMock(spec=Chapter)
        chapter.id = uuid.uuid4()
        search_id = uuid.uuid4()  # different UUID — will not match
        result = find_position([cast("Chapter", chapter)], search_id)
        assert result == 1


class TestEnsureOutlines:
    """ensure_outlines coverage."""

    async def test_ensure_outlines_with_non_adapter_uses_empty_string(self) -> None:
        """Non-StructureAdapter passed as adapter → empty stage (line 163)."""
        repo = AsyncMock()
        repo.get_all_for_novel = AsyncMock(return_value=[])
        repo.create = AsyncMock()

        chapter = MagicMock(spec=Chapter)
        chapter.id = uuid.uuid4()
        # Not a StructureAdapter — just a plain object
        adapter = object()

        result = await ensure_outlines(repo, uuid.uuid4(), [cast("Chapter", chapter)], adapter)

        assert chapter.id in result
        repo.create.assert_called_once_with(chapter_id=chapter.id, stage_assignment="")


class TestAiSuggestStage:
    """ai_suggest_stage coverage."""

    async def test_ai_suggest_stage_without_ai_service_uses_adapter(self) -> None:
        """Without AIRemapService, falls to adapter.suggest_stage (line 215)."""
        from narrare_core.planning.adapters.three_act import ThreeActAdapter

        result = await ai_suggest_stage(
            ai_remap_service=None,
            summary="A story summary.",
            structure_type="three_act",
            position=1,
            total=3,
            adapter=ThreeActAdapter(),
        )
        # ThreeActAdapter returns stage names
        assert result  # Should return a non-empty stage name

    async def test_ai_suggest_stage_without_service_and_non_adapter_returns_empty(
        self,
    ) -> None:
        """Without AIRemapService and non-adapter, returns '' (line 234)."""
        result = await ai_suggest_stage(
            ai_remap_service=None,
            summary="Something.",
            structure_type="three_act",
            position=1,
            total=3,
            adapter=object(),  # Not a StructureAdapter
        )
        assert result == ""
