"""CLI-level tests for ``scripts/check_module_coverage.py`` --update-baselines.

Focus: the ``--allow-removed`` escape hatch. Deliberate baseline-key
removals must be named on the command line, exactly one-for-one; anything
else aborts with exit code 1 and leaves the baselines file untouched.
Complements the model-level guard tests in ``test_coverage_model.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure scripts/ is on sys.path for the script imports.
_SCRIPTS = str(Path(__file__).resolve().parent.parent.parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import _coverage_model  # noqa: E402
import check_module_coverage  # noqa: E402
from _coverage_model import save_baselines  # noqa: E402


def _write_coverage_xml(path: Path, packages: dict[str, float]) -> None:
    """Write a minimal coverage.xml with one <package> per entry (line-rate
    given in percent, stored as a fraction as coverage.py does)."""
    entries = "".join(
        f'<package name="{name}" line-rate="{rate / 100}"></package>'
        for name, rate in packages.items()
    )
    path.write_text(
        f'<?xml version="1.0"?><coverage><packages>{entries}</packages></coverage>',
        encoding="utf-8",
    )


class TestAllowRemovedFlagParsing:
    """``--allow-removed`` parses as a raw comma-separated string."""

    def test_flag_defaults_to_empty_string(self) -> None:
        args = check_module_coverage.parse_args(["--coverage-xml", "x.xml"])
        assert args.allow_removed == ""

    def test_flag_accepts_comma_separated_keys(self) -> None:
        args = check_module_coverage.parse_args(
            ["--coverage-xml", "x.xml", "--allow-removed", "tasks, old_pkg"]
        )
        assert args.allow_removed == "tasks, old_pkg"


class TestUpdateBaselinesRemovalCli:
    """End-to-end ``--update-baselines`` runs against a temp baseline file."""

    @pytest.fixture
    def baseline_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        file = tmp_path / "coverage_baselines.json"
        monkeypatch.setattr(_coverage_model, "BASELINES_FILE", file)
        return file

    @pytest.fixture
    def coverage_xml(self, tmp_path: Path) -> Path:
        """coverage.xml seeing ``a`` and ``b`` — the dead ``tasks`` key is gone."""
        xml = tmp_path / "coverage.xml"
        _write_coverage_xml(xml, {"a": 90.0, "b": 80.0})
        return xml

    def test_removal_without_flag_fails_with_exit_1_and_untouched_file(
        self,
        baseline_file: Path,
        coverage_xml: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        save_baselines({"a": 90.0, "b": 80.0, "tasks": 50.0})
        before = baseline_file.read_bytes()

        rc = check_module_coverage.main(["--coverage-xml", str(coverage_xml), "--update-baselines"])

        assert rc == 1
        assert "Refusing to shrink" in capsys.readouterr().err
        assert baseline_file.read_bytes() == before

    def test_removal_with_exact_flag_succeeds_and_reports_removal(
        self,
        baseline_file: Path,
        coverage_xml: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        save_baselines({"a": 90.0, "b": 80.0, "tasks": 50.0})

        rc = check_module_coverage.main(
            [
                "--coverage-xml",
                str(coverage_xml),
                "--update-baselines",
                "--allow-removed",
                "tasks",
            ]
        )

        assert rc == 0
        out = capsys.readouterr().out
        assert "Removed 1 baseline key(s): tasks" in out
        assert _coverage_model.load_baselines() == {"a": 90.0, "b": 80.0}

    def test_removal_with_wrong_key_flag_fails(
        self,
        baseline_file: Path,
        coverage_xml: Path,
    ) -> None:
        save_baselines({"a": 90.0, "b": 80.0, "tasks": 50.0})
        before = baseline_file.read_bytes()

        rc = check_module_coverage.main(
            [
                "--coverage-xml",
                str(coverage_xml),
                "--update-baselines",
                "--allow-removed",
                "wrong_key",
            ]
        )

        assert rc == 1
        assert baseline_file.read_bytes() == before

    def test_update_without_removals_is_byte_level_noop(
        self,
        baseline_file: Path,
        coverage_xml: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Full-coverage rerun with no removals must leave the file untouched
        (no date flip, no reformatting — the no-drift smoke as a test)."""
        save_baselines({"a": 90.0, "b": 80.0})
        before = baseline_file.read_bytes()

        rc = check_module_coverage.main(["--coverage-xml", str(coverage_xml), "--update-baselines"])

        assert rc == 0
        assert baseline_file.read_bytes() == before
