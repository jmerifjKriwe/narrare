"""Cross-feature ref-index check chains (RULE-04 split).

``_check_timeline_refs`` / ``_check_chapter_frontmatter_refs`` — and the
``_check_hybrid_ref`` / ``_check_scalar_ref`` decision trees only they
call — relocated unchanged from ``CrossFeatureRefIndexImpl``: the
PLAN-001 T15 scene-plan scan pushed ``ref_index.py`` past the 300-line
service limit (RULE-04; the service was already over pre-T15). Pure
move — identical signatures and semantics; the service keeps the
storyboard scan and the public ``check_refs`` / ``resolve_ref``
surface, dispatching into these chains with its repositories.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from narrare.consistency.ref_index_helpers import (
    build_ref_issue,
    chapter_ref_values,
    iter_scalar_refs,
    parse_uuid,
)

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from narrare.chapters.models import Chapter
    from narrare.kb.models import KBEntry
    from narrare.planning.models import TimelineEvent
    from narrare_core.context.integration_contracts import RefIntegrityIssue


class _KBLookupProtocol(Protocol):
    """Minimal KB lookup surface — mirrors the service's duck protocol."""

    async def get_by_id(self, entry_id: uuid.UUID) -> KBEntry | None: ...
    async def get_by_name(self, novel_id: uuid.UUID, name: str) -> KBEntry | None: ...


class _TimelineRepoProtocol(Protocol):
    """Minimal timeline read surface — mirrors the service's duck protocol."""

    async def list_by_novel(self, novel_id: uuid.UUID) -> Sequence[TimelineEvent]: ...


class _ChapterRepoProtocol(Protocol):
    """Minimal chapter read surface — mirrors the service's duck protocol."""

    async def list_by_novel(
        self,
        novel_id: uuid.UUID,
        volume_id: uuid.UUID | None = None,
    ) -> Sequence[Chapter]: ...


async def check_timeline_refs(
    *,
    novel_id: uuid.UUID,
    timeline_repo: _TimelineRepoProtocol,
    kb_repo: _KBLookupProtocol,
) -> list[RefIntegrityIssue]:
    """Detect timeline-event refs that no longer resolve against the KB."""
    issues: list[RefIntegrityIssue] = []
    events = await timeline_repo.list_by_novel(novel_id)
    for event in events:
        for index, ref in enumerate(event.character_refs or []):
            issues.extend(
                await check_hybrid_ref(
                    novel_id=novel_id,
                    ref=ref,
                    location=f"timeline_events[{event.id}].character_refs[{index}]",
                    consumer_feature="timeline",
                    kb_repo=kb_repo,
                )
            )
        if event.location_ref:
            issues.extend(
                await check_hybrid_ref(
                    novel_id=novel_id,
                    ref=event.location_ref,
                    location=f"timeline_events[{event.id}].location_ref",
                    consumer_feature="timeline",
                    kb_repo=kb_repo,
                )
            )
    return issues


async def check_hybrid_ref(
    *,
    novel_id: uuid.UUID,
    ref: dict[str, object],
    location: str,
    consumer_feature: str,
    kb_repo: _KBLookupProtocol,
) -> list[RefIntegrityIssue]:
    """Check a hybrid ``{id, name}`` ref for deleted/deprecated/stale state."""
    del novel_id
    ref_id = ref.get("id")
    ref_name = ref.get("name")
    if not isinstance(ref_id, str):
        return []
    entry_id = parse_uuid(ref_id)
    if entry_id is None:
        return []
    entry = await kb_repo.get_by_id(entry_id)
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


async def check_chapter_frontmatter_refs(
    *,
    novel_id: uuid.UUID,
    chapter_repo: _ChapterRepoProtocol,
    kb_repo: _KBLookupProtocol,
) -> list[RefIntegrityIssue]:
    """Detect chapter-frontmatter refs that no longer resolve against the KB."""
    issues: list[RefIntegrityIssue] = []
    for chapter in await chapter_repo.list_by_novel(novel_id):
        for location, value in chapter_ref_values(chapter):
            for scalar in iter_scalar_refs(value):
                issue = await check_scalar_ref(
                    novel_id=novel_id,
                    location=location,
                    value=scalar,
                    consumer_feature="chapter_frontmatter",
                    kb_repo=kb_repo,
                )
                if issue is not None:
                    issues.append(issue)
    return issues


async def check_scalar_ref(
    *,
    novel_id: uuid.UUID,
    location: str,
    value: str,
    consumer_feature: str,
    kb_repo: _KBLookupProtocol,
) -> RefIntegrityIssue | None:
    """Check a scalar id/name ref against KB current state."""
    entry_id = parse_uuid(value)
    if entry_id is not None:
        entry = await kb_repo.get_by_id(entry_id)
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

    entry = await kb_repo.get_by_name(novel_id, value)
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
