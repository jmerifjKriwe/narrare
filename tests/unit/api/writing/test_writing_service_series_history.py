"""WritingService → series_history wiring (Spec 2, Task 7).

Verifies that ``WritingService.stream_generation`` fetches the series-history
block from :class:`SeriesHistoryProvider` and forwards it to the pipeline's
``series_history`` kwarg, with graceful degradation when no provider is
wired (RULE-11 — standalone path unchanged, empty string forwarded).

Mirrors ``test_writing_service_session_memory.py`` (the ADR-045 precedent
for optional Backend-injected context).
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import ANY, AsyncMock, MagicMock

from narrare.writing.service import WritingService
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.writing.draft_processor import DraftProcessor
from narrare_core.writing.pipeline import WritingPipeline

if TYPE_CHECKING:
    from narrare_core.llm import ResolvedModelConfig


def _gate_open_chapter_repo() -> AsyncMock:
    """Chapter repo whose chapter binds to ANY novel (S6 gate open).

    These tests exercise series-history wiring, not ownership — the
    access matrix lives in ``test_generation_access_matrix.py``.
    """
    from tests.factories import make_chapter

    repo = AsyncMock(spec=["get"])
    repo.get = AsyncMock(return_value=make_chapter(novel_id=ANY))
    return repo


def _gate_open_novel_repo() -> AsyncMock:
    """Novel repo where every novel belongs to the caller (S6 gate open)."""
    from tests.factories import make_novel

    repo = AsyncMock(spec=["get_by_id"])
    repo.get_by_id = AsyncMock(return_value=make_novel())
    return repo


def _make_request_model(user_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        chapter_id=uuid.uuid4(),
        novel_id=uuid.uuid4(),
        user_id=user_id,
        mode="full_draft",
        tone="balanced",
        status="pending",
        word_count=0,
    )


def _make_streaming_pipeline(*, capture: dict[str, Any] | None = None) -> MagicMock:
    pipeline = MagicMock(spec=WritingPipeline)
    pipeline.stop = AsyncMock()

    async def _generate(*_args: Any, **kwargs: Any) -> Any:
        if capture is not None:
            capture.update(kwargs)
        yield StreamChunk(text="Hello ")
        yield StreamChunk(
            text="world.",
            is_final=True,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

    pipeline.generate = _generate
    return pipeline


def _make_draft_processor() -> MagicMock:
    processor = MagicMock(spec=DraftProcessor)
    processor.process.side_effect = lambda text, **_kw: text
    return processor


def _static_runtime_factory(
    pipeline: MagicMock,
    config: ResolvedModelConfig,
    *,
    series_history_budget: int | None = None,
) -> Any:
    """Fixed-runtime pin over ``make_static_runtime_factory`` (ADR-086 L37)."""
    from tests.unit.api.writing._writing_factories import make_static_runtime_factory

    return make_static_runtime_factory(
        pipeline, config, series_history_budget=series_history_budget
    )


class TestWritingServiceSeriesHistoryConstructor:
    def test_accepts_and_stores_provider(
        self,
        mock_repo: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        provider = AsyncMock()
        service = WritingService(
            repo=mock_repo,
            runtime_factory=_static_runtime_factory(MagicMock(spec=WritingPipeline), config),
            draft_processor=MagicMock(spec=DraftProcessor),
            chapter_repo=_gate_open_chapter_repo(),
            novel_repo=_gate_open_novel_repo(),
            series_history_provider=provider,
        )
        assert service._series_history_provider is provider

    def test_defaults_provider_to_none(
        self,
        mock_repo: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        service = WritingService(
            repo=mock_repo,
            runtime_factory=_static_runtime_factory(MagicMock(spec=WritingPipeline), config),
            draft_processor=MagicMock(spec=DraftProcessor),
            chapter_repo=_gate_open_chapter_repo(),
            novel_repo=_gate_open_novel_repo(),
        )
        assert service._series_history_provider is None


class TestStreamGenerationSeriesHistory:
    async def test_forwards_series_history_when_provider_present(
        self,
        mock_repo: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        """The provider's block is forwarded to pipeline.generate."""
        user_id = uuid.uuid4()
        request_model = _make_request_model(user_id)
        mock_repo.get_by_id.return_value = request_model

        capture: dict[str, Any] = {}
        pipeline = _make_streaming_pipeline(capture=capture)

        provider = AsyncMock()
        provider.assemble_series_history.return_value = "Previously in this series…"

        service = WritingService(
            repo=mock_repo,
            runtime_factory=_static_runtime_factory(pipeline, config),
            draft_processor=_make_draft_processor(),
            chapter_repo=_gate_open_chapter_repo(),
            novel_repo=_gate_open_novel_repo(),
            series_history_provider=provider,
        )

        _ = [chunk async for chunk in service.stream_generation(request_model.id, str(user_id))]

        provider.assemble_series_history.assert_awaited_once_with(request_model.novel_id)
        assert capture["series_history"] == "Previously in this series…"

    async def test_empty_series_history_when_no_provider_backward_compatible(
        self,
        mock_repo: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        """No provider (standalone / existing tests) → empty series_history."""
        user_id = uuid.uuid4()
        request_model = _make_request_model(user_id)
        mock_repo.get_by_id.return_value = request_model

        capture: dict[str, Any] = {}
        pipeline = _make_streaming_pipeline(capture=capture)

        service = WritingService(
            repo=mock_repo,
            runtime_factory=_static_runtime_factory(pipeline, config),
            draft_processor=_make_draft_processor(),
            chapter_repo=_gate_open_chapter_repo(),
            novel_repo=_gate_open_novel_repo(),
        )

        _ = [chunk async for chunk in service.stream_generation(request_model.id, str(user_id))]

        assert capture["series_history"] == ""


class TestStreamGenerationSeriesHistoryBudget:
    async def test_forwards_series_history_budget_to_provider(
        self,
        mock_repo: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        """C5/ADR-082: the resolved series-history ceiling reaches the
        provider call (RULE-18b runtime-consumer evidence)."""
        user_id = uuid.uuid4()
        request_model = _make_request_model(user_id)
        mock_repo.get_by_id.return_value = request_model

        pipeline = _make_streaming_pipeline()
        provider = AsyncMock()
        provider.assemble_series_history.return_value = "Previously…"

        service = WritingService(
            repo=mock_repo,
            runtime_factory=_static_runtime_factory(pipeline, config, series_history_budget=12_000),
            draft_processor=_make_draft_processor(),
            chapter_repo=_gate_open_chapter_repo(),
            novel_repo=_gate_open_novel_repo(),
            series_history_provider=provider,
        )

        _ = [chunk async for chunk in service.stream_generation(request_model.id, str(user_id))]

        provider.assemble_series_history.assert_awaited_once_with(
            request_model.novel_id, token_budget=12_000
        )
