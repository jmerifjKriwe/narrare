"""Tests for user_id/project_id pass-through across all writing modes.

Split from ``test_invocation_wiring_extra.py`` to respect RULE-04.

FeatureInvocationEvidence is privacy-safe — it does NOT contain
user_id/project_id. Instead we verify by using a mock InvocationPipeline
that captures the PromptInvocationContext passed to prepare().

See: ADR-040 Decision 4, INFRA-013, CONSTRAINTS.md RULE-04/RULE-10.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare_core.ai_invocation._enums import ValidationStatus
from narrare_core.ai_invocation.models import ValidationResult
from narrare_core.ai_invocation.pipeline import PreparedInvocation
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.writing import GenerationMode
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.draft_processor import DraftProcessor
from tests.unit.core.writing._invocation_helpers import (
    CONFIG,
    _collect,
    _ctx,
    _make_pipeline,
    _req,
    _setup_run,
    _setup_stream,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_registry() -> Any:
    return MagicMock(spec=["stream", "run"])


@pytest.fixture()
def mock_composer() -> Any:
    comp = MagicMock(spec=PromptComposer)
    comp.build = AsyncMock(return_value=ComposedPrompt(system="sys", user="usr"))
    return comp


@pytest.fixture()
def mock_assembler() -> Any:
    asm = MagicMock(spec=WritingContextAssembler)
    asm.assemble = AsyncMock(return_value=_ctx())
    return asm


@pytest.fixture()
def mock_processor() -> Any:
    proc = MagicMock(spec=DraftProcessor)
    proc.process = MagicMock(spec=[], side_effect=lambda text, **kw: text)
    return proc


# ===========================================================================
# Cross-cutting: user_id and project_id pass-through
# ===========================================================================


class TestUserIdProjectIdPassThrough:
    """Verify user_id and project_id flow to the invocation context."""

    @staticmethod
    def _make_spy_pipeline() -> tuple[MagicMock, list[Any]]:
        """Create a mock pipeline that captures the context from prepare()."""
        captured: list[Any] = []

        async def capture_prepare(ctx: Any) -> Any:
            captured.append(ctx)
            return PreparedInvocation(
                context=ctx,
                validation=ValidationResult(status=ValidationStatus.PASS),
            )

        mock = MagicMock(spec=["prepare", "finalize"])
        mock.prepare = AsyncMock(side_effect=capture_prepare)
        mock.finalize = AsyncMock(
            return_value=MagicMock(
                spec=["validation", "evidence_recorded"],
                validation=MagicMock(spec=["is_valid"], is_valid=True),
                evidence_recorded=True,
            ),
        )
        return mock, captured

    async def _verify_ids(
        self,
        mock_registry: Any,
        mock_composer: Any,
        mock_assembler: Any,
        mock_processor: Any,
        mode: GenerationMode,
        *,
        min_captures: int = 1,
        setup_fn: Any = None,
        req_extra: dict[str, Any] | None = None,
        generate_extra: dict[str, Any] | None = None,
    ) -> None:
        """Shared body for pass-through assertions — reduces duplication."""
        user_id = uuid4()
        project_id = uuid4()
        spy, captured = self._make_spy_pipeline()
        pipeline = _make_pipeline(
            mock_registry,
            mock_composer,
            mock_assembler,
            mock_processor,
            invocation_pipeline=spy,
        )
        if setup_fn is not None:
            setup_fn(mock_registry)
        else:
            _setup_stream(mock_registry, "Text.")

        req_kwargs: dict[str, Any] = {"user_id": user_id, "project_id": project_id}
        if req_extra:
            req_kwargs.update(req_extra)
        gen_kwargs: dict[str, Any] = {"config": CONFIG}
        if generate_extra:
            gen_kwargs.update(generate_extra)
        await _collect(pipeline.generate(_req(mode, **req_kwargs), **gen_kwargs))
        assert len(captured) >= min_captures
        assert captured[0].user_id == user_id
        assert captured[0].project_id == project_id

    @pytest.mark.asyncio
    async def test_extend_passes_ids(
        self,
        mock_registry: Any,
        mock_composer: Any,
        mock_assembler: Any,
        mock_processor: Any,
    ) -> None:
        await self._verify_ids(
            mock_registry,
            mock_composer,
            mock_assembler,
            mock_processor,
            GenerationMode.EXTEND,
        )

    @pytest.mark.asyncio
    async def test_rewrite_passes_ids(
        self,
        mock_registry: Any,
        mock_composer: Any,
        mock_assembler: Any,
        mock_processor: Any,
    ) -> None:
        await self._verify_ids(
            mock_registry,
            mock_composer,
            mock_assembler,
            mock_processor,
            GenerationMode.REWRITE,
            generate_extra={"selection_text": "Original."},
        )

    @pytest.mark.asyncio
    async def test_coauthor_passes_ids(
        self,
        mock_registry: Any,
        mock_composer: Any,
        mock_assembler: Any,
        mock_processor: Any,
    ) -> None:
        await self._verify_ids(
            mock_registry,
            mock_composer,
            mock_assembler,
            mock_processor,
            GenerationMode.CO_AUTHOR,
            generate_extra={"selection_text": "Original.", "co_author_focus": ["dialogue"]},
        )

    @pytest.mark.asyncio
    async def test_scene_passes_ids(
        self,
        mock_registry: Any,
        mock_composer: Any,
        mock_assembler: Any,
        mock_processor: Any,
    ) -> None:
        await self._verify_ids(
            mock_registry,
            mock_composer,
            mock_assembler,
            mock_processor,
            GenerationMode.SCENE_BY_SCENE,
            min_captures=1,
            req_extra={"outline": "A hero enters."},
        )

    @pytest.mark.asyncio
    async def test_interview_passes_ids(
        self,
        mock_registry: Any,
        mock_composer: Any,
        mock_assembler: Any,
        mock_processor: Any,
    ) -> None:
        await self._verify_ids(
            mock_registry,
            mock_composer,
            mock_assembler,
            mock_processor,
            GenerationMode.INTERVIEW_ASSISTED,
            setup_fn=lambda reg: _setup_run(reg, "Question?"),
        )
