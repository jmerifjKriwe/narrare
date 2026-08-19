"""Tests for RULE-04 file-size classification in the architecture checker.

``scripts/architecture/_checkers/file_size.py`` (architecture-constraints
pre-commit gate) and ``scripts/check_python_file_size.py`` (python-size
ratchet gate) must classify files identically wherever their rules overlap.
The python-size gate checks the ``test_`` prefix FIRST (test hard limit 400)
before any suffix classification; the architecture checker previously had no
test rule at all, so ``test_*_service.py`` files were classified against the
service limit (300). The two RULE-04 gates therefore disagreed for
300 < lines <= 400 test service files: the pre-commit hook failed files the
python-size hook accepted (two C2 review findings, 2026-08-19; incident
shape: ``tests/unit/api/series/test_series_drift_persistence_service.py``).

The architecture checker must apply the test-prefix rule first, matching
``check_python_file_size.py`` classification order exactly.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.architecture._checkers.file_size import check_file_size  # noqa: E402
from scripts.architecture.helpers import load_config  # noqa: E402
from scripts.check_python_file_size import _limit_for  # noqa: E402


def _pyproject_limits() -> dict[str, int]:
    """Load the real ``[tool.narrare.architecture.file_size_limits]`` table.

    Using the live config (instead of a hand-mirrored dict) prevents the
    test's limit table from drifting away from pyproject.toml.
    """
    config: dict[str, Any] = load_config()
    raw: dict[str, Any] = config.get("file_size_limits", {}) or {}
    return {str(key): int(value) for key, value in raw.items()}


LIMITS = _pyproject_limits()

# Highest limit either gate can assign is 600 (scripts/); probe with headroom.
_PROBE_CEILING = 700


def _lines(count: int) -> list[str]:
    """Synthetic source of exactly ``count`` lines."""
    return [f"# line {i}" for i in range(count)]


def _effective_limit(rel_path: str, limits: dict[str, int] | None = None) -> int:
    """Black-box probe: the hard limit the architecture checker applies.

    Binary-searches the boundary; returns the largest line count that does
    NOT violate (a violation exists exactly when line_count > limit).
    """
    cfg = LIMITS if limits is None else limits
    assert check_file_size(rel_path, _lines(_PROBE_CEILING), cfg), (
        f"no violation at {_PROBE_CEILING} lines for {rel_path!r} — raise the probe ceiling"
    )
    lo, hi = 1, _PROBE_CEILING
    while lo < hi:
        mid = (lo + hi) // 2
        if check_file_size(rel_path, _lines(mid), cfg):
            hi = mid
        else:
            lo = mid + 1
    return lo - 1


class TestTestPrefixWinsOverSuffixes:
    """``test_*`` files hit the test limit (400), never a tighter suffix limit."""

    def test_test_service_file_at_350_lines_passes(self) -> None:
        """The defect: 350 lines with a service suffix must pass under the
        test limit of 400, not fail under the service limit of 300."""
        violations = check_file_size(
            "tests/unit/api/export/test_export_service.py", _lines(350), LIMITS
        )
        assert violations == []

    def test_test_service_file_at_400_lines_passes(self) -> None:
        violations = check_file_size(
            "tests/unit/api/export/test_export_service.py", _lines(400), LIMITS
        )
        assert violations == []

    def test_test_service_file_at_401_lines_violates_at_test_limit(self) -> None:
        violations = check_file_size(
            "tests/unit/api/export/test_export_service.py", _lines(401), LIMITS
        )
        assert len(violations) == 1
        assert violations[0].rule == "RULE-04"
        assert "hard limit: 400" in violations[0].detail

    def test_test_repo_file_gets_test_limit_not_repository(self) -> None:
        assert _effective_limit("tests/unit/x/test_draft_repo.py") == 400

    def test_test_agent_file_gets_test_limit_not_agent(self) -> None:
        assert _effective_limit("tests/unit/x/test_draft_agent.py") == 400

    def test_test_router_file_gets_test_limit_not_router(self) -> None:
        assert _effective_limit("tests/unit/x/test_router_drafts.py") == 400

    def test_incident_shape_series_drift_service_194_lines_passes(self) -> None:
        """The C2 incident shape: a 194-line test service file is clean."""
        violations = check_file_size(
            "tests/unit/api/series/test_series_drift_persistence_service.py",
            _lines(194),
            LIMITS,
        )
        assert violations == []


class TestServiceViolationsStillCaught:
    """Non-test service files keep the 300-line service limit."""

    def test_suffix_service_at_350_lines_violates(self) -> None:
        """A real ``*_service.py`` at 350 lines is still flagged."""
        violations = check_file_size(
            "apps/api/narrare/writing/draft_service.py", _lines(350), LIMITS
        )
        assert len(violations) == 1
        assert violations[0].rule == "RULE-04"
        assert "hard limit: 300" in violations[0].detail

    def test_exact_name_service_py_at_350_lines_violates(self) -> None:
        violations = check_file_size("apps/api/narrare/writing/service.py", _lines(350), LIMITS)
        assert len(violations) == 1
        assert "hard limit: 300" in violations[0].detail

    def test_service_file_at_300_lines_passes(self) -> None:
        assert check_file_size("apps/api/narrare/writing/service.py", _lines(300), LIMITS) == []


class TestConfigDrivenTestLimit:
    """The test limit is config-driven like every other category."""

    def test_limit_read_from_limits_dict(self) -> None:
        """A configured ``test`` limit overrides the SSOT value."""
        limits = dict(LIMITS, test=320)
        violations = check_file_size("tests/unit/x/test_export_service.py", _lines(350), limits)
        assert len(violations) == 1
        assert "hard limit: 320" in violations[0].detail


class TestGateParityWithPythonSizeGate:
    """Both RULE-04 gates must assign the same limit to overlapping shapes."""

    @pytest.mark.parametrize(
        "rel_path",
        [
            "tests/unit/api/series/test_series_drift_persistence_service.py",
            "tests/unit/api/settings/test_token_limits_service.py",
            "tests/unit/api/export/test_export_service.py",
            "apps/api/narrare/writing/service.py",
            "apps/api/narrare/writing/draft_service.py",
        ],
    )
    def test_architecture_limit_matches_python_size_gate(self, rel_path: str) -> None:
        _, py_gate_limit = _limit_for(Path(rel_path))
        assert _effective_limit(rel_path) == py_gate_limit


class TestUnifiedCategoryVocabulary:
    """2026-08-19 gate unification: the architecture checker applies the
    shared SSOT classifier (``scripts/architecture/file_size_limits.py``).
    These are the shapes where the two gates previously diverged."""

    # Router predicate: precise py-gate form — plural/gerund are NOT routers.
    def test_routers_py_gets_general_400_not_router(self) -> None:
        assert _effective_limit("apps/api/narrare/routers.py") == 400

    def test_routering_py_gets_general_400_not_router(self) -> None:
        assert _effective_limit("apps/api/narrare/routering.py") == 400

    def test_router_exact_and_prefix_stay_at_150(self) -> None:
        assert _effective_limit("apps/api/narrare/chat/router.py") == 150
        assert _effective_limit("apps/api/narrare/writing/router_drafts.py") == 150

    # Dependency category: previously default(400) in the arch checker.
    def test_deps_file_gets_200(self) -> None:
        assert _effective_limit("apps/api/narrare/writing/deps.py") == 200

    def test_dependencies_file_gets_200(self) -> None:
        assert _effective_limit("apps/api/narrare/series/dependencies.py") == 200

    def test_deps_prefixed_file_gets_200(self) -> None:
        assert _effective_limit("apps/api/narrare/writing/deps_writing.py") == 200

    # Script category: previously default(400) in the arch checker.
    def test_scripts_file_gets_600(self) -> None:
        assert _effective_limit("scripts/check_architecture.py") == 600

    def test_scripts_models_py_gets_script_600_not_models_200(self) -> None:
        assert _effective_limit("scripts/test_assertion_audit/models.py") == 600

    # Config/schema predicate: config.py/settings.py previously default(400).
    def test_config_py_gets_200(self) -> None:
        assert _effective_limit("apps/api/narrare/_app/config.py") == 200

    def test_settings_py_gets_200(self) -> None:
        assert _effective_limit("packages/core/narrare_core/settings.py") == 200

    # Arch-only categories retained at their (stricter) limits.
    def test_repository_files_get_250(self) -> None:
        assert _effective_limit("apps/api/narrare/writing/repository.py") == 250
        assert _effective_limit("tests/fakes/fake_chapter_repo.py") == 250

    def test_contracts_py_gets_200(self) -> None:
        assert _effective_limit("apps/api/narrare/writing/contracts.py") == 200

    def test_gateway_py_gets_300(self) -> None:
        assert _effective_limit("packages/core/narrare_core/llm/gateway.py") == 300

    def test_composer_py_gets_250(self) -> None:
        assert _effective_limit("packages/core/narrare_core/prompts/composer.py") == 250

    # Models: pyproject per-path entry (200) is the value authority.
    def test_models_py_gets_200(self) -> None:
        assert _effective_limit("apps/api/narrare/kb/models.py") == 200

    def test_architecture_limit_matches_python_size_gate_on_divergent_shapes(
        self,
    ) -> None:
        """Every previously-divergent shape now classifies identically."""
        shapes = [
            "apps/api/narrare/routers.py",
            "apps/api/narrare/routering.py",
            "apps/api/narrare/writing/deps_writing.py",
            "scripts/check_architecture.py",
            "scripts/test_assertion_audit/models.py",
            "apps/api/narrare/_app/config.py",
            "packages/core/narrare_core/settings.py",
            "apps/api/narrare/kb/models.py",
            "apps/api/narrare/writing/repository.py",
            "apps/api/narrare/writing/contracts.py",
            "packages/core/narrare_core/llm/gateway.py",
            "packages/core/narrare_core/prompts/composer.py",
        ]
        for rel_path in shapes:
            _, py_gate_limit = _limit_for(Path(rel_path))
            assert _effective_limit(rel_path) == py_gate_limit, rel_path


class TestInvalidLimitsTableReported:
    """An invalid/incomplete file_size_limits table is a loud RULE-04
    violation — never a silent fallback to hardcoded defaults (RULE-11)."""

    def test_partial_table_yields_config_violation(self) -> None:
        violations = check_file_size("apps/api/narrare/main.py", _lines(100), {"test": 400})
        assert len(violations) == 1
        assert violations[0].rule == "RULE-04"
        assert "file_size_limits" in violations[0].detail

    def test_full_table_with_override_still_config_driven(self) -> None:
        limits = dict(LIMITS, test=320)
        violations = check_file_size("tests/unit/x/test_export_service.py", _lines(350), limits)
        assert len(violations) == 1
        assert "hard limit: 320" in violations[0].detail

    def test_empty_table_falls_back_to_validated_pyproject_ssot(self) -> None:
        """``{}`` means "no override" — the pyproject SSOT applies."""
        assert check_file_size("apps/api/narrare/main.py", _lines(100), {}) == []
        assert _effective_limit("apps/api/narrare/main.py", limits={}) == 400


class TestLiveTreeGateParity:
    """The parity invariant, walked over the real repository tree.

    For every .py file in the UNION of both gates' scan scopes
    (apps/packages/scripts/tests/evals + root *.py), the limit the
    architecture checker applies must equal the (category, limit) the
    python-size gate computes. Classification is observed through each
    gate's production entry point — ``check_file_size`` (boundary probe)
    vs ``_limit_for`` — so a future re-localized predicate on either side
    trips this walk.
    """

    _SKIP_PARTS = frozenset(
        {
            "__pycache__",
            ".venv",
            ".git",
            "node_modules",
            ".next",
            "dist",
            "htmlcov",
            ".pytest_cache",
            "_scratch",
            "mutants",
            "migrations",
        }
    )

    def _iter_candidate_files(self) -> list[Path]:
        files: list[Path] = []
        for base in ("apps", "packages", "scripts", "tests", "evals"):
            base_dir = _ROOT / base
            if not base_dir.is_dir():
                continue
            for path in base_dir.rglob("*.py"):
                if path.name == "__init__.py":
                    continue
                rel = path.relative_to(_ROOT)
                if any(part in self._SKIP_PARTS for part in rel.parts):
                    continue
                if "alembic/versions" in rel.as_posix():
                    continue
                files.append(rel)
        for path in _ROOT.glob("*.py"):
            files.append(path.relative_to(_ROOT))
        return sorted(files)

    @pytest.mark.mutation_inert
    def test_both_gates_assign_identical_limits_across_repo_tree(self) -> None:
        from scripts.check_python_file_size import _limit_for

        files = self._iter_candidate_files()
        # Sanity: the walk must cover a real tree, not silently match nothing.
        assert len(files) > 500, "live-tree parity walk found suspiciously few files"

        mismatches: list[str] = []
        for rel in files:
            rel_str = rel.as_posix()
            _, py_gate_limit = _limit_for(_ROOT / rel)
            arch_limit = _effective_limit(rel_str)
            if arch_limit != py_gate_limit:
                mismatches.append(f"{rel_str}: arch={arch_limit} py-gate={py_gate_limit}")
        assert mismatches == [], (
            f"{len(mismatches)} files classified differently by the two "
            f"RULE-04 gates:\n" + "\n".join(mismatches[:20])
        )
