"""CR-AUFG-07-19 — Prompt History Pydantic schemas.

Split out of ``schemas.py`` per RULE-04 (file-size limit).  History is
DB-backed (``prompt_revisions`` table); the active override remains a FILE
(cascade source of truth).  ``is_active`` is DERIVED at read time by hashing
the current active override file — it is never persisted.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — Pydantic needs datetime at runtime for validation
from enum import StrEnum
from uuid import UUID  # noqa: TC003 — Pydantic needs UUID at runtime for validation

from pydantic import BaseModel, ConfigDict


class PromptHistoryScope(StrEnum):
    """Override scope for a prompt revision.

    For CR-AUFG-07-19 scope is resolved deterministically to ``PROJECT``
    (explicit user-vs-project override switching is deferred).  The column
    and enum exist for forward-compatibility.
    """

    PROJECT = "project"
    USER = "user"


class PromptRevisionResponse(BaseModel):
    """A single recorded prompt override revision.

    ``is_active`` is derived: it is ``True`` when this revision's
    ``content_hash`` equals the sha256 of the current active override file
    (resolved at read time, never persisted).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    prompt_id: str
    scope: PromptHistoryScope
    content: str
    content_hash: str
    actor_id: UUID | None = None
    source: str
    change_reason: str | None = None
    restored_from_id: UUID | None = None
    created_at: datetime
    is_active: bool = False


class PromptHistoryListResponse(BaseModel):
    """Paginated list of recorded revisions for a prompt + scope."""

    model_config = ConfigDict(from_attributes=True)

    prompt_id: str
    scope: PromptHistoryScope
    total: int
    limit: int
    offset: int
    revisions: list[PromptRevisionResponse]


class PromptRevisionCompareResponse(BaseModel):
    """Side-by-side content for comparing two revisions (or vs active)."""

    model_config = ConfigDict(from_attributes=True)

    prompt_id: str
    from_id: str
    to_id: str
    from_source: str
    to_source: str
    from_content: str
    to_content: str


class PromptRevisionRestoredResponse(BaseModel):
    """Result of an append-only restore.

    ``restored_revision`` is the NEW revision recorded for the restore action
    (``source="restore"``, ``restored_from_id`` → the original revision).
    ``active_content`` is the content now written to the active override file.
    """

    model_config = ConfigDict(from_attributes=True)

    prompt_id: str
    restored_revision: PromptRevisionResponse
    active_content: str
    previous_active_hash: str | None = None


class PromptHistoryClearedResponse(BaseModel):
    """Result of clearing history.  The active override file is untouched."""

    model_config = ConfigDict(from_attributes=True)

    prompt_id: str
    scope: PromptHistoryScope
    deleted_count: int
