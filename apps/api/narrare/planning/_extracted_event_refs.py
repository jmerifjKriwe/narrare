"""Name → KB-entity ref resolver for confirmed extracted events (§7 follow-up).

``confirm_extracted_event`` receives an :class:`ExtractedTemporalExpression`
that carries ``character_names`` / ``location_name`` (free-text names the
extractor observed near the expression). This pure helper resolves those names
against the novel's KB entities and produces the
``character_refs`` / ``location_ref`` wire shape persisted on a
``TimelineEvent`` — so extracted events render with the same real KB entity
links as manual / AI events (cross-feature ref-index tracks by entity id).

Resolution rules (PLAN-004 §7 follow-up):

* Names match **case-insensitively, trimmed** against KB entity names.
* Each match emits ``{"id": str(entity.id), "name": entity.name}`` (the wire
  shape consumed by the cross-feature ref-index — see
  ``consistency/ref_index.py`` and ``planning/timeline_schemas.py``).
* **Non-matches are omitted.** Only real KB entities are linked — a ref
  without a real entity id cannot be tracked by the ref-index, and the name is
  already present in the narrative text.
* ``location_ref`` is the single matching location entity, or ``None``.
* Empty / whitespace-only / unmatched names degrade to empty refs (RULE-11) —
  never an exception.

The helper is pure and ORM-agnostic: it consumes the structural
:class:`_ExtractedRefEntity` Protocol, so it is unit-testable with lightweight
``SimpleNamespace`` stand-ins and decoupled from SQLAlchemy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from narrare.kb.context_contracts import KBContextProviderProtocol
    from narrare.kb.models import KBEntry
    from narrare_core.agents.temporal_extraction_types import ExtractedTemporalExpression


class _ExtractedRefEntity(Protocol):
    """Structural shape the resolver reads (``KBEntry`` satisfies this).

    Members are declared read-only (``@property``): the resolver never mutates
    an entity, and this lets both a frozen dataclass adapter and the
    ``SimpleNamespace`` stand-ins used in unit tests satisfy the Protocol.

    Decoupling the helper from the SQLAlchemy model keeps it pure and
    unit-testable with lightweight stand-ins (see
    ``tests/unit/planning/test_extracted_event_refs.py``).
    """

    @property
    def id(self) -> uuid.UUID: ...

    @property
    def name(self) -> str: ...

    @property
    def entity_type(self) -> str: ...


@dataclass(frozen=True, slots=True)
class _RefEntity:
    """Plain adapter bridging the SQLAlchemy ``KBEntry`` (``Mapped[...]``
    class attributes) to the resolver's plain-typed Protocol.

    Built via direct attribute access, which resolves ``Mapped[T]`` to ``T``;
    this avoids the stricter class-level Protocol-membership check that
    ``list[KBEntry]`` would otherwise fail.
    """

    id: uuid.UUID
    name: str
    entity_type: str


def resolve_extracted_refs(
    *,
    character_names: Sequence[str],
    location_name: str,
    entities: Sequence[_ExtractedRefEntity],
) -> tuple[list[dict[str, str]], dict[str, str] | None]:
    """Resolve extracted names against KB entities into timeline-event refs.

    Args:
        character_names: Character names observed by the extractor near the
            temporal expression. Only names matching a KB character entity are
            linked; non-matches are omitted.
        location_name: Location name observed by the extractor. Resolves to the
            single matching KB location entity or ``None``.
        entities: The novel's KB entities (any entity type; this helper
            partitions by ``entity_type`` == ``"character"`` / ``"location"``).

    Returns:
        A ``(character_refs, location_ref)`` tuple in the wire shape persisted
        on ``TimelineEvent``: ``character_refs`` is a list of
        ``{"id": str, "name": str}`` dicts (deduped by entity id, order
        preserved); ``location_ref`` is the matching location dict or ``None``.
        Empty / unmatched input degrades to ``([], None)`` (RULE-11).
    """
    # Partition entities by type and index by normalized name for O(1) lookup.
    characters_by_name: dict[str, _ExtractedRefEntity] = {}
    locations_by_name: dict[str, _ExtractedRefEntity] = {}
    for entity in entities:
        key = entity.name.strip().lower()
        if not key:
            continue
        if entity.entity_type == "character":
            characters_by_name.setdefault(key, entity)
        elif entity.entity_type == "location":
            locations_by_name.setdefault(key, entity)

    # Resolve character names → refs, deduping by entity id (order preserved).
    character_refs: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for raw_name in character_names:
        match = characters_by_name.get(raw_name.strip().lower())
        if match is None:
            continue
        eid = str(match.id)
        if eid in seen_ids:
            continue
        seen_ids.add(eid)
        character_refs.append({"id": eid, "name": match.name})

    # Resolve the single location name → one ref or None.
    location_ref: dict[str, str] | None = None
    loc_match = locations_by_name.get(location_name.strip().lower())
    if loc_match is not None:
        location_ref = {"id": str(loc_match.id), "name": loc_match.name}

    return character_refs, location_ref


async def build_extracted_event_create_kwargs(
    provider: KBContextProviderProtocol | None,
    novel_id: uuid.UUID,
    extracted: ExtractedTemporalExpression,
) -> dict[str, object]:
    """Build the ``event_repo.create`` kwargs for a confirmed extracted event.

    Assembles the static extracted-event fields plus the KB-resolved
    ``character_refs`` / ``location_ref``. Refs are resolved by fetching the
    novel's character/location entities through the canonical KB provider
    (ADR-067 — no second repo) and matching the extracted names via
    :func:`resolve_extracted_refs`.

    RULE-11 (graceful degradation): when no provider is wired or the fetch
    fails, refs degrade to empty/``None`` — never an exception — so the event
    is always creatable.

    Args:
        provider: Canonical KB-context provider (``None`` → empty refs).
        novel_id: Novel the event belongs to.
        extracted: The confirmed extracted expression to persist.

    Returns:
        A kwargs dict ready to spread into ``event_repo.create(**kwargs)``
        (matches the repository's ``**fields: object`` signature).
    """
    # Fetch the novel's character/location entities, degrading to [] (RULE-11).
    # ``KBEntry`` is adapted to ``_RefEntity`` via direct attribute access
    # (resolves SQLAlchemy ``Mapped[T]`` → ``T``), feeding plain-typed entities
    # to the pure resolver.
    raw: Sequence[KBEntry]
    if provider is None:
        raw = []
    else:
        try:
            raw = await provider.fetch_entities(
                novel_id,
                entity_types=["character", "location"],
            )
        except Exception:
            raw = []
    entities: Sequence[_ExtractedRefEntity] = [
        _RefEntity(id=e.id, name=e.name, entity_type=e.entity_type) for e in raw
    ]

    character_refs, location_ref = resolve_extracted_refs(
        character_names=extracted.character_names,
        location_name=extracted.location_name,
        entities=entities,
    )

    return {
        "novel_id": novel_id,
        "event_name": extracted.event_name or extracted.expression,
        "description": extracted.context,
        "event_type": "plot_point",
        "timestamp_raw": extracted.timestamp_raw,
        "timestamp_normalized": "",
        "source": "extracted",
        "confidence": extracted.confidence,
        "is_confirmed": True,
        "character_refs": character_refs,
        "location_ref": location_ref,
    }
