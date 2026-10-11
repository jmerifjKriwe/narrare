"""Pure helpers for ADR-050 cross-feature reference indexing.

PLAN-001 T15 (ADR-096, spec §7): the storyboard scan reads scene plans —
the shared :func:`iter_scene_texts` from planning's public surface
(RULE-05: cross-domain via public export) replaces the legacy beat scan.
Locations are ``scene_plans[{id}].{field}`` and are NEVER rewritten
(RULE-22 §7 — user content).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Literal, cast

from narrare.planning import iter_scene_texts
from narrare_core.context.integration_contracts import (
    ContradictionReason,
    RefIntegrityIssue,
    RefResolutionStatus,
)
from narrare_core.shared.frontmatter import parse_frontmatter

if TYPE_CHECKING:
    from narrare.chapters.models import Chapter
    from narrare.planning.models import ChapterOutline, ScenePlan


_FRONTMATTER_REF_KEYS = frozenset(
    {
        "pov_character",
        "characters",
        "location",
        "locations",
        "faction",
        "factions",
        "system",
        "systems",
        "timeline",
        "timelines",
    }
)


def chapter_ref_values(chapter: Chapter) -> list[tuple[str, object]]:
    """Return structured chapter-frontmatter ref locations and values."""
    refs: list[tuple[str, object]] = []
    parsed = parse_frontmatter(chapter.content)
    if parsed.has_frontmatter:
        for key, value in parsed.metadata.items():
            if key in _FRONTMATTER_REF_KEYS:
                refs.append((f"chapters[{chapter.id}].frontmatter.{key}", value))
    pov_character_id = getattr(chapter, "pov_character_id", "")
    if isinstance(pov_character_id, str) and pov_character_id:
        refs.append((f"chapters[{chapter.id}].pov_character_id", pov_character_id))
    return refs


def storyboard_notes_texts(outline: ChapterOutline) -> list[tuple[str, str]]:
    """Return the outline's free-text notes location (storyboard scan).

    PLAN-001 T15 (spec §7): the beat scan was replaced by the scene-plan
    scan (:func:`scene_texts`); ``outline_notes`` remains storyboard free
    text that may contain KB names.
    """
    if outline.outline_notes:
        return [(f"chapter_outlines[{outline.id}].outline_notes", outline.outline_notes)]
    return []


def scene_texts(scene: ScenePlan) -> list[tuple[str, str]]:
    """Return scene-plan text locations that may contain KB names (spec §7).

    Delegates to planning's shared :func:`iter_scene_texts` — ONE scan
    definition for every consumer (kb lifecycle + ref-index). Locations
    use the ``scene_plans[{id}].{field}`` form; entries are NEVER
    rewritten (RULE-22 §7 — user content).
    """
    return iter_scene_texts(scene)


def parse_uuid(value: str) -> uuid.UUID | None:
    """Parse a UUID string, returning None for non-UUID legacy refs."""
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def iter_scalar_refs(value: object) -> list[str]:
    """Flatten supported scalar ref shapes into strings."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        # YAML/JSON containers are runtime-shaped; cast after the guard so
        # iterating over them remains type-safe.
        items = cast("list[object]", value)
        return [item for item in items if isinstance(item, str)]
    if isinstance(value, dict):
        # Hybrid refs may be {id, name}; parse both scalar fields.
        mapping = cast("dict[object, object]", value)
        refs: list[str] = []
        for key in ("id", "name"):
            item = mapping.get(key)
            if isinstance(item, str):
                refs.append(item)
        return refs
    return []


def build_ref_issue(
    *,
    consumer_feature: str,
    location: str,
    ref_kind: Literal["id", "name"],
    ref_value: str,
    resolved_status: RefResolutionStatus,
    reason: ContradictionReason,
    suggested_action: Literal[
        "remap_to_canonical",
        "mark_deprecated_in_context",
        "warn_only",
        "block_operation",
    ],
) -> RefIntegrityIssue:
    """Create a typed RefIntegrityIssue without per-call type casts."""
    return RefIntegrityIssue(
        consumer_feature=consumer_feature,
        consumer_location=location,
        ref_kind=ref_kind,
        ref_value=ref_value,
        resolved_status=resolved_status,
        reason=reason,
        suggested_action=suggested_action,
    )
