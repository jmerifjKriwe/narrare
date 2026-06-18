"""Chapter frontmatter KB-lifecycle consumer (ADR-050 P1-B).

Chapter frontmatter is user-authored structured content. This consumer
therefore NEVER rewrites chapter content on KB rename/deprecate/delete;
it only emits :class:`RefIntegrityIssue` records so consistency tooling can
surface the stale or dangling reference to the user.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, cast

from narrare_core.context.integration_contracts import (
    ContradictionReason,
    RefIntegrityIssue,
    RefResolutionStatus,
)
from narrare_core.shared.frontmatter import parse_frontmatter

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from uuid import UUID

    from narrare.chapters.models import Chapter
    from narrare.consistency.ref_integrity_sink import RefIntegrityIssueSink


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


class _ChapterRepoProtocol(Protocol):
    """Minimal chapter repository surface needed by this consumer."""

    async def list_by_novel(
        self,
        novel_id: UUID,
        volume_id: UUID | None = None,
    ) -> Sequence[Chapter]: ...


class ChapterFrontmatterRefConsumerImpl:
    """Chapter-frontmatter observer — issue-only, no rewrites.

    Args:
        chapter_repo: Chapter repository sharing the KB request session.
        issue_sink: Advisory write-side sink for integrity issues.
    """

    consumer_feature = "chapter_frontmatter"

    def __init__(
        self,
        chapter_repo: _ChapterRepoProtocol,
        issue_sink: RefIntegrityIssueSink,
    ) -> None:
        self._chapter_repo = chapter_repo
        self._sink = issue_sink

    async def on_kb_entity_renamed(
        self,
        *,
        novel_id: UUID,
        entity_id: UUID,
        old_name: str,
        new_name: str,
    ) -> None:
        """Emit stale-name issues for name-based frontmatter refs.

        ``new_name`` and ``entity_id`` are intentionally not used for mutation:
        RULE-22 requires user-authored content to remain unchanged until the
        user explicitly edits it.
        """
        del entity_id, new_name
        for chapter in await self._chapter_repo.list_by_novel(novel_id):
            for location, value in _frontmatter_refs(chapter):
                if old_name in _iter_scalar_refs(value):
                    await self._sink.emit(
                        _issue(
                            location=location,
                            ref_kind="name",
                            ref_value=old_name,
                            resolved_status="active",
                            reason="stale_name_ref",
                            suggested_action="warn_only",
                        )
                    )

    async def on_kb_entity_deprecated(self, *, novel_id: UUID, entity_id: UUID) -> None:
        """Emit warning issues for id-based refs to a deprecated entity."""
        entity_value = str(entity_id)
        for chapter in await self._chapter_repo.list_by_novel(novel_id):
            for location, value in _chapter_id_refs(chapter):
                if entity_value in _iter_scalar_refs(value):
                    await self._sink.emit(
                        _issue(
                            location=location,
                            ref_kind="id",
                            ref_value=entity_value,
                            resolved_status="deprecated",
                            reason="deprecated_ref_in_active_context",
                            suggested_action="mark_deprecated_in_context",
                        )
                    )

    async def on_kb_entity_deleted(self, *, novel_id: UUID, entity_id: UUID) -> None:
        """Emit hard-delete issues for id-based refs to the deleted entity."""
        entity_value = str(entity_id)
        for chapter in await self._chapter_repo.list_by_novel(novel_id):
            for location, value in _chapter_id_refs(chapter):
                if entity_value in _iter_scalar_refs(value):
                    await self._sink.emit(
                        _issue(
                            location=location,
                            ref_kind="id",
                            ref_value=entity_value,
                            resolved_status="deleted",
                            reason="deleted_ref_without_tombstone",
                            suggested_action="block_operation",
                        )
                    )


def _chapter_id_refs(chapter: Chapter) -> list[tuple[str, object]]:
    refs = list(_frontmatter_refs(chapter))
    pov_character_id = getattr(chapter, "pov_character_id", "")
    if isinstance(pov_character_id, str) and pov_character_id:
        refs.append((f"chapters[{chapter.id}].pov_character_id", pov_character_id))
    return refs


def _frontmatter_refs(chapter: Chapter) -> Iterator[tuple[str, object]]:
    parsed = parse_frontmatter(chapter.content)
    if not parsed.has_frontmatter:
        return
    for key, value in parsed.metadata.items():
        if key in _FRONTMATTER_REF_KEYS:
            yield f"chapters[{chapter.id}].frontmatter.{key}", value


def _iter_scalar_refs(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        # JSON/YAML values are runtime-shaped; narrow the container before
        # iterating so static analysis does not treat elements as unknown.
        items = cast("list[object]", value)
        return [item for item in items if isinstance(item, str)]
    if isinstance(value, dict):
        # Frontmatter may use hybrid {id, name} objects; the YAML parser
        # returns an unparameterized dict, so cast after the runtime guard.
        mapping = cast("dict[object, object]", value)
        refs: list[str] = []
        for key in ("id", "name"):
            item = mapping.get(key)
            if isinstance(item, str):
                refs.append(item)
        return refs
    return []


def _issue(
    *,
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
    return RefIntegrityIssue(
        consumer_feature="chapter_frontmatter",
        consumer_location=location,
        ref_kind=ref_kind,
        ref_value=ref_value,
        resolved_status=resolved_status,
        reason=reason,
        suggested_action=suggested_action,
    )
