"""Token limits service contracts.

Defines Protocol classes for the token limits module.
Contracts MUST exist before implementation (RULE-03).

Three-layer resolution: User-DB → Project-DB → Operator-Env → Code-Defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from narrare_core.llm.token_profiles import (
    TokenLimitProfile,
    resolve_output_limit_for_profile,
)

if TYPE_CHECKING:
    from narrare.settings.token_limits.models import ProjectTokenLimits, UserTokenLimits

#: The default resolved token profile (CR-08 P1). Derived from Core so the
#: backend default cannot drift from the authoritative vocabulary.
DEFAULT_TOKEN_PROFILE: str = TokenLimitProfile.BALANCED.value


# ---------------------------------------------------------------------------
# Domain model — fully resolved token limit configuration
# ---------------------------------------------------------------------------

#: The code-default per-tier budget distribution (the writing base).
#:
#: This is the single source of truth for the default distribution.  The
#: API response schema and any normalisation reference this constant so the
#: default cannot drift between layers.  Note that the *resolved*
#: :attr:`TokenLimitOverrides.tier_percentages` is ``None`` (not this dict)
#: when the user has not configured overrides — ``None`` is the sentinel that
#: tells ``WritingContextAssembler`` to keep mode-specific allocations
#: (extend / rewrite / first-chapter).  See FIND-012 / CR-AUFG-08-02.
DEFAULT_TIER_PERCENTAGES: dict[str, float] = {
    "immediate": 0.30,
    "recent": 0.20,
    "kb_referenced": 0.25,
    "kb_suggested": 0.15,
    "pinned": 0.10,
}


@dataclass(frozen=True, slots=True)
class TokenLimitOverrides:
    """Fully resolved token limit configuration (all layers merged).

    Represents the effective token limits after merging user → project →
    env → code defaults. Each field has a sensible default so callers
    always get a complete configuration.
    """

    output_limit: int = 4096
    """Raw requested maximum output tokens for LLM calls.

    This is the *requested* limit. The :attr:`effective_output_limit`
    property applies the CR-08 P1 profile semantics: preset profiles use
    their fixed preset limit; ``custom`` (and explicit-output-limit-without-
    profile) use this raw value.
    """
    token_profile: str = DEFAULT_TOKEN_PROFILE
    """Resolved token profile name (one of Core's public values).

    After resolution this holds the *resolved* profile: legacy
    ``conservative`` is normalised to ``balanced`` (CR-08 P1 D2), and an
    explicit ``output_limit`` override without a profile resolves to
    ``custom`` (CR-08 P1 D3). Never ``conservative``.
    """
    tier_percentages: dict[str, float] | None = None
    """Per-tier token-budget distribution override (must sum to 1.0).

    ``None`` (the default) means *not configured*: no user/project override
    supplied tier percentages, so the consumer should fall back to the
    code-default behaviour.  This is deliberately distinct from
    :data:`DEFAULT_TIER_PERCENTAGES` because core's
    ``WritingContextAssembler(tier_overrides=None)`` preserves mode-specific
    allocations (extend / rewrite / first-chapter), whereas passing the full
    default dict would clobber them.  The API boundary normalises ``None``
    back to :data:`DEFAULT_TIER_PERCENTAGES` for the frontend (FIND-012).
    """
    ws_timeout: int = 1800
    """WebSocket idle timeout in seconds."""
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

    @property
    def effective_output_limit(self) -> int:
        """Effective output tokens after applying CR-08 P1 profile semantics.

        Preset profiles resolve to their fixed preset limit; ``custom``
        resolves to the raw :attr:`output_limit`. Delegates to Core's
        :func:`~narrare_core.llm.token_profiles.resolve_output_limit_for_profile`
        so the requested-vs-effective distinction is computable at the
        resolved-view boundary without re-implementing Core policy.
        """
        return resolve_output_limit_for_profile(
            self.token_profile, raw_output_limit=self.output_limit
        )


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
