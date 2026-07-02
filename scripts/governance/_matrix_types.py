"""Type definitions and parsing for the Configuration Adoption Matrix.

Extracted from :mod:`configuration_matrix` to keep that module under RULE-04
(300 lines). This module owns the *data layer*: controlled vocabularies
(ADR-051 enums), frozen dataclasses, and YAML loading/parsing. It performs
NO validation — that responsibility belongs to
:mod:`configuration_matrix`.

RULE-07: reads only the matrix manifest (YAML) via ``yaml.safe_load`` and
imports NO application runtime modules.

ADR: docs/architecture/decisions/ADR-051-configuration-effect-adoption-contract.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, cast

import yaml

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "CLASSIFICATIONS",
    "LIFECYCLE_STATES",
    "Classification",
    "Lifecycle",
    "MatrixEntry",
    "MatrixReport",
    "MatrixStatus",
    "Violation",
    "load_matrix",
    "parse_matrix",
]

# ---------------------------------------------------------------------------
# Controlled vocabularies (ADR-051)
# ---------------------------------------------------------------------------

#: ADR-051 lifecycle states — the *adoption state* of a value.
LIFECYCLE_STATES: frozenset[str] = frozenset(
    {
        "adopted",
        "governed_default",
        "operator_default",
        "formal_finding",
        "covered_by_existing",
        "not_applicable",
    }
)

#: ADR-051 matrix-row classifications — the *kind/layer* of a setting.
#: ``user`` and ``project`` require a runtime_consumer + enforcement_evidence.
CLASSIFICATIONS: frozenset[str] = frozenset(
    {
        "user",
        "project",
        "operator",
        "runtime-derived",
        "governed_default",
        "test-only",
    }
)

#: Required fields on every matrix entry (ADR-051 Matrix Contract).
REQUIRED_FIELDS: tuple[str, ...] = (
    "setting_id",
    "classification",
    "lifecycle",
    "source",
    "resolver_service",
    "effect_semantics",
    "fallback_policy",
)


class Lifecycle(StrEnum):
    """ADR-051 lifecycle state of a configuration value."""

    ADOPTED = "adopted"
    GOVERNED_DEFAULT = "governed_default"
    OPERATOR_DEFAULT = "operator_default"
    FORMAL_FINDING = "formal_finding"
    COVERED_BY_EXISTING = "covered_by_existing"
    NOT_APPLICABLE = "not_applicable"


class Classification(StrEnum):
    """ADR-051 matrix-row classification of a setting's kind/layer."""

    USER = "user"
    PROJECT = "project"
    OPERATOR = "operator"
    RUNTIME_DERIVED = "runtime-derived"
    GOVERNED_DEFAULT = "governed_default"
    TEST_ONLY = "test-only"


class MatrixStatus(StrEnum):
    """Overall validation verdict for the matrix."""

    PASS = "PASS"  # nosec
    FAIL = "FAIL"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MatrixEntry:
    """A single parsed matrix entry."""

    setting_id: str
    classification: str
    lifecycle: str
    source: str
    resolver_service: str
    effect_semantics: str
    fallback_policy: str
    runtime_consumer: str | None = None
    enforcement_evidence: tuple[str, ...] = ()
    cross_layer_evidence: tuple[str, ...] = ()
    cr_task: str | None = None
    finding: str | None = None
    phase: str | None = None
    review_trigger: str | None = None
    rationale: str | None = None
    # ADR-061 P2 — aggregation prohibition. Optional declaration of the exact
    # setting(s) this row covers; when absent, ``setting_id`` IS the setting.
    settings: tuple[str, ...] = ()
    # ADR-061 P2 — opt-in rationale for a legitimately inseparable compound
    # ``setting_id``. Requires Architecture approval + allowlist entry. Absent
    # for every ordinary single-setting row.
    composite_rationale: str | None = None


@dataclass(frozen=True)
class Violation:
    """A single validation failure."""

    rule: str
    setting_id: str
    message: str


@dataclass(frozen=True)
class MatrixReport:
    """Aggregated validation report."""

    status: MatrixStatus
    total_entries: int
    expected_count: int
    violations: tuple[Violation, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        """True when the matrix validates cleanly."""
        return self.status == MatrixStatus.PASS


# ---------------------------------------------------------------------------
# Loading & parsing
# ---------------------------------------------------------------------------


def load_matrix(path: Path) -> dict[str, Any]:
    """Load and parse the matrix YAML manifest.

    Raises:
        FileNotFoundError: if *path* does not exist.
        yaml.YAMLError: if the document is not valid YAML.
    """
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        msg = f"Matrix root must be a mapping, got {type(data).__name__}"
        raise ValueError(msg)
    return cast("dict[str, Any]", data)


def parse_matrix(data: dict[str, Any]) -> tuple[list[MatrixEntry], list[str]]:
    """Parse a raw mapping into typed entries and the expected-id list.

    Structural keys (``expected_setting_ids``, ``entries``) are read here;
    per-entry field validation is deferred to the validator so a single
    report collects every violation.
    """
    expected_ids: list[str] = []
    raw_expected = data.get("expected_setting_ids", [])
    if isinstance(raw_expected, list):
        expected_ids = [str(item) for item in cast("list[object]", raw_expected)]

    entries: list[MatrixEntry] = []
    raw_entries = data.get("entries", [])
    if isinstance(raw_entries, list):
        for raw in cast("list[object]", raw_entries):
            if isinstance(raw, dict):
                entries.append(_parse_entry(cast("dict[str, Any]", raw)))
    return entries, expected_ids


def _parse_entry(raw: dict[str, Any]) -> MatrixEntry:
    """Coerce a raw entry mapping into a :class:`MatrixEntry`."""
    return MatrixEntry(
        setting_id=str(raw.get("setting_id", "")),
        classification=str(raw.get("classification", "")),
        lifecycle=str(raw.get("lifecycle", "")),
        source=str(raw.get("source", "")),
        resolver_service=str(raw.get("resolver_service", "")),
        effect_semantics=str(raw.get("effect_semantics", "")),
        fallback_policy=str(raw.get("fallback_policy", "")),
        runtime_consumer=_opt_str(raw.get("runtime_consumer")),
        enforcement_evidence=_to_str_tuple(raw.get("enforcement_evidence")),
        cross_layer_evidence=_to_str_tuple(raw.get("cross_layer_evidence")),
        cr_task=_opt_str(raw.get("cr_task")),
        finding=_opt_str(raw.get("finding")),
        phase=_opt_str(raw.get("phase")),
        review_trigger=_opt_str(raw.get("review_trigger")),
        rationale=_opt_str(raw.get("rationale")),
        settings=_to_str_tuple(raw.get("settings")),
        composite_rationale=_opt_str(raw.get("composite_rationale")),
    )


def _opt_str(value: Any) -> str | None:
    """Return a stripped string or None for empty/None values."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_str_tuple(value: Any) -> tuple[str, ...]:
    """Coerce a list-or-scalar into a tuple of non-empty strings."""
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    if isinstance(value, list):
        items = cast("list[object]", value)
        return tuple(str(item).strip() for item in items if str(item).strip())
    if isinstance(value, tuple):
        items = cast("tuple[object, ...]", value)
        return tuple(str(item).strip() for item in items if str(item).strip())
    return ()
