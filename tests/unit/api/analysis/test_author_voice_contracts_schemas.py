"""Contract + schema tests for ANAL-007 author voice.

Verifies:
- :class:`AuthorVoiceServiceProtocol` is ``@runtime_checkable`` and the
  concrete :class:`AuthorVoiceService` satisfies it (RULE-17 contract test).
- A fake service implementing the protocol satisfies it too (RULE-17 — no
  Mock-with-`# type: ignore`).
- The SSE event schema's defaults + field shapes are stable (the frontend
  Task 4 consumes this wire format).
- The request schema accepts both explicit chapter_ids and null/empty.

Mirrors ``test_voice_drift_contracts_schemas.py`` (RULE-17 precedent).

See:
    ADR-074 — Author Voice Storage Contract.
    CONSTRAINTS.md RULE-03 / RULE-17.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from narrare.analysis.contracts_author_voice import AuthorVoiceServiceProtocol
from narrare.analysis.schemas_author_voice import (
    AuthorVoiceRequest,
    AuthorVoiceResult,
    AuthorVoiceStreamEvent,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare_core.profiles.author_voice import AuthorVoiceProfile


class _FakeService:
    """Minimal protocol-compliant fake (RULE-17 — real implementation)."""

    async def analyze(
        self,
        novel_id: UUID,
        chapter_ids: list[UUID] | None,
        user_id: UUID,
    ) -> AsyncIterator[AuthorVoiceStreamEvent]:
        yield AuthorVoiceStreamEvent(event="done", is_final=True)

    async def get_profile(self, novel_id: UUID, user_id: UUID) -> AuthorVoiceProfile | None:
        return None

    async def clear_profile(self, novel_id: UUID, user_id: UUID) -> None:
        return None


class TestAuthorVoiceServiceProtocol:
    """The contract is runtime-checkable + satisfied by real + fake services."""

    def test_protocol_is_runtime_checkable(self) -> None:
        assert isinstance(_FakeService(), AuthorVoiceServiceProtocol)

    def test_concrete_service_satisfies_protocol(self) -> None:
        from unittest.mock import AsyncMock

        from narrare.analysis.author_voice_service import AuthorVoiceService
        from tests.unit.api.analysis._author_voice_test_helpers import (
            FakeAuthorVoiceRepository,
            FakeModelRegistry,
        )

        service = AuthorVoiceService(
            novel_repo=AsyncMock(),  # type: ignore[arg-type]
            chapter_repo=AsyncMock(),  # type: ignore[arg-type]
            repository=FakeAuthorVoiceRepository(),  # type: ignore[arg-type]
            model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
            model_config=None,
            composer=None,
        )
        assert isinstance(service, AuthorVoiceServiceProtocol)


class TestAuthorVoiceSSESchema:
    """The SSE event schema is stable (the frontend consumes it verbatim)."""

    def test_default_event_is_result_with_no_payload(self) -> None:
        event = AuthorVoiceStreamEvent()
        assert event.event == "result"
        assert event.result is None
        assert event.progress is None
        assert event.error is None
        assert event.is_final is False

    def test_progress_event_carries_only_progress(self) -> None:
        event = AuthorVoiceStreamEvent(event="progress", progress="working")
        assert event.event == "progress"
        assert event.progress == "working"
        assert event.result is None

    def test_done_event_is_final(self) -> None:
        event = AuthorVoiceStreamEvent(event="done", is_final=True)
        assert event.event == "done"
        assert event.is_final is True

    def test_error_event_is_final(self) -> None:
        event = AuthorVoiceStreamEvent(event="error", error="boom", is_final=True)
        assert event.event == "error"
        assert event.error == "boom"
        assert event.is_final is True

    def test_result_carries_novel_id_and_profile(self) -> None:
        result = AuthorVoiceResult(novel_id=str(uuid4()), profile=None)
        event = AuthorVoiceStreamEvent(event="result", result=result)
        assert event.event == "result"
        assert event.result is not None
        assert event.result.profile is None


class TestAuthorVoiceRequestSchema:
    """The request schema accepts explicit ids, null, and empty list."""

    def test_default_chapter_ids_is_none(self) -> None:
        request = AuthorVoiceRequest()
        assert request.chapter_ids is None

    def test_accepts_explicit_chapter_ids(self) -> None:
        ids = [str(uuid4()), str(uuid4())]
        request = AuthorVoiceRequest(chapter_ids=ids)
        assert request.chapter_ids == ids

    def test_accepts_empty_list(self) -> None:
        request = AuthorVoiceRequest(chapter_ids=[])
        assert request.chapter_ids == []
