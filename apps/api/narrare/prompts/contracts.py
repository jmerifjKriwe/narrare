"""Prompts API service contracts — written before implementation.

Includes PROMPT-003 (CR-AUFG-07-16) Protocols for the provider-free preview,
reset-with-metadata, and optional live-test endpoints. These Protocols are
the RULE-03 gate: they exist before any service implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.prompts.schemas import (
        CascadePathResponse,
        DiffResponse,
        PromptDetailResponse,
        PromptInfoResponse,
        SaveOverrideRequest,
        UpdateInfoResponse,
    )
    from narrare.prompts.schemas_prompt_history import (
        PromptHistoryClearedResponse,
        PromptHistoryListResponse,
        PromptHistoryScope,
        PromptRevisionCompareResponse,
        PromptRevisionRestoredResponse,
    )
    from narrare.prompts.schemas_prompt_ux import (
        LiveTestRequest,
        LiveTestStartedResponse,
        PreviewRequest,
        PreviewResponse,
        ResetResponse,
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


@runtime_checkable
class PromptHistoryServiceProtocol(Protocol):
    """Prompt History service Protocol (CR-AUFG-07-19).

    Composes the core file-based ``PromptManagementService`` with a DB-backed
    revision repository.  The active override remains a FILE (authoritative
    cascade source); revisions are a secondary, append-only record.  This is
    the RULE-03 gate: the Protocol exists before the service implementation.

    Recording-on-save is best-effort: the file write is authoritative; if the
    DB revision row cannot be persisted the failure is logged but does NOT
    block the override save.
    """

    async def save_override_recorded(
        self,
        prompt_id: str,
        request: SaveOverrideRequest,
        *,
        actor_id: UUID,
        scope: PromptHistoryScope = ...,
    ) -> None:
        """Write the active override file, then record a revision row.

        Order: file-first (authoritative), then DB row.  Dedup: skip the row
        when the content hash matches the most recent recorded revision.
        """
        ...

    async def list_history(
        self,
        prompt_id: str,
        *,
        scope: PromptHistoryScope = ...,
        limit: int = 50,
        offset: int = 0,
    ) -> PromptHistoryListResponse:
        """List recorded revisions, newest first, with derived ``is_active``."""
        ...

    async def compare_revisions(
        self,
        prompt_id: str,
        *,
        from_id: str,
        to_id: str,
        scope: PromptHistoryScope = ...,
    ) -> PromptRevisionCompareResponse:
        """Compare two revisions (or the literal ``"active"``) by content."""
        ...

    async def restore_revision(
        self,
        prompt_id: str,
        revision_id: UUID,
        *,
        actor_id: UUID,
        scope: PromptHistoryScope = ...,
    ) -> PromptRevisionRestoredResponse:
        """Append-only restore: write active file + record a NEW revision."""
        ...

    async def clear_history(
        self,
        prompt_id: str,
        *,
        scope: PromptHistoryScope = ...,
    ) -> PromptHistoryClearedResponse:
        """Delete all history rows; the active override file is untouched."""
        ...
