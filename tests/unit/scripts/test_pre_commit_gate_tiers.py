"""Ratchet tests for the pre-commit hook tiering (throughput T8/T9).

T8 moved the whole-project hooks (``pyright``, ``pyright-tests``, ``bandit``,
``openapi-regenerate``, ``typecheck-frontend``) to ``pre-push``, parked
``adoption-score`` at ``manual`` and kept ``conventional-commits`` at
``commit-msg``. Those decisions were prose in the config until now: any later
edit could quietly move a slow hook back into the commit path. These tests pin
the tiering (the script under test is the same gate wired into
``just check-architecture``), including the two evasion paths that would
otherwise satisfy every stage rule: duplicating a hook id and deleting a
tiered hook outright.
"""

from __future__ import annotations

from pathlib import Path

from scripts.check_pre_commit_gate_tiers import find_tier_violations

BASE = """
repos:
  - repo: local
    hooks:
      - id: ruff-lint
        stages: [pre-commit]
      - id: pyright
        stages: [pre-push]
"""


def test_violation_when_a_new_hook_claims_pre_push() -> None:
    text = BASE + "      - id: sneaky\n        stages: [pre-push]\n"
    assert any("sneaky" in v for v in find_tier_violations(text))


def test_violation_when_a_moved_hook_returns_to_commit() -> None:
    text = BASE.replace(
        "      - id: pyright\n        stages: [pre-push]",
        "      - id: pyright\n        stages: [pre-commit]",
    )
    assert any("pyright" in v for v in find_tier_violations(text))


def test_violation_when_a_moved_hook_disappears_from_push() -> None:
    text = """
repos:
  - repo: local
    hooks:
      - id: openapi-regenerate
        stages: [pre-commit]
"""
    assert any("openapi-regenerate" in v for v in find_tier_violations(text))


def test_real_config_is_clean() -> None:
    root = Path(__file__).resolve().parents[3]
    assert (
        find_tier_violations((root / ".pre-commit-config.yaml").read_text(encoding="utf-8")) == []
    )


def test_violation_when_a_hook_id_is_declared_twice() -> None:
    """A duplicate id could carry two stage declarations and pass every tier rule."""
    text = BASE + "      - id: pyright\n        stages: [pre-push]\n"
    violations = find_tier_violations(text)
    assert any("duplicate" in v and "pyright" in v for v in violations)


def test_violation_when_a_tiered_hook_is_deleted() -> None:
    """Deleting a push-tiered hook must not satisfy the ratchet."""
    text = """
repos:
  - repo: local
    hooks:
      - id: typecheck-frontend
        stages: [pre-push]
"""
    violations = find_tier_violations(text)
    assert any("missing" in v and "bandit" in v for v in violations)
