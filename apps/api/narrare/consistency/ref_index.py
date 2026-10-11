"""Read-side cross-feature KB reference index (ADR-050 P1-B).

The write-side observers repair or warn immediately when they are called.
This read-side index is the consistency backstop: it recomputes stale,
deprecated, and dangling refs directly from consumer storage so missed
observer events do not permanently hide integrity issues.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol

from narrare.consistency.ref_index_checks import (
    check_chapter_frontmatter_refs,
    check_timeline_refs,
)
from narrare.consistency.ref_index_helpers import (
    build_ref_issue,
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
            return await check_timeline_refs(
                novel_id=novel_id,
                timeline_repo=self._timeline_repo,
                kb_repo=self._kb_repo,
            )
        if consumer_feature == "chapter_frontmatter":
            return await check_chapter_frontmatter_refs(
                novel_id=novel_id,
                chapter_repo=self._chapter_repo,
                kb_repo=self._kb_repo,
            )
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

    async def _check_storyboard_refs(self, novel_id: uuid.UUID) -> list[RefIntegrityIssue]:
        """Detect storyboard refs that still name currently deprecated KB entries.

        PLAN-001 T15 (spec §7): scans the outline's free-text notes and the
        scene plans' text fields (via the shared ``iter_scene_texts``
        scan) — the legacy beat column is gone (Alembic 0049). Storyboard
        text is free-form, so hard-deleted names cannot be reconstructed
        without a tombstone store — the write-side rename hook catches
        old-name occurrences when the old name is still available.
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
