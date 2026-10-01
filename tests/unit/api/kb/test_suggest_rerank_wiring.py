"""Unit tests for the ADR-090 rerank wiring in ``get_kb_suggest_service``.

First production wiring of the rerank tier (post-upgrade follow-up item 4):
the KB suggest route's ``EmbeddingService`` — the ``EmbeddingStoreProtocol``
behind ``ProactiveContextService``, the only production caller of
``EmbeddingService.search`` — gains the same ``build_rerank_components`` DI
the admin embedding routes use. Pins both directions of the contract:

- Flag off (shipped default): the service is constructed exactly as before
  the tier existed (repo only, no rerank kwargs), ``build_rerank_components``
  is never invoked, and nothing is logged — byte-identical default path.
- Flag on: the builder supplies the reranker + KB text fetcher and both
  reach the ``EmbeddingService`` constructor (the stage inside ``search``
  then shapes candidate membership for the proactive pipeline).

The flag fixtures mirror ``tests/unit/api/embeddings/conftest.py``
(ADR-071 §8 env + cache-clear pattern). Both collaborators are stubbed at
their source-module boundary — the factory imports them lazily at call
time, so the patches intercept regardless.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from narrare.embeddings import dependencies as embeddings_dependencies
from narrare.embeddings import service as embeddings_service_module
from narrare.embeddings.repository import EmbeddingRepository
from narrare.kb.dependencies_core import get_kb_suggest_service
from narrare.kb.suggest_service import KBSuggestService
from narrare_core.settings import get_core_settings

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pytest import MonkeyPatch

# Type alias for one recorded EmbeddingService construction:
# (positional args, keyword args).
Construction = tuple[tuple[object, ...], dict[str, object]]

# ---------------------------------------------------------------------------
# ADR-090 rerank flag control (mirrors tests/unit/api/embeddings/conftest.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def rerank_on(monkeypatch: MonkeyPatch) -> Iterator[None]:
    """Enable the ADR-090 rerank pilot flag."""
    monkeypatch.setenv("NARRARE_EMBEDDING_RERANK", "true")
    get_core_settings.cache_clear()
    yield
    get_core_settings.cache_clear()


@pytest.fixture
def rerank_off(monkeypatch: MonkeyPatch) -> Iterator[None]:
    """Pin the ADR-090 flag OFF (the shipped default) regardless of env."""
    monkeypatch.delenv("NARRARE_EMBEDDING_RERANK", raising=False)
    get_core_settings.cache_clear()
    yield
    get_core_settings.cache_clear()


# ---------------------------------------------------------------------------
# Stub collaborators (store-only, no I/O — the factories just build objects)
# ---------------------------------------------------------------------------


def _stub_session() -> AsyncSession:
    """A spec'd session mock — the factories only store it at build time."""
    return cast("AsyncSession", MagicMock(spec=AsyncSession))


def _recording_service_class(record: list[Construction]) -> type:
    """Build an ``EmbeddingService`` stand-in that records its ctor calls."""

    class _RecordingEmbeddingService:
        def __init__(self, *args: object, **kwargs: object) -> None:
            record.append((args, kwargs))

    return _RecordingEmbeddingService


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_flag_off_constructs_service_argument_free(
    rerank_off: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """Flag off (default): byte-identical construction — no builder call."""
    builder_calls: list[object] = []

    def _unexpected_builder(session: object) -> tuple[None, None]:
        builder_calls.append(session)
        return None, None

    constructed: list[Construction] = []
    monkeypatch.setattr(embeddings_dependencies, "build_rerank_components", _unexpected_builder)
    monkeypatch.setattr(
        embeddings_service_module, "EmbeddingService", _recording_service_class(constructed)
    )

    with capture_logs() as logs:
        service = get_kb_suggest_service(_stub_session())

    assert isinstance(service, KBSuggestService)
    assert builder_calls == []
    assert len(constructed) == 1
    args, kwargs = constructed[0]
    assert kwargs == {}  # no rerank kwargs — exactly the pre-rerank signature
    assert len(args) == 1
    assert isinstance(args[0], EmbeddingRepository)
    assert logs == []


def test_flag_on_passes_rerank_components_to_service(
    rerank_on: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """Flag on: the DI builder's components reach the EmbeddingService ctor."""
    stub_reranker = object()
    stub_fetcher = object()
    builder_calls: list[object] = []

    def _stub_builder(session: object) -> tuple[object, object]:
        builder_calls.append(session)
        return stub_reranker, stub_fetcher

    constructed: list[Construction] = []
    monkeypatch.setattr(embeddings_dependencies, "build_rerank_components", _stub_builder)
    monkeypatch.setattr(
        embeddings_service_module, "EmbeddingService", _recording_service_class(constructed)
    )

    session = _stub_session()
    with capture_logs() as logs:
        get_kb_suggest_service(session)

    assert builder_calls == [session]
    assert len(constructed) == 1
    args, kwargs = constructed[0]
    assert len(args) == 1
    assert isinstance(args[0], EmbeddingRepository)
    assert kwargs == {"reranker": stub_reranker, "text_fetcher": stub_fetcher}
    assert logs == []
