"""SQLAlchemy models for template overrides storage.

Provides the ``KBTemplate`` model that stores user, project, and global
template overrides in the database.  Supports the cascade resolution
pattern: user → project → bundled defaults.  Templates are keyed by
``(entity_type, scope, scope_id)`` — no language dimension.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, Enum, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from narrare._app.database import Base


def _template_scope_values(members: type[TemplateScope]) -> list[str]:
    """Extract values from TemplateScope members for SQLAlchemy Enum."""
    return [m.value for m in members]


class TemplateScope(StrEnum):
    """Scope of a template override — determines cascade priority."""

    USER = "user"
    PROJECT = "project"
    GLOBAL = "global"


class KBTemplate(Base):
    """Stored template override — user/project/global level.

    Each row stores a full template override (YAML frontmatter + body markdown)
    for a specific entity type at a given scope level.  The cascade resolver
    checks higher-priority scopes (user > project > global) before falling
    back to bundled defaults.
    """

    __tablename__ = "kb_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope: Mapped[TemplateScope] = mapped_column(
        Enum(TemplateScope, values_callable=_template_scope_values),
        nullable=False,
    )
    scope_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    # The full template content (YAML frontmatter + body markdown)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    based_on_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    schema_version: Mapped[str] = mapped_column(
        String(20),
        default="2.0.0",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "scope",
            "scope_id",
            name="uq_kb_templates_unique",
        ),
        CheckConstraint(
            "entity_type IN ('character', 'concept', 'faction', 'location', "
            "'object', 'setting', 'system', 'timeline')",
            name="ck_kb_templates_entity_type",
        ),
        Index("ix_kb_templates_scope", "scope", "scope_id"),
    )

    def __repr__(self) -> str:
        return f"KBTemplate(id={self.id}, type={self.entity_type!r}, scope={self.scope.value})"
