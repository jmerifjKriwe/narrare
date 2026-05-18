"""Writing API service contracts — written before implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.writing.schemas import (
        AcceptResponse,
        GenerateRequest,
        GenerateResponse,
        GenerationStatsResponse,
        RejectResponse,
        SceneNextResponse,
        StopResponse,
    )


@runtime_checkable
class WritingServiceProtocol(Protocol):
    """Protocol for the writing API service."""

    async def start_generation(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        user_id: str,
        request: GenerateRequest,
    ) -> GenerateResponse: ...

    async def stream_generation(
        self,
        request_id: UUID,
        user_id: str,
    ) -> AsyncIterator[str]: ...

    async def stop_generation(
        self,
        request_id: UUID,
        user_id: str,
    ) -> StopResponse: ...

    async def accept_draft(
        self,
        request_id: UUID,
        user_id: str,
        modified_text: str | None = None,
    ) -> AcceptResponse: ...

    async def reject_draft(
        self,
        request_id: UUID,
        user_id: str,
    ) -> RejectResponse: ...

    async def next_scene(
        self,
        request_id: UUID,
        user_id: str,
    ) -> SceneNextResponse: ...

    async def accept_scene(
        self,
        request_id: UUID,
        scene_number: int,
        user_id: str,
    ) -> AcceptResponse: ...

    async def get_stats(
        self,
        novel_id: UUID,
        user_id: str,
    ) -> GenerationStatsResponse: ...


@runtime_checkable
class GenerationRepositoryProtocol(Protocol):
    """Protocol for the generation request repository."""

    async def create(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        user_id: UUID,
        mode: str,
    ) -> UUID: ...

    async def get_by_id(self, request_id: UUID) -> object | None: ...

    async def update_status(
        self,
        request_id: UUID,
        status: str,
        **kwargs: object,
    ) -> None: ...

    async def get_active_for_chapter(self, chapter_id: UUID) -> object | None: ...

    async def cleanup_stale(
        self,
        max_age_minutes: int = 30,
        pending_age_minutes: int = 5,
    ) -> int: ...

    async def get_stats_for_novel(self, novel_id: UUID) -> dict[str, object]: ...
