"""Write-path embedding dimension default resolution (RULE-18b, P-DIM).

Companion to ``test_embedding_model_resolution.py`` (P-EMB): the embedding
WRITE paths (``run_embed_source`` in tasks.py and ``EmbeddingService`` in
service.py) must resolve their default vector dimension from
``CoreSettings.default_embedding_dimension`` — not from a hardcoded ``1536``
literal. Aligned at defaults, but under an env override
(``DEFAULT_EMBEDDING_DIMENSION``) the recorded ``dimension`` metadata would
silently keep the hardcoded value (RULE-18b: a value exposed as configurable
must reach its runtime consumer).

The dimension is recorded as row metadata next to the vector (upsert column
``dimension``); it does not change the embedding call itself.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from narrare.embeddings.service import EmbeddingService
from narrare.embeddings.tasks import run_embed_source

if TYPE_CHECKING:
    import pytest

    from tests.fakes import FakeEmbeddingRepository


class TestTaskDimensionDefaultResolution:
    """``run_embed_source`` default dimension comes from CoreSettings, not a literal."""

    @patch("narrare.embeddings.tasks.embed_texts")
    async def test_default_dimension_resolved_from_core_settings(
        self,
        mock_embed: AsyncMock,
        fake_repo: FakeEmbeddingRepository,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Env-overridden DEFAULT_EMBEDDING_DIMENSION drives the upsert dimension.

        The unit-test settings isolation (tests/unit/conftest.py) clears the
        ``get_core_settings`` cache, so the override is picked up by the
        resolution inside ``run_embed_source``.
        """
        monkeypatch.setenv("DEFAULT_EMBEDDING_DIMENSION", "3072")
        mock_embed.return_value = [[0.1] * 3072]

        result = await run_embed_source(
            "kb_entry",
            uuid.uuid4(),
            "content",
            repo=fake_repo,
        )

        assert result is True
        # Dimension is row metadata — the embedding call itself is unchanged.
        mock_embed.assert_called_once_with(["content"], model="text-embedding-3-small")
        fake_repo.assert_called("upsert", dimension=3072)

    @patch("narrare.embeddings.tasks.embed_texts")
    async def test_default_dimension_at_defaults_uses_core_settings_default(
        self,
        mock_embed: AsyncMock,
        fake_repo: FakeEmbeddingRepository,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Without an override the settings default (1536) applies — no behavior change."""
        monkeypatch.delenv("DEFAULT_EMBEDDING_DIMENSION", raising=False)
        mock_embed.return_value = [[0.1] * 1536]

        result = await run_embed_source(
            "kb_entry",
            uuid.uuid4(),
            "content",
            repo=fake_repo,
        )

        assert result is True
        fake_repo.assert_called("upsert", dimension=1536)

    @patch("narrare.embeddings.tasks.embed_texts")
    async def test_explicit_dimension_wins_over_core_settings(
        self,
        mock_embed: AsyncMock,
        fake_repo: FakeEmbeddingRepository,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An explicit dimension argument takes precedence over the setting."""
        monkeypatch.setenv("DEFAULT_EMBEDDING_DIMENSION", "3072")
        mock_embed.return_value = [[0.1] * 256]

        result = await run_embed_source(
            "kb_entry",
            uuid.uuid4(),
            "content",
            repo=fake_repo,
            dimension=256,
        )

        assert result is True
        fake_repo.assert_called("upsert", dimension=256)


class TestServiceDimensionDefaultResolution:
    """``EmbeddingService`` default dimension comes from CoreSettings, not a literal."""

    async def test_service_dimension_resolved_from_core_settings(
        self,
        fake_repo: FakeEmbeddingRepository,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Env-overridden DEFAULT_EMBEDDING_DIMENSION drives ``service.dimension``."""
        monkeypatch.setenv("DEFAULT_EMBEDDING_DIMENSION", "3072")

        service = EmbeddingService(fake_repo)

        assert service.dimension == 3072

    async def test_service_dimension_at_defaults_uses_core_settings_default(
        self,
        fake_repo: FakeEmbeddingRepository,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Without an override the settings default (1536) applies — no behavior change."""
        monkeypatch.delenv("DEFAULT_EMBEDDING_DIMENSION", raising=False)

        service = EmbeddingService(fake_repo)

        assert service.dimension == 1536

    async def test_service_explicit_dimension_wins_over_core_settings(
        self,
        fake_repo: FakeEmbeddingRepository,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An explicit constructor dimension takes precedence over the setting."""
        monkeypatch.setenv("DEFAULT_EMBEDDING_DIMENSION", "3072")

        service = EmbeddingService(fake_repo, dimension=256)

        assert service.dimension == 256
