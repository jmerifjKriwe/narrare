"""KB Session Service — manages assisted creation session lifecycle.

Orchestrates session creation, field updates, AI suggestions, and completion.
Delegates AI operations to KBAssistService and storage to KBCreationSessionStore.

Every session access is ownership-scoped (IDOR remediation S7): a session is
only addressable by its owning user under its own novel. Foreign and unknown
ids are indistinguishable — ownership failures raise ``NotFoundError`` (→ 404
via the global handler), never a bare ``ValueError``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from narrare.kb.session_mapper import map_session_to_entry
from narrare.kb.session_models import KBCreationSession
from narrare.kb.session_ops import extract_filled_fields, validate_session_status
from narrare.kb.template_fields import get_template_fields
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from narrare.kb.assist_contracts import KBAssistProtocol
    from narrare.kb.contracts import KBServiceProtocol
    from narrare.kb.session_store import KBCreationSessionStore
    from narrare.novels.contracts import NovelRepositoryProtocol

logger = structlog.get_logger(__name__)


class KBSessionService:
    """Manages KB creation session lifecycle.

    Args:
        session_store: In-memory ephemeral storage (ADR-080).
        assist_service: KB assisted creation service (AI orchestration).
        novel_repo: Novel repository — create-time novel ownership gate.
        kb_service: KB entry service — used to persist completed sessions.
    """

    def __init__(
        self,
        session_store: KBCreationSessionStore,
        assist_service: KBAssistProtocol,
        novel_repo: NovelRepositoryProtocol,
        kb_service: KBServiceProtocol | None = None,
    ) -> None:
        self._store = session_store
        self._assist = assist_service
        self._novel_repo = novel_repo
        self._kb_service = kb_service

    async def create_session(
        self,
        novel_id: UUID,
        user_id: UUID,
        entity_type: str,
    ) -> KBCreationSession:
        """Create a new KB creation session with template fields.

        Raises:
            NotFoundError: The novel does not belong to the caller — no
                session row is created (Pattern B gate, IDOR S7).
        """
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))
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

    async def get_session(
        self, session_id: UUID, novel_id: UUID, user_id: UUID
    ) -> KBCreationSession | None:
        """Retrieve a session by ID, scoped to (novel_id, user_id).

        Returns None for unknown AND foreign sessions — the two are
        indistinguishable to the caller (Pattern A, anti-enumeration).
        """
        session = await self._store.get(session_id)
        if session is None or session.novel_id != novel_id or session.user_id != user_id:
            return None
        return session

    async def answer_field(
        self, session_id: UUID, novel_id: UUID, user_id: UUID, field_key: str, value: str
    ) -> KBCreationSession:
        """Update a field with a user-provided value (ownership-gated)."""
        session = await self._get_or_raise(session_id, novel_id, user_id)
        validate_session_status(session, "active")

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
        self, session_id: UUID, novel_id: UUID, user_id: UUID, field_key: str
    ) -> tuple[KBCreationSession, dict[str, object]]:
        """Request AI suggestion for a field (ownership-gated).

        Returns updated session + suggestion.
        """
        session = await self._get_or_raise(session_id, novel_id, user_id)
        validate_session_status(session, "active")

        existing = extract_filled_fields(session)

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
        self, session_id: UUID, novel_id: UUID, user_id: UUID
    ) -> tuple[KBCreationSession, dict[str, str | None]]:
        """Get next interview question from AI (ownership-gated)."""
        session = await self._get_or_raise(session_id, novel_id, user_id)
        validate_session_status(session, "active")

        existing = extract_filled_fields(session)

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
        self, session_id: UUID, novel_id: UUID, user_id: UUID
    ) -> tuple[KBCreationSession, dict[str, object]]:
        """Request AI enhancement of the entire entry (ownership-gated)."""
        session = await self._get_or_raise(session_id, novel_id, user_id)
        validate_session_status(session, "active")

        existing = extract_filled_fields(session)

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
        novel_id: UUID,
        user_id: UUID,
        name: str | None = None,
    ) -> tuple[KBCreationSession, UUID]:
        """Complete session and create KB entry (ownership-gated).

        The optional ``name`` (complete request body, F9-1) fills
        ``session.name`` before mapping; absent/None keeps the
        name-required guard.

        Creates the KB entry from session fields BEFORE marking the
        session as complete. If entry creation fails, the session
        stays in its previous state (active/review) — the user can
        retry or fix the issue.

        Returns:
            Tuple of (updated session, created entry ID).

        Raises:
            NotFoundError: Session is unknown or not owned by (novel_id, user_id).
            ValueError: Invalid status, name missing, or KB service misconfigured.
        """
        session = await self._get_or_raise(session_id, novel_id, user_id)
        validate_session_status(session, "active", "review")

        # F9-1: body name applied in memory only — persistence happens
        # with the STEP 2 store update, so a failed entry creation
        # leaves the session unchanged.
        if name:
            session.name = name

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

    async def abandon_session(self, session_id: UUID, novel_id: UUID, user_id: UUID) -> None:
        """Mark session as abandoned and delete from store (ownership-gated)."""
        session = await self._get_or_raise(session_id, novel_id, user_id)
        session.status = "abandoned"
        session.updated_at = datetime.now(UTC)
        await self._store.update(session)
        await self._store.delete(session_id)

    async def _get_or_raise(
        self, session_id: UUID, novel_id: UUID, user_id: UUID
    ) -> KBCreationSession:
        """Get the caller-owned session or raise NotFoundError (IDOR S7)."""
        session = await self.get_session(session_id, novel_id, user_id)
        if session is None:
            raise NotFoundError("KB creation session", identifier=str(session_id))
        return session
