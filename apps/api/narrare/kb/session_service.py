"""KB Session Service — manages assisted creation session lifecycle.

Orchestrates session creation, field updates, AI suggestions, and completion.
Delegates AI operations to KBAssistService and storage to KBCreationSessionStore.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from narrare.kb.session_mapper import map_session_to_entry
from narrare.kb.session_models import KBCreationSession
from narrare.kb.template_fields import get_template_fields

if TYPE_CHECKING:
    from narrare.kb.assist_contracts import KBAssistProtocol
    from narrare.kb.contracts import KBServiceProtocol
    from narrare.kb.session_store import KBCreationSessionStore

logger = structlog.get_logger(__name__)


class KBSessionService:
    """Manages KB creation session lifecycle.

    Args:
        session_store: Redis-backed ephemeral storage.
        assist_service: KB assisted creation service (AI orchestration).
        kb_service: KB entry service — used to persist completed sessions.
    """

    def __init__(
        self,
        session_store: KBCreationSessionStore,
        assist_service: KBAssistProtocol,
        kb_service: KBServiceProtocol | None = None,
    ) -> None:
        self._store = session_store
        self._assist = assist_service
        self._kb_service = kb_service

    async def create_session(
        self,
        novel_id: UUID,
        user_id: UUID,
        entity_type: str,
    ) -> KBCreationSession:
        """Create a new KB creation session with template fields."""
        fields = get_template_fields(entity_type)
        session = KBCreationSession(
            id=uuid4(),
            novel_id=novel_id,
            user_id=user_id,
            entity_type=entity_type,
            fields=fields,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        await self._store.create(session)
        logger.info(
            "kb_session_created",
            session_id=str(session.id),
            entity_type=entity_type,
        )
        return session

    async def get_session(self, session_id: UUID) -> KBCreationSession | None:
        """Retrieve a session by ID."""
        return await self._store.get(session_id)

    async def answer_field(
        self,
        session_id: UUID,
        field_key: str,
        value: str,
    ) -> KBCreationSession:
        """Update a field with a user-provided value."""
        session = await self._get_or_raise(session_id)
        self._validate_status(session, "active")

        for field in session.fields:
            if field.field_key == field_key:
                field.user_value = value
                field.source = "user"
                field.final_value = value
                break
        else:
            raise ValueError(f"Field '{field_key}' not found in session")

        session.updated_at = datetime.now(UTC)
        await self._store.update(session)
        return session

    async def request_suggestion(
        self,
        session_id: UUID,
        field_key: str,
    ) -> tuple[KBCreationSession, dict[str, object]]:
        """Request AI suggestion for a field. Returns updated session + suggestion."""
        session = await self._get_or_raise(session_id)
        self._validate_status(session, "active")

        existing = self._extract_existing_fields(session)

        suggestion = await self._assist.get_suggestion(
            novel_id=session.novel_id,
            entity_type=session.entity_type,
            field_key=field_key,
            existing_fields=existing,
        )

        # Update field with suggestion
        for field in session.fields:
            if field.field_key == field_key:
                field.ai_suggested_value = suggestion.suggestion
                field.ai_reasoning = suggestion.reasoning
                break

        session.updated_at = datetime.now(UTC)
        await self._store.update(session)

        return session, {
            "field_key": suggestion.field_key,
            "suggestion": suggestion.suggestion,
            "reasoning": suggestion.reasoning,
            "context_used": suggestion.context_used,
        }

    async def request_interview_question(
        self,
        session_id: UUID,
    ) -> tuple[KBCreationSession, dict[str, str | None]]:
        """Get next interview question from AI."""
        session = await self._get_or_raise(session_id)
        self._validate_status(session, "active")

        existing = self._extract_existing_fields(session)

        question = await self._assist.get_interview_question(
            novel_id=session.novel_id,
            entity_type=session.entity_type,
            existing_fields=existing,
        )

        session.updated_at = datetime.now(UTC)
        await self._store.update(session)

        return session, {
            "field_key": question.field_key,
            "question": question.question,
            "reasoning": question.reasoning,
        }

    async def request_enhancement(
        self,
        session_id: UUID,
    ) -> tuple[KBCreationSession, dict[str, object]]:
        """Request AI enhancement of the entire entry."""
        session = await self._get_or_raise(session_id)
        self._validate_status(session, "active")

        existing = self._extract_existing_fields(session)

        enhancement = await self._assist.get_enhancement(
            novel_id=session.novel_id,
            entity_type=session.entity_type,
            existing_fields=existing,
        )

        # Update fields from draft_entry
        for field in session.fields:
            if field.field_key in enhancement.draft_entry:
                suggested = enhancement.draft_entry[field.field_key]
                if isinstance(suggested, str):
                    field.ai_suggested_value = suggested
                    field.ai_reasoning = enhancement.reasoning
                    if not field.user_value:
                        field.final_value = suggested
                        field.source = "ai"

        session.updated_at = datetime.now(UTC)
        await self._store.update(session)

        return session, {
            "draft_entry": enhancement.draft_entry,
            "progress": enhancement.progress,
            "reasoning": enhancement.reasoning,
            "context_used": enhancement.context_used,
        }

    async def complete_session(
        self,
        session_id: UUID,
    ) -> tuple[KBCreationSession, UUID]:
        """Complete session and create KB entry.

        Creates the KB entry from session fields BEFORE marking the
        session as complete. If entry creation fails, the session
        stays in its previous state (active/review) — the user can
        retry or fix the issue.

        Returns:
            Tuple of (updated session, created entry ID).

        Raises:
            ValueError: Session not found, invalid status, or name missing.
        """
        session = await self._get_or_raise(session_id)
        self._validate_status(session, "active", "review")

        # Fill final_value for any remaining fields
        for field in session.fields:
            if field.final_value is None:
                field.final_value = field.user_value or field.ai_suggested_value

        # STEP 1: Create KB entry (can fail → session stays unchanged)
        if self._kb_service is None:
            raise ValueError("KB service not configured — cannot create entry from session")

        entry_data = map_session_to_entry(session)
        entry = await self._kb_service.create(
            novel_id=session.novel_id,
            user_id=session.user_id,
            data=entry_data,
        )

        # STEP 2: Only after successful entry creation, mark session complete
        session.status = "complete"
        session.updated_at = datetime.now(UTC)
        await self._store.update(session)

        logger.info(
            "kb_session_completed_with_entry",
            session_id=str(session.id),
            entry_id=str(entry.id),
            entity_type=session.entity_type,
        )

        return session, entry.id

    async def abandon_session(self, session_id: UUID) -> None:
        """Mark session as abandoned and delete from store."""
        session = await self._get_or_raise(session_id)
        session.status = "abandoned"
        session.updated_at = datetime.now(UTC)
        await self._store.update(session)
        await self._store.delete(session_id)

    def _extract_existing_fields(self, session: KBCreationSession) -> dict[str, str]:
        """Extract filled field values from session as a dict."""
        result: dict[str, str] = {}
        for field in session.fields:
            value = field.final_value or field.user_value or field.ai_suggested_value
            if value:
                result[field.field_key] = value
        return result

    async def _get_or_raise(self, session_id: UUID) -> KBCreationSession:
        """Get session or raise ValueError if not found."""
        session = await self._store.get(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        return session

    def _validate_status(self, session: KBCreationSession, *allowed: str) -> None:
        """Validate session status is in allowed list."""
        if session.status not in allowed:
            raise ValueError(
                f"Session {session.id} has status '{session.status}', expected one of {allowed}"
            )
