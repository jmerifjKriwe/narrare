"""Output budget value objects — pure Pydantic models.

Contains :class:`OutputBudget` (validated token limit) and
:class:`OutputBudgetDecision` (budget with provenance metadata).
Extracted into a separate module to avoid circular imports between
``__init__.py`` and ``resolver.py``.

This module has ZERO internal package imports — only Pydantic.

See: ADR-038, INFRA-013, CONSTRAINTS.md RULE-04.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OutputBudget(BaseModel):
    """Validated value object for output token budget.

    Represents a resolved output token limit with its source profile.
    Tokens must be positive.

    Args:
        max_tokens: Maximum output tokens allowed (must be > 0).
        profile: Named profile, e.g. ``'quick'``, ``'balanced'``, ``'long_texts'``.
    """

    model_config = ConfigDict(frozen=True)

    max_tokens: int = Field(gt=0, description="Maximum output tokens allowed.")
    profile: str | None = Field(
        default=None,
        description="Named profile, e.g. 'quick', 'balanced', 'long_texts'.",
    )

    @model_validator(mode="after")
    def _validate_profile(self) -> OutputBudget:
        """Ensure profile is None or non-empty."""
        if self.profile is not None and len(self.profile) == 0:
            raise ValueError("profile must be non-empty if provided")
        return self


class OutputBudgetDecision(BaseModel):
    """Resolved output budget with provenance metadata.

    Records the final output budget, where it came from, and why it was
    selected. Used as evidence for adoption claims.

    Args:
        budget: The resolved output budget.
        source: Origin of the decision (e.g. ``'intent_profile'``, ``'default_config'``).
        reason: Human-readable explanation of the decision.
    """

    model_config = ConfigDict(frozen=True)

    budget: OutputBudget
    source: str = Field(
        min_length=1,
        description="Origin: 'intent_profile', 'default_config', etc.",
    )
    reason: str = Field(
        min_length=1,
        description="Human-readable explanation of the decision.",
    )
