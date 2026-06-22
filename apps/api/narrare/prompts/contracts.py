"""Prompts API service contracts — written before implementation.

Includes PROMPT-003 (CR-AUFG-07-16) Protocols for the provider-free preview,
reset-with-metadata, and optional live-test endpoints. These Protocols are
the RULE-03 gate: they exist before any service implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare.prompts.schemas import (
        CascadePathResponse,
        DiffResponse,
        LiveTestRequest,
        LiveTestStartedResponse,
        PreviewRequest,
        PreviewResponse,
        PromptDetailResponse,
        PromptInfoResponse,
        ResetResponse,
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


@runtime_checkable
class PromptPreviewApiProtocol(Protocol):
    """Backend preview service Protocol (PROMPT-003 / CR-AUFG-07-16).

    Wraps the Core ``PromptPreviewProtocol`` and maps Core dataclasses to
    the API-layer Pydantic response. Contains no LLM/agent/provider code.
    """

    async def preview(
        self,
        prompt_id: str,
        request: PreviewRequest,
    ) -> PreviewResponse: ...


@runtime_checkable
class PromptResetApiProtocol(Protocol):
    """Backend reset service Protocol.

    Returns metadata describing the post-reset effective prompt instead of a
    bare boolean, so the UI can render the restored state without a follow-up
    GET. Required by PROMPT-003 §B.1.
    """

    async def reset_with_metadata(self, prompt_id: str) -> ResetResponse: ...


@runtime_checkable
class PromptLiveTestApiProtocol(Protocol):
    """Backend live-test service Protocol (SSE-streamed, provider-gated).

    ``validate_live_test`` performs provider/secret/rate-limit gating and
    returns metadata before streaming begins. ``stream_live_test`` yields
    ``text/event-stream`` frames. The implementation lives in Task 9; this
    Protocol is declared here so the router (Task 10) can depend on the
    contract before the service exists (RULE-03).
    """

    async def validate_live_test(
        self,
        prompt_id: str,
        request: LiveTestRequest,
        *,
        user_id: str,
    ) -> LiveTestStartedResponse: ...

    def stream_live_test(
        self,
        prompt_id: str,
        request: LiveTestRequest,
        *,
        user_id: str,
        metadata: LiveTestStartedResponse,
    ) -> AsyncIterator[str]: ...
