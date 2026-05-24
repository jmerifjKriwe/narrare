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
#   "retry_max_attempts": 3,
#   "retry_base_delay": 1.0
# }


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
