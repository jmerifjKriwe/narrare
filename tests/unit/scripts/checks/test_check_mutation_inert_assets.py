"""Unit tests for scripts/checks/check_mutation_inert_assets.py.

Covers the convention gate that prevents the MutMut crash documented in
GitHub issue #146: asset-reading tests under the MutMut scopes must carry
``@pytest.mark.mutation_inert``.
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]  # tests/unit/scripts/checks/ → repo root
_SCRIPT = _REPO_ROOT / "scripts" / "checks" / "check_mutation_inert_assets.py"


def _load_checker():
    """Load the checker as an isolated module (it lives outside a package)."""
    spec = importlib.util.spec_from_file_location("check_mutation_inert_assets", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_mutation_inert_assets"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def checker():
    return _load_checker()


def _write(tmp_path: Path, rel: str, body: str) -> Path:
    """Write a synthetic test file under tmp_path and return its path."""
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Synthetic fixtures — exact detection semantics
# ---------------------------------------------------------------------------


def test_clean_module_level_constant_marked_passes(checker, tmp_path: Path) -> None:
    """A test reading a repo asset via a module constant + marker → OK."""
    f = _write(
        tmp_path,
        "tests/unit/core/foo/test_ok.py",
        """
        from pathlib import Path
        import pytest

        REPO_ROOT = Path(__file__).resolve().parents[3]
        MANIFEST = REPO_ROOT / "scripts" / "architecture" / "prompt-surface-manifest.yaml"

        @pytest.mark.mutation_inert
        def test_reads_manifest() -> None:
            assert "intent" in MANIFEST.read_text()
        """,
    )
    assert checker._scan_file(f) == []


def test_clean_class_level_marker_passes(checker, tmp_path: Path) -> None:
    """A class whose methods read assets + class-level marker → OK."""
    f = _write(
        tmp_path,
        "tests/unit/core/foo/test_cls_ok.py",
        """
        from pathlib import Path
        import pytest

        REPO_ROOT = Path(__file__).resolve().parents[3]

        @pytest.mark.mutation_inert
        class TestManifest:
            def test_a(self) -> None:
                assert REPO_ROOT.joinpath("pyproject.toml").exists()

            def test_b(self) -> None:
                assert "x" in REPO_ROOT.joinpath("pyproject.toml").read_text()
        """,
    )
    assert checker._scan_file(f) == []


def test_clean_module_pytestmark_passes(checker, tmp_path: Path) -> None:
    """Module-level ``pytestmark`` covers every asset-reading test → OK."""
    f = _write(
        tmp_path,
        "tests/unit/core/foo/test_pym.py",
        """
        from pathlib import Path
        import pytest

        pytestmark = pytest.mark.mutation_inert
        REPO_ROOT = Path(__file__).resolve().parents[3]

        def test_reads() -> None:
            assert REPO_ROOT.joinpath("pyproject.toml").exists()
        """,
    )
    assert checker._scan_file(f) == []


def test_partial_class_marking_passes(checker, tmp_path: Path) -> None:
    """Only the asset-reading method needs the marker (mirrors test_observability)."""
    f = _write(
        tmp_path,
        "tests/unit/core/foo/test_partial.py",
        """
        from pathlib import Path
        import pytest

        REPO_ROOT = Path(__file__).resolve().parents[3]
        SRC = REPO_ROOT / "packages" / "core"

        class TestMixed:
            def test_does_not_read(self) -> None:
                assert 1 + 1 == 2

            @pytest.mark.mutation_inert
            def test_reads_source(self) -> None:
                assert SRC.exists()
        """,
    )
    assert checker._scan_file(f) == []


def test_inline_parents_with_marker_passes(checker, tmp_path: Path) -> None:
    """Inline ``parents[N]`` inside the test body + marker → OK (test_preview pattern)."""
    f = _write(
        tmp_path,
        "tests/unit/core/foo/test_inline_ok.py",
        """
        from pathlib import Path
        import pytest

        @pytest.mark.mutation_inert
        def test_inline() -> None:
            root = Path(__file__).resolve().parents[3]
            assert "packages/core" in str(root.joinpath("packages", "core"))
        """,
    )
    assert checker._scan_file(f) == []


def test_missing_marker_on_module_constant_is_flagged(checker, tmp_path: Path) -> None:
    """Asset-reading test via module constant WITHOUT marker → violation."""
    f = _write(
        tmp_path,
        "tests/unit/core/foo/test_bad_const.py",
        """
        from pathlib import Path
        import pytest

        REPO_ROOT = Path(__file__).resolve().parents[3]
        MANIFEST = REPO_ROOT / "scripts" / "architecture" / "prompt-surface-manifest.yaml"

        class TestManifest:
            def test_reads(self) -> None:
                assert "intent" in MANIFEST.read_text()
        """,
    )
    violations = checker._scan_file(f)
    assert len(violations) == 1
    v = violations[0]
    assert v.scope == "TestManifest"
    assert "mutation_inert" in v.detail


def test_missing_marker_on_helper_call_is_flagged(checker, tmp_path: Path) -> None:
    """Tests that read via an asset-reading helper, unmarked → violation.

    Mirrors the real test_dialogue_coach_template.py: a module-level
    ``TEMPLATE_PATH`` constant is read only inside ``_read_template()``,
    and the test methods merely call the helper.
    """
    f = _write(
        tmp_path,
        "tests/unit/core/foo/test_helper_bad.py",
        """
        from pathlib import Path
        import pytest

        TEMPLATE = (
            Path(__file__).resolve().parents[3]
            / "packages" / "core" / "narrare_core" / "prompts" / "_bundled" / "system.md"
        )

        def _read_template() -> str:
            return TEMPLATE.read_text()

        class TestTemplate:
            def test_a(self) -> None:
                assert "## System" in _read_template()
        """,
    )
    violations = checker._scan_file(f)
    assert len(violations) == 1
    assert violations[0].scope == "TestTemplate"


def test_missing_marker_on_inline_parents_is_flagged(checker, tmp_path: Path) -> None:
    """Inline ``parents[N]`` reading a repo asset, unmarked → violation."""
    f = _write(
        tmp_path,
        "tests/unit/core/foo/test_inline_bad.py",
        """
        from pathlib import Path

        def test_inline() -> None:
            root = Path(__file__).resolve().parents[3]
            assert root.joinpath("pyproject.toml").read_text()
        """,
    )
    violations = checker._scan_file(f)
    assert len(violations) == 1
    assert violations[0].scope == "test_inline"


def test_within_tests_fixture_not_flagged(checker, tmp_path: Path) -> None:
    """``parents[N]`` pointing at a tests/data fixture must NOT be flagged.

    The asset is inside the test tree → MutMut copies it → no crash. The
    repo-asset-literal gate excludes this case (no out-of-tests indicator).
    """
    f = _write(
        tmp_path,
        "tests/unit/core/foo/test_fixture.py",
        """
        from pathlib import Path

        def test_local_fixture() -> None:
            data = Path(__file__).resolve().parents[1] / "data" / "fixture.json"
            assert data.read_text().strip()
        """,
    )
    assert checker._scan_file(f) == []


def test_parents_without_repo_asset_not_flagged(checker, tmp_path: Path) -> None:
    """``parents[N]`` without any repo-asset indicator → not asset-reading."""
    f = _write(
        tmp_path,
        "tests/unit/core/foo/test_no_asset.py",
        """
        from pathlib import Path

        def test_something(tmp_path) -> None:
            parent = Path(__file__).resolve().parents[1]
            assert parent.name
        """,
    )
    assert checker._scan_file(f) == []


def test_non_test_file_ignored(checker, tmp_path: Path) -> None:
    """A helper module named ``utils.py`` is not scanned (only ``test_*.py``)."""
    _write(
        tmp_path,
        "tests/unit/core/foo/utils.py",
        """
        from pathlib import Path
        ROOT = Path(__file__).resolve().parents[3]
        VAL = ROOT.joinpath("pyproject.toml").read_text()
        """,
    )
    # _scan_file itself doesn't filter by name; find_violations does via rglob.
    scopes = [tmp_path / "tests" / "unit" / "core"]
    assert checker.find_violations(scopes) == []


def test_find_violations_scans_scope(checker, tmp_path: Path) -> None:
    """find_violations walks the scope and aggregates per-file violations."""
    _write(
        tmp_path,
        "tests/unit/core/sub/test_a.py",
        """
        from pathlib import Path
        ROOT = Path(__file__).resolve().parents[4]
        def test_reads() -> None:
            assert ROOT.joinpath("pyproject.toml").exists()
        """,
    )
    _write(
        tmp_path,
        "tests/unit/core/sub/test_b.py",
        """
        from pathlib import Path
        import pytest
        @pytest.mark.mutation_inert
        def test_marked() -> None:
            ROOT = Path(__file__).resolve().parents[4]
            assert ROOT.joinpath("pyproject.toml").exists()
        """,
    )
    scopes = [tmp_path / "tests" / "unit" / "core"]
    violations = checker.find_violations(scopes)
    assert len(violations) == 1
    assert violations[0].file.endswith("test_a.py")


def test_json_output(checker, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """``--json`` produces machine-readable output and exit code 1 on violation."""
    _write(
        tmp_path,
        "tests/unit/core/sub/test_bad.py",
        """
        from pathlib import Path
        ROOT = Path(__file__).resolve().parents[4]
        def test_reads() -> None:
            assert ROOT.joinpath("pyproject.toml").exists()
        """,
    )
    rc = checker.main(["--scopes", str(tmp_path / "tests" / "unit" / "core"), "--json"])
    assert rc == 1
    out = capsys.readouterr().out
    assert '"passed": false' in out
    assert "test_bad.py" in out


def test_no_violations_returns_zero(checker, tmp_path: Path) -> None:
    """A clean scope exits 0 with a success message."""
    _write(
        tmp_path,
        "tests/unit/core/sub/test_ok.py",
        """
        from pathlib import Path
        import pytest
        @pytest.mark.mutation_inert
        def test_ok() -> None:
            ROOT = Path(__file__).resolve().parents[4]
            assert ROOT.joinpath("pyproject.toml").exists()
        """,
    )
    rc = checker.main(["--scopes", str(tmp_path / "tests" / "unit" / "core")])
    assert rc == 0


def test_missing_scope_directory_skipped(checker, tmp_path: Path) -> None:
    """A non-existent scope directory is skipped, not an error."""
    missing = tmp_path / "does-not-exist"
    assert checker.find_violations([missing]) == []


# ---------------------------------------------------------------------------
# Real-repo regression — the two known violators from issue #146
# ---------------------------------------------------------------------------


def test_real_repo_dialogue_coach_tests_are_marked(checker) -> None:
    """The two former violators (issue #146) must now carry the marker.

    This is the integration guard: if the marker is ever removed from
    ``test_dialogue_coach_manifest.py`` or ``test_dialogue_coach_template.py``,
    this test (and the checker, and ``just check``) will fail again.
    """
    scopes = [
        _REPO_ROOT / "tests" / "unit" / "core",
        _REPO_ROOT / "tests" / "unit" / "api",
    ]
    violations = checker.find_violations(scopes)
    flagged_files = {v.file for v in violations}
    # These two files MUST be clean now. Listing them explicitly makes a
    # regression obvious in the failure message.
    for rel in (
        "tests/unit/core/prompts/test_dialogue_coach_manifest.py",
        "tests/unit/core/prompts/test_dialogue_coach_template.py",
    ):
        assert rel not in flagged_files, (
            f"{rel} regressed: missing @pytest.mark.mutation_inert (violations: {violations})"
        )
