"""Settings SQLAlchemy models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from narrare._app.database import Base


class UserSettings(Base):
    __tablename__ = "user_settings"
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    ui_language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    theme: Mapped[str] = mapped_column(String(20), default="system", nullable=False)
    custom_tones: Mapped[list[object]] = mapped_column(
        JSONB, default=list, server_default="[]", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ProjectSettings(Base):
    __tablename__ = "project_settings"
    novel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("novels.id", ondelete="CASCADE"), primary_key=True
    )
    autosave_interval: Mapped[int] = mapped_column(default=30, nullable=False)
    default_language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    ai_provider: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    ai_model: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    # JSON blob for per-task model overrides (legacy)
    model_overrides: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    # AI override columns (added in migration 0004)
    category_overrides: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    intent_overrides: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    token_limit_overrides: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    token_limit_profile: Mapped[str] = mapped_column(
        String(20), default="balanced", server_default="balanced", nullable=False
    )
    # ADR-069 Decision 2: per-project adaptive settings (enabled flag +
    # weights). JSONB mirrors the established category_overrides /
    # intent_overrides / token_limit_overrides pattern. NULL = no settings
    # row yet → AdaptiveContextProviderImpl returns defaults (graceful
    # degradation, Phase 2 contract preserved).
    adaptive_settings: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class UserProvider(Base):
    """A user's registered AI provider (e.g. Anthropic, OpenRouter)."""

    __tablename__ = "user_providers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "provider_name", name="uq_user_providers_user_name"),
    )


class UserAiSettings(Base):
    """User-level AI configuration: default model, overrides, token limits."""

    __tablename__ = "user_ai_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    default_provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_providers.id", ondelete="SET NULL"),
        nullable=True,
    )
    default_model: Mapped[str] = mapped_column(
        String(200), default="", server_default="", nullable=False
    )
    category_overrides: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    intent_overrides: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    token_limit_profile: Mapped[str] = mapped_column(
        String(20), default="balanced", server_default="balanced", nullable=False
    )
    token_limit_overrides: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    embedding_provider: Mapped[str] = mapped_column(
        String(20), default="auto", server_default="auto", nullable=False
    )
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
