"""KB assist service contract and response schemas.

Extracted from contracts.py per RULE-04 (file size limit).
Contracts are written before implementation (RULE-03).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from uuid import UUID


# ---------------------------------------------------------------------------
# Response schemas (moved from schemas.py per RULE-04)
# ---------------------------------------------------------------------------


class KBAssistQuestionResponse(BaseModel):
    """Response from interview mode — a single question about a field."""

    field_key: str
    question: str
    reasoning: str | None = None


class KBAssistSuggestionResponse(BaseModel):
    """Response from suggest mode — AI suggestion for a field."""

    field_key: str
    suggestion: str
    reasoning: str | None = None
    context_used: list[str] = []


class KBAssistEnhancementResponse(BaseModel):
    """Response from enhance mode — AI-generated draft of multiple fields."""

    draft_entry: dict[str, object]
    progress: float = Field(ge=0.0, le=1.0)
    reasoning: str | None = None
    context_used: list[str] = []


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class KBAssistProtocol(Protocol):
    """Protocol for KB assisted creation service.

    Provides three interaction modes for guided KB entry creation:
    - interview: Ask focused questions about template fields
    - suggest: Suggest values for specific fields
    - enhance: Generate a draft of multiple fields at once
    """

    async def get_interview_question(
        self,
        *,
        novel_id: UUID,
        entity_type: str,
        existing_fields: dict[str, str],
    ) -> KBAssistQuestionResponse: ...

    async def get_suggestion(
        self,
        *,
        novel_id: UUID,
        entity_type: str,
        field_key: str,
        existing_fields: dict[str, str],
    ) -> KBAssistSuggestionResponse: ...

    async def get_enhancement(
        self,
        *,
        novel_id: UUID,
        entity_type: str,
        existing_fields: dict[str, str],
    ) -> KBAssistEnhancementResponse: ...
