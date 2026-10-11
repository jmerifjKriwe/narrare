"""MECHANICAL zero-write guard for the scene-AI surface (PLAN-001 FU-d).

T8 enforced SceneAIService's zero-DB-write property only BEHAVIORALLY
(fake call-recording + HTTP pin in ``test_scene_ai_guards.py``). This
module adds the missing mechanical enforcement: a source scan that fails
the suite the moment a repo/session write call appears in the scene-AI
modules — no test execution required to bite.

Scanned files (derived by GLOB, not hardcoded — a future scene-AI module
matching ``scene_ai*.py`` / ``_scene_ai*.py`` in
``apps/api/narrare/planning/`` is auto-covered): the scan set is asserted
non-empty and to contain the three known modules, so the glob can neither
silently match nothing nor silently drop a known module:
- ``apps/api/narrare/planning/scene_ai_service.py``
- ``apps/api/narrare/planning/_scene_ai_support.py``
- ``apps/api/narrare/planning/_scene_ai_factory.py``

Deny-list (conservative — every entry is an unambiguous DB write on a
repo/session object; nothing else):
- ``.bulk_replace(`` — ScenePlanRepository aggregate-PUT write (the one
  write method the whole zero-write design routes AROUND)
- ``.create(`` / ``.update(`` / ``.save(`` — repo-verb writes on the
  still-injected novel/chapter repos (persist new rows / mutate rows /
  save detached state)
- ``.add(`` / ``.add_all(`` — ``AsyncSession.add/add_all`` staging
- ``.merge(`` — ``AsyncSession.merge`` (write + SELECT)
- ``.delete(`` — ``AsyncSession.delete`` / ORM collection delete
- ``.flush(`` — ``AsyncSession.flush`` (pushes staged writes to SQL)
- ``.commit(`` — ``AsyncSession.commit`` (the transaction boundary)
- ``session.execute(`` — raw SQL execution (also matches
  ``self._session.execute(``); services must never touch a session —
  only repositories do (layered architecture).

Allow-list rationale — deliberately NOT denied (read surface): the
service touches the injected novel/chapter repos ONLY through
``get_by_id``-class reads (``novel_repo.get_by_id``,
``chapter_repo.get_by_id`` — the ownership guards), plus
``.list_by_chapter``/``.list_by_novel``-style reads elsewhere in the
family; ``.resolve(``, ``.prepare(``, ``.build(``, ``.run(`` are the
composer/registry/agent seams — none of them persist anything. Denying
read-shaped or infrastructure-shaped calls would make the guard
false-positive on the legitimate code path and get disabled; a guard
that never runs guards nothing.

Scope note: the scan covers comments and docstrings too (any occurrence
counts) — keeping the check a plain substring scan makes it mechanical
and immune to AST-escape tricks; prose mentioning write calls belongs in
docs, not in these modules.

Companion behavioral proof: ``test_scene_ai_guards.py::TestZeroWrites``
(records that the runtime path performs no writes); this module pins the
SOURCE so a future write cannot even land unnoticed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]

_REVIEW_GLOBS: tuple[str, ...] = ("scene_ai*.py", "_scene_ai*.py")
_PLANNING_DIR = REPO_ROOT / "apps" / "api" / "narrare" / "planning"

# Known scene-AI modules — the glob MUST keep matching these (guards
# against the scan set silently going empty or dropping a module).
_KNOWN_SCENE_AI_MODULES: frozenset[str] = frozenset(
    {
        "scene_ai_service.py",
        "_scene_ai_support.py",
        "_scene_ai_factory.py",
    }
)


def _scene_ai_sources() -> list[Path]:
    """Derive the scene-AI scan set from the planning directory by glob."""
    files: set[Path] = set()
    for pattern in _REVIEW_GLOBS:
        files.update(_PLANNING_DIR.glob(pattern))
    return sorted(files)


_WRITE_PATTERNS: tuple[str, ...] = (
    ".bulk_replace(",
    ".create(",
    ".update(",
    ".save(",
    ".add(",
    ".add_all(",
    ".merge(",
    ".delete(",
    ".flush(",
    ".commit(",
    "session.execute(",
)


@pytest.mark.mutation_inert
class TestSceneAiZeroWriteStaticGuard:
    """Source-scan regression guard: no repo/session write calls, ever.

    ``mutation_inert``: these are static assertions on committed repo-root
    sources reached via ``parents[4]``. They cannot kill a source-code
    mutant by construction, and the path resolves to a non-existent
    location inside MutMut's ``mutants/`` sandbox, which would crash the
    mutation run (issue #146).
    """

    def test_scan_set_is_non_empty_and_covers_known_modules(self) -> None:
        """The glob-derived scan set never matches air, drops no module.

        Guards the guard: a scan set that silently became empty (renamed
        directory, typo'd glob) or lost a known module would turn the
        zero-write guard into a no-op while staying green.
        """
        sources = _scene_ai_sources()
        names = {path.name for path in sources}
        assert sources, "scene-AI glob matched nothing — the guard would scan air"
        missing = _KNOWN_SCENE_AI_MODULES - names
        assert not missing, f"known scene-AI modules fell outside the scan set: {sorted(missing)}"

    def test_scene_ai_sources_contain_no_repo_or_session_write_calls(self) -> None:
        """Every scene-AI source file is free of deny-list write patterns.

        Failure names the exact file, line number, and matched pattern so
        the offending call can be removed without hunting.
        """
        offenses: list[str] = []

        for path in _scene_ai_sources():
            assert path.is_file(), f"scene-AI source vanished from the scan set: {path}"
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                for pattern in _WRITE_PATTERNS:
                    if pattern in line:
                        offenses.append(f"{path.name}:{lineno}: {pattern!r} → {line.strip()}")

        assert offenses == [], (
            "Scene-AI surface must be zero-DB-write (spec §5.2): proposals "
            "return to the client and are applied via the aggregate PUT. "
            "Found write-call patterns:\n" + "\n".join(offenses)
        )
