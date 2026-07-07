"""ADR-061 P1 — per-setting effect-integrity checker tests (presence AND truth).

Closes RC1 (presence != truth): the ``runtime_consumer`` must name a REAL code
location, and the cited evidence must cover THIS setting, not a sibling.

BLOCKING since the AUFG-01-09 follow-up (2026-07-06): unproven entries
(consumer_only / gap / broken) fail the gate. These unit tests exercise the
verifier function directly and assert the classification of each entry
(VERIFIED / CONSUMER_ONLY / GAP / BROKEN).
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from governance._matrix_effect_integrity import (  # noqa: E402
    EffectEvidenceEntry,
    Verification,
    validate_effect_integrity,
)
from governance._matrix_types import MatrixEntry  # noqa: E402

_REPO_ROOT = _PROJECT_ROOT  # tests resolve real files under the repo


def _entry(
    setting_id: str,
    *,
    classification: str = "operator",
    lifecycle: str = "adopted",
) -> MatrixEntry:
    return MatrixEntry(
        setting_id=setting_id,
        classification=classification,
        lifecycle=lifecycle,
        source="src",
        resolver_service="R",
        effect_semantics="changes X",
        fallback_policy="warn",
        runtime_consumer="Consumer.apply",
        enforcement_evidence=("tests/unit/x.py::t",),
    )


def _ev(
    setting_id: str,
    *,
    consumer_file: str,
    consumer_symbol: str,
    test_file: tuple[str, ...],
    verification: Verification = Verification.MANIFEST,
) -> EffectEvidenceEntry:
    return EffectEvidenceEntry(
        setting_id=setting_id,
        verification=verification,
        consumer_file=consumer_file,
        consumer_symbol=consumer_symbol,
        test_file=test_file,
        notes="test",
    )


# Real repo files used to prove truth checks against the filesystem.
_REAL_CONSUMER = "scripts/governance/configuration_matrix.py"  # contains "validate_matrix"
_REAL_TEST = (
    "tests/unit/scripts/governance/test_configuration_matrix.py"  # contains "validate_matrix"
)


# ---------------------------------------------------------------------------
# In-scope predicate — only user/project/adopted entries are checked
# ---------------------------------------------------------------------------


def test_out_of_scope_entries_are_skipped() -> None:
    """operator/governed_default (not adopted) entries are not in P1 scope."""
    entries = [
        _entry("op_default", classification="operator", lifecycle="operator_default"),
        _entry("gov", classification="governed_default", lifecycle="governed_default"),
    ]
    report = validate_effect_integrity(entries, {}, _REPO_ROOT)

    assert report.total_in_scope == 0
    assert report.gaps == 0


# ---------------------------------------------------------------------------
# VERIFIED — manifest-fallback PASS (consumer real + test references setting)
# ---------------------------------------------------------------------------


def test_manifest_fallback_verified_pass() -> None:
    """A manifest entry whose consumer file + symbol + test all exist is VERIFIED."""
    entries = [_entry("configuration_adoption_matrix", lifecycle="adopted")]
    evidence = {
        "configuration_adoption_matrix": _ev(
            "configuration_adoption_matrix",
            consumer_file=_REAL_CONSUMER,
            consumer_symbol="validate_matrix",
            test_file=(_REAL_TEST,),
        )
    }
    report = validate_effect_integrity(entries, evidence, _REPO_ROOT)

    assert report.verified == 1
    assert report.gaps == 0
    assert report.broken == 0
    assert report.consumer_only == 0
    detail = report.details[0]
    assert detail.setting_id == "configuration_adoption_matrix"
    assert detail.verified is True


# ---------------------------------------------------------------------------
# Graph-grounded PASS — verification level recorded
# ---------------------------------------------------------------------------


def test_graph_verified_entry_records_graph_level() -> None:
    entries = [_entry("ws_idle_timeout", lifecycle="adopted")]
    evidence = {
        "ws_idle_timeout": _ev(
            "ws_idle_timeout",
            consumer_file="apps/api/narrare/writing/ws_handler.py",
            consumer_symbol="WritingSessionHandler",
            test_file=("tests/unit/api/writing/test_router_sessions_basic.py",),
            verification=Verification.GRAPH,
        )
    }
    report = validate_effect_integrity(entries, evidence, _REPO_ROOT)

    assert report.verified == 1
    assert report.details[0].verification == Verification.GRAPH


# ---------------------------------------------------------------------------
# GAP — no manifest entry (governed debt)
# ---------------------------------------------------------------------------


def test_in_scope_without_manifest_entry_is_gap() -> None:
    entries = [_entry("orphan_setting", classification="user", lifecycle="adopted")]
    report = validate_effect_integrity(entries, {}, _REPO_ROOT)

    assert report.gaps == 1
    assert report.verified == 0


# ---------------------------------------------------------------------------
# Sibling-evidence-only — consumer real but test does not cover THIS setting
# ---------------------------------------------------------------------------


def test_sibling_evidence_only_not_verified() -> None:
    """A test that exists but does NOT reference the setting/consumer is sibling-only.

    This is the ADR-060 class: ``websocket_idle_retry_cascade`` cited
    ``test_ws_handler.py`` while the retry settings never reached the handler.
    The entry falls to CONSUMER_ONLY (consumer is real, evidence is sibling).
    """
    # A real test file that does NOT mention "WritingSessionHandler" nor the setting.
    sibling_test = "tests/unit/api/writing/test_ws_turn_budget.py"
    entries = [_entry("ws_idle_timeout", lifecycle="adopted")]
    evidence = {
        "ws_idle_timeout": _ev(
            "ws_idle_timeout",
            consumer_file="apps/api/narrare/writing/ws_handler.py",
            consumer_symbol="WritingSessionHandler",
            test_file=(sibling_test,),
        )
    }
    report = validate_effect_integrity(entries, evidence, _REPO_ROOT)

    assert report.verified == 0
    assert report.consumer_only == 1
    detail = report.details[0]
    assert detail.verified is False
    assert "sibling" in detail.reason


# ---------------------------------------------------------------------------
# BROKEN — manifest cites a non-existent file / symbol (real defect)
# ---------------------------------------------------------------------------


def test_missing_consumer_file_is_broken() -> None:
    entries = [_entry("bogus", lifecycle="adopted")]
    evidence = {
        "bogus": _ev(
            "bogus",
            consumer_file="does/not/exist.py",
            consumer_symbol="Nope",
            test_file=(_REAL_TEST,),
        )
    }
    report = validate_effect_integrity(entries, evidence, _REPO_ROOT)

    assert report.broken == 1
    assert report.details[0].verified is False


def test_consumer_symbol_not_in_file_is_broken() -> None:
    """A plausible-looking consumer string that the file does not contain = false control."""
    entries = [_entry("fake", lifecycle="adopted")]
    evidence = {
        "fake": _ev(
            "fake",
            consumer_file=_REAL_CONSUMER,
            consumer_symbol="ThisSymbolDoesNotExistHere",
            test_file=(_REAL_TEST,),
        )
    }
    report = validate_effect_integrity(entries, evidence, _REPO_ROOT)

    assert report.broken == 1


def test_missing_test_file_is_broken() -> None:
    entries = [_entry("notest", lifecycle="adopted")]
    evidence = {
        "notest": _ev(
            "notest",
            consumer_file=_REAL_CONSUMER,
            consumer_symbol="validate_matrix",
            test_file=("tests/unit/__missing__.py",),
        )
    }
    report = validate_effect_integrity(entries, evidence, _REPO_ROOT)

    assert report.broken == 1


# ---------------------------------------------------------------------------
# Report shape
# ---------------------------------------------------------------------------


def test_report_counts_are_consistent() -> None:
    entries = [
        _entry("ok", lifecycle="adopted"),
        _entry("gap", classification="user", lifecycle="adopted"),
        _entry("sib", lifecycle="adopted"),
        _entry("out", classification="operator", lifecycle="operator_default"),
    ]
    evidence = {
        "ok": _ev(
            "ok",
            consumer_file=_REAL_CONSUMER,
            consumer_symbol="validate_matrix",
            test_file=(_REAL_TEST,),
        ),
        "sib": _ev(
            "sib",
            consumer_file=_REAL_CONSUMER,
            consumer_symbol="validate_matrix",
            test_file=("tests/unit/api/writing/test_ws_turn_budget.py",),
        ),
    }
    report = validate_effect_integrity(entries, evidence, _REPO_ROOT)

    assert report.total_in_scope == 3
    assert report.verified == 1
    assert report.gaps == 1
    assert report.consumer_only == 1
    assert report.broken == 0
    # The verifier function reports governed debt; the entry-point checker
    # (BLOCKING since AUFG-01-09) turns non-zero debt into exit 1.
    assert report.has_governed_debt is True
