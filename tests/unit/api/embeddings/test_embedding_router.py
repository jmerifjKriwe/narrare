"""Unit tests for embedding admin router and DI factories.

The router is thin delegation (RULE-06). These tests call the endpoint
functions directly with a fake service, verifying the request→service→response
mapping (including the ``request.model if request else None`` branch) without
spinning up the full HTTP stack.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from narrare.embeddings.dependencies import (
    get_embedding_repository,
    get_embedding_service,
)
from narrare.embeddings.repository import EmbeddingRepository
from narrare.embeddings.router import (
    get_embedding_status,
    get_model_info,
    reprocess_embeddings,
)
from narrare.embeddings.schemas import ReprocessRequest
from narrare.embeddings.service import EmbeddingService
from narrare_core.embeddings.store import EmbeddingStats


class _FakeService:
    """Minimal stand-in for ``EmbeddingService`` used by the router."""

    def __init__(self) -> None:
        self.model = "text-embedding-3-small"
        self.dimension = 1536
        self.provider = "openai"
        self.reprocess_calls: list[str | None] = []

    async def get_status(
        self,
        novel_id: UUID,
        source_ids: set[UUID] | None = None,
    ) -> EmbeddingStats:
        del novel_id, source_ids
        return EmbeddingStats(
            total=10,
            embedded=8,
            pending=2,
            failed=0,
            coverage_percentage=80.0,
        )

    async def reprocess(
        self,
        novel_id: UUID,
        model: str | None = None,
        source_ids: list[tuple[UUID, str]] | None = None,
    ) -> int:
        del novel_id, source_ids
        self.reprocess_calls.append(model)
        return 5


class TestGetEmbeddingStatus:
    async def test_maps_service_stats_to_response(self) -> None:
        response = await get_embedding_status(uuid4(), "user", service=_FakeService())  # type: ignore[arg-type]

        assert response.total == 10
        assert response.embedded == 8
        assert response.pending == 2
        assert response.failed == 0
        assert response.coverage_percentage == 80.0


class TestReprocessEmbeddings:
    async def test_with_request_forwards_model(self) -> None:
        service = _FakeService()
        response = await reprocess_embeddings(
            uuid4(),
            "user",
            ReprocessRequest(model="custom-model"),
            service=service,  # type: ignore[arg-type]
        )

        assert response.queued == 5
        assert service.reprocess_calls == ["custom-model"]

    async def test_without_request_passes_none(self) -> None:
        service = _FakeService()
        response = await reprocess_embeddings(
            uuid4(),
            "user",
            None,
            service=service,  # type: ignore[arg-type]
        )

        assert response.queued == 5
        assert service.reprocess_calls == [None]


class TestGetModelInfo:
    async def test_returns_active_model_attributes(self) -> None:
        response = await get_model_info("user", service=_FakeService())  # type: ignore[arg-type]

        assert response.model == "text-embedding-3-small"
        assert response.dimension == 1536
        assert response.provider == "openai"


class TestDependencies:
    def test_get_embedding_repository_wraps_session(self) -> None:
        session = MagicMock(spec=AsyncSession)
        repo = get_embedding_repository(session)
        assert isinstance(repo, EmbeddingRepository)

    def test_get_embedding_service_builds_from_session(self) -> None:
        session = MagicMock(spec=AsyncSession)
        service = get_embedding_service(session)
        assert isinstance(service, EmbeddingService)
