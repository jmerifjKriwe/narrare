"""Token limit override models.

Separate tables for user and project token limit overrides.
Each stores overrides as a single JSONB column for maximum flexibility.
"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from narrare._app.database import Base

# JSONB overrides structure (same for both tables):
# {
#   "output_limit": 4096,
#   "token_profile": "balanced",
#   "tier_percentages": {"immediate": 0.30, ...},
#   "ws_timeout": 1800,
# }
#
# ADR-060: the legacy ``retry_max_attempts`` / ``retry_base_delay`` keys are no
# longer part of the override vocabulary. There are no dedicated SQLAlchemy
# columns for them (overrides live in the single JSONB ``overrides`` dict);
# any such keys persisted in existing rows are silently ignored by the resolver
# (unknown-key drop in ``TokenLimitsService._merge_overrides``). Transport retry
# is now governed at the provider layer — no destructive migration is required.


class UserTokenLimits(Base):
    """User-level token limit overrides.

    Stores per-user overrides that take highest priority in the
    three-layer resolution cascade (user → project → env → code defaults).
    """

    __tablename__ = "user_token_limits"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    """User ID (matches auth system)."""

    overrides: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict, nullable=False)
    """JSONB dict of token limit overrides (see structure above)."""


class ProjectTokenLimits(Base):
    """Project-level token limit overrides.

    Stores per-project overrides that take second priority in the
    resolution cascade (after user, before env/code defaults).
    """

    __tablename__ = "project_token_limits"

    project_id: Mapped[str] = mapped_column(String, primary_key=True)
    """Project/novel ID."""

    overrides: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict, nullable=False)
    """JSONB dict of token limit overrides (same structure as UserTokenLimits)."""
