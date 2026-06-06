"""Tests for scripts/adoption/audit_report.py.

Validates AuditReport construction, JSON/Markdown serialization,
build_audit_report with mock data, and state resolution logic.

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
    AUDIT_STATE_IDENTIFIED,
    AUDIT_STATE_RATCHETED_DEBT,
    AUDIT_STATE_RUNTIME_VERIFIED,
    AUDIT_STATE_STATIC_VERIFIED,
    AuditReport,
    AuditTransition,
    ModeAuditState,
    _resolve_audit_state,
)

# ── AuditTransition ───────────────────────────────────────────────


class TestAuditTransition:
    def test_construction(self) -> None:
        t = AuditTransition(
            state="adopted",
            timestamp="2026-01-01T00:00:00Z",
            evidence_id="evidence:writing/new_chapter",
            reason="adopted",
        )
        assert t.state == "adopted"
        assert t.evidence_id is not None

    def test_none_evidence_id(self) -> None:
        t = AuditTransition(
            state="identified",
            timestamp="2026-01-01T00:00:00Z",
            evidence_id=None,
            reason="not in registry",
        )
        assert t.evidence_id is None


# ── ModeAuditState ────────────────────────────────────────────────


class TestModeAuditState:
    def test_construction(self) -> None:
        mas = ModeAuditState(
            mode="new_chapter",
            category="writing",
            current_state="adopted",
        )
        assert mas.mode == "new_chapter"
        assert mas.transitions == []
        assert mas.debt_items == []
        assert not mas.requires_runtime_evidence

    def test_with_debt_items(self) -> None:
        mas = ModeAuditState(
            mode="extend_chapter",
            category="writing",
            current_state="ratcheted_debt",
            debt_items=["writing | extend_chapter | not_adopted"],
        )
        assert len(mas.debt_items) == 1


# ── AuditReport serialization ─────────────────────────────────────


class TestAuditReportToJson:
    def test_valid_json(self) -> None:
        report = AuditReport(
            generated_at="2026-01-01T00:00:00Z",
            modes=[
                ModeAuditState(
                    mode="new_chapter",
                    category="writing",
                    current_state="adopted",
                )
            ],
            total_modes=1,
            adopted_count=1,
        )
        raw = report.to_json()
        data = json.loads(raw)
        assert data["total_modes"] == 1
        assert data["adopted_count"] == 1
        assert data["modes"][0]["mode"] == "new_chapter"

    def test_roundtrip(self) -> None:
        report = AuditReport(
            generated_at="2026-01-01T00:00:00Z",
            modes=[],
            debt_summary={"adopted": 5, "ratcheted_debt": 2},
            total_modes=7,
        )
        data = json.loads(report.to_json())
        assert data["debt_summary"]["adopted"] == 5


class TestAuditReportToMarkdown:
    def test_contains_header(self) -> None:
        report = AuditReport(
            generated_at="2026-01-01T00:00:00Z",
            modes=[],
        )
        md = report.to_markdown()
        assert "# Audit Lifecycle Report" in md
        assert "2026-01-01T00:00:00Z" in md

    def test_contains_mode_detail(self) -> None:
        report = AuditReport(
            generated_at="2026-01-01T00:00:00Z",
            modes=[
                ModeAuditState(
                    mode="new_chapter",
                    category="writing",
                    current_state="adopted",
                    transitions=[
                        AuditTransition(
                            state="adopted",
                            timestamp="2026-01-01T00:00:00Z",
                            evidence_id="adopted:writing/new_chapter",
                            reason="adopted",
                        )
                    ],
                )
            ],
            total_modes=1,
            adopted_count=1,
        )
        md = report.to_markdown()
        assert "writing/new_chapter" in md
        assert "adopted" in md
        # Evidence ID appears in transition line: `adopted` at ...
        assert "2026-01-01T00:00:00Z" in md

    def test_debt_summary_rendered(self) -> None:
        report = AuditReport(
            generated_at="2026-01-01T00:00:00Z",
            modes=[],
            debt_summary={"adopted": 3, "ratcheted_debt": 1},
        )
        md = report.to_markdown()
        assert "adopted" in md
        assert "ratcheted_debt" in md


# ── _resolve_audit_state ──────────────────────────────────────────


class TestResolveAuditState:
    def test_adopted(self) -> None:
        state, _reason, eid = _resolve_audit_state(
            mode_name="new_chapter",
            category="writing",
            static_verified=True,
            runtime_verified=True,
            adopted=True,
            debt_keys_for_mode=[],
            in_registry=True,
        )
        assert state == AUDIT_STATE_ADOPTED
        assert eid is not None

    def test_runtime_verified_only(self) -> None:
        state, _reason, _eid = _resolve_audit_state(
            mode_name="new_chapter",
            category="writing",
            static_verified=True,
            runtime_verified=True,
            adopted=False,
            debt_keys_for_mode=[],
            in_registry=True,
        )
        assert state == AUDIT_STATE_RUNTIME_VERIFIED

    def test_static_verified_only(self) -> None:
        state, _reason, _eid = _resolve_audit_state(
            mode_name="new_chapter",
            category="writing",
            static_verified=True,
            runtime_verified=False,
            adopted=False,
            debt_keys_for_mode=[],
            in_registry=True,
        )
        assert state == AUDIT_STATE_STATIC_VERIFIED

    def test_ratcheted_debt(self) -> None:
        state, _reason, _eid = _resolve_audit_state(
            mode_name="extend_chapter",
            category="writing",
            static_verified=True,
            runtime_verified=True,
            adopted=True,
            debt_keys_for_mode=["writing | extend_chapter | not_adopted"],
            in_registry=True,
        )
        assert state == AUDIT_STATE_RATCHETED_DEBT

    def test_not_in_registry(self) -> None:
        state, reason, _eid = _resolve_audit_state(
            mode_name="unknown_mode",
            category="writing",
            static_verified=False,
            runtime_verified=False,
            adopted=False,
            debt_keys_for_mode=[],
            in_registry=False,
        )
        assert state == AUDIT_STATE_IDENTIFIED
        assert "not found" in reason

    def test_below_threshold(self) -> None:
        state, _reason, _eid = _resolve_audit_state(
            mode_name="new_chapter",
            category="writing",
            static_verified=False,
            runtime_verified=False,
            adopted=False,
            debt_keys_for_mode=[],
            in_registry=True,
        )
        assert state == AUDIT_STATE_IDENTIFIED

    def test_debt_overrides_adopted(self) -> None:
        """Debt items take priority even if mode is adopted."""
        state, _, _ = _resolve_audit_state(
            mode_name="x",
            category="writing",
            static_verified=True,
            runtime_verified=True,
            adopted=True,
            debt_keys_for_mode=["writing | x | not_adopted"],
            in_registry=True,
        )
        assert state == AUDIT_STATE_RATCHETED_DEBT
