"""ADR-061 P2 — aggregation prohibition checker (one setting per row).

Single responsibility (RULE-06): reject matrix entries that aggregate multiple
distinct settings under one ``setting_id``. This is the structural rule that
makes RULE-18b enforceable *per setting* rather than per aggregate row.

RULE-07: imports no application runtime modules; operates on parsed
:class:`MatrixEntry` values only.

ADR: docs/architecture/decisions/ADR-061-matrix-effect-integrity-hardening.md
"""

from __future__ import annotations

import re

from governance._matrix_types import MatrixEntry, Violation

__all__ = ["validate_aggregation"]

# ---------------------------------------------------------------------------
# Aggregate-name detection (CONSERVATIVE, high-precision)
# ---------------------------------------------------------------------------
#
# The detection mechanism is intentionally narrow to avoid false positives
# during the blocking phase (the matrix prose legitimately enumerates many
# related concepts). Two complementary, high-precision signals are used:
#
# 1. ``setting_id`` cascade/joiner name analysis — the historical ADR-060
#    signature (``*_cascade``) plus the mid-name joiner ``*_retry_*`` where a
#    retry token sits BETWEEN two distinct concerns (``idle_retry_timeout``).
#    A trailing ``_retry`` (``llm_transport_retry``) is a single concern and
#    passes.
# 2. Opt-in explicit ``settings:`` declaration — when an author declares the
#    covered settings explicitly, ``len > 1`` without a ``composite_rationale``
#    is rejected. This is the preferred high-precision path for future rows.
#
# A noisy prose token-scan over ``source``/``runtime_consumer``/
# ``effect_semantics`` was evaluated and *rejected* for the blocking phase:
# entries like ``operator_default_governance`` legitimately enumerate many
# distinct named constants while remaining a single governance unit, so a
# prose scan would generate false positives the ADR explicitly warns against.
# The explicit ``settings:`` declaration is the structured replacement.

#: ``*_cascade`` and ``*_cascade_*`` — the canonical aggregate signature.
_CASCADE_RE = re.compile(r"_cascade($|_)")

#: Mid-name ``*_retry_*`` joiner — retry BETWEEN two distinct concerns.
#: A trailing ``_retry`` (single concern) does NOT match.
_MID_RETRY_RE = re.compile(r"^[a-z][a-z0-9]*_retry_[a-z0-9_]+")


def _is_aggregate_name(setting_id: str) -> bool:
    """Return True for cascade/joiner setting_id names."""
    return bool(_CASCADE_RE.search(setting_id) or _MID_RETRY_RE.match(setting_id))


def _is_composite_approved(entry: MatrixEntry, allowlist: frozenset[str]) -> bool:
    """A composite is governed only when BOTH gates pass: allowlist AND rationale.

    Requiring both prevents a silent waiver: the allowlist records Architecture
    approval, and ``composite_rationale`` documents the justification at the row
    that actually carries the aggregate name.
    """
    return entry.setting_id in allowlist and bool(
        entry.composite_rationale and entry.composite_rationale.strip()
    )


def validate_aggregation(
    entries: list[MatrixEntry],
    composite_allowlist: frozenset[str],
) -> tuple[Violation, ...]:
    """Reject entries that aggregate multiple distinct settings.

    Args:
        entries: parsed matrix entries.
        composite_allowlist: Architecture-approved composite setting_ids that
            also require a ``composite_rationale`` on the row to be permitted.

    Returns:
        Violations for every rejected aggregate row.
    """
    violations: list[Violation] = []
    for entry in entries:
        sid = entry.setting_id
        if not sid:
            continue

        if _is_aggregate_name(sid) and not _is_composite_approved(entry, composite_allowlist):
            violations.append(
                Violation(
                    rule="aggregated_setting_id",
                    setting_id=sid,
                    message=(
                        "setting_id aggregates multiple distinct settings "
                        "(cascade/joiner name). RULE-18b is enforceable per "
                        "setting only: split into one row per setting, or "
                        "obtain Architecture approval (composite_allowlist + "
                        "composite_rationale)."
                    ),
                )
            )

        violations.extend(_check_settings_declaration(entry, composite_allowlist))
    return tuple(violations)


def _check_settings_declaration(
    entry: MatrixEntry,
    allowlist: frozenset[str],
) -> list[Violation]:
    """Validate the explicit ``settings:`` declaration when present."""
    if not entry.settings:
        return []

    distinct = tuple(dict.fromkeys(entry.settings))  # preserve order, dedupe
    if len(distinct) > 1:
        if _is_composite_approved(entry, allowlist):
            return []
        return [
            Violation(
                rule="declared_multi_setting",
                setting_id=entry.setting_id,
                message=(
                    f"settings: declares {len(distinct)} distinct settings "
                    f"({', '.join(distinct)}) under one row without an approved "
                    "composite_rationale. Split into one row per setting."
                ),
            )
        ]

    # Exactly one declared setting (len > 1 handled above; empty handled at top).
    if distinct:
        declared = distinct[0]
        if declared != entry.setting_id:
            return [
                Violation(
                    rule="settings_mismatch",
                    setting_id=entry.setting_id,
                    message=(
                        f"settings: declares '{declared}' which does not match "
                        f"setting_id '{entry.setting_id}'."
                    ),
                )
            ]
    return []
