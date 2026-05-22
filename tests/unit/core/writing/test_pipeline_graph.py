"""Tests for writing/pipeline_graph.py — WritingGraph integration paths.

Covers stream_via_writing_graph() and run_with_persistence().
Both delegate to create_writing_graph() + graph.run(), so the graph
factory is mocked throughout.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from narrare_core.agents.writing_graph_types import WritingDeps, WritingState
from narrare_core.llm.gateway import ModelRegistry
from narrare_core.llm.intents import ResolvedModelConfig
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.models import GenerationMode, GenerationRequest, WritingContext
from narrare_core.writing.pipeline_graph import run_with_persistence, stream_via_writing_graph

if TYPE_CHECKING:
    from narrare_core.llm.result import StreamChunk

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config() -> ResolvedModelConfig:
    return ResolvedModelConfig(
        provider_name="test",
        model_id="test-model",
        temperature=0.7,
        max_tokens=2000,
        streams=True,
    )


def _request() -> GenerationRequest:
    return GenerationRequest(
        chapter_id=uuid4(),
        project_id=uuid4(),
        user_id=uuid4(),
        mode=GenerationMode.FULL_DRAFT,
    )


def _default_context() -> WritingContext:
    return WritingContext(
        chapter_content="Previous content.",
        project_title="Test Novel",
        genre="fantasy",
        language="en",
        tone="balanced",
        writing_language="English",
    )


def _mock_graph(final_text: str = "Generated text.") -> MagicMock:
    """Create a mock graph whose run() returns a WritingState."""
    graph = MagicMock(spec=["run"])
    result = WritingState(final=final_text)
    graph.run = AsyncMock(return_value=result)
    return graph


async def _collect(chunks: Any) -> list[StreamChunk]:
    """Collect all chunks from an async generator."""
    result: list[StreamChunk] = []
    async for c in chunks:
        result.append(c)
    return result


class FakeGraphStore:
    """In-memory GraphStateStore for persistence tests."""

    def __init__(self, saved_state: WritingState | None = None) -> None:
        self._saved = saved_state
        self.saved_calls: list[tuple[str, object]] = []

    async def load(self, run_id: str) -> WritingState | None:
        return self._saved

    async def save(self, run_id: str, state: object) -> None:
        self.saved_calls.append((run_id, state))

    async def delete(self, run_id: str) -> None:
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_registry() -> MagicMock:
    return MagicMock(spec=ModelRegistry)


@pytest.fixture()
def mock_assembler() -> MagicMock:
    return MagicMock(spec=WritingContextAssembler)


_PATCH_TARGET = "narrare_core.agents.writing_graph.create_writing_graph"


# ---------------------------------------------------------------------------
# Test stream_via_writing_graph
# ---------------------------------------------------------------------------


class TestStreamViaWritingGraph:
    """Tests for stream_via_writing_graph()."""

    @pytest.mark.asyncio
    async def test_yields_single_final_chunk(
        self, mock_registry: MagicMock, mock_assembler: MagicMock
    ) -> None:
        """Returns exactly one StreamChunk with final text."""
        graph = _mock_graph("Hello World")
        with patch(_PATCH_TARGET, return_value=graph):
            chunks = await _collect(
                stream_via_writing_graph(
                    _request(),
                    _default_context(),
                    _config(),
                    registry=mock_registry,
                    context_assembler=mock_assembler,
                )
            )
        assert len(chunks) == 1
        assert chunks[0].text == "Hello World"
        assert chunks[0].is_final is True
        assert chunks[0].usage is None

    @pytest.mark.asyncio
    async def test_constructs_writing_deps_correctly(
        self, mock_registry: MagicMock, mock_assembler: MagicMock
    ) -> None:
        """WritingDeps passed to graph.run() carries the right fields."""
        graph = _mock_graph("text")
        request, context, config = _request(), _default_context(), _config()
        with patch(_PATCH_TARGET, return_value=graph):
            await _collect(
                stream_via_writing_graph(
                    request,
                    context,
                    config,
                    registry=mock_registry,
                    context_assembler=mock_assembler,
                    api_key="key-123",
                    base_url="https://api.test",
                )
            )
        deps: WritingDeps = graph.run.call_args.kwargs["deps"]
        assert deps.registry is mock_registry
        assert deps.context_assembler is mock_assembler
        assert deps.model_config is config
        assert deps.api_key == "key-123"
        assert deps.base_url == "https://api.test"
        assert deps.chapter_content == context.chapter_content
        assert deps.chapter_outline == context.chapter_outline
        assert deps.genre == context.genre
        assert deps.word_target == request.word_target
        assert deps.tone == context.tone
        assert deps.writing_language == context.writing_language

    @pytest.mark.asyncio
    async def test_constructs_initial_state_with_ids(
        self, mock_registry: MagicMock, mock_assembler: MagicMock
    ) -> None:
        """WritingState passed to graph.run() has correct IDs from request."""
        graph = _mock_graph("text")
        request = _request()
        with patch(_PATCH_TARGET, return_value=graph):
            await _collect(
                stream_via_writing_graph(
                    request,
                    _default_context(),
                    _config(),
                    registry=mock_registry,
                    context_assembler=mock_assembler,
                )
            )
        state: WritingState = graph.run.call_args.kwargs["state"]
        assert state.chapter_id == str(request.chapter_id)
        assert state.novel_id == str(request.project_id)


# ---------------------------------------------------------------------------
# Test run_with_persistence
# ---------------------------------------------------------------------------


class TestRunWithPersistence:
    """Tests for run_with_persistence()."""

    @pytest.mark.asyncio
    async def test_no_store_yields_final_chunk(
        self, mock_registry: MagicMock, mock_assembler: MagicMock
    ) -> None:
        """Without a store, still yields the final chunk."""
        graph = _mock_graph("Final output")
        with patch(_PATCH_TARGET, return_value=graph):
            chunks = await _collect(
                run_with_persistence(
                    _request(),
                    _default_context(),
                    _config(),
                    registry=mock_registry,
                    context_assembler=mock_assembler,
                )
            )
        assert len(chunks) == 1
        assert chunks[0].text == "Final output"
        assert chunks[0].is_final is True

    @pytest.mark.asyncio
    async def test_with_store_and_run_id_loads_state(
        self, mock_registry: MagicMock, mock_assembler: MagicMock
    ) -> None:
        """When store returns a saved WritingState, it is used as initial_state."""
        saved = WritingState(chapter_id="ch-1", novel_id="nv-1", draft="existing draft")
        store = FakeGraphStore(saved_state=saved)
        graph = _mock_graph("completed")
        with patch(_PATCH_TARGET, return_value=graph):
            await _collect(
                run_with_persistence(
                    _request(),
                    _default_context(),
                    _config(),
                    registry=mock_registry,
                    context_assembler=mock_assembler,
                    store=store,
                    run_id="resume-123",
                )
            )
        state: WritingState = graph.run.call_args.kwargs["state"]
        # The loaded state should be used, not a fresh one
        assert state is saved
        assert state.draft == "existing draft"

    @pytest.mark.asyncio
    async def test_with_store_no_saved_state_uses_new_state(
        self, mock_registry: MagicMock, mock_assembler: MagicMock
    ) -> None:
        """When store.load() returns None, a fresh WritingState is created."""
        store = FakeGraphStore(saved_state=None)
        graph = _mock_graph("done")
        request = _request()
        with patch(_PATCH_TARGET, return_value=graph):
            await _collect(
                run_with_persistence(
                    request,
                    _default_context(),
                    _config(),
                    registry=mock_registry,
                    context_assembler=mock_assembler,
                    store=store,
                    run_id="run-456",
                )
            )
        state: WritingState = graph.run.call_args.kwargs["state"]
        # Fresh state with IDs from request
        assert state.chapter_id == str(request.chapter_id)
        assert state.novel_id == str(request.project_id)
        assert state.draft == ""  # no prior draft

    @pytest.mark.asyncio
    async def test_with_store_saves_final_state(
        self, mock_registry: MagicMock, mock_assembler: MagicMock
    ) -> None:
        """After completion, store.save() is called with run_id and result."""
        graph = _mock_graph("final text")
        store = FakeGraphStore()
        with patch(_PATCH_TARGET, return_value=graph):
            await _collect(
                run_with_persistence(
                    _request(),
                    _default_context(),
                    _config(),
                    registry=mock_registry,
                    context_assembler=mock_assembler,
                    store=store,
                    run_id="save-test",
                )
            )
        assert len(store.saved_calls) == 1
        saved_run_id, saved_state = store.saved_calls[0]
        assert saved_run_id == "save-test"
        assert isinstance(saved_state, WritingState)
        assert saved_state.final == "final text"

    @pytest.mark.asyncio
    async def test_generates_run_id_when_none(
        self, mock_registry: MagicMock, mock_assembler: MagicMock
    ) -> None:
        """When run_id is None, a UUID is generated for store.save()."""
        graph = _mock_graph("auto-id")
        store = FakeGraphStore()
        with patch(_PATCH_TARGET, return_value=graph):
            await _collect(
                run_with_persistence(
                    _request(),
                    _default_context(),
                    _config(),
                    registry=mock_registry,
                    context_assembler=mock_assembler,
                    store=store,
                    run_id=None,
                )
            )
        assert len(store.saved_calls) == 1
        saved_run_id, _ = store.saved_calls[0]
        assert saved_run_id is not None
        UUID(saved_run_id)  # raises ValueError if not a valid UUID

    @pytest.mark.asyncio
    async def test_uses_provided_run_id(
        self, mock_registry: MagicMock, mock_assembler: MagicMock
    ) -> None:
        """When run_id is provided, store.save() receives it exactly."""
        graph = _mock_graph("provided-id")
        store = FakeGraphStore()
        with patch(_PATCH_TARGET, return_value=graph):
            await _collect(
                run_with_persistence(
                    _request(),
                    _default_context(),
                    _config(),
                    registry=mock_registry,
                    context_assembler=mock_assembler,
                    store=store,
                    run_id="test-123",
                )
            )
        saved_run_id, _ = store.saved_calls[0]
        assert saved_run_id == "test-123"

    @pytest.mark.asyncio
    async def test_store_load_not_called_when_no_run_id(
        self, mock_registry: MagicMock, mock_assembler: MagicMock
    ) -> None:
        """When run_id is None, store.load() is never called."""
        graph = _mock_graph("no-load")
        store = FakeGraphStore()
        load_calls: list[str] = []
        original_load = store.load

        async def tracked_load(run_id: str) -> WritingState | None:
            load_calls.append(run_id)
            return await original_load(run_id)

        store.load = tracked_load
        with patch(_PATCH_TARGET, return_value=graph):
            await _collect(
                run_with_persistence(
                    _request(),
                    _default_context(),
                    _config(),
                    registry=mock_registry,
                    context_assembler=mock_assembler,
                    store=store,
                    run_id=None,
                )
            )
        assert load_calls == []
