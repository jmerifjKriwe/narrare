"""ADR-056 runtime-aware commit-gate ratchet regression.

Extracted from ``test_check_adoption_runtime_semantics.py`` to respect
RULE-04 (file-size). Asserts the two ADR-056 properties:

1. A marker set resolving a previously-debt mode no longer surfaces as fake
   debt — the runtime-aware gate witnesses it (baseline cleanup unblocked).
2. A deliberately un-probed mode (no committed marker) still FAILS the
   ratchet — new debt is caught at commit time.

Uses synthetic categories/modes so the test does not couple to real modes.
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

import check_adoption  # noqa: E402
from adoption.scorer import AdoptionReport  # noqa: E402
from adoption.scorer_models import CategoryScore  # noqa: E402
from adoption.scorer_modes import ModeScore, RuntimeCheckDetail  # noqa: E402
from scripts.architecture.baselines import (  # noqa: E402
    compare_section,
    stable_fingerprint,
)


def _synth_report(
    *,
    category: str,
    mode: str,
    runtime_verified: bool,
    adopted: bool,
    runtime_detail: tuple[str, str] | None,
) -> AdoptionReport:
    """Build a synthetic single-mode report exercising adoption_debt_fingerprints.

    The mode is always ``static_verified=True`` (so the runtime-gap and
    not_adopted branches are governed purely by *runtime_verified* / *adopted*).
    ``runtime_detail`` is ``(requirement, evidence_status)`` or ``None``.
    """
    details = (
        [
            RuntimeCheckDetail(
                requirement=runtime_detail[0],
                declared="required",
                evidence_status=runtime_detail[1],
                note="",
            )
        ]
        if runtime_detail is not None
        else []
    )
    mode_score = ModeScore(
        mode=mode,
        score=1.0,
        status="PASS",
        static_verified=True,
        runtime_verified=runtime_verified,
        adopted=adopted,
        requires_runtime_evidence=True,
        runtime_details=details,
    )
    category_score = CategoryScore(
        category=category,
        score=1.0,
        status="PASS",
        modes=[mode_score],
    )
    return AdoptionReport(overall_score=1.0, status="PASS", categories=[category_score])


class TestRuntimeAwareCommitGateRatchet:
    """ADR-056 — runtime-aware commit gate witnesses resolved modes but still
    ratchets genuinely new debt."""

    _CATEGORY = "synth_cat"
    _RESOLVED_MODE = "resolved_mode"
    _UNPROBED_MODE = "unprobed_mode"

    def test_resolved_mode_emits_no_runtime_gap(self) -> None:
        """Property 1 — a marker set resolving a previously-debt mode is
        witnessed: ``adoption_debt_fingerprints`` emits neither a runtime-gap
        nor a not_adopted fingerprint for it (no fake debt)."""
        report = _synth_report(
            category=self._CATEGORY,
            mode=self._RESOLVED_MODE,
            runtime_verified=True,
            adopted=True,
            runtime_detail=("final_validation", "verified"),
        )

        debt = check_adoption.adoption_debt_fingerprints(report)

        previously_debt_fingerprint = stable_fingerprint(
            self._CATEGORY, self._RESOLVED_MODE, "runtime", "final_validation", "missing"
        )
        not_adopted_fingerprint = stable_fingerprint(
            self._CATEGORY, self._RESOLVED_MODE, "not_adopted"
        )

        assert previously_debt_fingerprint not in debt
        assert not_adopted_fingerprint not in debt
        # A fully-resolved mode contributes no adoption debt at all.
        assert debt == set()

    def test_resolved_mode_ratchet_tolerates_one_directional_shrink(self, tmp_path: Path) -> None:
        """Property 1 (ratchet side) — the baseline may still carry the old
        previously-debt fingerprint; a runtime-aware run that resolves it sees
        the item as RESOLVED (not NEW), so ``comparison.ok`` stays True. This
        one-directional tolerance unblocks the baseline cleanup."""
        report = _synth_report(
            category=self._CATEGORY,
            mode=self._RESOLVED_MODE,
            runtime_verified=True,
            adopted=True,
            runtime_detail=("final_validation", "verified"),
        )
        current = check_adoption.adoption_debt_fingerprints(report)
        previously_debt_fingerprint = stable_fingerprint(
            self._CATEGORY, self._RESOLVED_MODE, "runtime", "final_validation", "missing"
        )
        baseline_file = tmp_path / "baseline.json"
        baseline_file.write_text(
            json.dumps({"adoption_debt": [previously_debt_fingerprint]}),
            encoding="utf-8",
        )

        comparison = compare_section(current, "adoption_debt", baseline_file)

        assert comparison.ok is True
        assert comparison.new_items == set()
        assert previously_debt_fingerprint in comparison.resolved_items

    def test_unprobed_mode_still_produces_runtime_gap(self) -> None:
        """Property 2 — a deliberately un-probed mode (no committed marker)
        surfaces both its runtime gap and its not_adopted fingerprint as
        current debt."""
        report = _synth_report(
            category=self._CATEGORY,
            mode=self._UNPROBED_MODE,
            runtime_verified=False,
            adopted=False,
            runtime_detail=("final_validation", "missing"),
        )

        debt = check_adoption.adoption_debt_fingerprints(report)

        gap_fingerprint = stable_fingerprint(
            self._CATEGORY, self._UNPROBED_MODE, "runtime", "final_validation", "missing"
        )
        not_adopted_fingerprint = stable_fingerprint(
            self._CATEGORY, self._UNPROBED_MODE, "not_adopted"
        )

        assert gap_fingerprint in debt
        assert not_adopted_fingerprint in debt

    def test_unprobed_mode_fails_the_ratchet_new_debt_caught(self, tmp_path: Path) -> None:
        """Property 2 (ratchet side) — the un-probed mode's fingerprint is NOT
        in the baseline, so ``compare_section`` reports it as NEW debt and the
        gate fails (``comparison.ok is False``). ADR-056 preserves this: the
        commit gate still catches genuinely new debt."""
        report = _synth_report(
            category=self._CATEGORY,
            mode=self._UNPROBED_MODE,
            runtime_verified=False,
            adopted=False,
            runtime_detail=("final_validation", "missing"),
        )
        current = check_adoption.adoption_debt_fingerprints(report)
        gap_fingerprint = stable_fingerprint(
            self._CATEGORY, self._UNPROBED_MODE, "runtime", "final_validation", "missing"
        )
        baseline_file = tmp_path / "baseline.json"
        baseline_file.write_text(json.dumps({"adoption_debt": []}), encoding="utf-8")

        comparison = compare_section(current, "adoption_debt", baseline_file)

        assert comparison.ok is False
        assert gap_fingerprint in comparison.new_items
