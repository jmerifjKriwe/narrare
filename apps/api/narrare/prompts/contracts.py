"""Prompts API service contracts — written before implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from narrare.prompts.schemas import (
        CascadePathResponse,
        DiffResponse,
        PromptDetailResponse,
        PromptInfoResponse,
        SaveOverrideRequest,
        UpdateInfoResponse,
    )


@runtime_checkable
class PromptManagementProtocol(Protocol):
    """Protocol for prompt management API service."""

    async def list_prompts(
        self,
        *,
        category: str | None = None,
    ) -> list[PromptInfoResponse]: ...

    async def get_prompt(self, prompt_id: str) -> PromptDetailResponse | None: ...

    async def save_override(self, prompt_id: str, request: SaveOverrideRequest) -> None: ...

    async def reset_override(self, prompt_id: str) -> bool: ...

    async def cascade_info(self, prompt_id: str) -> list[CascadePathResponse]: ...

    async def detect_updates(self) -> list[UpdateInfoResponse]: ...

    async def get_diff(self, prompt_id: str) -> DiffResponse | None: ...
