"""Tests for build_audit_report() integration.

Validates the full report building pipeline from scorer output,
registry, and baseline. Split from test_audit_report.py per RULE-04.

See: ADR-040 Decision 3.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_SCRIPTS = str(Path(__file__).resolve().parent.parent.parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from adoption.audit_report import (  # noqa: E402
    AUDIT_STATE_ADOPTED,
    AUDIT_STATE_RATCHETED_DEBT,
    AUDIT_STATE_STATIC_VERIFIED,
    build_audit_report,
)
from adoption.scorer import (  # noqa: E402
    AdoptionReport,
    CategoryScore,
)
from adoption.scorer_modes import ModeScore  # noqa: E402

# ── Helpers ────────────────────────────────────────────────────────


def _make_mode_score(
    mode: str = "new_chapter",
    *,
    score: float = 0.90,
    static_verified: bool = True,
    runtime_verified: bool = True,
    adopted: bool = True,
) -> ModeScore:
    return ModeScore(
        mode=mode,
        score=score,
        status="PASS",
        static_verified=static_verified,
        runtime_verified=runtime_verified,
        adopted=adopted,
    )


def _make_report(modes: list[ModeScore] | None = None) -> AdoptionReport:
    ms = modes or [_make_mode_score()]
    return AdoptionReport(
        overall_score=0.90,
        status="PASS",
        categories=[
            CategoryScore(
                category="writing",
                score=0.90,
                status="PASS",
                modes=ms,
            )
        ],
    )


def _make_registry(
    *,
    mode_name: str = "new_chapter",
    category: str = "writing",
) -> dict[str, object]:
    return {
        "features": {
            category: {
                "modes": {mode_name: {}},
                "required_infrastructure": {},
                "context_variables": {"must": [], "should": []},
            }
        },
    }


def _make_baseline_file(tmp_path: Path, debt_items: list[str] | None = None) -> Path:
    """Create a temporary ai-gate-baseline.json with optional debt items."""
    baseline = {"adoption_debt": debt_items or []}
    p = tmp_path / "ai-gate-baseline.json"
    p.write_text(json.dumps(baseline), encoding="utf-8")
    return p


# ── build_audit_report ────────────────────────────────────────────


class TestBuildAuditReport:
    def test_basic_construction(self, tmp_path: Path) -> None:
        baseline = _make_baseline_file(tmp_path)
        report = _make_report()
        registry = _make_registry()
        audit = build_audit_report(report, registry, baseline)

        assert audit.total_modes == 1
        assert audit.adopted_count == 1
        assert audit.modes[0].mode == "new_chapter"
        assert audit.modes[0].current_state == AUDIT_STATE_ADOPTED

    def test_with_debt(self, tmp_path: Path) -> None:
        baseline = _make_baseline_file(
            tmp_path,
            debt_items=["writing | new_chapter | not_adopted"],
        )
        report = _make_report()
        registry = _make_registry()
        audit = build_audit_report(report, registry, baseline)

        assert audit.modes[0].current_state == AUDIT_STATE_RATCHETED_DEBT
        assert len(audit.modes[0].debt_items) == 1

    def test_missing_baseline(self, tmp_path: Path) -> None:
        baseline = tmp_path / "nonexistent.json"
        report = _make_report()
        registry = _make_registry()
        audit = build_audit_report(report, registry, baseline)

        # Should work fine with no debt.
        assert audit.total_modes == 1
        assert audit.modes[0].current_state == AUDIT_STATE_ADOPTED

    def test_static_only_mode(self, tmp_path: Path) -> None:
        baseline = _make_baseline_file(tmp_path)
        mode = _make_mode_score(
            static_verified=True,
            runtime_verified=False,
            adopted=False,
        )
        report = _make_report(modes=[mode])
        registry = _make_registry()
        audit = build_audit_report(report, registry, baseline)

        assert audit.modes[0].current_state == AUDIT_STATE_STATIC_VERIFIED
        assert audit.static_verified_count == 1

    def test_multiple_categories(self, tmp_path: Path) -> None:
        baseline = _make_baseline_file(tmp_path)
        report = AdoptionReport(
            overall_score=0.85,
            status="PASS",
            categories=[
                CategoryScore(
                    category="writing",
                    score=0.90,
                    status="PASS",
                    modes=[
                        _make_mode_score("new_chapter"),
                        _make_mode_score("extend_chapter", adopted=False, runtime_verified=False),
                    ],
                ),
                CategoryScore(
                    category="analysis",
                    score=0.80,
                    status="PASS",
                    modes=[
                        _make_mode_score("review"),
                    ],
                ),
            ],
        )
        registry: dict[str, object] = {
            "features": {
                "writing": {
                    "modes": {"new_chapter": {}, "extend_chapter": {}},
                    "required_infrastructure": {},
                    "context_variables": {"must": [], "should": []},
                },
                "analysis": {
                    "modes": {"review": {}},
                    "required_infrastructure": {},
                    "context_variables": {"must": [], "should": []},
                },
            },
        }
        audit = build_audit_report(report, registry, baseline)

        assert audit.total_modes == 3
        # new_chapter: adopted, extend_chapter: static_verified, review: adopted
        assert audit.adopted_count == 2

    def test_list_mode_format(self, tmp_path: Path) -> None:
        """Registry modes as list (legacy format)."""
        baseline = _make_baseline_file(tmp_path)
        report = _make_report()
        registry: dict[str, object] = {
            "features": {
                "writing": {
                    "modes": ["new_chapter"],
                    "required_infrastructure": {},
                    "context_variables": {"must": [], "should": []},
                },
            },
        }
        audit = build_audit_report(report, registry, baseline)
        assert audit.total_modes == 1
        assert audit.modes[0].mode == "new_chapter"

    def test_requires_runtime_evidence_flag(self, tmp_path: Path) -> None:
        baseline = _make_baseline_file(tmp_path)
        mode = _make_mode_score(runtime_verified=False, adopted=False)
        report = _make_report(modes=[mode])
        registry = _make_registry()
        audit = build_audit_report(report, registry, baseline)

        # Mode is in registry and not runtime_verified → flag set.
        assert audit.modes[0].requires_runtime_evidence is True
