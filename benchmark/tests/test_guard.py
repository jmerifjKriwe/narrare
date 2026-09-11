"""CI-isolation guard — root pytest collection must never include benchmark/.

ADR-083 carve-out: benchmark tests are manually-only
(``uv run pytest benchmark/tests/``). The root pytest configuration
implicitly excludes ``benchmark/`` because ``testpaths`` names only the
production test tree. This guard FAILS if ``benchmark`` ever appears in
the CI collection paths, or if ``testpaths`` grows beyond the sanctioned
roots without a deliberate guard update.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, cast

_REPO_ROOT = Path(__file__).resolve().parents[2]
"""Repository root (benchmark/tests/ → repo root)."""

_SANCTIONED_TESTPATHS = frozenset({"tests", "evals"})
"""Collection roots the CI pytest run may ever name.

``evals`` is sanctioned for symmetry with the evals area registration
precedent; ``benchmark`` must never be added here (ADR-083).
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
