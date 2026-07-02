"""ADR-061 P2 — aggregation prohibition checker tests (one setting per row).

RULE-07: the validator imports no application runtime modules; these tests
exercise it with in-memory entries plus one read of the real manifest.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from governance._matrix_aggregation import validate_aggregation  # noqa: E402
from governance._matrix_types import MatrixEntry, load_matrix, parse_matrix  # noqa: E402

_MATRIX_PATH = (
    _PROJECT_ROOT / "docs" / "architecture" / "governance" / "configuration-adoption-matrix.yaml"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry(
    setting_id: str = "s1",
    *,
    settings: tuple[str, ...] = (),
    composite_rationale: str | None = None,
    classification: str = "operator",
    lifecycle: str = "adopted",
) -> MatrixEntry:
    """Build a minimal valid entry for aggregation testing."""
    return MatrixEntry(
        setting_id=setting_id,
        classification=classification,
        lifecycle=lifecycle,
        source="src",
        resolver_service="R.resolve",
        effect_semantics="changes X",
        fallback_policy="warn",
        runtime_consumer="Consumer.apply",
        enforcement_evidence=("tests/unit/x.py::t",),
        settings=settings,
        composite_rationale=composite_rationale,
    )


def _rules(violations: tuple[object, ...]) -> set[str]:
    return {v.rule for v in violations}  # type: ignore[attr-defined]


def _ids(violations: tuple[object, ...]) -> set[str]:
    return {v.setting_id for v in violations}  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Happy path — single setting per row
# ---------------------------------------------------------------------------


def test_clean_single_setting_rows_pass() -> None:
    """Ordinary single-setting rows (no cascade/joiner name, no settings list) pass."""
    entries = [_entry("output_limit"), _entry("ws_idle_timeout")]
    violations = validate_aggregation(entries, frozenset())

    assert violations == ()


def test_empty_matrix_passes() -> None:
    assert validate_aggregation([], frozenset()) == ()


# ---------------------------------------------------------------------------
# setting_id cascade / joiner name analysis (the ADR-060 class)
# ---------------------------------------------------------------------------


def test_cascade_setting_id_rejected() -> None:
    """A ``*_cascade`` setting_id aggregates multiple concerns (ADR-060 instance)."""
    entries = [_entry("websocket_idle_retry_cascade")]
    violations = validate_aggregation(entries, frozenset())

    assert "aggregated_setting_id" in _rules(violations)
    assert "websocket_idle_retry_cascade" in _ids(violations)


def test_mid_retry_joiner_rejected() -> None:
    """A mid-name ``*_retry_*`` joiner signals two unrelated concerns.

    ``llm_transport_retry`` (retry at the END) is a single concern and MUST pass;
    ``idle_retry_timeout`` (retry in the MIDDLE joining two concerns) is rejected.
    """
    bad = [_entry("idle_retry_timeout")]
    assert "aggregated_setting_id" in _rules(validate_aggregation(bad, frozenset()))

    good = [_entry("llm_transport_retry")]
    assert validate_aggregation(good, frozenset()) == ()


def test_suffix_only_retry_passes() -> None:
    """A single concern ending in ``_retry`` is not an aggregate."""
    entries = [_entry("llm_transport_retry")]
    assert validate_aggregation(entries, frozenset()) == ()


# ---------------------------------------------------------------------------
# Explicit settings: declaration (opt-in high-precision path)
# ---------------------------------------------------------------------------


def test_declared_multiple_settings_without_rationale_rejected() -> None:
    """An explicit ``settings: [a, b]`` declaration without rationale is rejected."""
    entries = [_entry("retry_cascade", settings=("retry_max_attempts", "retry_base_delay"))]
    violations = validate_aggregation(entries, frozenset())

    assert "declared_multi_setting" in _rules(violations)


def test_declared_multiple_settings_with_rationale_passes() -> None:
    """A legitimately inseparable compound with composite_rationale is governed-allowed."""
    entries = [
        _entry(
            "atomic_pair",
            settings=("a_value", "b_value"),
            composite_rationale="A and B are set atomically by the same SDK call (ADR-XX).",
        )
    ]
    violations = validate_aggregation(entries, frozenset({"atomic_pair"}))

    assert violations == ()


def test_single_declared_setting_mismatch_rejected() -> None:
    """If ``settings:`` declares one id it must equal the row setting_id."""
    entries = [_entry("foo", settings=("bar",))]
    violations = validate_aggregation(entries, frozenset())

    assert "settings_mismatch" in _rules(violations)


def test_single_declared_setting_matching_passes() -> None:
    entries = [_entry("foo", settings=("foo",))]
    assert validate_aggregation(entries, frozenset()) == ()


# ---------------------------------------------------------------------------
# Allowlist + composite_rationale escape hatch
# ---------------------------------------------------------------------------


def test_cascade_in_allowlist_without_rationale_still_rejected() -> None:
    """Allowlist alone is not enough — the entry must ALSO carry composite_rationale.

    Both gates (allowlist AND rationale) must pass, so an approved composite is
    explicitly justified at the row, not silently waved through.
    """
    entries = [_entry("websocket_idle_retry_cascade")]  # no composite_rationale
    violations = validate_aggregation(entries, frozenset({"websocket_idle_retry_cascade"}))

    assert "aggregated_setting_id" in _rules(violations)


def test_cascade_with_rationale_but_not_in_allowlist_rejected() -> None:
    """composite_rationale without allowlist approval is not enough either."""
    entries = [_entry("websocket_idle_retry_cascade", composite_rationale="because")]
    violations = validate_aggregation(entries, frozenset())

    assert "aggregated_setting_id" in _rules(violations)


def test_cascade_with_allowlist_and_rationale_passes() -> None:
    entries = [
        _entry(
            "websocket_idle_retry_cascade",
            composite_rationale="Architecture-approved atomic compound (ADR-XX).",
        )
    ]
    violations = validate_aggregation(entries, frozenset({"websocket_idle_retry_cascade"}))

    assert violations == ()


# ---------------------------------------------------------------------------
# Integration — the real matrix manifest
# ---------------------------------------------------------------------------


def test_real_matrix_passes_aggregation_rule() -> None:
    """The committed matrix (post-ADR-060 split) has no aggregated setting_ids.

    This is the P2 DoD: the current 26-entry matrix PASSES the blocking rule.
    """
    data = load_matrix(_MATRIX_PATH)
    entries, _ = parse_matrix(data)

    violations = validate_aggregation(entries, frozenset())

    assert violations == (), (
        "matrix has aggregated setting_ids: "
        f"{[(v.rule, v.setting_id, v.message) for v in violations]}"
    )
