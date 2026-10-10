"""Read-side cross-feature KB reference index (ADR-050 P1-B).

The write-side observers repair or warn immediately when they are called.
This read-side index is the consistency backstop: it recomputes stale,
deprecated, and dangling refs directly from consumer storage so missed
observer events do not permanently hide integrity issues.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol

from narrare.consistency.ref_index_helpers import (
    build_ref_issue,
    chapter_ref_values,
    iter_scalar_refs,
    parse_uuid,
    scene_texts,
    storyboard_notes_texts,
)

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from narrare.chapters.models import Chapter
    from narrare.kb.models import KBEntry
    from narrare.planning.models import ChapterOutline, ScenePlan, TimelineEvent
    from narrare_core.context.integration_contracts import (
        RefIntegrityIssue,
        RefResolutionStatus,
    )


class _KBLookupProtocol(Protocol):
    async def get_by_id(self, entry_id: uuid.UUID) -> KBEntry | None: ...
    async def get_by_name(self, novel_id: uuid.UUID, name: str) -> KBEntry | None: ...


class _TimelineRepoProtocol(Protocol):
    async def list_by_novel(self, novel_id: uuid.UUID) -> Sequence[TimelineEvent]: ...


class _OutlineRepoProtocol(Protocol):
    async def get_all_for_novel(self, novel_id: uuid.UUID) -> Sequence[ChapterOutline]: ...


class _SceneRepoProtocol(Protocol):
    """Minimal scene-plan read surface for the storyboard scan (spec §7)."""

    async def list_by_novel(self, novel_id: uuid.UUID) -> Sequence[ScenePlan]: ...


class _ChapterRepoProtocol(Protocol):
    async def list_by_novel(
        self,
        novel_id: uuid.UUID,
        volume_id: uuid.UUID | None = None,
    ) -> Sequence[Chapter]: ...


class CrossFeatureRefIndexImpl:
    """Resolve consumer-side KB refs against current KB state.

    Args:
        kb_repo: KB repository used for authoritative entity lookup.
        timeline_repo: Timeline event repository.
        outline_repo: Storyboard outline repository (free-text notes scan).
        chapter_repo: Chapter repository for frontmatter refs.
        scene_repo: Scene-plan repository (spec §7 scene text scan — the
            planned-beats scan's replacement, PLAN-001 T15).
    """

    def __init__(
        self,
        *,
        kb_repo: _KBLookupProtocol,
        timeline_repo: _TimelineRepoProtocol,
        outline_repo: _OutlineRepoProtocol,
        chapter_repo: _ChapterRepoProtocol,
        scene_repo: _SceneRepoProtocol,
    ) -> None:
        self._kb_repo = kb_repo
        self._timeline_repo = timeline_repo
        self._outline_repo = outline_repo
        self._chapter_repo = chapter_repo
        self._scene_repo = scene_repo

    async def check_refs(
        self,
        *,
        novel_id: uuid.UUID,
        consumer_feature: str,
    ) -> list[RefIntegrityIssue]:
        """Return all currently detectable ref-integrity issues."""
        if consumer_feature == "timeline":
            return await self._check_timeline_refs(novel_id)
        if consumer_feature == "chapter_frontmatter":
            return await self._check_chapter_frontmatter_refs(novel_id)
        if consumer_feature == "storyboard":
            return await self._check_storyboard_refs(novel_id)
        return []

    async def resolve_ref(
        self,
        *,
        novel_id: uuid.UUID,
        ref_kind: Literal["id", "name"],
        ref_value: str,
    ) -> RefResolutionStatus:
        """Resolve a single id/name ref against KB current state."""
        entry = None
        if ref_kind == "id":
            entry_id = parse_uuid(ref_value)
            if entry_id is not None:
                entry = await self._kb_repo.get_by_id(entry_id)
        else:
            entry = await self._kb_repo.get_by_name(novel_id, ref_value)

        if entry is None:
            return "unknown"
        if getattr(entry, "status", "") == "deprecated":
            return "deprecated"
        return "active"

    async def _check_timeline_refs(self, novel_id: uuid.UUID) -> list[RefIntegrityIssue]:
        issues: list[RefIntegrityIssue] = []
        events = await self._timeline_repo.list_by_novel(novel_id)
        for event in events:
            for index, ref in enumerate(event.character_refs or []):
                issues.extend(
                    await self._check_hybrid_ref(
                        novel_id=novel_id,
                        ref=ref,
                        location=f"timeline_events[{event.id}].character_refs[{index}]",
                        consumer_feature="timeline",
                    )
                )
            if event.location_ref:
                issues.extend(
                    await self._check_hybrid_ref(
                        novel_id=novel_id,
                        ref=event.location_ref,
                        location=f"timeline_events[{event.id}].location_ref",
                        consumer_feature="timeline",
                    )
                )
        return issues

    async def _check_hybrid_ref(
        self,
        *,
        novel_id: uuid.UUID,
        ref: dict[str, object],
        location: str,
        consumer_feature: str,
    ) -> list[RefIntegrityIssue]:
        del novel_id
        ref_id = ref.get("id")
        ref_name = ref.get("name")
        if not isinstance(ref_id, str):
            return []
        entry_id = parse_uuid(ref_id)
        if entry_id is None:
            return []
        entry = await self._kb_repo.get_by_id(entry_id)
        if entry is None:
            return [
                build_ref_issue(
                    consumer_feature=consumer_feature,
                    location=location,
                    ref_kind="id",
                    ref_value=ref_id,
                    resolved_status="deleted",
                    reason="deleted_ref_without_tombstone",
                    suggested_action="block_operation",
                )
            ]

        issues: list[RefIntegrityIssue] = []
        status = "deprecated" if getattr(entry, "status", "") == "deprecated" else "active"
        if status == "deprecated":
            issues.append(
                build_ref_issue(
                    consumer_feature=consumer_feature,
                    location=location,
                    ref_kind="id",
                    ref_value=ref_id,
                    resolved_status="deprecated",
                    reason="deprecated_ref_in_active_context",
                    suggested_action="mark_deprecated_in_context",
                )
            )
        if isinstance(ref_name, str) and ref_name != getattr(entry, "name", ""):
            issues.append(
                build_ref_issue(
                    consumer_feature=consumer_feature,
                    location=location,
                    ref_kind="name",
                    ref_value=ref_name,
                    resolved_status=status,
                    reason="stale_name_ref",
                    suggested_action="remap_to_canonical",
                )
            )
        return issues

    async def _check_chapter_frontmatter_refs(
        self,
        novel_id: uuid.UUID,
    ) -> list[RefIntegrityIssue]:
        issues: list[RefIntegrityIssue] = []
        for chapter in await self._chapter_repo.list_by_novel(novel_id):
            for location, value in chapter_ref_values(chapter):
                for scalar in iter_scalar_refs(value):
                    issue = await self._check_scalar_ref(
                        novel_id=novel_id,
                        location=location,
                        value=scalar,
                        consumer_feature="chapter_frontmatter",
                    )
                    if issue is not None:
                        issues.append(issue)
        return issues

    async def _check_storyboard_refs(self, novel_id: uuid.UUID) -> list[RefIntegrityIssue]:
        """Detect storyboard refs that still name currently deprecated KB entries.

        PLAN-001 T15 (spec §7): scans the outline's free-text notes and the
        scene plans' text fields (via the shared ``iter_scene_texts``
        scan); ``planned_beats`` is no longer read. Storyboard text is
        free-form, so hard-deleted names cannot be reconstructed without a
        tombstone store — the write-side rename hook catches old-name
        occurrences when the old name is still available.
        """
        issues: list[RefIntegrityIssue] = []
        outlines = await self._outline_repo.get_all_for_novel(novel_id)
        for outline in outlines:
            for text_location, text in storyboard_notes_texts(outline):
                issue = await self._deprecated_name_issue(
                    novel_id=novel_id,
                    text=text,
                    location=text_location,
                )
                if issue is not None:
                    issues.append(issue)
        scenes = await self._scene_repo.list_by_novel(novel_id)
        for scene in scenes:
            for text_location, text in scene_texts(scene):
                issue = await self._deprecated_name_issue(
                    novel_id=novel_id,
                    text=text,
                    location=text_location,
                )
                if issue is not None:
                    issues.append(issue)
        return issues

    async def _deprecated_name_issue(
        self,
        *,
        novel_id: uuid.UUID,
        text: str,
        location: str,
    ) -> RefIntegrityIssue | None:
        words = {part.strip(".,;:!?()[]{}\"'") for part in text.split()}
        for word in words:
            if not word:
                continue
            entry = await self._kb_repo.get_by_name(novel_id, word)
            if entry is not None and getattr(entry, "status", "") == "deprecated":
                return build_ref_issue(
                    consumer_feature="storyboard",
                    location=location,
                    ref_kind="name",
                    ref_value=word,
                    resolved_status="deprecated",
                    reason="deprecated_ref_in_active_context",
                    suggested_action="warn_only",
                )
        return None

    async def _check_scalar_ref(
        self,
        *,
        novel_id: uuid.UUID,
        location: str,
        value: str,
        consumer_feature: str,
    ) -> RefIntegrityIssue | None:
        entry_id = parse_uuid(value)
        if entry_id is not None:
            entry = await self._kb_repo.get_by_id(entry_id)
            if entry is None:
                return build_ref_issue(
                    consumer_feature=consumer_feature,
                    location=location,
                    ref_kind="id",
                    ref_value=value,
                    resolved_status="deleted",
                    reason="deleted_ref_without_tombstone",
                    suggested_action="block_operation",
                )
            if getattr(entry, "status", "") == "deprecated":
                return build_ref_issue(
                    consumer_feature=consumer_feature,
                    location=location,
                    ref_kind="id",
                    ref_value=value,
                    resolved_status="deprecated",
                    reason="deprecated_ref_in_active_context",
                    suggested_action="mark_deprecated_in_context",
                )
            return None

        entry = await self._kb_repo.get_by_name(novel_id, value)
        if entry is None:
            return build_ref_issue(
                consumer_feature=consumer_feature,
                location=location,
                ref_kind="name",
                ref_value=value,
                resolved_status="unknown",
                reason="stale_name_ref",
                suggested_action="warn_only",
            )
        if getattr(entry, "status", "") == "deprecated":
            return build_ref_issue(
                consumer_feature=consumer_feature,
                location=location,
                ref_kind="name",
                ref_value=value,
                resolved_status="deprecated",
                reason="deprecated_ref_in_active_context",
                suggested_action="mark_deprecated_in_context",
            )
        return None
