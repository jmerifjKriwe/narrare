"""Unit tests for WritingService novel title/genre supply wiring.

Pins that ``stream_generation`` fetches the novel ownership-aware
(``novel_repo.get_by_id(novel_id, user)`` — sibling-service resolution
pattern) and passes ``project_title``/``genre`` into the pipeline, and
that fetch failure degrades to empty strings (RULE-11): the draft
proceeds without novel context.
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

# ---------------------------------------------------------------------------
# Helpers (mirror test_writing_service_session_memory.py)
# ---------------------------------------------------------------------------


def _gate_open_chapter_repo() -> AsyncMock:
    """Chapter repo whose chapter binds to ANY novel (S6 gate open)."""
    from tests.factories import make_chapter

    repo = AsyncMock(spec=["get"])
    repo.get = AsyncMock(return_value=make_chapter(novel_id=ANY))
    return repo


def _novel_repo_with(novel: Any) -> AsyncMock:
    """Novel repo returning the given novel (or None) from ``get_by_id``."""
    repo = AsyncMock(spec=["get_by_id"])
    repo.get_by_id = AsyncMock(return_value=novel)
    return repo


def _make_request_model(user_id: uuid.UUID) -> SimpleNamespace:
    """Create a fake GenerationRequest ORM model with valid attributes."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        chapter_id=uuid.uuid4(),
        novel_id=uuid.uuid4(),
        user_id=user_id,
        mode="full_draft",
        tone="balanced",
        status="pending",
        scenes=None,
        word_count=0,
    )


def _make_streaming_pipeline(
    *,
    capture: dict[str, Any] | None = None,
) -> MagicMock:
    """Mock WritingPipeline whose generate() yields text + final chunk."""
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
    """Mock DraftProcessor — returns input text unchanged."""
    processor = MagicMock(spec=DraftProcessor)
    processor.process.side_effect = lambda text, **_kw: text
    return processor


def _make_service(
    mock_repo: AsyncMock,
    config: ResolvedModelConfig,
    pipeline: MagicMock,
    novel_repo: AsyncMock,
) -> WritingService:
    """WritingService wired for stream-supply tests."""
    from tests.unit.api.writing._writing_factories import make_static_runtime_factory

    return WritingService(
        repo=mock_repo,
        # ADR-086 L37: fixed-runtime pin (render- and outcome-inert).
        runtime_factory=make_static_runtime_factory(pipeline, config),
        draft_processor=_make_draft_processor(),
        chapter_repo=_gate_open_chapter_repo(),
        novel_repo=novel_repo,
    )


async def _drain(service: WritingService, request_id: uuid.UUID, user_id: str) -> list[Any]:
    """Consume the entire stream and return the chunks."""
    return [chunk async for chunk in service.stream_generation(request_id, user_id)]


# ---------------------------------------------------------------------------
# Wiring — novel title/genre reach the pipeline
# ---------------------------------------------------------------------------


class TestStreamGenerationNovelSupply:
    async def test_stream_generation_passes_novel_title_and_genre_to_pipeline(
        self,
        mock_repo: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        """stream_generation() forwards ownership-checked title/genre."""
        from tests.factories import make_novel

        user_id = uuid.uuid4()
        request_model = _make_request_model(user_id)
        mock_repo.get_by_id.return_value = request_model

        capture: dict[str, Any] = {}
        pipeline = _make_streaming_pipeline(capture=capture)
        novel_repo = _novel_repo_with(make_novel(title="The Ship Beneath", genre="Space Opera"))
        service = _make_service(mock_repo, config, pipeline, novel_repo)

        await _drain(service, request_model.id, str(user_id))

        novel_repo.get_by_id.assert_called_once_with(request_model.novel_id, user_id)
        assert capture["project_title"] == "The Ship Beneath"
        assert capture["genre"] == "Space Opera"

    async def test_stream_generation_supplys_empty_strings_for_blank_fields(
        self,
        mock_repo: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        """None-ish novel fields degrade to empty strings, not None."""
        from tests.factories import make_novel

        user_id = uuid.uuid4()
        request_model = _make_request_model(user_id)
        mock_repo.get_by_id.return_value = request_model

        capture: dict[str, Any] = {}
        pipeline = _make_streaming_pipeline(capture=capture)
        novel_repo = _novel_repo_with(make_novel(title="", genre=None))
        service = _make_service(mock_repo, config, pipeline, novel_repo)

        await _drain(service, request_model.id, str(user_id))

        assert capture["project_title"] == ""
        assert capture["genre"] == ""


# ---------------------------------------------------------------------------
# Degradation — fetch failure never blocks the draft (RULE-11)
# ---------------------------------------------------------------------------


class TestStreamGenerationNovelSupplyDegradation:
    async def test_stream_generation_degrades_to_empty_when_novel_repo_raises(
        self,
        mock_repo: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        """Repo failure → empty supplies, stream still completes."""
        user_id = uuid.uuid4()
        request_model = _make_request_model(user_id)
        mock_repo.get_by_id.return_value = request_model

        capture: dict[str, Any] = {}
        pipeline = _make_streaming_pipeline(capture=capture)
        novel_repo = _novel_repo_with(None)
        novel_repo.get_by_id = AsyncMock(side_effect=RuntimeError("db down"))
        service = _make_service(mock_repo, config, pipeline, novel_repo)

        chunks = await _drain(service, request_model.id, str(user_id))

        assert capture["project_title"] == ""
        assert capture["genre"] == ""
        assert len(chunks) == 2
        assert chunks[-1].is_final is True

    async def test_stream_generation_degrades_to_empty_when_novel_missing(
        self,
        mock_repo: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        """Ownership miss / deleted novel (None) → empty supplies, draft proceeds."""
        user_id = uuid.uuid4()
        request_model = _make_request_model(user_id)
        mock_repo.get_by_id.return_value = request_model

        capture: dict[str, Any] = {}
        pipeline = _make_streaming_pipeline(capture=capture)
        novel_repo = _novel_repo_with(None)
        service = _make_service(mock_repo, config, pipeline, novel_repo)

        chunks = await _drain(service, request_model.id, str(user_id))

        assert capture["project_title"] == ""
        assert capture["genre"] == ""
        assert len(chunks) == 2
        assert chunks[-1].is_final is True
