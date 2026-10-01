"""Unit tests for the ADR-090 rerank DI wiring (``build_rerank_components``).

Pins the Backend wiring decision (ADR-090 Decisions 5-6) at the factory
seam:

- Flag off (shipped default): no components are built — the service keeps
  the byte-identical pre-rerank search path, and the availability probe /
  reranker constructor are never consulted.
- Flag on, ``embeddings`` extra absent: no components + exactly ONE
  structured ``embedding_rerank_unavailable`` warning
  (``reason="extra_missing"``) — RULE-11 loud degradation.
- Flag on, extra present (RULE-18b): the ``MultiVectorReranker`` receives
  the ``CoreSettings.embedding_rerank_model`` knob (the pinned checkpoint
  — never the ST library default), and the text fetcher routes through
  ``KBRepository.get_bodies_by_ids``.

``MultiVectorReranker`` and the availability probe are stubbed at the
dependencies-module boundary — no checkpoint download, runs identically
with or without the ``embeddings`` extra installed.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from narrare.embeddings import dependencies as embeddings_dependencies
from narrare.embeddings.dependencies import build_rerank_components
from narrare_core.settings import get_core_settings

if TYPE_CHECKING:
    from pytest import MonkeyPatch


class _StubReranker:
    """Records the model name the wiring passes to ``MultiVectorReranker``."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name


class _StubKBRepository:
    """Stand-in for ``KBRepository`` behind the text-fetcher closure."""

    def __init__(self, session: object) -> None:
        self.session = session

    async def get_bodies_by_ids(self, entry_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        return {entry_id: f"body-{entry_id}" for entry_id in entry_ids}


def _stub_session() -> AsyncSession:
    """A spec'd session mock — the factories only store it at build time."""
    return cast("AsyncSession", MagicMock(spec=AsyncSession))


def test_wiring_flag_off_builds_no_components(
    rerank_off: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """Flag off (default): no components, no availability probe, no warning."""
    constructed: list[str] = []

    class _AssertingStub:
        def __init__(self, model_name: str) -> None:
            constructed.append(model_name)

    monkeypatch.setattr(embeddings_dependencies, "is_rerank_available", lambda: True)
    monkeypatch.setattr(embeddings_dependencies, "MultiVectorReranker", _AssertingStub)

    with capture_logs() as logs:
        components = build_rerank_components(_stub_session())

    assert components == (None, None)
    assert constructed == []
    assert logs == []


def test_wiring_flag_on_extra_missing_degrades(
    rerank_on: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """Flag on, extra absent: no components + exactly ONE structured warning."""
    monkeypatch.setattr(embeddings_dependencies, "is_rerank_available", lambda: False)

    with capture_logs() as logs:
        components = build_rerank_components(_stub_session())

    assert components == (None, None)
    unavailable = [log for log in logs if log["event"] == "embedding_rerank_unavailable"]
    assert len(unavailable) == 1
    assert unavailable[0]["log_level"] == "warning"
    assert unavailable[0]["reason"] == "extra_missing"


async def test_wiring_flag_on_builds_reranker_with_settings_model(
    rerank_on: None,
    monkeypatch: MonkeyPatch,
) -> None:
    """RULE-18b: the settings model knob reaches the reranker constructor;
    the text fetcher routes through the KB repository."""
    monkeypatch.setattr(embeddings_dependencies, "is_rerank_available", lambda: True)
    monkeypatch.setattr(embeddings_dependencies, "MultiVectorReranker", _StubReranker)
    monkeypatch.setattr(embeddings_dependencies, "KBRepository", _StubKBRepository)

    reranker, text_fetcher = build_rerank_components(_stub_session())

    assert isinstance(reranker, _StubReranker)
    assert reranker.model_name == get_core_settings().embedding_rerank_model
    assert text_fetcher is not None
    source_id = uuid4()
    assert await text_fetcher([source_id]) == {source_id: f"body-{source_id}"}
