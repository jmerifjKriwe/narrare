"""User-routing survivor guard — pins the system-default confinement list.

The user-routing migration
(docs/superpowers/plans/2026-09-01-user-routing-migration.md, Task 7) moved
every request-scoped, user-facing dependency factory from the operator-plane
pattern ``build_system_default_config(SystemModelCategory...)`` to the
per-user model-routing cascade. This guard pins the survivor set: running
the SAME sweep as the plan (``rg -ln build_system_default_config
apps/api/narrare/ | grep -v test``) must yield EXACTLY the sanctioned
constant.

- A NEW file adopting the legacy pattern for a user-facing dependency fails
  loudly (the assertion prints the unexpected file).
- Removing a sanctioned survivor without updating the constant also fails —
  the list is forced to stay honest.

The sweep logic itself is proven against tmp_path fixtures (adopter
detection, test-path exclusion, missing-survivor detection); exactly one
test runs the sweep against the real repo tree.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

#: Literal the plan's sweep greps for (the operator-plane model factory).
LEGACY_PATTERN = "build_system_default_config"

#: Sweep root of the plan's Task-7 command.
SWEEP_ROOT = "apps/api/narrare"

#: The ONLY files allowed to reference the legacy system-default factory.
#: Every entry needs a documented reason here — this constant is the
#: machine-checked version of the plan's "sanctioned survivors" list.
SANCTIONED_SYSTEM_DEFAULT_SURVIVORS: frozenset[str] = frozenset(
    {
        # The definition itself (ADR-071 operator fallback).
        "apps/api/narrare/_app/dependencies_services.py",
        # Documented operator plane: startup wiki listener in _app/lifespan.py
        # (no user context exists at lifespan startup) — plan Global
        # Constraints: "Operator plane stays".
        "apps/api/narrare/wiki/dependencies_core.py",
    }
)


def sweep_system_default_files(root: Path, sweep_root: str = SWEEP_ROOT) -> set[str]:
    """Return repo-relative posix paths under ``sweep_root`` hitting the pattern.

    Mirrors the plan's sweep command exactly: every ``*.py`` file whose path
    does NOT contain ``test`` (``grep -v test`` substring semantics) and whose
    text contains :data:`LEGACY_PATTERN` (``rg -ln`` literal match).
    """
    hits: set[str] = set()
    for path in (root / sweep_root).rglob("*.py"):
        rel = path.relative_to(root)
        if "test" in rel.as_posix():
            continue
        if LEGACY_PATTERN in path.read_text(encoding="utf-8"):
            hits.add(rel.as_posix())
    return hits


def _survivor_diff_message(actual: set[str]) -> str:
    """Format a +unexpected/-missing diff against the sanctioned constant."""
    unexpected = sorted(actual - SANCTIONED_SYSTEM_DEFAULT_SURVIVORS)
    missing = sorted(SANCTIONED_SYSTEM_DEFAULT_SURVIVORS - actual)
    lines = [
        "User-routing survivor guard violated: "
        "build_system_default_config file set drifted from the sanctioned constant.",
    ]
    if unexpected:
        lines.append(
            "  new legacy adopters (must migrate to the per-user "
            "model-routing cascade, or be sanctioned here with a reason):"
        )
        lines.extend(f"    + {p}" for p in unexpected)
    if missing:
        lines.append(
            "  sanctioned survivor removed (update the constant honestly — "
            "do not silently shrink it):"
        )
        lines.extend(f"    - {p}" for p in missing)
    return "\n".join(lines)


# ===========================================================================
# Sweep logic — proven against tmp_path fixtures (no real-repo I/O here).
# ===========================================================================


class TestSweepLogic:
    """The sweep detects adopters, excludes test paths, and notices removals."""

    def _tree(self, tmp_path: Path, files: dict[str, str]) -> Path:
        for rel, content in files.items():
            target = tmp_path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        return tmp_path

    def test_new_adopter_is_detected(self, tmp_path: Path) -> None:
        # A user-facing dependency file adopting the legacy pattern must show
        # up next to the sanctioned survivor — the loud-failure case.
        root = self._tree(
            tmp_path,
            {
                f"{SWEEP_ROOT}/_app/dependencies_services.py": (
                    f"def {LEGACY_PATTERN}(category):\n    return None\n"
                ),
                f"{SWEEP_ROOT}/writing/dependencies.py": (
                    f"from narrare._app.dependencies_services import {LEGACY_PATTERN}\n"
                ),
            },
        )
        assert sweep_system_default_files(root) == {
            f"{SWEEP_ROOT}/_app/dependencies_services.py",
            f"{SWEEP_ROOT}/writing/dependencies.py",
        }

    def test_test_paths_are_excluded(self, tmp_path: Path) -> None:
        # grep -v test: substring semantics — test_*.py, *_test.py and a
        # testing/ directory are all excluded (mirrors the plan's command).
        root = self._tree(
            tmp_path,
            {
                f"{SWEEP_ROOT}/test_dependencies.py": LEGACY_PATTERN,
                f"{SWEEP_ROOT}/dependencies_test_helper.py": LEGACY_PATTERN,
                f"{SWEEP_ROOT}/testing/x.py": LEGACY_PATTERN,
                f"{SWEEP_ROOT}/dependencies.py": "no pattern here\n",
            },
        )
        assert sweep_system_default_files(root) == set()

    def test_removed_survivor_is_detected(self, tmp_path: Path) -> None:
        # Only ONE sanctioned file present → the sweep must still report it,
        # proving the real-repo assertion fails on a silently removed survivor.
        root = self._tree(
            tmp_path,
            {f"{SWEEP_ROOT}/_app/dependencies_services.py": LEGACY_PATTERN},
        )
        assert sweep_system_default_files(root) == {
            f"{SWEEP_ROOT}/_app/dependencies_services.py",
        }

    def test_clean_tree_yields_empty_set(self, tmp_path: Path) -> None:
        root = self._tree(tmp_path, {f"{SWEEP_ROOT}/dependencies.py": "clean\n"})
        assert sweep_system_default_files(root) == set()

    def test_diff_message_lists_both_directions(self) -> None:
        message = _survivor_diff_message(
            {f"{SWEEP_ROOT}/rogue.py", f"{SWEEP_ROOT}/_app/dependencies_services.py"}
        )
        assert "+ apps/api/narrare/rogue.py" in message
        assert "- apps/api/narrare/wiki/dependencies_core.py" in message
        assert "apps/api/narrare/_app/dependencies_services.py" not in message.split("+")[0]


# ===========================================================================
# The real-repo pin — the guard itself.
# ===========================================================================


class TestRealRepoSurvivors:
    def test_survivor_set_matches_sanctioned_constant(self) -> None:
        actual = sweep_system_default_files(REPO_ROOT)
        assert actual == set(SANCTIONED_SYSTEM_DEFAULT_SURVIVORS), _survivor_diff_message(actual)
