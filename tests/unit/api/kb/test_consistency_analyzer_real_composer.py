"""Real-composer routing regression tests for KBConsistencyAnalyzer.

Split out of ``test_consistency_analyzer.py`` (RULE-04: parent hit the
400-line hard limit; coordinator approved this as the package's 3rd path).

Why this file exists: the CONS-001 hazard is only observable through the
REAL PromptComposer/PromptRegistry route resolution. Every other test in
the parent module uses FakeComposer, which never routes — exactly why the
silent zero-issue regression survived. These tests pin the analyzer's
``PromptContext.mode`` to the governed route-table MODE string
(``"consistency"``), not the intent's enum value (``"kb_consistency"``),
which ``resolve_prompt_route`` rejects and the per-entity swallow hides.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare._app.dependencies_services import StaticModelResolution
from narrare.kb.consistency_analyzer import KBConsistencyAnalyzer
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.gateway import ModelRegistry
from narrare_core.llm.model_routing import ResolvedModel
from tests.unit.api.kb.test_consistency_analyzer import FakeKBEntry, FakeKBRepo

if TYPE_CHECKING:
    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.models import KBEntry


class TestRealComposerRouting:
    """CONS-001-hazard regression (E2E-GATE carry-forward 2026-10-15).

    The analyzer must compose on the REAL PromptComposer: its
    ``PromptContext.mode`` is a route-table MODE string, not the intent's
    enum value. The pre-fix ``mode="kb_consistency"`` was rejected by
    ``resolve_prompt_route`` (allowed: consistency|merge) and swallowed
    per-entity — every prior test used FakeComposer, which is exactly why
    the silent zero-issue check survived.
    """

    @pytest.mark.asyncio
    async def test_analyze_entry_composes_on_the_real_composer(self) -> None:
        from narrare.kb.consistency_analyzer import (
            _EntryInternalIssue,
            _EntryInternalOutput,
        )
        from narrare_core.prompts.composer import PromptComposer
        from narrare_core.prompts.registry import PromptRegistry

        registry = MagicMock(spec=ModelRegistry)
        registry.run = AsyncMock(
            return_value=_EntryInternalOutput(
                issues=[
                    _EntryInternalIssue(
                        field_keys=["summary"],
                        description="Conflicting goals",
                        contradiction="wants to stay vs must leave",
                        suggested_resolution="Pick the deadline",
                        severity="major",
                        confidence=0.9,
                    )
                ],
                assessment="One contradiction found.",
            )
        )
        analyzer = KBConsistencyAnalyzer(
            kb_repo=cast("KBRepositoryProtocol", FakeKBRepo()),
            registry=registry,
            model_resolution=StaticModelResolution(
                ResolvedModel(
                    config=cast("ResolvedModelConfig", MagicMock(spec=ResolvedModelConfig))
                )
            ),
            composer=PromptComposer(PromptRegistry()),
        )

        issues = await analyzer._analyze_entry(
            cast("KBEntry", FakeKBEntry(name="Alice", body="A brave warrior"))
        )

        assert len(issues) == 1
        assert issues[0].description == "Conflicting goals"
        registry.run.assert_awaited_once()
