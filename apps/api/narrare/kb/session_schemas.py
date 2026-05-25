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
