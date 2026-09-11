"""CI-isolation governance test — benchmark/ is NEVER collected by CI testpaths.

Per the ADR-083 manually-only carve-out, the benchmark area runs outside CI
(``uv run pytest benchmark/tests/``). The root pytest configuration excludes
``benchmark/`` implicitly because ``testpaths`` names only the production
test tree. ``benchmark/tests/test_guard.py`` asserts the same contract, but
that file lives in the CI-excluded benchmark tree and therefore only runs
manually — this mirror lives INSIDE the CI-collected tree so the contract
is machine-enforced on every CI run.

Fails if ``benchmark/`` is added to the root ``testpaths``, or if
``testpaths`` grows beyond the sanctioned roots ``{tests, evals}``.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, cast

_REPO_ROOT = Path(__file__).resolve().parents[3]
"""Repository root (tests/unit/scripts/ → repo root)."""

_SANCTIONED_TESTPATHS = frozenset({"tests", "evals"})
"""Collection roots the CI pytest run may ever name.

``evals`` is sanctioned per the evals area registration precedent;
``benchmark`` must never be added here (ADR-083).
"""


def _root_testpaths() -> list[str]:
    """Return the root pytest ``testpaths`` list parsed from pyproject.toml."""
    with (_REPO_ROOT / "pyproject.toml").open("rb") as manifest:
        data: dict[str, Any] = tomllib.load(manifest)
    tool: dict[str, Any] = data.get("tool", {})
    pytest_config: dict[str, Any] = tool.get("pytest", {})
    ini_options: dict[str, Any] = pytest_config.get("ini_options", {})
    raw: object = ini_options.get("testpaths", [])
    assert isinstance(raw, list), (
        f"root testpaths must be a list, got {type(raw).__name__} — cannot guard"
    )
    entries = cast("list[Any]", raw)
    return [str(entry) for entry in entries]


def test_root_testpaths_exclude_benchmark() -> None:
    """benchmark/ must never be a root/CI pytest collection path."""
    testpaths = _root_testpaths()
    assert "benchmark" not in testpaths, (
        "benchmark/ appeared in root pytest testpaths — this violates the "
        f"ADR-083 manually-only carve-out (testpaths={testpaths!r})"
    )


def test_root_testpaths_only_cover_sanctioned_roots() -> None:
    """Root testpaths may only name the sanctioned CI collection roots."""
    testpaths = _root_testpaths()
    unknown = set(testpaths) - _SANCTIONED_TESTPATHS
    assert not unknown, (
        f"root testpaths grew beyond the sanctioned roots {{tests, evals}}: "
        f"{sorted(unknown)!r} — update this guard deliberately if a new CI "
        "collection root is added"
    )
