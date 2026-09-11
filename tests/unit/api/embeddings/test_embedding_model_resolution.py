"""Write-path embedding model default resolution (RULE-18b, P-EMB).

The embedding WRITE path (``run_embed_source``) must resolve its default
model from ``CoreSettings.default_embedding_model`` — the same source every
READ path already uses (``EmbeddingService``, ``NoteSearchService``, and the
core embedding provider). Before P-EMB the write path hardcoded the literal
``"text-embedding-3-small"``: aligned at defaults, but under an env override
(``DEFAULT_EMBEDDING_MODEL``) rows were written under a model the search
never queried. The upsert conflict key is ``(source_type, source_id,
model)``, so semantic search silently returned nothing.

RULE-18b Configuration Effect Integrity: a value exposed as configurable
must reach its runtime consumer — these tests are the per-value regression
proof for the write path.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from narrare.embeddings.tasks import run_embed_source

if TYPE_CHECKING:
    import pytest

    from tests.fakes import FakeEmbeddingRepository


class TestModelDefaultResolution:
    """``run_embed_source`` default model comes from CoreSettings, not a literal."""

    @patch("narrare.embeddings.tasks.embed_texts")
    async def test_default_model_resolved_from_core_settings(
        self,
        mock_embed: AsyncMock,
        fake_repo: FakeEmbeddingRepository,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Env-overridden DEFAULT_EMBEDDING_MODEL drives embed + upsert + lookup.

        The unit-test settings isolation (tests/unit/conftest.py) clears the
        ``get_core_settings`` cache, so the override is picked up by the
        resolution inside ``run_embed_source``.
        """
        monkeypatch.setenv("DEFAULT_EMBEDDING_MODEL", "test-embed-model")
        mock_embed.return_value = [[0.1] * 1536]

        result = await run_embed_source(
            "kb_entry",
            uuid.uuid4(),
            "content",
            repo=fake_repo,
        )

        assert result is True
        mock_embed.assert_called_once_with(["content"], model="test-embed-model")
        # Idempotency lookup and upsert land under the SAME settings-resolved
        # model — the conflict key (source_type, source_id, model) must match
        # what the search path queries.
        fake_repo.assert_called("get_by_source", model="test-embed-model")
        fake_repo.assert_called("upsert", model="test-embed-model")

    @patch("narrare.embeddings.tasks.embed_texts")
    async def test_default_at_defaults_uses_core_settings_default(
        self,
        mock_embed: AsyncMock,
        fake_repo: FakeEmbeddingRepository,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Without an override the settings default applies (no behavior change)."""
        monkeypatch.delenv("DEFAULT_EMBEDDING_MODEL", raising=False)
        mock_embed.return_value = [[0.1] * 1536]

        result = await run_embed_source(
            "kb_entry",
            uuid.uuid4(),
            "content",
            repo=fake_repo,
        )

        assert result is True
        mock_embed.assert_called_once_with(["content"], model="text-embedding-3-small")
        fake_repo.assert_called("upsert", model="text-embedding-3-small")

    @patch("narrare.embeddings.tasks.embed_texts")
    async def test_explicit_model_wins_over_core_settings(
        self,
        mock_embed: AsyncMock,
        fake_repo: FakeEmbeddingRepository,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An explicit model argument takes precedence over the setting."""
        monkeypatch.setenv("DEFAULT_EMBEDDING_MODEL", "test-embed-model")
        mock_embed.return_value = [[0.1] * 1536]

        result = await run_embed_source(
            "kb_entry",
            uuid.uuid4(),
            "content",
            repo=fake_repo,
            model="explicit-model",
        )

        assert result is True
        mock_embed.assert_called_once_with(["content"], model="explicit-model")
        fake_repo.assert_called("upsert", model="explicit-model")
