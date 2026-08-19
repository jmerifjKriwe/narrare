"""Tests for scripts/check_python_file_size.py — core logic.

Covers file category detection (_limit_for), exclusion rules (_should_skip),
line counting (_count_lines), and violation collection (collect_violations).
Scan-roots parity with the architecture gate lives in
test_gate_scan_root_parity.py (RULE-04 split, 2026-08-19).
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.check_python_file_size import (  # noqa: E402
    FileSizeViolation,
    _count_lines,
    _limit_for,
    _should_skip,
    collect_violations,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_py_file(tmp_path: Path, rel: str, content: str) -> Path:
    """Create a .py file at the relative path under tmp_path."""
    target = tmp_path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def _lines_content(n: int) -> str:
    """Generate n lines of Python content."""
    return "\n".join(f"# line {i}" for i in range(n)) + "\n"


# ---------------------------------------------------------------------------
# Tests: _limit_for
# ---------------------------------------------------------------------------


class TestLimitFor:
    """File category and limit detection."""

    def test_general_python_gets_400(self, tmp_path: Path) -> None:
        path = tmp_path / "utils.py"
        kind, limit = _limit_for(path, tmp_path)
        assert kind == "general"
        assert limit == 400

    def test_router_py_gets_150(self, tmp_path: Path) -> None:
        kind, limit = _limit_for(tmp_path / "router.py", tmp_path)
        assert kind == "router"
        assert limit == 150

    def test_router_subname_gets_150(self, tmp_path: Path) -> None:
        kind, limit = _limit_for(tmp_path / "router_drafts.py", tmp_path)
        assert kind == "router"
        assert limit == 150

    def test_dependencies_py_gets_200(self, tmp_path: Path) -> None:
        kind, limit = _limit_for(tmp_path / "dependencies.py", tmp_path)
        assert kind == "dependency"
        assert limit == 200

    def test_deps_py_gets_200(self, tmp_path: Path) -> None:
        kind, limit = _limit_for(tmp_path / "deps.py", tmp_path)
        assert kind == "dependency"
        assert limit == 200

    def test_deps_subname_gets_200(self, tmp_path: Path) -> None:
        kind, limit = _limit_for(tmp_path / "deps_kb.py", tmp_path)
        assert kind == "dependency"
        assert limit == 200

    def test_service_py_gets_300(self, tmp_path: Path) -> None:
        kind, limit = _limit_for(tmp_path / "service.py", tmp_path)
        assert kind == "service"
        assert limit == 300

    def test_sub_service_py_gets_300(self, tmp_path: Path) -> None:
        kind, limit = _limit_for(tmp_path / "draft_service.py", tmp_path)
        assert kind == "service"
        assert limit == 300

    def test_agent_py_gets_200(self, tmp_path: Path) -> None:
        kind, limit = _limit_for(tmp_path / "agent.py", tmp_path)
        assert kind == "agent"
        assert limit == 200

    def test_sub_agent_py_gets_200(self, tmp_path: Path) -> None:
        kind, limit = _limit_for(tmp_path / "writing_agent.py", tmp_path)
        assert kind == "agent"
        assert limit == 200

    def test_config_py_gets_200(self, tmp_path: Path) -> None:
        kind, limit = _limit_for(tmp_path / "config.py", tmp_path)
        assert kind == "config_schema"
        assert limit == 200

    def test_schemas_py_gets_200(self, tmp_path: Path) -> None:
        kind, limit = _limit_for(tmp_path / "schemas.py", tmp_path)
        assert kind == "config_schema"
        assert limit == 200

    def test_sub_schemas_py_gets_200(self, tmp_path: Path) -> None:
        kind, limit = _limit_for(tmp_path / "kb_schemas.py", tmp_path)
        assert kind == "config_schema"
        assert limit == 200

    def test_models_py_gets_200(self, tmp_path: Path) -> None:
        """2026-08-19 gate unification: models limit reconciled to the
        pyproject per-path SSOT value (200), previously 500 here."""
        kind, limit = _limit_for(tmp_path / "models.py", tmp_path)
        assert kind == "models"
        assert limit == 200

    def test_test_file_gets_400(self, tmp_path: Path) -> None:
        kind, limit = _limit_for(tmp_path / "test_service.py", tmp_path)
        assert kind == "test"
        assert limit == 400

    def test_scripts_get_600(self, tmp_path: Path) -> None:
        path = tmp_path / "scripts" / "check_something.py"
        kind, limit = _limit_for(path, tmp_path)
        assert kind == "script"
        assert limit == 600

    def test_settings_py_gets_200(self, tmp_path: Path) -> None:
        kind, limit = _limit_for(tmp_path / "settings.py", tmp_path)
        assert kind == "config_schema"
        assert limit == 200


class TestUnifiedCategoryVocabulary:
    """2026-08-19 gate unification: the python-size gate consumes the shared
    SSOT classifier (scripts/architecture/file_size_limits.py) and thereby
    gains the architecture checker's categories (repository, contracts,
    gateway, composer) and its precise router predicate."""

    def test_routers_py_is_general_not_router(self, tmp_path: Path) -> None:
        """Router predicate reconciled to the precise form: routers.py /
        routering.py are NOT router files (previously router/150 only in
        the architecture checker via an overbroad prefix match)."""
        kind, limit = _limit_for(tmp_path / "routers.py", tmp_path)
        assert kind == "general"
        assert limit == 400

    def test_repo_suffix_gets_250(self, tmp_path: Path) -> None:
        kind, limit = _limit_for(tmp_path / "draft_repo.py", tmp_path)
        assert kind == "repository"
        assert limit == 250

    def test_repository_exact_gets_250(self, tmp_path: Path) -> None:
        kind, limit = _limit_for(tmp_path / "repository.py", tmp_path)
        assert kind == "repository"
        assert limit == 250

    def test_contracts_py_gets_200(self, tmp_path: Path) -> None:
        kind, limit = _limit_for(tmp_path / "contracts.py", tmp_path)
        assert kind == "contracts"
        assert limit == 200

    def test_gateway_py_gets_300(self, tmp_path: Path) -> None:
        kind, limit = _limit_for(tmp_path / "gateway.py", tmp_path)
        assert kind == "gateway"
        assert limit == 300

    def test_composer_py_gets_250(self, tmp_path: Path) -> None:
        kind, limit = _limit_for(tmp_path / "composer.py", tmp_path)
        assert kind == "composer"
        assert limit == 250

    def test_scripts_models_py_is_script_not_models(self, tmp_path: Path) -> None:
        """Path-based script rule (600) has priority over name rules."""
        kind, limit = _limit_for(tmp_path / "scripts" / "models.py", tmp_path)
        assert kind == "script"
        assert limit == 600

    def test_repo_file_over_limit_detected(self, tmp_path: Path) -> None:
        _make_py_file(tmp_path, "apps/draft_repo.py", _lines_content(251))
        violations = collect_violations(tmp_path)
        assert len(violations) == 1
        assert violations[0].kind == "repository"
        assert violations[0].limit == 250


# ---------------------------------------------------------------------------
# Tests: _should_skip
# ---------------------------------------------------------------------------


class TestShouldSkip:
    """Exclusion rules for files."""

    def test_init_py_skipped(self, tmp_path: Path) -> None:
        assert _should_skip(tmp_path / "__init__.py", tmp_path)

    def test_alembic_versions_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "alembic" / "versions" / "0001_initial.py"
        assert _should_skip(path, tmp_path)

    def test_pycache_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "__pycache__" / "module.cpython-314.pyc"
        assert "__pycache__" in path.parts

    def test_regular_file_not_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "service.py"
        assert not _should_skip(path, tmp_path)

    def test_test_file_not_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "test_service.py"
        assert not _should_skip(path, tmp_path)

    def test_dot_venv_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / ".venv" / "lib" / "something.py"
        assert _should_skip(path, tmp_path)

    def test_scratch_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "_scratch" / "something.py"
        assert _should_skip(path, tmp_path)


# ---------------------------------------------------------------------------
# Tests: _count_lines
# ---------------------------------------------------------------------------


class TestCountLines:
    """Line counting includes all lines (blank, comments, code)."""

    def test_counts_all_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "test.py"
        path.write_text("line1\nline2\nline3\n", encoding="utf-8")
        assert _count_lines(path) == 3

    def test_counts_blank_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "test.py"
        path.write_text("line1\n\n\nline2\n", encoding="utf-8")
        assert _count_lines(path) == 4

    def test_empty_file_is_zero(self, tmp_path: Path) -> None:
        path = tmp_path / "test.py"
        path.write_text("", encoding="utf-8")
        assert _count_lines(path) == 0

    def test_single_newline_is_one(self, tmp_path: Path) -> None:
        path = tmp_path / "test.py"
        path.write_text("\n", encoding="utf-8")
        assert _count_lines(path) == 1


# ---------------------------------------------------------------------------
# Tests: collect_violations
# ---------------------------------------------------------------------------


class TestCollectViolations:
    """Integration test: create files, check violations."""

    def test_no_violations_when_under_limit(self, tmp_path: Path) -> None:
        _make_py_file(tmp_path, "apps/service.py", _lines_content(50))
        violations = collect_violations(tmp_path)
        assert len(violations) == 0

    def test_router_over_limit_detected(self, tmp_path: Path) -> None:
        _make_py_file(tmp_path, "apps/router.py", _lines_content(200))
        violations = collect_violations(tmp_path)
        assert len(violations) == 1
        assert violations[0].kind == "router"
        assert violations[0].lines == 200
        assert violations[0].limit == 150

    def test_service_over_limit_detected(self, tmp_path: Path) -> None:
        _make_py_file(tmp_path, "apps/service.py", _lines_content(350))
        violations = collect_violations(tmp_path)
        assert len(violations) == 1
        assert violations[0].kind == "service"
        assert violations[0].limit == 300

    def test_init_py_not_checked(self, tmp_path: Path) -> None:
        _make_py_file(tmp_path, "apps/__init__.py", _lines_content(500))
        violations = collect_violations(tmp_path)
        assert len(violations) == 0

    def test_alembic_versions_not_checked(self, tmp_path: Path) -> None:
        _make_py_file(tmp_path, "alembic/versions/0001.py", _lines_content(800))
        violations = collect_violations(tmp_path)
        assert len(violations) == 0

    def test_multiple_violations_collected(self, tmp_path: Path) -> None:
        _make_py_file(tmp_path, "apps/router.py", _lines_content(200))
        _make_py_file(tmp_path, "apps/service.py", _lines_content(350))
        violations = collect_violations(tmp_path)
        assert len(violations) == 2

    def test_scripts_get_higher_limit(self, tmp_path: Path) -> None:
        _make_py_file(tmp_path, "scripts/check_stuff.py", _lines_content(500))
        violations = collect_violations(tmp_path)
        assert len(violations) == 0

    def test_scripts_over_600_detected(self, tmp_path: Path) -> None:
        _make_py_file(tmp_path, "scripts/check_stuff.py", _lines_content(650))
        violations = collect_violations(tmp_path)
        assert len(violations) == 1
        assert violations[0].kind == "script"
        assert violations[0].limit == 600

    def test_test_file_at_limit_passes(self, tmp_path: Path) -> None:
        _make_py_file(tmp_path, "tests/test_example.py", _lines_content(400))
        violations = collect_violations(tmp_path)
        assert len(violations) == 0

    def test_test_file_over_limit_detected(self, tmp_path: Path) -> None:
        _make_py_file(tmp_path, "tests/test_example.py", _lines_content(401))
        violations = collect_violations(tmp_path)
        assert len(violations) == 1
        assert violations[0].kind == "test"
        assert violations[0].limit == 400

    def test_dependency_file_over_limit(self, tmp_path: Path) -> None:
        _make_py_file(tmp_path, "apps/dependencies.py", _lines_content(250))
        violations = collect_violations(tmp_path)
        assert len(violations) == 1
        assert violations[0].kind == "dependency"
        assert violations[0].limit == 200

    def test_deps_file_over_limit(self, tmp_path: Path) -> None:
        _make_py_file(tmp_path, "apps/deps.py", _lines_content(250))
        violations = collect_violations(tmp_path)
        assert len(violations) == 1
        assert violations[0].kind == "dependency"
        assert violations[0].limit == 200

    def test_models_at_reconciled_limit(self, tmp_path: Path) -> None:
        _make_py_file(tmp_path, "apps/models.py", _lines_content(200))
        violations = collect_violations(tmp_path)
        assert len(violations) == 0

    def test_models_over_reconciled_limit(self, tmp_path: Path) -> None:
        _make_py_file(tmp_path, "apps/models.py", _lines_content(201))
        violations = collect_violations(tmp_path)
        assert len(violations) == 1
        assert violations[0].kind == "models"
        assert violations[0].limit == 200


# ---------------------------------------------------------------------------
# Tests: FileSizeViolation.fingerprint
# ---------------------------------------------------------------------------


class TestFingerprint:
    """Fingerprints are stable and exclude line counts."""

    def test_stable_fingerprint(self) -> None:
        v1 = FileSizeViolation(path=Path("apps/service.py"), lines=350, limit=300, kind="service")
        v2 = FileSizeViolation(path=Path("apps/service.py"), lines=340, limit=300, kind="service")
        # Same file/kind/limit → same fingerprint (lines excluded)
        assert v1.fingerprint() == v2.fingerprint()

    def test_different_file_different_fingerprint(self) -> None:
        v1 = FileSizeViolation(path=Path("apps/service.py"), lines=350, limit=300, kind="service")
        v2 = FileSizeViolation(path=Path("apps/other.py"), lines=350, limit=300, kind="service")
        assert v1.fingerprint() != v2.fingerprint()

    def test_different_kind_different_fingerprint(self) -> None:
        v1 = FileSizeViolation(path=Path("apps/file.py"), lines=350, limit=300, kind="service")
        v2 = FileSizeViolation(path=Path("apps/file.py"), lines=350, limit=150, kind="router")
        assert v1.fingerprint() != v2.fingerprint()
