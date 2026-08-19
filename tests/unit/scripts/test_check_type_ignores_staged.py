"""Tests for scripts/check_type_ignores/staged.py — pre-commit staged scope.

``check_staged`` is tested through a fake :class:`StagedSource` (RULE-03
contract) so no git state is needed; ``GitStagedSource`` plumbing is
covered by one real-git test against a throwaway repository.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.check_type_ignores.staged import (  # noqa: E402
    SEVERITY_BUDGET,
    SEVERITY_ERROR,
    GitStagedSource,
    check_staged,
)


class FakeStagedSource:
    """In-memory StagedSource: repo-relative path → file content."""

    def __init__(self, files: list[tuple[str, str]]) -> None:
        self._files = files

    def staged_python_files(self) -> list[tuple[str, str]]:
        return self._files


def _baseline(files: dict[str, int]) -> dict[str, dict[str, int]]:
    return {"files": files}


class TestCheckStagedClean:
    """Clean staged files pass."""

    def test_no_staged_files_passes(self) -> None:
        report = check_staged(FakeStagedSource([]), _baseline({}))
        assert report.exit_code == 0
        assert report.scanned_files == 0
        assert report.findings == []

    def test_staged_file_without_suppressions_passes(self) -> None:
        report = check_staged(FakeStagedSource([("tests/unit/plain.py", "x = 1\n")]), _baseline({}))
        assert report.exit_code == 0

    def test_count_at_or_below_baseline_passes(self) -> None:
        content = "x = f()  # type: ignore[arg-type]\n"
        report = check_staged(
            FakeStagedSource([("tests/unit/a.py", content)]),
            _baseline({"tests/unit/a.py": 1}),
        )
        assert report.exit_code == 0

    def test_reduction_below_baseline_passes(self) -> None:
        report = check_staged(
            FakeStagedSource([("tests/unit/a.py", "x = 1\n")]),
            _baseline({"tests/unit/a.py": 3}),
        )
        assert report.exit_code == 0


class TestCheckStagedViolations:
    """Violations map to the documented severities."""

    def test_test_budget_growth_is_exit_1(self) -> None:
        content = "x = f()  # type: ignore[arg-type]\ny = g()  # type: ignore[arg-type]\n"
        report = check_staged(
            FakeStagedSource([("tests/unit/a.py", content)]),
            _baseline({"tests/unit/a.py": 1}),
        )
        assert report.exit_code == SEVERITY_BUDGET
        assert len(report.findings) == 1
        assert "exceed the per-file baseline 1 (+1)" in report.findings[0].message

    def test_new_test_file_with_suppressions_is_exit_1(self) -> None:
        content = "x = f()  # type: ignore[arg-type]\n"
        report = check_staged(
            FakeStagedSource([("tests/unit/new_file.py", content)]), _baseline({})
        )
        assert report.exit_code == SEVERITY_BUDGET

    def test_naked_ignore_in_staged_file_is_exit_2(self) -> None:
        report = check_staged(
            FakeStagedSource([("tests/unit/a.py", "x = f()  # type: ignore\n")]),
            _baseline({"tests/unit/a.py": 5}),
        )
        assert report.exit_code == SEVERITY_ERROR
        assert report.findings[0].message.startswith("naked")

    def test_uncommented_production_suppression_is_exit_2(self) -> None:
        content = "x = f()  # type: ignore[arg-type]\n"
        report = check_staged(
            FakeStagedSource([("apps/api/narrare/mod.py", content)]),
            _baseline({"apps/api/narrare/mod.py": 1}),
        )
        assert report.exit_code == SEVERITY_ERROR
        assert "without reason comment" in report.findings[0].message

    def test_reasoned_production_suppression_within_budget_passes(self) -> None:
        content = "x = f()  # type: ignore[arg-type]  # reason: stubs\n"
        report = check_staged(
            FakeStagedSource([("apps/api/narrare/mod.py", content)]),
            _baseline({"apps/api/narrare/mod.py": 1}),
        )
        assert report.exit_code == 0

    def test_production_growth_is_exit_2_even_with_reason(self) -> None:
        content = (
            "x = f()  # type: ignore[arg-type]  # reason: stubs\n"
            "y = g()  # type: ignore[arg-type]  # reason: stubs\n"
        )
        report = check_staged(
            FakeStagedSource([("apps/api/narrare/mod.py", content)]),
            _baseline({"apps/api/narrare/mod.py": 1}),
        )
        assert report.exit_code == SEVERITY_ERROR

    def test_error_outranks_budget_across_files(self) -> None:
        files = [
            ("tests/unit/a.py", "x = f()  # type: ignore[arg-type]\n"),
            ("apps/api/narrare/mod.py", "x = f()  # type: ignore\n"),
        ]
        report = check_staged(FakeStagedSource(files), _baseline({}))
        assert report.exit_code == SEVERITY_ERROR
        assert report.scanned_files == 2

    def test_docstring_prose_in_staged_file_is_not_a_suppression(self) -> None:
        content = '"""Never write ``# type: ignore[arg-type]`` for mocks."""\nx = 1\n'
        report = check_staged(FakeStagedSource([("tests/unit/a.py", content)]), _baseline({}))
        assert report.exit_code == 0


class TestGitStagedSource:
    """The git plumbing reads exactly the staged index content."""

    def test_staged_index_content_is_read_verbatim(self, tmp_path: Path) -> None:
        def git(*args: str) -> None:
            subprocess.run(
                ["git", *args],
                cwd=tmp_path,
                check=True,
                capture_output=True,
            )

        git("init", "-q")
        git("config", "user.email", "test@example.com")
        git("config", "user.name", "Test")

        staged_content = "x = f()  # type: ignore[arg-type]\n"
        (tmp_path / "staged.py").write_text(staged_content, encoding="utf-8")
        (tmp_path / "untracked.py").write_text("y = 2  # type: ignore\n", encoding="utf-8")
        git("add", "staged.py")

        source = GitStagedSource(cwd=tmp_path)
        files = source.staged_python_files()

        assert [name for name, _ in files] == ["staged.py"]
        assert files[0][1] == staged_content
