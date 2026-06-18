"""Cross-feature integration contracts for shared KB-related data.

This module defines the **RULE-22 integration contracts** between the
features that share KB entity references:

* **KB** (owner of ``KBEntry`` lifecycle: draft/reviewed/canon/deprecated)
* **Planning → Timeline** (consumer; stores hybrid JSON ``{id, name}`` refs
  in ``timeline_events.character_refs`` and ``timeline_events.location_ref``)
* **Planning → Storyboard** (consumer; reads ``chapter_outlines`` and
  ``chapter.position`` only — does NOT hold direct KB entity refs)
* **Chapters → Frontmatter** (consumer; references KB entities via
  ``pov_character``, ``location``, ``faction`` keys)
* **Consistency** (consumer of all of the above via the staged pipeline
  in ADR-044 — already covered by ``TimelineEventEnvelope`` provenance)

These contracts are written before implementation (RULE-03). They are
**Protocols** because the concrete enforcement lives in Backend
repositories/services and Platform CI checkers. Core only owns the
vocabulary and the lifecycle semantics (RULE-07).

Reference: ADR-050 P1-B — CR-AUFG-04-06.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from uuid import UUID


# ---------------------------------------------------------------------------
# Shared vocabulary
# ---------------------------------------------------------------------------


#: Lifecycle states KB entities may be in. Matches the
#: ``ck_kb_entries_status`` CHECK constraint in ``kb/models.py`` plus
#: the synthetic states the cross-feature contract must reason about
#: even when the source column does not (yet) expose them.
KBLifecycleState = Literal[
    "draft",
    "reviewed",
    "canon",
    "deprecated",
    # Synthetic states used by ref-status enrichment. These are NOT
    # stored on ``KBEntry.status`` — they describe how a consumer saw
    # the entity at lookup time.
    "unknown",  # consumer looked up an id/name and found no match
    "deleted",  # entity was hard-deleted; consumer still holds a stale ref
]


#: Outcome a consumer observes when it dereferences a KB ref (id or
#: name) through the contract. ``active`` is the umbrella term for
#: draft/reviewed/canon — i.e. the entity is queryable and considered
#: authoritative unless explicitly deprecated. Mirrors the
#: ``_KB_STATUS_MAP`` bridge in ``consistency/timeline_envelope.py``
#: but elevates it to a Core-level contract so every consumer uses the
#: same vocabulary (ADR-050 Decision 2).
RefResolutionStatus = Literal["active", "deprecated", "unknown", "deleted"]


#: Reasons a cross-feature contradiction should be promoted from a soft
#: warning to a typed consistency issue (see CONS-001). The values are
#: machine-readable so the consistency pipeline can apply policy.
ContradictionReason = Literal[
    "stale_name_ref",  # JSON {id, name} where name no longer matches KB
    "deprecated_ref_in_active_context",  # deprecated entity used as if canon
    "deleted_ref_without_tombstone",  # ref points at a hard-deleted entity
    "rename_target_missing",  # entity was renamed but ref still uses old name
    "duplicate_after_merge",  # post-merge two refs point at the same entity
    "type_drift",  # ref was character, KB now says location
]


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


# ---------------------------------------------------------------------------
# Per-consumer contracts
# ---------------------------------------------------------------------------


@runtime_checkable
class TimelineRefConsumer(KBEntityLifecycleObserver, Protocol):
    """Specialisation for the Timeline consumer (PLAN-004).

    Timeline stores ``character_refs: list[dict[str, str]]`` and
    ``location_ref: dict[str, str] | None`` as hybrid JSON
    ``{id, name}`` in ``timeline_events``. The id is the canonical
    KBEntry id at write time; the name is the canonical name at
    write time. Both can become stale after rename/delete.

    Required behaviour:

    * ``on_kb_entity_renamed``: update every ``{id, name}`` where
      ``id == entity_id`` AND ``name == old_name``. Emit one
      :class:`RefIntegrityIssue` per chapter-scoped timeline if the
      rename crosses a story beat (heuristic, see PLAN-004-architecture).
    * ``on_kb_entity_deprecated``: do NOT rewrite; mark the JSON ref
      with ``"status": "deprecated"`` so ADR-044's
      ``enrich_timeline_envelopes`` reports it correctly.
    * ``on_kb_entity_deleted``: emit a
      :class:`RefIntegrityIssue` with reason
      ``deleted_ref_without_tombstone`` for every event referencing
      the deleted id.
    """

    @property
    def consumer_feature(self) -> str:
        return "timeline"
        ...


@runtime_checkable
class StoryboardRefConsumer(KBEntityLifecycleObserver, Protocol):
    """Specialisation for the Storyboard consumer (PLAN-005).

    The Storyboard does NOT store direct KB entity refs. It reads
    ``chapter_outlines`` (``stage_assignment``, ``planned_beats``,
    ``outline_notes``) and ``chapter.position``. Therefore the
    Storyboard is affected by KB lifecycle changes only **indirectly**:

    * ``planned_beats`` may reference entity names in free text.
      Rename/deprecate does NOT rewrite user-authored beats
      (RULE-22 §7). The consumer surfaces a soft warning instead.
    * The storyboard itself has no JSON refs to repair.

    Required behaviour:

    * ``on_kb_entity_renamed``: scan ``outline_notes`` and
      ``planned_beats[].text`` for occurrences of ``old_name``. Emit
      :class:`RefIntegrityIssue` with reason ``stale_name_ref`` for
      each match. Do NOT rewrite.
    * ``on_kb_entity_deprecated``: scan planned beats for the name.
      Emit :class:`RefIntegrityIssue` with reason
      ``deprecated_ref_in_active_context`` if found.
    * ``on_kb_entity_deleted``: scan planned beats for the name.
      Emit :class:`RefIntegrityIssue` with reason
      ``deleted_ref_without_tombstone`` if found.
    """

    @property
    def consumer_feature(self) -> str:
        return "storyboard"
        ...


@runtime_checkable
class ChapterFrontmatterRefConsumer(KBEntityLifecycleObserver, Protocol):
    """Specialisation for chapter frontmatter (WRITE-001 / KB-001).

    Frontmatter references KB entities via keys ``pov_character``,
    ``characters``, ``location``, ``locations``, ``faction``,
    ``factions``, ``system``, ``systems``, ``timeline``,
    ``timelines``. Values may be entity ids (preferred) or names
    (legacy/free-form). Frontmatter is user-authored content
    (RULE-22 §6: ``_USER_CONTENT_VARS`` includes ``chapter_text``
    but frontmatter is structured data on the chapter itself —
    rename/delete MUST NOT auto-rewrite it).

    Required behaviour:

    * ``on_kb_entity_renamed``: never rewrite frontmatter. Emit
      :class:`RefIntegrityIssue` with reason ``stale_name_ref`` for
      each name-based ref that no longer matches.
    * ``on_kb_entity_deprecated``: emit a warning issue. Frontmatter
      continues to reference the deprecated entity until the user
      explicitly updates it.
    * ``on_kb_entity_deleted``: emit an error issue
      (``deleted_ref_without_tombstone``). Future writes that try to
      consume the frontmatter ref will be unable to resolve it.
    """

    @property
    def consumer_feature(self) -> str:
        return "chapter_frontmatter"
        ...
