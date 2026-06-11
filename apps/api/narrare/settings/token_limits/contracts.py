"""Token limits service contracts.

Defines Protocol classes for the token limits module.
Contracts MUST exist before implementation (RULE-03).

Three-layer resolution: User-DB → Project-DB → Operator-Env → Code-Defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from narrare.settings.token_limits.models import ProjectTokenLimits, UserTokenLimits


# ---------------------------------------------------------------------------
# Domain model — fully resolved token limit configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TokenLimitOverrides:
    """Fully resolved token limit configuration (all layers merged).

    Represents the effective token limits after merging user → project →
    env → code defaults. Each field has a sensible default so callers
    always get a complete configuration.
    """

    output_limit: int = 4096
    """Maximum output tokens for LLM calls."""
    token_profile: str = "balanced"
    """Active token profile name (quick, balanced, long, custom)."""
    tier_percentages: dict[str, float] = field(
        default_factory=lambda: {
            "immediate": 0.30,
            "recent": 0.20,
            "kb_referenced": 0.25,
            "kb_suggested": 0.15,
            "pinned": 0.10,
        }
    )
    """Token budget distribution across context tiers (must sum to 1.0)."""
    ws_timeout: int = 1800
    """WebSocket idle timeout in seconds."""
    retry_max_attempts: int = 3
    """Maximum retry attempts for LLM calls."""
    retry_base_delay: float = 1.0
    """Base delay in seconds for retry backoff."""
    legacy_per_category_overrides: dict[str, object] | None = None
    """Temporary legacy field for SET-005 dual-write migration.
    Stores old-format per-category overrides during transition.
    Will be removed after migration is complete."""
    max_chapter_tokens: int = 2000
    """Maximum tokens per chapter preview in consistency checks."""
    max_kb_entries: int = 100
    """Maximum KB entries to include in consistency context."""
    max_selection_words: int = 2000
    """Maximum word count for co-author selection text (SET-005 cascade)."""


# ---------------------------------------------------------------------------
# Repository Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class TokenLimitsRepositoryProtocol(Protocol):
    """Repository for token limit overrides storage."""

    async def get_user_limits(self, user_id: str) -> UserTokenLimits:
        """Get user-level token limit overrides. Auto-creates if missing."""
        ...

    async def update_user_limits(
        self, user_id: str, overrides: dict[str, object]
    ) -> UserTokenLimits:
        """Update user-level token limit overrides."""
        ...

    async def get_project_limits(self, project_id: str) -> ProjectTokenLimits:
        """Get project-level token limit overrides. Auto-creates if missing."""
        ...

    async def update_project_limits(
        self, project_id: str, overrides: dict[str, object]
    ) -> ProjectTokenLimits:
        """Update project-level token limit overrides."""
        ...


# ---------------------------------------------------------------------------
# Service Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class TokenLimitsServiceProtocol(Protocol):
    """Service for resolving token limits across layers."""

    async def get_resolved_limits(
        self,
        user_id: str,
        project_id: str | None = None,
    ) -> TokenLimitOverrides:
        """Resolve token limits: user → project → env → code defaults.

        Merges settings from all layers with user overrides having the
        highest priority and code defaults the lowest.
        """
        ...

    async def update_user_limits(
        self,
        user_id: str,
        overrides: dict[str, object],
    ) -> None:
        """Update user-level token limit overrides.

        Args:
            user_id: The user's ID.
            overrides: Dict of fields to update (output_limit, token_profile,
                tier_percentages, ws_timeout, retry_max_attempts,
                retry_base_delay).
        """
        ...

    async def update_project_limits(
        self,
        project_id: str,
        overrides: dict[str, object],
    ) -> None:
        """Update project-level token limit overrides.

        Args:
            project_id: The project's ID.
            overrides: Same structure as update_user_limits.
        """
        ...
