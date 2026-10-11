"""KB-lifecycle consumers in the planning module (ADR-050 P1-B, CR-AUFG-04-06).

Two consumers live here because both owned data shapes are in
``planning/models.py``:

* ``TimelineRefConsumerImpl`` — hybrid JSON ``{id, name}`` refs on
  ``timeline_events.character_refs`` / ``location_ref``. The id is the
  canonical KBEntry id; the name is a *derived* denormalisation (not user
  content), so this consumer MAY rewrite the stored name on rename and MAY
  inject a ``status: deprecated`` marker on deprecate. On hard delete it
  emits ``RefIntegrityIssue(reason="deleted_ref_without_tombstone")``.
* ``StoryboardRefConsumerImpl`` — name-based free text in scene plans
  (all text fields, spec §7) and ``outline_notes``. This is USER CONTENT
  (RULE-22 §7): the consumer NEVER rewrites; it only scans for
  occurrences of the (old) entity name and emits soft issues.

Why rename-only scanning for Storyboard deprecate/delete: those observer
methods receive ``entity_id`` only (Core Protocol). Free-text matching
needs a name, which is gone after delete. Deprecate therefore leaves
event-time detection to the authoritative read-side
(:class:`CrossFeatureRefIndex`); only ``rename`` — which carries
``old_name`` — can scan at event time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol

import structlog

from narrare.planning._helpers import iter_scene_texts
from narrare_core.context.integration_contracts import (
    ContradictionReason,
    RefIntegrityIssue,
    RefResolutionStatus,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from narrare.consistency.ref_integrity_sink import RefIntegrityIssueSink
    from narrare.planning.models import ChapterOutline, ScenePlan, TimelineEvent

logger = structlog.get_logger(__name__)


class _OutlineRepoProtocol(Protocol):
    """Minimal read surface the Storyboard consumer needs (outline notes)."""

    async def get_all_for_novel(self, novel_id: UUID) -> Sequence[ChapterOutline]: ...


class _SceneRepoProtocol(Protocol):
    """Minimal scene-plan read surface the Storyboard consumer needs."""

    async def list_by_novel(self, novel_id: UUID) -> Sequence[ScenePlan]: ...


class _TimelineRepoProtocol(Protocol):
    """Minimal timeline-event surface the Timeline consumer needs.

    Mirrors ``_OutlineRepoProtocol`` and the sibling protocols in
    ``consistency/ref_index.py``: the consumer depends on the *shape*
    it calls (``list_by_novel`` + ``update``), not on the concrete
    ``TimelineEventRepository``. This keeps the consumer unit-testable
    with in-memory fakes and consistent with its sibling consumers.
    """

    async def list_by_novel(self, novel_id: UUID) -> Sequence[TimelineEvent]: ...

    async def update(self, event_id: UUID, **fields: object) -> TimelineEvent: ...


# ===========================================================================
# Timeline consumer
# ===========================================================================


class TimelineRefConsumerImpl:
    """Timeline observer — id-based hybrid JSON refs.

    Args:
        event_repo: TimelineEvent repository (shares the request session).
        issue_sink: Where ``RefIntegrityIssue`` instances are surfaced.
    """

    consumer_feature = "timeline"

    def __init__(
        self,
        event_repo: _TimelineRepoProtocol,
        issue_sink: RefIntegrityIssueSink,
    ) -> None:
        self._event_repo = event_repo
        self._sink = issue_sink

    async def on_kb_entity_renamed(
        self,
        *,
        novel_id: UUID,
        entity_id: UUID,
        old_name: str,
        new_name: str,
    ) -> None:
        events = await self._event_repo.list_by_novel(novel_id)
        for event in events:
            new_chars = _rename_in_refs(event.character_refs, entity_id, old_name, new_name)
            new_loc = _rename_in_location(event.location_ref, entity_id, old_name, new_name)
            if new_chars is not None or new_loc is not None:
                updates: dict[str, object] = {}
                if new_chars is not None:
                    updates["character_refs"] = new_chars
                if new_loc is not None:
                    updates["location_ref"] = new_loc
                await self._event_repo.update(event.id, **updates)

    async def on_kb_entity_deprecated(
        self,
        *,
        novel_id: UUID,
        entity_id: UUID,
    ) -> None:
        events = await self._event_repo.list_by_novel(novel_id)
        for event in events:
            new_chars = _mark_deprecated_in_refs(event.character_refs, entity_id)
            new_loc = _mark_deprecated_in_location(event.location_ref, entity_id)
            if new_chars is not None or new_loc is not None:
                updates: dict[str, object] = {}
                if new_chars is not None:
                    updates["character_refs"] = new_chars
                if new_loc is not None:
                    updates["location_ref"] = new_loc
                await self._event_repo.update(event.id, **updates)

    async def on_kb_entity_deleted(
        self,
        *,
        novel_id: UUID,
        entity_id: UUID,
    ) -> None:
        events = await self._event_repo.list_by_novel(novel_id)
        for event in events:
            for index, ref in enumerate(event.character_refs or []):
                if _ref_matches_id(ref, entity_id):
                    await self._sink.emit(
                        _deleted_issue(
                            f"timeline_events[{event.id}].character_refs[{index}]",
                            entity_id,
                        )
                    )
            if event.location_ref and _ref_matches_id(event.location_ref, entity_id):
                await self._sink.emit(
                    _deleted_issue(
                        f"timeline_events[{event.id}].location_ref",
                        entity_id,
                    )
                )


# ===========================================================================
# Storyboard consumer — read-only, issues only
# ===========================================================================


class StoryboardRefConsumerImpl:
    """Storyboard observer — name-based free text. NEVER rewrites.

    Scans scene plans (all text fields via :func:`iter_scene_texts`,
    PLAN-001 spec §7) and outline notes for stale entity names.

    Args:
        outline_repo: ChapterOutline repository (shares the request
            session) — supplies the ``outline_notes`` scan.
        scene_repo: ScenePlan repository (shares the request session) —
            supplies the scene text scan.
        issue_sink: Where ``RefIntegrityIssue`` instances are surfaced.
    """

    consumer_feature = "storyboard"

    def __init__(
        self,
        outline_repo: _OutlineRepoProtocol,
        scene_repo: _SceneRepoProtocol,
        issue_sink: RefIntegrityIssueSink,
    ) -> None:
        self._outline_repo = outline_repo
        self._scene_repo = scene_repo
        self._sink = issue_sink

    async def on_kb_entity_renamed(
        self,
        *,
        novel_id: UUID,
        entity_id: UUID,
        old_name: str,
        new_name: str,
    ) -> None:
        del new_name  # unused — we never rewrite; we only flag stale names.
        outlines = await self._outline_repo.get_all_for_novel(novel_id)
        for outline in outlines:
            if old_name in (outline.outline_notes or ""):
                await self._sink.emit(
                    _issue(
                        reason="stale_name_ref",
                        location=f"chapter_outlines[{outline.id}].outline_notes",
                        ref_kind="name",
                        ref_value=old_name,
                        resolved_status="active",
                    )
                )
        scenes = await self._scene_repo.list_by_novel(novel_id)
        for scene in scenes:
            for location, text in iter_scene_texts(scene):
                if old_name in text:
                    await self._sink.emit(
                        _issue(
                            reason="stale_name_ref",
                            location=location,
                            ref_kind="name",
                            ref_value=old_name,
                            resolved_status="active",
                        )
                    )

    async def on_kb_entity_deprecated(self, *, novel_id: UUID, entity_id: UUID) -> None:
        # Name-based free text cannot be scanned from entity_id alone and the
        # Core Protocol passes no name here. Authoritative detection is the
        # read-side CrossFeatureRefIndex (ADR-050 Option B).
        del novel_id, entity_id  # explicitly no-op, documented.

    async def on_kb_entity_deleted(self, *, novel_id: UUID, entity_id: UUID) -> None:
        # Entity (and its name) is gone — free-text scan impossible at event
        # time. Read-side index reports the now-unresolvable name as "unknown".
        del novel_id, entity_id  # explicitly no-op, documented.


# ===========================================================================
# Pure helpers — operate on the hybrid {id, name} JSON shape
# ===========================================================================


def _ref_matches_id(ref: dict[str, object] | None, entity_id: UUID) -> bool:
    if not ref:
        return False
    return str(ref.get("id", "")) == str(entity_id)


def _rename_in_refs(
    refs: list[dict[str, object]] | None,
    entity_id: UUID,
    old_name: str,
    new_name: str,
) -> list[dict[str, object]] | None:
    """Return a rebuilt list with renamed refs, or None if nothing changed."""
    if not refs:
        return None
    changed = False
    rebuilt: list[dict[str, object]] = []
    for ref in refs:
        new_ref = dict(ref)
        if _ref_matches_id(new_ref, entity_id) and new_ref.get("name") == old_name:
            new_ref["name"] = new_name
            changed = True
        rebuilt.append(new_ref)
    return rebuilt if changed else None


def _rename_in_location(
    location: dict[str, object] | None,
    entity_id: UUID,
    old_name: str,
    new_name: str,
) -> dict[str, object] | None:
    if not location:
        return None
    if _ref_matches_id(location, entity_id) and location.get("name") == old_name:
        new_loc = dict(location)
        new_loc["name"] = new_name
        return new_loc
    return None


def _mark_deprecated_in_refs(
    refs: list[dict[str, object]] | None,
    entity_id: UUID,
) -> list[dict[str, object]] | None:
    if not refs:
        return None
    changed = False
    rebuilt: list[dict[str, object]] = []
    for ref in refs:
        new_ref = dict(ref)
        if _ref_matches_id(new_ref, entity_id):
            new_ref["status"] = "deprecated"
            changed = True
        rebuilt.append(new_ref)
    return rebuilt if changed else None


def _mark_deprecated_in_location(
    location: dict[str, object] | None,
    entity_id: UUID,
) -> dict[str, object] | None:
    if not location:
        return None
    if _ref_matches_id(location, entity_id):
        new_loc = dict(location)
        new_loc["status"] = "deprecated"
        return new_loc
    return None


def _issue(
    *,
    reason: ContradictionReason,
    location: str,
    ref_kind: Literal["id", "name"],
    ref_value: str,
    resolved_status: RefResolutionStatus,
    suggested_action: Literal[
        "remap_to_canonical",
        "mark_deprecated_in_context",
        "warn_only",
        "block_operation",
    ] = "warn_only",
) -> RefIntegrityIssue:
    return RefIntegrityIssue(
        consumer_feature="storyboard",
        consumer_location=location,
        ref_kind=ref_kind,
        ref_value=ref_value,
        resolved_status=resolved_status,
        reason=reason,
        suggested_action=suggested_action,
    )


def _deleted_issue(location: str, entity_id: UUID) -> RefIntegrityIssue:
    return RefIntegrityIssue(
        consumer_feature="timeline",
        consumer_location=location,
        ref_kind="id",
        ref_value=str(entity_id),
        resolved_status="deleted",
        reason="deleted_ref_without_tombstone",
        suggested_action="block_operation",
    )
