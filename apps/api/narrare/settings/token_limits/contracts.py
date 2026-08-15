"""Token limits service contracts.

Defines the resolved token-limit domain model (TokenLimitOverrides) and
the code-default constants. The runtime-checkable repository/service
Protocols live in protocols.py (RULE-04 split, C5 Task 2a).
Contracts MUST exist before implementation (RULE-03).

Three-layer resolution: User-DB → Project-DB → Operator-Env → Code-Defaults.
"""

from __future__ import annotations

from dataclasses import dataclass

from narrare_core.context.budget import (
    DEFAULT_SERIES_HISTORY_BUDGET,
    DEFAULT_TOTAL_BUDGET,
)
from narrare_core.llm.token_profiles import (
    TokenLimitProfile,
    resolve_output_limit_for_profile,
)

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
    context_total_budget: int = DEFAULT_TOTAL_BUDGET
    """Total input-context token budget for writing AND analysis
    (ADR-082 Decisions 1/5 — one knob). Ceiling, not a consumption
    mandate; capped against the model's context window at runtime by the
    ContextBudgetResolver (``min(configured, window - reserve)``; the
    resolver never scales up — design doc D5). Default single-sourced
    from Core (DEFAULT_TOKEN_PROFILE precedent).
    """
    series_history_budget: int = DEFAULT_SERIES_HISTORY_BUDGET
    """Series-history block ceiling WITHIN the total (ADR-082 Decisions
    1/3 — guarded carve-out, not additive). Effective value =
    ``min(configured, 50% x effective_total)`` when series history is in
    scope.
    """

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
