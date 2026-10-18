"""Bandit scan-scope parity tests — every bandit surface scans the same roots.

The pre-push bandit hook historically received outgoing-range ``.py``
filenames (pre-commit's default filename passing), while ``just security``
and the CI security job ran ``bandit -r`` over production code only — a
3-way scope divergence surfaced by a failed push (B404/B405 findings in
``scripts/`` that no local full-scan gate could see). Unified 2026-08-20:
all surfaces scan production + scripts + evals, and the push hook scans a
FIXED ``-r`` target set (``pass_filenames: false``), so its scope is
identical to CI/just by construction — no history-dependent scan sets.

These tests pin that contract: the pre-push hook's ``-r`` targets, the CI
bandit step's ``-r`` targets, and the ``justfile`` security recipe's ``-r``
targets must each equal the pinned literal below (and therefore each other).
Any UNILATERAL target change on any surface fails; a coordinated scope change
must update this literal together with all three surfaces.

Since the R3 quality split (W1-3/W1-4) the CI Bandit step lives verbatim
inside the composite ``.github/actions/quality`` (called by ci.yml's
quality and test-unit jobs), so the CI helper resolves the invocation
THROUGH the composite — the semantic contract is "the ONE Bandit
invocation that CI executes", wherever it physically lives.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_PRE_COMMIT_CONFIG = _ROOT / ".pre-commit-config.yaml"
_CI_WORKFLOW = _ROOT / ".github" / "workflows" / "ci.yml"
_JUSTFILE = _ROOT / "justfile"
# Local composite actions callable from ci.yml via ``uses:`` (repo-relative).
_LOCAL_COMPOSITE_PREFIX = "./.github/actions/"

# The pinned bandit scan-target contract of ALL surfaces (production +
# scripts + evals). These tests fail on any UNILATERAL target change; a
# coordinated change must update this literal together with the pre-push
# hook, the CI step, and the justfile recipe.
EXPECTED_BANDIT_TARGETS: frozenset[str] = frozenset(
    {"apps/api/narrare", "packages/core/narrare_core", "scripts", "evals"}
)


def _targets_after_dash_r(command: str) -> set[str]:
    """Extract the recursive-scan targets that follow ``-r`` in a bandit command.

    Robust to formatting: YAML block-scalar line continuations
    (backslash-newline) are collapsed and whitespace normalized before
    tokenizing, so a target list split across lines (the CI step) parses
    identically to a single-line one (the pre-commit entry). Tokens after
    ``-r`` are collected until the next flag, so flag order changes
    (e.g. ``-c`` after ``-r``) do not affect the result.
    """
    tokens = " ".join(command.replace("\\\n", " ").split()).split()
    targets: set[str] = set()
    collecting = False
    for token in tokens:
        if collecting:
            if token.startswith("-"):
                break
            targets.add(token)
        elif token == "-r":
            collecting = True
    return targets


def _bandit_hook() -> dict[str, Any]:
    """Return the bandit hook entry from .pre-commit-config.yaml."""
    config = yaml.safe_load(_PRE_COMMIT_CONFIG.read_text(encoding="utf-8"))
    hooks = [
        hook
        for repo in config.get("repos", [])
        for hook in repo.get("hooks", [])
        if hook.get("id") == "bandit"
    ]
    assert len(hooks) == 1, f"expected exactly one bandit hook, found {len(hooks)}"
    return hooks[0]


def _bandit_steps_in(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter a step list down to those invoking bandit (by name or run)."""
    return [
        step
        for step in steps
        if "bandit" in str(step.get("name", "")).lower()
        or "bandit" in str(step.get("run", "")).lower()
    ]


def _ci_bandit_steps() -> list[dict[str, Any]]:
    """Return the ONE Bandit invocation definition the CI pipeline executes.

    Since the R3 quality split (W1-3/W1-4) the Bandit step lives verbatim
    inside the local composite ``.github/actions/quality``, which ci.yml's
    quality and test-unit jobs call via ``uses:`` — so this resolves the
    invocation THROUGH the composite instead of parsing ci.yml job steps
    only. Collected: direct ci.yml job steps plus the steps of every local
    composite a ci.yml job calls. Each composite counts ONCE per distinct
    path — multiple call sites of one composite execute one definition,
    not drift (two call sites of one Bandit definition is the designed
    fold, not a parity violation).

    Loud-zero guard: finds ZERO bandit steps in BOTH ci.yml and all
    composites → assertion failure with a teach-the-helper message, never
    a vacuous pass (the invocation moved elsewhere again and the helper
    must learn the new location first).
    """
    workflow = yaml.safe_load(_CI_WORKFLOW.read_text(encoding="utf-8"))
    job_steps: list[dict[str, Any]] = [
        step for job in workflow.get("jobs", {}).values() for step in job.get("steps", [])
    ]
    steps = _bandit_steps_in(job_steps)
    composite_paths = sorted(
        {
            str(step["uses"])
            for step in job_steps
            if str(step.get("uses", "")).startswith(_LOCAL_COMPOSITE_PREFIX)
        }
    )
    for rel_path in composite_paths:
        action_file = _ROOT / rel_path.removeprefix("./") / "action.yml"
        action = yaml.safe_load(action_file.read_text(encoding="utf-8"))
        steps += _bandit_steps_in(list(action.get("runs", {}).get("steps", [])))
    assert steps, (
        "ZERO bandit steps found in ci.yml and .github/actions/**/action.yml — "
        "the CI Bandit invocation moved to a new location; teach "
        "_ci_bandit_steps() where it lives now (loud-zero guard, no vacuous pass)"
    )
    return steps


