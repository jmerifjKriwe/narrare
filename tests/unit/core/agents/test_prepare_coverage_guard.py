"""Structural guard — no bare ``get_model()`` resolution in API production code.

Task 7 of the pydantic-ai structural fixes plan closes the last bare
``registry.get_model(...)`` call sites in ``apps/api/narrare/`` (beta
reader x2, prompt live-test x1). This guard keeps the tree closed:
every model resolution in API production code must go through the
single assembly point ``ModelRegistry.prepare()`` (Task 4), never
through a bare ``get_model()`` call.

Detection is AST-based (not regex over raw text), so docstrings,
comments, and string literals cannot produce false positives — only
real ``.get_model(...)`` call expressions are flagged.

Sanctioned exceptions (mechanism kept explicit; the set is currently
EMPTY):

- ``setup/provider_service.py`` ``_test_call``: sanctioned leave-as-is
  (6d assessment) — it validates a RAW user-supplied key/model/endpoint
  BEFORE any ``ResolvedModelConfig`` exists, so ``prepare()`` would
  require fabricating a config (workaround). It builds its own bare
  ``Agent`` (ADR-015 allow-agent) and performs NO registry resolution,
  hence there is no ``get_model`` call to sanction.
- wiki core path (``WikiGenerationAgent``): the settings pass-through
  gap lives in ``packages/core`` — OUTSIDE the scanned root
  (``apps/api/narrare/``), so it cannot trip this guard; it is pinned
  by the skipped test in ``tests/unit/api/wiki/test_wiki_prepare_wiring.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# Every test reads committed repo-root assets via ``parents[N]`` — excluded
# from MutMut runs (sandbox resolves parents[N] differently, issue #146).
pytestmark = pytest.mark.mutation_inert

_REPO_ROOT = Path(__file__).resolve().parents[4]
_API_ROOT = _REPO_ROOT / "apps" / "api" / "narrare"

# Files (relative to apps/api/narrare/) where a bare ``.get_model(``
# call expression is sanctioned. Currently empty — see module docstring
# for why setup/_test_call and the wiki core path do NOT need entries.
_SANCTIONED_BARE_GET_MODEL: frozenset[str] = frozenset()


def _bare_get_model_calls(path: Path) -> list[int]:
    """Return the line numbers of bare ``.get_model(...)`` call expressions."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get_model"
    ]


def test_api_root_contains_production_files() -> None:
    """Guard sanity: the scanned root must exist and contain Python files."""
    assert _API_ROOT.is_dir()
    assert any(_API_ROOT.rglob("*.py"))


def test_no_bare_get_model_calls_in_api_production_code() -> None:
    """Every model resolution under apps/api/narrare/ goes through prepare()."""
    violations: dict[str, list[int]] = {}
    scanned = 0
    for path in sorted(_API_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        scanned += 1
        rel = path.relative_to(_API_ROOT).as_posix()
        if rel in _SANCTIONED_BARE_GET_MODEL:
            continue
        lines = _bare_get_model_calls(path)
        if lines:
            violations[rel] = lines
    assert scanned > 0, "sanity: production tree was scanned"
    assert not violations, (
        "Bare ModelRegistry.get_model() call sites found — resolve via "
        f"ModelRegistry.prepare() (single assembly point, Task 4): {violations}"
    )


def test_sanctioned_exceptions_exist_on_disk() -> None:
    """Sanctioned paths must reference real files (guards against drift)."""
    for rel in _SANCTIONED_BARE_GET_MODEL:
        assert (_API_ROOT / rel).is_file(), f"sanctioned exception not on disk: {rel}"
