"""KB session request/response schemas.

Extracted from schemas.py per RULE-04 (file size limit).
Schemas for KB creation session lifecycle endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    """Request body for creating a new KB creation session."""

    entity_type: str = Field(min_length=1, max_length=50)


class AnswerFieldRequest(BaseModel):
    """Request body for answering a field in a KB creation session."""

    value: str = Field(min_length=1)


class CompleteSessionRequest(BaseModel):
    """Optional request body for completing a KB creation session.

    F9-1: the FE collects the entry name at the final step and sends it
    here. The body itself is optional (absent body or absent name keeps
    the existing name-required guard in the service/mapper); name
    constraints mirror ``KBEntryCreate.name``.
    """

    name: str | None = Field(default=None, min_length=1, max_length=500)


class KBSessionCompleteResponse(BaseModel):
    """Response after completing a session and creating the KB entry."""

    session: dict[str, object]
    """Serialized KBCreationSession after completion."""

    entry_id: str
    """UUID of the newly created KB entry."""
