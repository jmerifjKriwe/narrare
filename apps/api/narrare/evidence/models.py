"""SQLAlchemy ORM model for the invocation_evidence table.

Maps ``FeatureInvocationEvidence`` domain values to PostgreSQL columns.
Privacy-safe: no prompt text, user prose, or eval case content (ADR-038).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from narrare._app.database import Base


class InvocationEvidenceModel(Base):
    """ORM model for the invocation_evidence table.

    Each row captures adoption evidence for a single AI invocation:
    feature metadata, enrichment/validation outcomes, budget resolution,
    and audit state. Appends only — no UPDATE path.

    Privacy guarantee: Columns are identifiers, statuses, booleans,
    and structured metadata only. No raw prompt text or user prose.
    """

    __tablename__ = "invocation_evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    feature_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    intent: Mapped[str] = mapped_column(String(50), nullable=False)
    mode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    language: Mapped[str] = mapped_column(String(5), nullable=False, server_default="en")
    streaming: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=func.false())
    preference_status: Mapped[str] = mapped_column(String(20), nullable=False)
    kb_suggested_status: Mapped[str] = mapped_column(String(20), nullable=False)
    voice_profile_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    output_budget_profile: Mapped[str | None] = mapped_column(String(50), nullable=True)
    final_prompt_validated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    validation_errors: Mapped[list[str] | None] = mapped_column(JSONB, nullable=False, default=list)
    audit_state: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    prompt_route: Mapped[str] = mapped_column(String(200), nullable=False)

    # ADR-045 §2: correlation fields (nullable for backward compatibility).
    invocation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    # ADR-070: project-scope column for per-novel snapshot queries.
    # NULL on pre-0035 rows and when the invocation context had no project.
    novel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    prepared_context_fingerprint: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    prompt_fingerprint: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    budget_decision_fingerprint: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    model_call_marker: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    manual_injection_exception: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    # ADR-069 D11: adaptive context provenance + resolved weights.
    # NULL on pre-ADR-069 rows and when adaptive context is disabled.
    adaptive_source_summary: Mapped[dict[str, str] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    adaptive_weights: Mapped[dict[str, float] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"InvocationEvidenceModel(id={self.id}, feature_id={self.feature_id!r}, "
            f"intent={self.intent!r}, audit_state={self.audit_state!r})"
        )