def _just_security_bandit_lines() -> list[str]:
    """Return the ``security`` recipe body lines that invoke bandit.

    The recipe header carries a dependency (``security: check-secrets``) —
    the header line itself is skipped; only indented lines after it belong
    to the recipe body, and the recipe ends at the next unindented line.
    Comment lines (``#``) inside the body are ignored, and a line counts as
    a bandit invocation only when ``bandit`` appears as a whole token.
    """
    bandit_lines: list[str] = []
    in_recipe = False
    for line in _JUSTFILE.read_text(encoding="utf-8").splitlines():
        if not in_recipe:
            if line.startswith("security:"):
                in_recipe = True
            continue
        if line.strip() and not line[0].isspace():
            break  # next top-level construct ends the recipe
        stripped = line.strip()
        if stripped.startswith("#"):
            continue  # comment inside the recipe body
        if "bandit" in stripped.split():
            bandit_lines.append(stripped)
    return bandit_lines


class TestBanditScopeParity:
    """The pre-push hook, the CI step, and the just recipe scan one target set."""

    def test_exactly_one_ci_bandit_step(self) -> None:
        """Guards against duplicated or vanished Bandit invocations in CI.

        Counts direct ci.yml steps plus each local composite's steps (once
        per distinct composite). Zero steps fails in the helper (loud-zero
        guard); two would mean duplicated/diverged invocations.
        """
        steps = _ci_bandit_steps()
        assert len(steps) == 1

    def test_pre_push_hook_targets_equal_ci_targets(self) -> None:
        """The core parity invariant: hook ``-r`` targets == CI ``-r`` targets.

        A unilateral target change on either surface (the 3-way divergence
        class this file pins) fails here.
        """
        ci_steps = _ci_bandit_steps()
        assert len(ci_steps) == 1
        hook_targets = _targets_after_dash_r(str(_bandit_hook()["entry"]))
        ci_targets = _targets_after_dash_r(str(ci_steps[0]["run"]))
        assert hook_targets == ci_targets

    def test_pre_push_hook_targets_equal_expected(self) -> None:
        """The hook's ``-r`` targets equal the pinned contract literal."""
        assert _targets_after_dash_r(str(_bandit_hook()["entry"])) == set(EXPECTED_BANDIT_TARGETS)

    def test_ci_targets_equal_expected(self) -> None:
        """The CI step's ``-r`` targets equal the pinned contract literal."""
        ci_steps = _ci_bandit_steps()
        assert len(ci_steps) == 1
        assert _targets_after_dash_r(str(ci_steps[0]["run"])) == set(EXPECTED_BANDIT_TARGETS)

    def test_pre_push_hook_passes_no_filenames(self) -> None:
        """``pass_filenames: false`` is what makes the push scope fixed.

        Re-enabling filename passing would reintroduce a history-dependent
        scan set (outgoing-range files) alongside the ``-r`` targets even
        while the target parity above still holds.
        """
        assert _bandit_hook().get("pass_filenames") is False

    def test_exactly_one_just_security_bandit_line(self) -> None:
        """Guards against duplicated or diverged bandit lines in the recipe.

        A second bandit invocation (e.g. an ad-hoc scan added next to the
        unified one) must be a conscious change, not silent drift.
        """
        assert len(_just_security_bandit_lines()) == 1

    def test_just_security_targets_equal_expected(self) -> None:
        """The just recipe's ``-r`` targets equal the pinned contract literal.

        This closes the third surface: hook, CI step, and ``just security``
        are all machine-pinned to the same target set.
        """
        lines = _just_security_bandit_lines()
        assert len(lines) == 1
        assert _targets_after_dash_r(lines[0]) == set(EXPECTED_BANDIT_TARGETS)
