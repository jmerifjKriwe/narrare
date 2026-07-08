"""Tests for CURRENT_STATE volatility-policy SSOT checker."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_SCRIPTS = str(Path(__file__).resolve().parent.parent.parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import check_current_state_facts as checker  # noqa: E402


def _patch_checker_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    current_state_text: str,
) -> None:
    """Point checker globals at isolated temp files and stable old-style facts."""
    current_state_path = tmp_path / "CURRENT_STATE.md"
    current_state_path.write_text(current_state_text, encoding="utf-8")

    monkeypatch.setattr(checker, "CURRENT_STATE_PATH", current_state_path)


_VALID_AUTHORITY_CURRENT_STATE = """
# Narrare — Current State

`CURRENT_STATE.md` is a human status handoff, not a generated metrics registry.

- Architecture rules and exceptions: see `docs/_shared/CONSTRAINTS.md`.
- ADRs: see `docs/architecture/decisions/INDEX.md`.
- Feature specs: see `docs/features/INDEX.md`.
- Open questions: see `docs/architecture/questions/INDEX.md`.
- Adoption/runtime evidence: run `just check-adoption`.
- System health: run `just check-health`.
- Knowledge Graph shape/risk: use `code-review-graph_list_graph_stats_tool`.
"""


_OLD_STYLE_MATCHING_COUNT_CLAIMS = """
# Narrare — Current State

- Architecture rules: 23 rules
- ADRs: 47
- Feature specs: 99 individual files
- Features: 77 registered entries
- Exceptions: 14 in ai-gate-baseline.json and 10 in CONSTRAINTS.md §7
- Backend tests: passing across 653 test files
- Frontend tests: 186 test files (Vitest)
- Adoption: 109 ratcheted baseline items
- Open questions: 3 active (Q-001, Q-002, Q-011)
- Open questions: 9 resolved
"""


def test_current_state_with_authorities_and_no_volatile_counts_passes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CURRENT_STATE can omit generated counts when it links to authorities."""
    _patch_checker_environment(monkeypatch, tmp_path, _VALID_AUTHORITY_CURRENT_STATE)

    result = checker.main()

    output = capsys.readouterr().out
    assert result == 0
    assert "volatility policy" in output


def test_current_state_with_backend_test_file_count_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Backend/frontend test-file totals are volatile and must be reported."""
    current_state = (
        _VALID_AUTHORITY_CURRENT_STATE + "\n- Backend tests: passing across 653 test files\n"
    )
    _patch_checker_environment(monkeypatch, tmp_path, current_state)

    result = checker.main()

    output = capsys.readouterr().out
    assert result == 1
    assert "Backend/frontend test-file count" in output


def test_current_state_without_required_authorities_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Matching stale counts are not a substitute for authority links/commands."""
    _patch_checker_environment(monkeypatch, tmp_path, _OLD_STYLE_MATCHING_COUNT_CLAIMS)

    result = checker.main()

    output = capsys.readouterr().out
    assert result == 1
    assert "Missing required authority" in output
    assert "docs/_shared/CONSTRAINTS.md" in output
    assert "just check-health" in output
