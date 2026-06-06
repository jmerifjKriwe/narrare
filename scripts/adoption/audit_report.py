#!/usr/bin/env python3
"""Audit lifecycle reporting for adoption findings.

Builds an AuditReport from the adoption registry, scorer output
(AdoptionReport), and the ai-gate-baseline.json debt list.

The report tracks per-mode lifecycle states (AuditState) with transition
history, debt linkage, and summary statistics. Output formats: JSON for
CI consumption, Markdown for human review.

See: ADR-040 Decision 3.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from adoption.scorer import PASS_THRESHOLD, AdoptionReport

if TYPE_CHECKING:
    from pathlib import Path

# ── Audit states (mirrors core/ai_invocation/_enums.py AuditState) ──

AUDIT_STATE_IDENTIFIED = "identified"
AUDIT_STATE_STATIC_VERIFIED = "static_verified"
AUDIT_STATE_RUNTIME_VERIFIED = "runtime_verified"
AUDIT_STATE_ADOPTED = "adopted"
AUDIT_STATE_RATCHETED_DEBT = "ratcheted_debt"
AUDIT_STATE_BLOCKED = "blocked"

# All valid audit states.
VALID_AUDIT_STATES: frozenset[str] = frozenset(
    {
        AUDIT_STATE_IDENTIFIED,
        AUDIT_STATE_STATIC_VERIFIED,
        AUDIT_STATE_RUNTIME_VERIFIED,
        AUDIT_STATE_ADOPTED,
        AUDIT_STATE_RATCHETED_DEBT,
        AUDIT_STATE_BLOCKED,
    }
)


# ── Data models ──────────────────────────────────────────────────────


@dataclass
class AuditTransition:
    """A single state transition in the audit lifecycle."""

    state: str  # AuditState value
    timestamp: str  # ISO-8601
    evidence_id: str | None  # Link to evidence record or test probe
    reason: str


@dataclass
class ModeAuditState:
    """Audit lifecycle state for a single mode."""

    mode: str
    category: str
    current_state: str  # Latest AuditState
    transitions: list[AuditTransition] = field(default_factory=list[AuditTransition])
    debt_items: list[str] = field(default_factory=list[str])  # Baseline debt references
    requires_runtime_evidence: bool = False


@dataclass
class AuditReport:
    """Aggregate audit lifecycle report across all modes."""

    generated_at: str
    modes: list[ModeAuditState] = field(default_factory=list[ModeAuditState])
    debt_summary: dict[str, int] = field(default_factory=dict[str, int])
    total_modes: int = 0
    adopted_count: int = 0
    runtime_verified_count: int = 0
    static_verified_count: int = 0
    debt_count: int = 0

    def to_json(self) -> str:
        """Machine-readable JSON for CI consumption."""
        data = asdict(self)
        return json.dumps(data, indent=2, ensure_ascii=False)

    def to_markdown(self) -> str:
        """Human-readable markdown for review."""
        lines: list[str] = []
        lines.append("# Audit Lifecycle Report")
        lines.append("")
        lines.append(f"**Generated:** {self.generated_at}")
        lines.append("")
        lines.append("| Metric | Count |")
        lines.append("|--------|-------|")
        lines.append(f"| Total modes | {self.total_modes} |")
        lines.append(f"| Adopted | {self.adopted_count} |")
        lines.append(f"| Runtime verified | {self.runtime_verified_count} |")
        lines.append(f"| Static verified | {self.static_verified_count} |")
        lines.append(f"| Debt items | {self.debt_count} |")
        lines.append("")

        # Debt summary.
        if self.debt_summary:
            lines.append("## Debt Summary by State")
            lines.append("")
            for state, count in sorted(self.debt_summary.items()):
                lines.append(f"- **{state}**: {count}")
            lines.append("")

        # Per-mode detail.
        lines.append("## Mode Details")
        lines.append("")
        for m in self.modes:
            state_icon = _state_icon(m.current_state)
            lines.append(f"### {m.category}/{m.mode} — {state_icon} {m.current_state}")
            if m.requires_runtime_evidence:
                lines.append("- Requires runtime evidence: **yes**")
            if m.debt_items:
                lines.append("- Debt items:")
                for di in m.debt_items:
                    lines.append(f"  - `{di}`")
            if m.transitions:
                lines.append("- Transitions:")
                for t in m.transitions:
                    lines.append(f"  - `{t.state}` at {t.timestamp} — {t.reason}")
            lines.append("")

        return "\n".join(lines)


# ── Helpers ──────────────────────────────────────────────────────────


def _state_icon(state: str) -> str:
    """Return a display icon for an audit state."""
    icons: dict[str, str] = {
        AUDIT_STATE_ADOPTED: "✅",
        AUDIT_STATE_RUNTIME_VERIFIED: "🔍",
        AUDIT_STATE_STATIC_VERIFIED: "📝",
        AUDIT_STATE_RATCHETED_DEBT: "⚠️",
        AUDIT_STATE_IDENTIFIED: "❓",
        AUDIT_STATE_BLOCKED: "🚫",
    }
    return icons.get(state, "  ")


def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(tz=UTC).isoformat()


def _parse_baseline_debt(baseline_path: Path) -> dict[str, list[str]]:
    """Parse ai-gate-baseline.json adoption_debt into per-mode debt items.

    Returns: dict mapping ``"category/mode"`` to list of debt strings.
    """
    if not baseline_path.exists():
        return {}
    with baseline_path.open("r", encoding="utf-8") as fh:
        data: Any = json.load(fh)
    debt_list: list[str] = data.get("adoption_debt", [])
    result: dict[str, list[str]] = {}
    for entry in debt_list:
        parts = [p.strip() for p in entry.split("|")]
        if len(parts) >= 2:
            key = f"{parts[0]}/{parts[1]}"
            result.setdefault(key, []).append(entry)
    return result


def _resolve_audit_state(
    mode_name: str,
    category: str,
    static_verified: bool,
    runtime_verified: bool,
    adopted: bool,
    debt_keys_for_mode: list[str],
    in_registry: bool,
) -> tuple[str, str, str | None]:
    """Determine the audit state for a mode.

    Returns (state, reason, evidence_id).
    """
    # Priority 1: In baseline debt → RATCHETED_DEBT.
    if debt_keys_for_mode:
        return (
            AUDIT_STATE_RATCHETED_DEBT,
            f"{len(debt_keys_for_mode)} item(s) in ai-gate-baseline.json",
            None,
        )

    # Priority 2: Missing from registry entirely → IDENTIFIED.
    if not in_registry:
        return (
            AUDIT_STATE_IDENTIFIED,
            "mode not found in adoption registry",
            None,
        )

    # Priority 3: Fully adopted.
    if adopted:
        return (
            AUDIT_STATE_ADOPTED,
            "static + runtime verified, adopted=True",
            f"adopted:{category}/{mode_name}",
        )

    # Priority 4: Runtime verified (but not fully adopted).
    if runtime_verified:
        return (
            AUDIT_STATE_RUNTIME_VERIFIED,
            "runtime evidence present, score below adoption threshold",
            f"runtime:{category}/{mode_name}",
        )

    # Priority 5: Static verified only.
    if static_verified:
        return (
            AUDIT_STATE_STATIC_VERIFIED,
            f"score >= {PASS_THRESHOLD} but no runtime evidence",
            f"static:{category}/{mode_name}",
        )

    # Default: identified (not yet verified).
    return (
        AUDIT_STATE_IDENTIFIED,
        "score below static verification threshold",
        None,
    )


# ── Public API ───────────────────────────────────────────────────────


def build_audit_report(
    adoption_report: AdoptionReport,
    registry: dict[str, Any],
    baseline_path: Path,
) -> AuditReport:
    """Build an AuditReport from scorer output, registry, and baseline.

    Parameters
    ----------
    adoption_report:
        The computed AdoptionReport from ``compute_adoption_report()``.
    registry:
        The parsed adoption-registry.yaml data.
    baseline_path:
        Path to ``ai-gate-baseline.json``.

    Returns
    -------
    AuditReport with lifecycle states for every mode.
    """
    now = _now_iso()
    baseline_debt = _parse_baseline_debt(baseline_path)
    features: dict[str, Any] = registry.get("features", {})
    generated_at = now

    modes: list[ModeAuditState] = []
    debt_summary: dict[str, int] = {}

    # Build a set of all registered mode keys for the "in_registry" check.
    registry_mode_keys: set[str] = set()
    for cat_name, cfg in features.items():
        raw_modes = cfg.get("modes", [])
        if isinstance(raw_modes, dict):
            mode_dict = cast("dict[str, Any]", raw_modes)
            for mn_str in mode_dict:
                registry_mode_keys.add(f"{cat_name}/{mn_str}")
        elif isinstance(raw_modes, list):
            mode_list = cast("list[Any]", raw_modes)
            for item in mode_list:
                if isinstance(item, str):
                    registry_mode_keys.add(f"{cat_name}/{item}")

    for cat_score in adoption_report.categories:
        for mode_score in cat_score.modes:
            mode_key = f"{cat_score.category}/{mode_score.mode}"
            debt_items = baseline_debt.get(mode_key, [])
            in_registry = mode_key in registry_mode_keys

            state, reason, evidence_id = _resolve_audit_state(
                mode_name=mode_score.mode,
                category=cat_score.category,
                static_verified=mode_score.static_verified,
                runtime_verified=mode_score.runtime_verified,
                adopted=mode_score.adopted,
                debt_keys_for_mode=debt_items,
                in_registry=in_registry,
            )

            transition = AuditTransition(
                state=state,
                timestamp=now,
                evidence_id=evidence_id,
                reason=reason,
            )

            modes.append(
                ModeAuditState(
                    mode=mode_score.mode,
                    category=cat_score.category,
                    current_state=state,
                    transitions=[transition],
                    debt_items=debt_items,
                    requires_runtime_evidence=not mode_score.runtime_verified and in_registry,
                )
            )

    # Compute summary counts.
    adopted_count = sum(1 for m in modes if m.current_state == AUDIT_STATE_ADOPTED)
    runtime_verified_count = sum(
        1 for m in modes if m.current_state == AUDIT_STATE_RUNTIME_VERIFIED
    )
    static_verified_count = sum(1 for m in modes if m.current_state == AUDIT_STATE_STATIC_VERIFIED)
    total_debt = sum(len(m.debt_items) for m in modes)

    # Debt summary: count modes per state.
    for m in modes:
        debt_summary[m.current_state] = debt_summary.get(m.current_state, 0) + 1

    return AuditReport(
        generated_at=generated_at,
        modes=modes,
        debt_summary=debt_summary,
        total_modes=len(modes),
        adopted_count=adopted_count,
        runtime_verified_count=runtime_verified_count,
        static_verified_count=static_verified_count,
        debt_count=total_debt,
    )
