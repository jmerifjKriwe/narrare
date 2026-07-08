"""KB entity lifecycle contracts: ref integrity + Protocols + policy.

Core-level behavioural contracts every consumer of KB entity references
must satisfy: :class:`RefIntegrityIssue` (issue data shape),
:class:`KBEntityLifecycleObserver` (write-side), :class:`CrossFeatureRefIndex`
(read-side), :class:`ContradictionPromotionPolicy` (issue promotion).

Contracts-first (RULE-03); defined as Protocols because enforcement
lives in Backend services and Platform CI. Core owns vocabulary +
lifecycle semantics only (RULE-07). Extracted from the former monolithic
``integration_contracts.py`` per RULE-04; vocabulary in :mod:`._vocab`,
per-consumer specialisations in :mod:`._planning_consumer` /
:mod:`._chapters_consumer`. Reference: ADR-050 P1-B — CR-AUFG-04-06.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.context.integration_contracts._vocab import (
        ContradictionReason,
        RefResolutionStatus,
    )


# ---------------------------------------------------------------------------
# Ref integrity result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RefIntegrityIssue:
    """A single cross-feature reference integrity issue.

    Produced by :meth:`CrossFeatureRefIndex.check_refs` for each
    consumer-side reference that fails to resolve cleanly against the
    current KB state. Aggregated into warnings or promoted to typed
    consistency issues depending on policy (see
    :class:`ContradictionPromotionPolicy`).
    """

    consumer_feature: str  # e.g. "timeline", "storyboard", "chapter_frontmatter"
    consumer_location: str  # e.g. "timeline_events[12].character_refs[1]"
    ref_kind: Literal["id", "name"]
    ref_value: str  # the raw id or name as stored by the consumer
    resolved_status: RefResolutionStatus
    reason: ContradictionReason
    suggested_action: Literal[
        "remap_to_canonical",
        "mark_deprecated_in_context",
        "warn_only",
        "block_operation",
    ]


# ---------------------------------------------------------------------------
# Cross-feature ref index — Protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class KBEntityLifecycleObserver(Protocol):
    """Contract every consumer of KB entity refs MUST implement.

    When the KB module changes entity lifecycle (rename, deprecate,
    tombstone, hard delete, merge), it calls every registered observer
    so consumers can update their persisted refs or surface stale
    references.

    Why a Protocol and not a function: each consumer has different
    storage (Timeline JSON, Chapter frontmatter text, Storyboard
    outline notes). The Protocol lets each consumer adapt to its own
    storage shape; the KB module does not need to know how the
    consumer persists its refs.

    Implementations live in Backend services
    (``apps/api/narrare/{planning,chapters,storyboard}/``). They are
    registered with the :class:`CrossFeatureRefIndex` via DI at app
    startup. Core defines the contract; Backend implements it
    (RULE-07).
    """

    @property
    def consumer_feature(self) -> str:
        """Stable identifier of the consuming feature
        (e.g. ``"timeline"``, ``"chapter_frontmatter"``)."""
        ...

    async def on_kb_entity_renamed(
        self,
        *,
        novel_id: UUID,
        entity_id: UUID,
        old_name: str,
        new_name: str,
    ) -> None:
        """Called when a KB entity's name changes.

        Consumers SHOULD update stored ``{id, name}`` refs where the
        id matches and the stored name equals ``old_name``. Consumers
        that store name-only refs (chapter frontmatter text) MUST
        surface a stale-name warning rather than silently rewriting
        user content (RULE-22 §7: explicit/manual sources are not
        auto-rewritten).
        """
        ...

    async def on_kb_entity_deprecated(
        self,
        *,
        novel_id: UUID,
        entity_id: UUID,
    ) -> None:
        """Called when a KB entity transitions to ``deprecated`` status.

        Consumers MUST NOT delete their refs. They SHOULD mark the ref
        as ``deprecated`` in any hybrid JSON shape they persist and
        surface a warning when the ref appears in active generation
        context.
        """
        ...

    async def on_kb_entity_deleted(
        self,
        *,
        novel_id: UUID,
        entity_id: UUID,
    ) -> None:
        """Called when a KB entity is hard-deleted.

        Hard delete is destructive. Consumers MUST NOT silently drop
        refs; they SHOULD either (a) promote to a tombstone marker in
        their own storage, or (b) emit a :class:`RefIntegrityIssue`
        with ``reason="deleted_ref_without_tombstone"`` that the
        consistency pipeline can surface.

        Implementations that choose (a) document the tombstone shape
        in their feature spec. The KB module itself does not store
        tombstones (hard delete is hard delete).
        """
        ...


@runtime_checkable
class CrossFeatureRefIndex(Protocol):
    """Read-side contract: resolve consumer-side refs against current KB.

    Used by the consistency pipeline and the Context Inspector to
    answer: "given the refs consumer X holds right now, which ones
    are stale, deprecated, or dangling?"

    Implementations live in Backend (e.g. a service in
    ``apps/api/narrare/consistency/`` that joins timeline_events /
    chapter frontmatter / chapter_outlines against kb_entries).

    ADR-044's :func:`enrich_timeline_envelopes` is a partial
    implementation of this Protocol (Timeline consumer only, name-based
    matching). The full Protocol covers all consumers and id+name
    matching.
    """

    async def check_refs(
        self,
        *,
        novel_id: UUID,
        consumer_feature: str,
    ) -> list[RefIntegrityIssue]:
        """Return all ref integrity issues for one consumer feature.

        Args:
            novel_id: Scope the scan to one novel.
            consumer_feature: Identifier matching a registered
                :class:`KBEntityLifecycleObserver.consumer_feature`.

        Returns:
            List of :class:`RefIntegrityIssue`. Empty list when every
            ref resolves cleanly. Issues are NOT mutated — promotion
            to typed consistency issues is decided by
            :class:`ContradictionPromotionPolicy`.
        """
        ...

    async def resolve_ref(
        self,
        *,
        novel_id: UUID,
        ref_kind: Literal["id", "name"],
        ref_value: str,
    ) -> RefResolutionStatus:
        """Resolve a single ref to its current lifecycle status.

        Returns ``active`` for any non-deprecated entity,
        ``deprecated`` for entities marked deprecated in KB,
        ``unknown`` when the ref cannot be resolved by either id or
        name (lookup miss), and ``deleted`` only when the caller can
        prove a prior existence (e.g. via tombstone marker in the
        consumer's own storage).
        """
        ...


@dataclass(frozen=True, slots=True)
class ContradictionPromotionPolicy:
    """Policy that decides when a :class:`RefIntegrityIssue` becomes
    a typed ``ConsistencyIssue`` (CONS-001).

    The consistency pipeline already has a single-pass agent and an
    ADR-044 staged pipeline. This policy is the bridge between
    deterministic ref-integrity checks and the typed issue space:
    soft warnings stay warnings, hard contradictions get promoted so
    the user sees them in the consistency report.

    The default policy promotes:

    * ``stale_name_ref`` → ``warning`` (informational, common after
      rename)
    * ``deprecated_ref_in_active_context`` → ``warning`` (user may
      have intended to reference deprecated lore)
    * ``deleted_ref_without_tombstone`` → ``error`` (dangling ref,
      cannot be honoured)
    * ``rename_target_missing`` → ``error`` (rename implied a target
      that does not exist)
    * ``duplicate_after_merge`` → ``warning`` (post-merge cleanup
      opportunity)
    * ``type_drift`` → ``error`` (entity changed type, ref semantics
      broken)

    Backend services construct this policy from project settings
    (RULE-18: no hardcoded config in routers). Core defines the
    shape; Backend defines the values.
    """

    promote_to_error: frozenset[ContradictionReason] = frozenset(
        {
            "deleted_ref_without_tombstone",
            "rename_target_missing",
            "type_drift",
        }
    )
    promote_to_warning: frozenset[ContradictionReason] = frozenset(
        {
            "stale_name_ref",
            "deprecated_ref_in_active_context",
            "duplicate_after_merge",
        }
    )
