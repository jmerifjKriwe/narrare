"""Enumerations for the AI invocation adoption contract.

Status types, audit lifecycle states, and requirement levels used across
the invocation pipeline. Extracted from models.py per RULE-04.

See: ADR-038, INFRA-013.
"""

from __future__ import annotations

from enum import StrEnum

# ---------------------------------------------------------------------------
# Evidence statuses
# ---------------------------------------------------------------------------


class PreferenceStatus(StrEnum):
    """Delivery status of user preferences for an invocation."""

    PROVIDED = "provided"
    MANUAL = "manual"
    NOT_APPLICABLE = "not_applicable"
    MISSING = "missing"


class KBSuggestedStatus(StrEnum):
    """Delivery status of KB-suggested context for an invocation."""

    PROVIDED = "provided"
    BUDGET_REJECTED = "budget_rejected"
    NOT_APPLICABLE = "not_applicable"
    MISSING = "missing"


# ---------------------------------------------------------------------------
# Audit lifecycle
# ---------------------------------------------------------------------------


class AuditState(StrEnum):
    """Audit lifecycle state for adoption findings.

    See ADR-038 § Audit Lifecycle States for transition criteria.
    """

    IDENTIFIED = "identified"
    SPECIFIED = "specified"
    STATIC_VERIFIED = "static_verified"
    RUNTIME_VERIFIED = "runtime_verified"
    ADOPTED = "adopted"
    RATCHETED_DEBT = "ratcheted_debt"
    BLOCKED = "blocked"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class ValidationStatus(StrEnum):
    """Outcome of a validation check."""

    # Bandit B105 false positive: validation status enum value, not a secret.
    PASS = "pass"  # nosec B105
    FAIL = "fail"


# ---------------------------------------------------------------------------
# Adoption policy requirements
# ---------------------------------------------------------------------------


class PreferenceRequirement(StrEnum):
    """Requirement level for preference delivery in an adoption policy."""

    REQUIRED = "required"
    MANUAL = "manual"
    NOT_APPLICABLE = "not_applicable"


class KBSuggestedRequirement(StrEnum):
    """Requirement level for KB-suggested context in an adoption policy."""

    PROVIDED = "provided"
    BUDGET_REJECTED = "budget_rejected"
    NOT_APPLICABLE = "not_applicable"
