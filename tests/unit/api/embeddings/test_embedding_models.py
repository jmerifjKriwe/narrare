"""Unit tests for embedding SQLAlchemy models.

Tests ``__repr__`` methods and basic model instantiation.
No DB required — these are pure Python string representations.
"""

from __future__ import annotations

import uuid

from narrare.embeddings.models import ContextUsageEvent, Embedding


class TestEmbeddingRepr:
    """Embedding.__repr__ produces a readable string."""

    def test_embedding_repr_includes_id_and_source(self) -> None:
        """__repr__ shows id, source_type:source_id, and model."""
        emb = Embedding(
            id=uuid.uuid4(),
            source_type="kb_entry",
            source_id=uuid.uuid4(),
            content_hash="abc123",
            embedding=[0.1] * 4,
            model="text-embedding-3-small",
            dimension=4,
        )
        result = repr(emb)
        assert "Embedding(" in result
        assert "kb_entry" in result
        assert "text-embedding-3-small" in result


class TestContextUsageEventRepr:
    """ContextUsageEvent.__repr__ produces a readable string."""

    def test_context_usage_event_repr_includes_id_and_action(self) -> None:
        """__repr__ shows id, entry_id, action, and source."""
        event = ContextUsageEvent(
            id=uuid.uuid4(),
            novel_id=uuid.uuid4(),
            entry_id=uuid.uuid4(),
            action="accepted",
            source="proactive",
        )
        result = repr(event)
        assert "ContextUsageEvent(" in result
        assert "accepted" in result
        assert "proactive" in result
