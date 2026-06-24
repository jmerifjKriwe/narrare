"""CR-AUFG-07-19 — ``prompt_revisions`` ORM model.

History is DB-backed and append-only.  The active override remains a FILE
(cascade source of truth, owned by core ``PromptManagementService``); this
table is a secondary, non-authoritative record keyed by the logical identity
``(prompt_id, scope)``.  ``is_active`` is therefore DERIVED at read time
(hash the current file vs stored hashes), never persisted.

RULE-08: core stays infra-free, so this model lives in the backend layer and
is not imported by ``packages/core``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from narrare._app.database import Base


class PromptRevision(Base):
    """Append-only record of a single prompt override revision.

    Rows are written by the backend ``PromptHistoryApiService`` immediately
    after the core service writes the active override FILE.  Recording is
    best-effort: a DB failure is logged but does not roll back the file write
    (the file is authoritative).

    ``scope`` is forward-compatible: CR-AUFG-07-19 resolves it to ``"project"``
    deterministically.  ``actor_id`` is nullable so system-initiated restores
    and user deletions (FK SET NULL) do not cascade-delete history.
    """

    __tablename__ = "prompt_revisions"
    __table_args__ = (
        # Composite index supporting the history list query
        # (WHERE prompt_id=? AND scope=? ORDER BY created_at DESC).
        # ``text("created_at DESC")`` is the documented SQLAlchemy way to
        # declare a descending index at class-body scope, where the
        # ``created_at`` Mapped attribute is not yet bound.
        Index(
            "ix_prompt_revisions_prompt_scope_created",
            "prompt_id",
            "scope",
            text("created_at DESC"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    prompt_id: Mapped[str] = mapped_column(String(200), nullable=False)
    scope: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default="project",
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    change_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    restored_from_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompt_revisions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"PromptRevision(id={self.id}, prompt_id={self.prompt_id!r}, "
            f"scope={self.scope!r}, source={self.source!r})"
        )
