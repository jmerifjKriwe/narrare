"""Tests for embeddings/store.py — EmbeddingStoreProtocol, SearchResult, EmbeddingStats."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from uuid import UUID, uuid4

import pytest

from narrare_core.embeddings.store import EmbeddingStats, EmbeddingStoreProtocol, SearchResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uuid() -> UUID:
    return uuid4()


# ---------------------------------------------------------------------------
# SearchResult tests
# ---------------------------------------------------------------------------


class TestSearchResult:
    """SearchResult dataclass construction and field validation."""

    def test_search_result_construction_succeeds(self) -> None:
        sid = _uuid()
        result = SearchResult(
            source_id=sid,
            source_type="kb_entry",
            score=0.95,
            content_hash="abc123",
        )
        assert result.source_id == sid
        assert result.source_type == "kb_entry"
        assert result.score == 0.95
        assert result.content_hash == "abc123"

    def test_search_result_score_zero_is_valid(self) -> None:
        result = SearchResult(
            source_id=_uuid(),
            source_type="kb_entry",
            score=0.0,
            content_hash="hash",
        )
        assert result.score == 0.0

    def test_search_result_score_one_is_valid(self) -> None:
        result = SearchResult(
            source_id=_uuid(),
            source_type="kb_entry",
            score=1.0,
            content_hash="hash",
        )
        assert result.score == 1.0

    def test_search_result_negative_score_is_allowed(self) -> None:
        """Negative scores are permitted — callers should document meaning."""
        result = SearchResult(
            source_id=_uuid(),
            source_type="kb_entry",
            score=-0.5,
            content_hash="hash",
        )
        assert result.score == -0.5

    def test_search_result_is_frozen(self) -> None:
        result = SearchResult(
            source_id=_uuid(),
            source_type="kb_entry",
            score=0.9,
            content_hash="hash",
        )
        with pytest.raises(FrozenInstanceError):
            result.score = 0.8  # type: ignore[misc]

    def test_search_result_equality_by_value(self) -> None:
        sid = _uuid()
        a = SearchResult(source_id=sid, source_type="kb_entry", score=0.9, content_hash="h")
        b = SearchResult(source_id=sid, source_type="kb_entry", score=0.9, content_hash="h")
        assert a == b

    def test_search_result_inequality_by_score(self) -> None:
        sid = _uuid()
        a = SearchResult(source_id=sid, source_type="kb_entry", score=0.9, content_hash="h")
        b = SearchResult(source_id=sid, source_type="kb_entry", score=0.8, content_hash="h")
        assert a != b


# ---------------------------------------------------------------------------
# EmbeddingStats tests
# ---------------------------------------------------------------------------


class TestEmbeddingStats:
    """EmbeddingStats dataclass construction and coverage calculation."""

    def test_embedding_stats_construction_succeeds(self) -> None:
        stats = EmbeddingStats(
            total=100,
            embedded=80,
            pending=15,
            failed=5,
            coverage_percentage=80.0,
        )
        assert stats.total == 100
        assert stats.embedded == 80
        assert stats.pending == 15
        assert stats.failed == 5
        assert stats.coverage_percentage == 80.0

    def test_embedding_stats_coverage_calculation(self) -> None:
        """coverage_percentage = embedded / total * 100."""
        total = 200
        embedded = 150
        coverage = embedded / total * 100
        stats = EmbeddingStats(
            total=total,
            embedded=embedded,
            pending=40,
            failed=10,
            coverage_percentage=coverage,
        )
        assert stats.coverage_percentage == 75.0

    def test_embedding_stats_zero_total(self) -> None:
        """Edge case: novel with no embeddable entities."""
        stats = EmbeddingStats(
            total=0,
            embedded=0,
            pending=0,
            failed=0,
            coverage_percentage=0.0,
        )
        assert stats.total == 0
        assert stats.coverage_percentage == 0.0

    def test_embedding_stats_full_coverage(self) -> None:
        """All entities embedded."""
        stats = EmbeddingStats(
            total=50,
            embedded=50,
            pending=0,
            failed=0,
            coverage_percentage=100.0,
        )
        assert stats.coverage_percentage == 100.0

    def test_embedding_stats_is_frozen(self) -> None:
        stats = EmbeddingStats(total=10, embedded=5, pending=3, failed=2, coverage_percentage=50.0)
        with pytest.raises(FrozenInstanceError):
            stats.total = 20  # type: ignore[misc]

    def test_embedding_stats_equality_by_value(self) -> None:
        a = EmbeddingStats(total=10, embedded=5, pending=3, failed=2, coverage_percentage=50.0)
        b = EmbeddingStats(total=10, embedded=5, pending=3, failed=2, coverage_percentage=50.0)
        assert a == b


# ---------------------------------------------------------------------------
# EmbeddingStoreProtocol conformance tests
# ---------------------------------------------------------------------------


class TestEmbeddingStoreProtocol:
    """Verify that the protocol is runtime-checkable."""

    def test_mock_implementation_passes_isinstance(self) -> None:
        """A class implementing all methods satisfies the protocol."""

        class FakeStore:
            async def generate(self, source_type: str, source_id: UUID, content: str) -> None:
                pass

            async def search(
                self,
                query: str,
                *,
                source_type: str | None = None,
                novel_id: UUID | None = None,
                threshold: float = 0.7,
                limit: int = 20,
                model: str | None = None,
            ) -> list[SearchResult]:
                return []

            async def delete(self, source_type: str, source_id: UUID) -> None:
                pass

            async def get_status(self, novel_id: UUID) -> EmbeddingStats:
                return EmbeddingStats(
                    total=0, embedded=0, pending=0, failed=0, coverage_percentage=0.0
                )

            async def reprocess(self, novel_id: UUID, model: str | None = None) -> None:
                pass

        assert isinstance(FakeStore(), EmbeddingStoreProtocol)

    def test_incomplete_implementation_fails_isinstance(self) -> None:
        """A class missing methods does NOT satisfy the protocol."""

        class IncompleteStore:
            async def generate(self, source_type: str, source_id: UUID, content: str) -> None:
                pass

        # Protocol structural typing: missing search, delete, get_status, reprocess
        assert not isinstance(IncompleteStore(), EmbeddingStoreProtocol)

    def test_protocol_imports_no_db_dependencies(self) -> None:
        """Importing the protocol module triggers no sqlalchemy/fastapi imports."""
        import importlib
        import sys

        # Record modules before import
        before = set(sys.modules.keys())

        importlib.import_module("narrare_core.embeddings.store")

        after = set(sys.modules.keys())
        new_modules = after - before

        forbidden = {"sqlalchemy", "asyncpg", "fastapi"}
        for mod in new_modules:
            base = mod.split(".")[0]
            assert base not in forbidden, f"Forbidden module imported: {mod}"
