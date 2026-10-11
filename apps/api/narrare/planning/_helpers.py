"""Outline mapping helpers — converts between ORM models and schemas.

Extracted from service.py to respect the 300-line file size limit (RULE-04).
AI remap helpers (WRITE-012) live in _remap_helpers.py (RULE-04 split).

PLAN-001 T14 (ADR-096): sync is scene-driven. ``build_outline_data`` /
``compute_sync`` accept the chapter's scene plans and map them to Core's
``ScenePlanData`` (``_to_core_scene``) so the Core sync checker never
touches ORM/JSONB shapes. ``iter_scene_texts`` exposes the scene text
scan surface shared by KB-lifecycle consumers (spec §7).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import structlog

from narrare.planning.schemas import OutlineResponse
from narrare_core.planning.models import (
    ChapterOutlineData,
    ScenePlanData,
    ScenePresence,
    SceneStatus,
    SyncStatus,
)
from narrare_core.planning.sync import StructuralSyncChecker

if TYPE_CHECKING:
    import uuid
    from collections.abc import Mapping, Sequence
    from typing import Protocol

    from narrare.chapters.models import Chapter
    from narrare.planning.models import ChapterOutline, ScenePlan
    from narrare.planning.schemas import ChapterInStoryboard

    class _OutlineRepoProtocol(Protocol):
        """Minimal outline repository interface — duck-typing for ensure_outlines."""

        async def get_all_for_novel(self, novel_id: uuid.UUID) -> list[ChapterOutline]: ...
        async def create(self, chapter_id: uuid.UUID, stage_assignment: str) -> ChapterOutline: ...


_logger = structlog.get_logger(__name__)

_checker = StructuralSyncChecker()


def _ref_name(ref: object) -> str:
    """Hybrid ``{id, name}`` JSONB ref → display name ('' when absent).

    Refs are user content of arbitrary runtime shape; only a dict carrying
    a string name resolves.
    """
    if isinstance(ref, dict):
        name = cast("dict[object, object]", ref).get("name", "")
        if isinstance(name, str):
            return name
    return ""


def _to_core_scene(row: ScenePlan) -> ScenePlanData:
    """ORM scene row → Core ``ScenePlanData`` (PLAN-001 spec §3.2).

    Names are resolved from the hybrid KB refs at the API boundary — Core
    stays free of JSONB ref semantics.
    """
    presences: list[ScenePresence] = []
    # JSONB is arbitrary at runtime even though the column is typed
    # ``list[dict[str, object]]``; treat each entry as ``object`` so the
    # isinstance guard stays runtime-meaningful (backfill tolerance).
    raw_presences: Sequence[object] = cast("Sequence[object]", row.present_characters or [])
    for presence in raw_presences:
        if not isinstance(presence, dict):
            continue
        presence_mapping = cast("dict[object, object]", presence)
        presences.append(
            ScenePresence(
                name=str(presence_mapping.get("name", "") or ""),
                goal=str(presence_mapping.get("goal", "") or ""),
            )
        )
    try:
        status = SceneStatus(row.status)
    except ValueError:
        # scene_plans.status is app-controlled (Literal-validated PUT +
        # backfill), so this is data corruption, not user input — degrade
        # to the conservative default instead of failing the whole
        # storyboard view; the structured log keeps it visible (RULE-11).
        _logger.warning("unknown_scene_status", status=row.status, scene_id=str(row.id))
        status = SceneStatus.PLANNED
    return ScenePlanData(
        id=row.id,
        position=row.position,
        title=row.title,
        pov_character_name=_ref_name(row.pov_character_ref),
        location_name=_ref_name(row.location_ref),
        present_characters=tuple(presences),
        purpose=row.purpose,
        conflict=row.conflict,
        resolution=row.resolution,
        beats=tuple(row.beats or ()),
        status=status,
    )


def iter_scene_texts(scene: ScenePlan) -> list[tuple[str, str]]:
    """Yield ``(location, text)`` pairs over a scene's text fields (spec §7).

    Shared scan surface for KB-lifecycle consumers: every field that may
    carry an entity name in free text. Locations use the
    ``scene_plans[{id}].{field}`` form; entries are NEVER rewritten
    (RULE-22 §7 — user content).
    """
    base = f"scene_plans[{scene.id}]"
    pairs: list[tuple[str, str]] = [
        (f"{base}.title", scene.title),
        (f"{base}.purpose", scene.purpose),
        (f"{base}.conflict", scene.conflict),
        (f"{base}.resolution", scene.resolution),
    ]
    for index, beat in enumerate(scene.beats or []):
        pairs.append((f"{base}.beats[{index}]", beat))
    # Same JSONB runtime-arbitrary tolerance as ``_to_core_scene``.
    raw_presences: Sequence[object] = cast("Sequence[object]", scene.present_characters or [])
    for index, presence in enumerate(raw_presences):
        if not isinstance(presence, dict):
            continue
        presence_mapping = cast("dict[object, object]", presence)
        name = presence_mapping.get("name", "")
        goal = presence_mapping.get("goal", "")
        if isinstance(name, str):
            pairs.append((f"{base}.present_characters[{index}].name", name))
        if isinstance(goal, str):
            pairs.append((f"{base}.present_characters[{index}].goal", goal))
    pov_name = _ref_name(scene.pov_character_ref)
    if pov_name:
        pairs.append((f"{base}.pov_character_ref.name", pov_name))
    location_name = _ref_name(scene.location_ref)
    if location_name:
        pairs.append((f"{base}.location_ref.name", location_name))
    return pairs


def to_outline_response(outline: ChapterOutline) -> OutlineResponse:
    """Convert a ChapterOutline ORM object to OutlineResponse."""
    return OutlineResponse(
        id=outline.id,
        chapter_id=outline.chapter_id,
        stage_assignment=outline.stage_assignment,
        outline_notes=outline.outline_notes,
        created_at=outline.created_at,
        updated_at=outline.updated_at,
    )


def build_outline_data(
    chapter: Chapter,
    outline: ChapterOutline | None,
    scenes: Sequence[ScenePlan] = (),
) -> ChapterOutlineData:
    """Build ChapterOutlineData for sync status computation.

    ``scenes`` are the chapter's scene plans (novel-scoped fetch threaded
    by the service); they drive the scene-based sync rules (ADR-096).
    """
    scene_data = tuple(_to_core_scene(scene) for scene in scenes)
    if outline is None:
        return ChapterOutlineData(
            chapter_id=chapter.id,
            stage_assignment="",
            outline_notes="",
            has_content=bool(chapter.content),
            word_count=chapter.word_count,
            has_summary=bool(chapter.summary),
            scenes=scene_data,
        )
    return ChapterOutlineData(
        chapter_id=chapter.id,
        stage_assignment=outline.stage_assignment,
        outline_notes=outline.outline_notes,
        has_content=bool(chapter.content),
        word_count=chapter.word_count,
        has_summary=bool(chapter.summary),
        scenes=scene_data,
    )


def compute_sync(
    chapter: Chapter,
    outline: ChapterOutline | None,
    suggested_stage: str,
    scenes: Sequence[ScenePlan] = (),
) -> SyncStatus:
    """Calculate sync status for a single chapter."""
    data = build_outline_data(chapter, outline, scenes)
    return _checker.calculate_sync_status(data, suggested_stage)


def find_position(chapters: list[Chapter], chapter_id: uuid.UUID) -> int:
    """Return 1-based position of a chapter in the list."""
    for idx, ch in enumerate(chapters, start=1):
        if ch.id == chapter_id:
            return idx
    return 1


async def ensure_outlines(
    outline_repo: _OutlineRepoProtocol,
    novel_id: uuid.UUID,
    chapters: list[Chapter],
    adapter: object,
) -> dict[uuid.UUID, ChapterOutline]:
    """Ensure every chapter has an outline, auto-creating missing ones."""
    from narrare_core.planning.adapters.base import StructureAdapter

    raw = await outline_repo.get_all_for_novel(novel_id)
    outlines = raw or []
    outline_map: dict[uuid.UUID, ChapterOutline] = {o.chapter_id: o for o in outlines}
    total = max(len(chapters), 1)

    for idx, ch in enumerate(chapters, start=1):
        if ch.id not in outline_map:
            if isinstance(adapter, StructureAdapter):
                suggested = adapter.suggest_stage(idx, total)
            else:
                suggested = ""
            outline = await outline_repo.create(chapter_id=ch.id, stage_assignment=suggested)
            outline_map[ch.id] = outline
    return outline_map


def chapter_in_storyboard(
    chapter: Chapter,
    outline_map: Mapping[uuid.UUID, ChapterOutline],
    idx: int,
    adapter: object,
    total: int,
    scenes: Sequence[ScenePlan] = (),
) -> ChapterInStoryboard:
    """Build a ChapterInStoryboard for a single chapter."""
    from narrare.planning.schemas import ChapterInStoryboard
    from narrare_core.planning.adapters.base import StructureAdapter

    outline = outline_map.get(chapter.id)
    suggested = ""
    if isinstance(adapter, StructureAdapter):
        suggested = adapter.suggest_stage(idx, total)
    status = compute_sync(chapter, outline, suggested, scenes)
    return ChapterInStoryboard(
        chapter_id=chapter.id,
        title=chapter.title,
        word_count=chapter.word_count,
        sync_status=status.value,
        position=chapter.position,
    )
