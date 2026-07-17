"""Reusable KB-context provider — canonical fetch+render for KB prompt context.

Implements ADR-067 (Alt C: thin, consolidating). Wraps the ADR-050 render
contract (``RenderedKBContext``) plus the existing canonical renderers so
non-writing features (planning, analysis) get ONE KB-context source instead
of re-inventing fetch/format helpers or stubbing ``""``.

This module introduces **no new wire format**. It reuses, in place:

* :func:`narrare.kb.worldbuilding_entity_assembly.list_entities` — fetch.
* :func:`kb_entry_to_kb_entity` (below) — the canonical ``KBEntry→KBEntity``
  mapper (succeeds the private copy in ``dependencies_voice_check``).
* :func:`narrare_core.writing._helpers.format_entities` — per-type compact
  envelope renderer (``### Type: Name\\nContent`` + provenance accounting).
* :func:`narrare_core.writing._relationship_format.format_relationships` —
  the ``→`` relationship renderer.
* :func:`narrare.kb._world_context.fetch_world_context` — the
  ``- name (type): brief`` aggregate for kb merge/extract.

RULE-11 (graceful degradation): an unavailable repository or empty KB yields
a bundle of empty :class:`RenderedKBContext` (``.text == ""``) — never an
exception — so every consumer always composes its prompt. Provenance flows
through :class:`RenderOptions` (FIND-017).

See:
    ADR-067 — Reusable KB-Context Provider
    ADR-050 — KB Envelope (render contract)
    CONSTRAINTS.md RULE-03/06/07/11/22
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.kb.context_contracts import KBContextBundle
from narrare.kb.worldbuilding_entity_assembly import list_entities
from narrare_core.context._kb_envelope import RenderedKBContext
from narrare_core.context._render_options import RenderOptions
from narrare_core.writing._helpers import format_entities
from narrare_core.writing._relationship_format import format_relationships

if TYPE_CHECKING:
    import uuid

    from narrare.kb.contracts import KBRepositoryProtocol, RelationshipRepositoryProtocol
    from narrare.kb.models import KBEntry
    from narrare_core.writing.context_models import KBEntity

logger = structlog.get_logger(__name__)

#: Entity types rendered into the bundle's three slots. Types outside this set
#: are fetched-but-ignored by ``fetch_context`` (timeline only reasons over
#: characters/locations/factions; other types reach prompts via other vars).
_ENTITY_SLOTS: dict[str, str] = {
    "character": "characters",
    "location": "locations",
    "faction": "factions",
}

#: Default entity-type filter when the caller omits ``entity_types``.
_DEFAULT_ENTITY_TYPES: list[str] = ["character", "location", "faction"]

_EMPTY_RENDER_PATH = "narrare.kb._context_provider.KBContextProvider"


def _empty_rendered() -> RenderedKBContext:
    """Build an empty ``RenderedKBContext`` (RULE-11 degradation sentinel)."""
    return RenderedKBContext(
        text="",
        preserved_fields=frozenset(),
        omitted_fields=(),
        entry_count=0,
        render_path=_EMPTY_RENDER_PATH,
    )


def kb_entry_to_kb_entity(entry: KBEntry) -> KBEntity:
    """Convert a persisted KB entry to the canonical ``KBEntity`` shape.

    This is the single canonical ``KBEntry→KBEntity`` mapper (ADR-067). It
    succeeds the private ``_entry_to_kb_entity`` in
    ``analysis/dependencies_voice_check.py`` (which now delegates here) so
    there is one place that maps persistence → render-source shape.

    Provenance fields (``source``, ``review_status``, ``status``) are carried
    through so :func:`format_entities` can render provenance brackets when
    ``RenderOptions.annotate_provenance`` is set (FIND-017 / RULE-22).
    """
    from narrare_core.writing.context_models import KBEntity

    return KBEntity(
        entity_id=str(entry.id),
        entity_type=entry.entity_type,
        name=entry.name,
        content=entry.body or "",
        updated_at=entry.updated_at.isoformat() if entry.updated_at else None,
        metadata=entry.metadata_,
        status=entry.status,
        source=entry.source,
        review_status=entry.review_status,
    )


class KBContextProvider:
    """Backend service-layer KB-context provider (ADR-067).

    Implements :class:`~narrare.kb.context_contracts.KBContextProviderProtocol`.
    Fetches KB entities via ``list_entities``, maps them via
    :func:`kb_entry_to_kb_entity`, splits by entity type, and renders each
    slot through the ADR-050 envelope (:func:`format_entities`). Relationships
    are rendered through :func:`format_relationships`. ``fetch_world_context``
    delegates to the existing kb merge/extract aggregate.

    Args:
        kb_repo: KB entry repository (scoped read). ``None`` → empty bundle.
        relationship_repo: Relationship repository for ``kb_relationships``.
            ``None`` → empty relationships slot (the rest of the bundle still
            renders).
    """

    def __init__(
        self,
        kb_repo: KBRepositoryProtocol | None,
        relationship_repo: RelationshipRepositoryProtocol | None = None,
    ) -> None:
        self._kb_repo = kb_repo
        self._rel_repo = relationship_repo

    async def fetch_context(
        self,
        novel_id: uuid.UUID,
        *,
        entity_types: list[str] | None = None,
        options: RenderOptions | None = None,
    ) -> KBContextBundle:
        """Fetch KB entities and render them per-type into a bundle.

        See :meth:`KBContextProviderProtocol.fetch_context` for the contract.
        Never raises: repository failure degrades to an empty bundle (RULE-11).
        """
        render_options = options or RenderOptions()

        if self._kb_repo is None:
            return KBContextBundle.empty(render_options)

        try:
            entries = await list_entities(
                self._kb_repo,
                novel_id,
                list(entity_types) if entity_types is not None else None,
            )
        except Exception:
            logger.warning("kb_context_fetch_unavailable", exc_info=True)
            return KBContextBundle.empty(render_options)

        # Partition into the bundle's three rendered slots.
        by_slot: dict[str, list[KBEntity]] = {slot: [] for slot in _ENTITY_SLOTS.values()}
        for entry in entries:
            slot = _ENTITY_SLOTS.get(entry.entity_type)
            if slot is not None:
                by_slot[slot].append(kb_entry_to_kb_entity(entry))

        characters = format_entities(by_slot["characters"], options=render_options)
        locations = format_entities(by_slot["locations"], options=render_options)
        factions = format_entities(by_slot["factions"], options=render_options)
        relationships = await self._fetch_relationships(novel_id)

        return KBContextBundle(
            characters=characters,
            locations=locations,
            factions=factions,
            relationships=relationships,
            render_options=render_options,
        )

    async def fetch_entities(
        self,
        novel_id: uuid.UUID,
        *,
        entity_types: list[str] | None = None,
    ) -> list[KBEntry]:
        """Fetch the novel's raw KB entries (ADR-067 single KB source).

        Returns the persisted :class:`KBEntry` records so consumers that need
        entity-level data (e.g. resolving extracted names to real entity links
        for ``TimelineEvent.character_refs`` / ``location_ref``, §7 follow-up)
        reuse this fetch instead of wiring a second KB repository.
        ``fetch_context`` renders these same records into prompt text; this
        method exposes the records themselves.

        Never raises: an unavailable repository or fetch failure degrades to
        ``[]`` (RULE-11) so a consumer always proceeds (e.g. with empty refs).
        """
        if self._kb_repo is None:
            return []
        try:
            return await list_entities(
                self._kb_repo,
                novel_id,
                list(entity_types) if entity_types is not None else None,
            )
        except Exception:
            logger.warning("kb_entities_fetch_unavailable", exc_info=True)
            return []

    async def fetch_world_context(
        self,
        novel_id: uuid.UUID,
        *,
        entity_type: str | None = None,
        max_entries: int = 30,
    ) -> str:
        """Aggregate compact world context for kb merge/extract.

        Succeeds :func:`narrare.kb._world_context.fetch_world_context`: same
        ``- name (type): brief`` wire format (validated by
        ``validate_world_context``). Returns ``""`` on an unavailable
        repository or empty KB (RULE-11).
        """
        from narrare.kb._world_context import fetch_world_context

        if self._kb_repo is None:
            return ""
        return await fetch_world_context(
            self._kb_repo,
            novel_id,
            entity_type=entity_type,
            max_entries=max_entries,
        )

    async def _fetch_relationships(self, novel_id: uuid.UUID) -> RenderedKBContext:
        """Render the novel's relationship edges, degrading to empty (RULE-11)."""
        if self._rel_repo is None:
            return _empty_rendered()
        try:
            edges = await self._rel_repo.get_relationships_with_names(novel_id=novel_id)
        except Exception:
            logger.warning("kb_context_relationships_unavailable", exc_info=True)
            return _empty_rendered()
        return format_relationships(edges)
