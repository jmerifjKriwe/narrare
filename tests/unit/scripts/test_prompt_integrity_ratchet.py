"""Tests for prompt-integrity ratchet hardening (T3).

Covers:
1. Per-variable dead-var emission — ``check_variable_usage`` emits one
   Violation per dead SYSTEM_VARS entry (no comma-joined aggregate), so each
   dead var is individually baselinable via its ``rule | file | detail``
   signature.
2. STALE-BASELINE detection — ``prompt_integrity.run_all_checks`` fails the
   gate when a baseline entry matches no live finding (and no finding
   reported outside the prompt-integrity advisory window).
3. Regen'd empty baseline — a cleaned ``prompt_integrity_findings`` section
   passes when the registry has no dead variables.

All tests run against isolated temp trees (monkeypatched ROOT / baseline
path); the real repo is never mutated.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.architecture._checkers import _check_variables, prompt_integrity  # noqa: E402
from scripts.architecture.types import CheckResult, Violation  # noqa: E402

_REGISTRY_REL = "packages/core/narrare_core/prompts/variable_registry.py"

# Sub-checkers of run_all_checks that are irrelevant to the ratchet logic
# under test — replaced with no-ops so tests exercise only baseline matching.
_UNRELATED_SUBCHECKS = (
    "check_intent_consistency",
    "check_variable_registration",
    "check_prompt_i18n_completeness",
    "check_i18n_parity",
)


def _dead_var_detail(var: str) -> str:
    return f"Dead variable in SYSTEM_VARS — registered but never used in any prompt template: {var}"


def _dead_var_signature(var: str) -> str:
    return f"PROMPT-VARS | {_REGISTRY_REL} | {_dead_var_detail(var)}"


def _make_fake_repo(tmp_path: Path, system_vars: list[str], template_vars: list[str]) -> None:
    """Create a minimal repo tree (registry + one template) under tmp_path."""
    prompts = tmp_path / "packages" / "core" / "narrare_core" / "prompts"
    bundled = prompts / "_bundled"
    bundled.mkdir(parents=True)
    sv = ", ".join(f'"{v}"' for v in system_vars)
    tv = ", ".join(f'"{v}"' for v in template_vars)
    (prompts / "variable_registry.py").write_text(
        "USER_CONTENT_VARS: frozenset = frozenset()\n"
        f"SYSTEM_VARS: frozenset = frozenset({{{sv}}})\n"
        f"FEATURE_DYNAMIC_VARS: frozenset = frozenset({{{tv}}})\n",
        encoding="utf-8",
    )
    placeholders = "".join(f"{{{{{v}}}}}" for v in template_vars)
    (bundled / "template.md").write_text(f"text {placeholders}\n", encoding="utf-8")


def _patch_ratchet_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    baseline_findings: list[str],
) -> None:
    """Point run_all_checks at a temp baseline and disable unrelated sub-checks."""
    baseline_path = tmp_path / "ai-gate-baseline.json"
    baseline_path.write_text(
        json.dumps({"prompt_integrity_findings": baseline_findings}), encoding="utf-8"
    )
    monkeypatch.setattr(prompt_integrity, "_BASELINE_PATH", baseline_path)

    def _noop(result: CheckResult) -> None:
        pass

    for name in _UNRELATED_SUBCHECKS:
        monkeypatch.setattr(prompt_integrity, name, _noop)


# =====================================================================
# 1. Per-variable emission
# =====================================================================


class TestPerVariableEmission:
    """check_variable_usage emits one Violation per dead SYSTEM_VARS entry."""

    def test_two_dead_vars_produce_two_distinct_violations(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _make_fake_repo(
            tmp_path, system_vars=["dead_one", "dead_two", "alive"], template_vars=["alive"]
        )
        monkeypatch.setattr(_check_variables, "ROOT", tmp_path)

        result = CheckResult()
        _check_variables.check_variable_usage(result)

        dead = [v for v in result.approved_exceptions if "Dead variable" in v.detail]
        assert len(dead) == 2
        details = {v.detail for v in dead}
        assert _dead_var_detail("dead_one") in details
        assert _dead_var_detail("dead_two") in details
        # No comma-joined aggregate entry
        assert not any("dead_one, dead_two" in d for d in details)
        # Signature scheme preserved per-var: rule | file | detail
        for v in dead:
            assert v.rule == "PROMPT-VARS"
            assert str(v.file) == _REGISTRY_REL
            assert v.approved is True

    def test_no_dead_vars_emits_nothing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _make_fake_repo(tmp_path, system_vars=["alive"], template_vars=["alive"])
        monkeypatch.setattr(_check_variables, "ROOT", tmp_path)

        result = CheckResult()
        _check_variables.check_variable_usage(result)

        assert result.approved_exceptions == []


# =====================================================================
# 2. Individual baselinability through run_all_checks
# =====================================================================


class TestIndividualBaselining:
    """Each dead var is ratcheted independently against the baseline."""

    def test_baselined_var_stays_approved_and_unbaselined_var_fails(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _make_fake_repo(tmp_path, system_vars=["dead_one", "dead_two"], template_vars=[])
        monkeypatch.setattr(_check_variables, "ROOT", tmp_path)
        _patch_ratchet_environment(monkeypatch, tmp_path, [_dead_var_signature("dead_one")])

        result = CheckResult()
        prompt_integrity.run_all_checks(result)

        # dead_one: baselined → approved exception, never a violation
        assert not any("dead_one" in v.detail for v in result.violations)
        approved = [v for v in result.approved_exceptions if "dead_one" in v.detail]
        assert len(approved) == 1

        # dead_two: not baselined → promoted to [UNBASELINED] violation
        unbaselined = [v for v in result.violations if "dead_two" in v.detail]
        assert len(unbaselined) == 1
        assert unbaselined[0].detail.startswith("[UNBASELINED]")

        # dead_one matched a live finding → no STALE-BASELINE
        assert not any("STALE-BASELINE" in v.detail for v in result.violations)


# =====================================================================
# 3. STALE-BASELINE detection
# =====================================================================


class TestStaleBaselineDetection:
    """Baseline entries matching no live finding fail the gate."""

    def test_baseline_entry_without_live_finding_fails(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _make_fake_repo(tmp_path, system_vars=["alive"], template_vars=["alive"])
        monkeypatch.setattr(_check_variables, "ROOT", tmp_path)
        phantom = (
            "PROMPT-VARS | packages/core/narrare_core/prompts/variable_registry.py | "
            "Dead variable(s) in SYSTEM_VARS — registered but never used in any "
            "prompt template: feedback_text, mode, style_constraints"
        )
        _patch_ratchet_environment(monkeypatch, tmp_path, [phantom])

        result = CheckResult()
        prompt_integrity.run_all_checks(result)

        stale = [v for v in result.violations if "STALE-BASELINE" in v.detail]
        assert len(stale) == 1
        assert stale[0].detail.startswith("[STALE-BASELINE]")
        assert phantom in stale[0].detail
        # Exit-failing: emitted as a violation, not an advisory exception
        assert not any("STALE-BASELINE" in v.detail for v in result.approved_exceptions)

    def test_baseline_entry_matching_non_prompt_integrity_finding_is_not_stale(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A baseline entry still matching a finding reported in another bucket
        (base-scanner violation with identical rule|file|detail) is not phantom."""
        _make_fake_repo(tmp_path, system_vars=["alive"], template_vars=["alive"])
        monkeypatch.setattr(_check_variables, "ROOT", tmp_path)
        sig = "PROMPT-VARS | packages/core/narrare_core/prompts/variable_registry.py | some detail"
        _patch_ratchet_environment(monkeypatch, tmp_path, [sig])

        result = CheckResult()
        rule, file_, detail = sig.split(" | ", 2)
        result.violations.append(Violation(file=Path(file_), line=0, rule=rule, detail=detail))
        prompt_integrity.run_all_checks(result)

        assert not any("STALE-BASELINE" in v.detail for v in result.violations)


# =====================================================================
# 4. Regen'd empty baseline
# =====================================================================


class TestEmptyBaselineRegen:
    """A regenerated empty prompt_integrity_findings section passes cleanly."""

    def test_empty_baseline_with_clean_registry_passes(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _make_fake_repo(tmp_path, system_vars=["alive"], template_vars=["alive"])
        monkeypatch.setattr(_check_variables, "ROOT", tmp_path)
        _patch_ratchet_environment(monkeypatch, tmp_path, [])

        result = CheckResult()
        prompt_integrity.run_all_checks(result)

        assert result.violations == []
        assert result.approved_exceptions == []
