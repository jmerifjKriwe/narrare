"""PROMPT-INTEGRITY · Prompt content integrity checks (Gate 9).

Detects:
- Route governance issues (intents without proper classification)
- Variable registration issues (unregistered template variables)
- Variable usage issues (dead registrations)
- i18n parity gaps (EN prompts without DE/FR counterparts for localized families)
- Rogue level-2 headers in registry-governed system.md templates
  (R2 Slice 0 — ``_check_system_headers``)

INFRA-012: New findings are blocking violations. Pre-existing gaps listed in the
``ai-gate-baseline.json`` ``prompt_integrity_findings`` section are reported as
approved exceptions.

Baseline hygiene (T3 hardening):
- Findings are ratcheted individually (one baseline signature per finding), so
  single-finding drift cannot hide inside an aggregate signature.
- A baseline entry matching no current finding is itself a failure
  (``[STALE-BASELINE]``) — resolved debt must be pruned from the baseline, not
  carried as a phantom entry.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from scripts.architecture._checkers._check_i18n import (
    check_i18n_parity,
    check_prompt_i18n_completeness,
)
from scripts.architecture._checkers._check_intents import check_intent_consistency
from scripts.architecture._checkers._check_system_headers import (
    check_system_prompt_l2_headers,
)
from scripts.architecture._checkers._check_variables import (
    check_variable_registration,
    check_variable_usage,
)
from scripts.architecture.helpers import ROOT
from scripts.architecture.types import CheckResult, Violation

if TYPE_CHECKING:
    ...

# ---------------------------------------------------------------------------
# Baseline loader for prompt-integrity advisory findings
# ---------------------------------------------------------------------------

_BASELINE_PATH = ROOT / "scripts" / "architecture" / "ai-gate-baseline.json"


def _load_prompt_integrity_baseline() -> set[str]:
    """Load the ``prompt_integrity_findings`` baseline set from JSON.

    Returns a set of normalised finding signatures — one per finding, e.g.
    ``"PROMPT-VARS | .../variable_registry.py | Dead variable in SYSTEM_VARS — ...: <name>"``.
    An empty set means no baseline is present (all advisory findings are new).
    """
    try:
        with open(_BASELINE_PATH) as f:
            data = json.load(f)
    except FileNotFoundError, json.JSONDecodeError:
        return set()

    return set(data.get("prompt_integrity_findings", []))


# ---------------------------------------------------------------------------
# Main entry point — run all prompt integrity checks
# ---------------------------------------------------------------------------


def run_all_checks(result: CheckResult) -> None:
    """Run all prompt integrity checks and populate *result*.

    This is the main entry point callable from check_architecture.py.

    INFRA-012 enforcement:
    - New intent-governance and variable-registration issues → ``result.violations``
      (blocking — fail CI).
    - Legacy advisory findings (i18n gaps, dead vars) → baselined findings use
      ``result.approved_exceptions``; UNBASELINED advisory findings become
      ``result.violations`` to enforce no-silent-growth.
    - STALE baseline entries (matching no current finding) → ``result.violations``
      (blocking — resolved debt must be pruned from the baseline).
    """
    baseline = _load_prompt_integrity_baseline()

    # --- Blocking checks (INFRA-012, always violations) ---
    # Intent route governance — every LLMIntent must have a classification
    check_intent_consistency(result)

    # Variable registration — every {{variable}} must be in a provenance registry
    check_variable_registration(result)

    # --- Advisory checks with baseline ratcheting ---
    # Collect advisory findings into a temporary list first, then compare
    # against the baseline. Unbaselined findings become violations.
    pre_baseline_count = len(result.approved_exceptions)
    # Findings already reported outside the prompt-integrity advisory window
    # (base-scanner output + blocking findings from this run). A baseline
    # entry still matching one of those is relocated, not phantom.
    other_sigs = {_finding_signature(v) for v in result.violations}
    other_sigs.update(_finding_signature(v) for v in result.approved_exceptions)

    check_prompt_i18n_completeness(result)
    check_i18n_parity(result)
    check_variable_usage(result)

    # Ratchet: any new advisory finding that is NOT in the baseline → violation
    new_advisory = result.approved_exceptions[pre_baseline_count:]
    live_sigs: set[str] = set()
    for v in new_advisory:
        sig = _finding_signature(v)
        live_sigs.add(sig)
        if sig not in baseline:
            # Promote to blocking violation
            result.violations.append(
                Violation(
                    file=v.file,
                    line=v.line,
                    rule=v.rule,
                    detail=f"[UNBASELINED] {v.detail} — add to "
                    f"ai-gate-baseline.json prompt_integrity_findings if intentional",
                )
            )

    # STALE-BASELINE: baseline entries matching no live advisory finding AND no
    # finding reported in another bucket are phantom debt → blocking failure.
    # This is the root-cause prevention for baseline drift going unnoticed.
    for sig in sorted(baseline - live_sigs - other_sigs):
        result.violations.append(
            Violation(
                file=Path("scripts/architecture/ai-gate-baseline.json"),
                line=0,
                rule="PROMPT-INTEGRITY",
                detail=(
                    f"[STALE-BASELINE] Baseline entry matches no current finding — remove: {sig}"
                ),
            )
        )

    # Remove baselined findings from approved_exceptions (they're expected)
    # but keep them visible by re-adding only the baselined ones
    result.approved_exceptions = result.approved_exceptions[:pre_baseline_count]
    for v in new_advisory:
        sig = _finding_signature(v)
        if sig in baseline:
            result.approved_exceptions.append(v)

    # --- R2 Slice 0: level-2 header governance (own explicit allowlist) ---
    # Runs AFTER the advisory ratchet window closes: its allowlisted templates
    # are governed by the dedicated ``system_prompt_l2_header_allowlist``
    # baseline section (path-keyed, reason + slice ref per entry), NOT by the
    # ``prompt_integrity_findings`` signature ratchet above.
    check_system_prompt_l2_headers(result)


def _finding_signature(violation: Violation) -> str:
    """Normalise a violation entry into its baseline signature string."""
    return f"{violation.rule} | {violation.file} | {violation.detail}"
