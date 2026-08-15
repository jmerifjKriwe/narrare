"""Token limits service Protocols.

Runtime-checkable repository/service contracts for the token limits
module, split from contracts.py (RULE-04, C5 Task 2a — plan Deviations
#8). The resolved domain model (TokenLimitOverrides) and the code-default
constants remain in contracts.py. Contracts MUST exist before
implementation (RULE-03).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from narrare.settings.token_limits.contracts import TokenLimitOverrides
    from narrare.settings.token_limits.models import ProjectTokenLimits, UserTokenLimits


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
                tier_percentages, ws_timeout).
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
