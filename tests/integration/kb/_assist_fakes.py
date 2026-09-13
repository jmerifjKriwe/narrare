"""Fakes for the KB session API integration tests (RULE-TEST-01).

Replaces the former ``MagicMock(spec=KBSessionService)`` fixture with a
real-value fake: every method returns the same deterministic, correctly
typed shape the sessions API contract produces (the defaults the mock
fixture used). Call recording is explicit (``calls`` lists — the
FakeLLMGateway / CountingSessionStore convention) instead of mock
introspection. Individual methods stay overridable per test via plain
attribute assignment — the AsyncMock-on-fake override pattern sanctioned
by testing-standards.md § RULE-TEST-01.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from narrare.kb.session_models import KBCreationField, KBCreationSession

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from uuid import UUID


class _RecordedMethod[R]:
    """Awaitable call recorder around a fake method implementation.

    Provides exactly the two faces of ``AsyncMock`` the integration tests
    consume: ``await method(...)`` delegating to a real-signature
    implementation, and ``assert_awaited_once()`` backed by the explicit
    ``calls`` list. Instance attributes shadow the class attribute, so
    ``svc.method = AsyncMock(...)`` overrides keep working unchanged.
    """

    __slots__ = ("_impl", "_name", "calls")

    def __init__(self, name: str, impl: Callable[..., Awaitable[R]]) -> None:
        self._name = name
        self._impl = impl
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def assert_awaited_once(self) -> None:
        """Assert the method was awaited exactly once."""
        if len(self.calls) != 1:
            msg = f"{self._name}: expected exactly 1 await, got {len(self.calls)}"
            raise AssertionError(msg)

    async def __call__(self, *args: object, **kwargs: object) -> R:
        self.calls.append((args, kwargs))
        return await self._impl(*args, **kwargs)


def make_session(**overrides: object) -> KBCreationSession:
    """Build a deterministic ``KBCreationSession`` (keyword overrides allowed)."""
    defaults: dict[str, object] = {
        "id": uuid4(),
        "novel_id": uuid4(),
        "user_id": uuid4(),
        "entity_type": "character",
        "fields": [
            KBCreationField(field_key="name", label="Name", required=True),
            KBCreationField(field_key="personality", label="Personality"),
        ],
    }
    defaults.update(overrides)
    return KBCreationSession.model_validate(defaults)


class FakeKBSessionService:
    """Deterministic real-value fake for ``KBSessionService``.

    Return shapes mirror the real service signatures (session models plus
    the exact assist payload dicts). Each public method is a
    :class:`_RecordedMethod` bound to a private implementation carrying the
    real parameter signature, so a ``KBSessionService`` signature change
    surfaces here as an explicit mismatch instead of silently passing
    (contract-first fakes, RULE-03/ADR-086).
    """

    def __init__(self) -> None:
        self.create_session = _RecordedMethod("create_session", self._create_session)
        self.get_session = _RecordedMethod("get_session", self._get_session)
        self.answer_field = _RecordedMethod("answer_field", self._answer_field)
        self.request_suggestion = _RecordedMethod("request_suggestion", self._request_suggestion)
        self.request_interview_question = _RecordedMethod(
            "request_interview_question", self._request_interview_question
        )
        self.request_enhancement = _RecordedMethod("request_enhancement", self._request_enhancement)
        self.complete_session = _RecordedMethod("complete_session", self._complete_session)
        self.abandon_session = _RecordedMethod("abandon_session", self._abandon_session)

    async def _create_session(
        self, novel_id: UUID, user_id: UUID, entity_type: str
    ) -> KBCreationSession:
        del novel_id, user_id, entity_type  # deterministic fake
        return make_session()

    async def _get_session(
        self, session_id: UUID, novel_id: UUID, user_id: UUID
    ) -> KBCreationSession | None:
        del session_id, novel_id, user_id  # deterministic fake
        return make_session()

    async def _answer_field(
        self, session_id: UUID, novel_id: UUID, user_id: UUID, field_key: str, value: str
    ) -> KBCreationSession:
        del session_id, novel_id, user_id, field_key, value  # deterministic fake
        return make_session()

    async def _request_suggestion(
        self, session_id: UUID, novel_id: UUID, user_id: UUID, field_key: str
    ) -> tuple[KBCreationSession, dict[str, object]]:
        del session_id, novel_id, user_id, field_key  # deterministic fake
        return (
            make_session(),
            {
                "field_key": "name",
                "suggestion": "Aria",
                "reasoning": "Fits genre",
                "context_used": [],
            },
        )

    async def _request_interview_question(
        self, session_id: UUID, novel_id: UUID, user_id: UUID
    ) -> tuple[KBCreationSession, dict[str, str | None]]:
        del session_id, novel_id, user_id  # deterministic fake
        return (
            make_session(),
            {
                "field_key": "personality",
                "question": "What drives this character?",
                "reasoning": "Core trait",
            },
        )

    async def _request_enhancement(
        self, session_id: UUID, novel_id: UUID, user_id: UUID
    ) -> tuple[KBCreationSession, dict[str, object]]:
        del session_id, novel_id, user_id  # deterministic fake
        return (
            make_session(),
            {
                "draft_entry": {"name": "Aria"},
                "progress": 0.5,
                "reasoning": "Good start",
                "context_used": [],
            },
        )

    async def _complete_session(
        self, session_id: UUID, novel_id: UUID, user_id: UUID
    ) -> tuple[KBCreationSession, UUID]:
        del session_id, novel_id, user_id  # deterministic fake
        return (make_session(status="complete"), uuid4())

    async def _abandon_session(self, session_id: UUID, novel_id: UUID, user_id: UUID) -> None:
        del session_id, novel_id, user_id  # deterministic fake
