"""Relationship endpoint resolution for the extraction apply flow (KB-007).

Resolves both endpoints of a ``relationship`` item (``source_entity_name``/
``target_entity_name``, with legacy ``name``/``related_entity_name``
fallbacks) to KB endpoints. Each endpoint is resolved against the
request's in-batch creations FIRST, then the database — a relationship
may reference an entity created earlier in the same apply request
(benchmark run 5: such items failed with ``source_lookup_failed``
because resolution only saw pre-request state).

Split from ``_extraction_resolution.py`` for RULE-04 compliance (the
update-entity half stayed there; the relationship half grew past the
file-size limit when in-batch resolution was added). All guards are
blocking-only: they may skip an item, never synthesize a merge —
wrong-name unification is prevented semantically by the extraction
prompt's distractor guard, not by lexical heuristics here.

See:
    :class:`narrare.kb.extraction_apply_service.ExtractionApplyService`
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from sqlalchemy.exc import MultipleResultsFound

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.models import KBEntry
    from narrare.kb.schemas_extraction import (
        ApplyExtractionEntryResult,
        ApplyExtractionItem,
    )

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class EndpointRef:
    """Minimal endpoint identity (id + name) for a resolved endpoint.

    Deliberately decoupled from the ORM ``KBEntry`` so endpoints can also
    come from entities created earlier in the same apply request — those
    are not DB rows (yet), only pending inserts.
    """

    id: uuid.UUID
    """The KB entry's primary key."""

    name: str
    """The KB entry's name."""


@dataclass(frozen=True)
class RelationshipEndpoints:
    """Resolved source and target endpoints for a relationship item."""

    source: EndpointRef
    """The relationship's subject endpoint."""

    target: EndpointRef
    """The relationship's object endpoint."""


@dataclass(frozen=True)
class UnresolvedRelationship:
    """A relationship item whose endpoints cannot be resolved.

    ``reason`` is a stable machine-readable identifier that the apply
    service reports in ``ApplyExtractionResponse.skipped`` — unapplied
    items are never silently dropped.
    """

    reason: str


async def resolve_relationship_endpoints(
    item: ApplyExtractionItem,
    kb_repo: KBRepositoryProtocol,
    novel_id: uuid.UUID,
    in_batch_creations: Sequence[ApplyExtractionEntryResult] | None = None,
) -> RelationshipEndpoints | UnresolvedRelationship:
    """Resolve both endpoints of a ``relationship`` item to KB endpoints.

    Source resolution: ``source_entity_name``, falling back to ``name``
    (legacy payloads carried the source entity name there — the prompt
    contract pre-v1.4.0, which used ``name`` for a relationship label,
    is the dead path this resolver repairs). Target resolution:
    ``target_entity_name``, falling back to ``related_entity_name``.

    Each endpoint is resolved against the request's in-batch creations
    FIRST (case-insensitive, mirroring the repository's ``ilike``
    lookup), then the database — so a relationship may reference an
    entity the same apply request just created.

    Every failure mode logs a distinct warning and yields an
    :class:`UnresolvedRelationship` with a stable reason — the caller
    reports the item as skipped (RULE-11 per-item isolation, no crash,
    no silent drop).

    Args:
        item: The endorsed extraction item.
        kb_repo: KB repository (novel-scoped lookups).
        novel_id: Novel whose KB is the resolution scope.
        in_batch_creations: Entries created earlier in the same apply
            request (the service's ``created_entries`` accumulator).

    Returns:
        :class:`RelationshipEndpoints` on success, otherwise
        :class:`UnresolvedRelationship`.
    """
    source_name = item.source_entity_name or item.name
    target_name = item.target_entity_name or item.related_entity_name
    if not _has_text(source_name) or not _has_text(target_name):
        logger.warning(
            "relationship_missing_endpoint_names",
            name=item.name,
            source_entity_name=item.source_entity_name,
            target_entity_name=item.target_entity_name,
        )
        return UnresolvedRelationship(reason="missing_source_or_target_name")

    in_batch = _in_batch_index(in_batch_creations)

    assert source_name is not None
    source = await _resolve_endpoint(
        kb_repo, novel_id, source_name, role="source", in_batch=in_batch
    )
    if isinstance(source, UnresolvedRelationship):
        return source

    assert target_name is not None
    target = await _resolve_endpoint(
        kb_repo, novel_id, target_name, role="target", in_batch=in_batch
    )
    if isinstance(target, UnresolvedRelationship):
        return target

    return RelationshipEndpoints(source=source, target=target)


def _in_batch_index(
    creations: Sequence[ApplyExtractionEntryResult] | None,
) -> dict[str, EndpointRef]:
    """Index the request's in-batch creations by casefolded name.

    Casefolded keys mirror the repository's case-insensitive ``ilike``
    lookup, so in-batch and DB resolution agree on name matching.
    """
    if not creations:
        return {}
    return {
        creation.name.casefold(): EndpointRef(id=UUID(creation.id), name=creation.name)
        for creation in creations
    }


async def _resolve_endpoint(
    kb_repo: KBRepositoryProtocol,
    novel_id: uuid.UUID,
    name: str,
    role: str,
    in_batch: dict[str, EndpointRef],
) -> EndpointRef | UnresolvedRelationship:
    """Resolve one endpoint: in-batch creations first, then the database.

    In-batch creations take precedence so the relationship references the
    entity instance this request just created, not a coincidental
    pre-existing row.
    """
    ref = in_batch.get(name.casefold())
    if ref is not None:
        return ref
    entry = await _lookup_by_name(kb_repo, novel_id, name, role)
    if isinstance(entry, UnresolvedRelationship):
        return entry
    return EndpointRef(id=entry.id, name=entry.name)


async def _lookup_by_name(
    kb_repo: KBRepositoryProtocol,
    novel_id: uuid.UUID,
    name: str,
    role: str,
) -> KBEntry | UnresolvedRelationship:
    """Novel-scoped exact-name lookup with a role-tagged failure reason.

    Ambiguous names (several matches) are treated as unresolvable —
    never a silent pick.
    """
    try:
        entry = await kb_repo.get_by_name(novel_id, name)
    except MultipleResultsFound:
        logger.warning("relationship_ambiguous_name", role=role, name=name)
        return UnresolvedRelationship(reason=f"{role}_ambiguous_name")
    except Exception as exc:
        logger.warning(
            "relationship_name_lookup_failed",
            role=role,
            name=name,
            error=str(exc),
        )
        return UnresolvedRelationship(reason=f"{role}_lookup_failed")

    if entry is None:
        logger.warning(
            "relationship_endpoint_not_found",
            role=role,
            name=name,
            novel_id=str(novel_id),
        )
        return UnresolvedRelationship(reason=f"{role}_not_found")
    return entry


def _has_text(value: str | None) -> bool:
    """True when value is a non-empty, non-whitespace string."""
    return value is not None and value.strip() != ""
