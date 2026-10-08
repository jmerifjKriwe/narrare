# apps/api/narrare/settings/writing_goals.py
"""Novel writing-goal storage accessors (STATS-001 E5 — spec E-4/E-5).

``project_settings.writing_goals`` is a nullable JSONB column with the v1
shape ``{"target_words": int | null}`` (exactly one documented key; whole-
object replace semantics on PATCH — see the model comment and
``schemas_project_settings.WritingGoalsPayload``).

Two pieces, one responsibility each (RULE-06):

- :func:`parse_target_words` — the pure typed accessor for the v1 shape.
  Shape only: whatever int is stored passes through (including ≤ 0); the
  "no goal for non-positive targets" POLICY lives in the analytics service
  (``WritingQueryService._goal_block``, landed in E4).
- :class:`ProjectSettingsGoalSource` — the real ``GoalSource`` (E4 seam,
  ``analytics.contracts``): a pure adapter over the repository's read-only
  ``get_writing_goals`` read (RULE-08: SQL lives in ``repository.py``),
  swapped in at the DI factory (``analytics/dependencies.py``) for
  ``NullGoalSource`` — the service and router never change.

Read-only by design: the repository read this delegates to never
auto-creates a settings row (unlike ``ProjectSettingsRepository.get``).
``GET /analytics/writing`` must not write (the auto-create is only safe
behind the settings router's ownership gate, IDOR remediation S11a); a
novel without a settings row simply has no goal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    import uuid

    from narrare.settings.repository import ProjectSettingsRepository

#: The single documented v1 key inside the ``writing_goals`` JSONB object.
TARGET_WORDS_KEY = "target_words"


def parse_target_words(data: object | None) -> int | None:
    """Typed accessor for the v1 ``writing_goals`` shape.

    Returns the stored ``target_words`` int, or ``None`` when there is no
    goal to report: NULL column, empty object, explicit ``null`` target, a
    non-int value (bool excluded explicitly — ``bool ⊂ int``; floats,
    strings and lists are hand-edited/foreign rows), or a top-level
    non-dict row (JSONB is schemaless — corrupt values reach this accessor
    straight from the column). All corruption degrades to "no goal", never
    crashes the read — RULE-11 honesty at the boundary.
    """
    if not isinstance(data, dict):
        return None
    # Re-type the narrowed dict: isinstance narrows ``object`` to
    # ``dict[Unknown, Unknown]``; the v1 contract keys/values are precise.
    typed = cast("dict[str, object]", data)
    target = typed.get(TARGET_WORDS_KEY)
    if isinstance(target, bool) or not isinstance(target, int):
        return None
    return target


class ProjectSettingsGoalSource:
    """Reads a novel's goal target from ``project_settings.writing_goals``.

    Implements the ``GoalSource`` seam (analytics.contracts, spec E-4) as a
    pure adapter over the repository's read-only ``get_writing_goals`` —
    no SQL here (RULE-08), no caching (unset ⇒ goal block simply absent),
    same request session via the repository (one transaction).
    """

    def __init__(self, repo: ProjectSettingsRepository) -> None:
        self._repo = repo

    async def target_words(self, novel_id: uuid.UUID) -> int | None:
        """GoalSource seam — the novel's stored target, ``None`` = no goal."""
        return parse_target_words(await self._repo.get_writing_goals(novel_id))
