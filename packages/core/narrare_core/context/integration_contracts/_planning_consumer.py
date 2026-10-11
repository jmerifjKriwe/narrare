"""Planning consumers of the KB entity lifecycle (ADR-050 P1-B).

Specialisations of :class:`KBEntityLifecycleObserver` for the two
planning-owned consumers of KB entity references:

* :class:`TimelineRefConsumer` — hybrid JSON ``{id, name}`` refs on
  ``timeline_events`` (PLAN-004).
* :class:`StoryboardRefConsumer` — name-based free text in
  ``chapter_outlines`` (``outline_notes``) and ``scene_plans``
  (PLAN-005 / PLAN-001); never holds authoritative JSON refs.

Extracted from the former monolithic ``integration_contracts.py`` per
RULE-04. Base Protocol in :mod:`._kb_lifecycle`; vocabulary in
:mod:`._vocab`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from narrare_core.context.integration_contracts._kb_lifecycle import KBEntityLifecycleObserver


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
      :class:`~narrare_core.context.integration_contracts.RefIntegrityIssue` with reason
      ``deleted_ref_without_tombstone`` for every event referencing
      the deleted id.
    """

    @property
    def consumer_feature(self) -> str:
        return "timeline"
        ...


@runtime_checkable
class StoryboardRefConsumer(KBEntityLifecycleObserver, Protocol):
    """Specialisation for the Storyboard consumer (PLAN-005, scene-scan per PLAN-001 §7).

    The Storyboard does NOT store authoritative KB entity refs. It reads
    ``chapter_outlines`` (``stage_assignment``, ``outline_notes``) and the
    chapter's ``scene_plans`` rows. Scene POV/location carry *hybrid*
    ``{id, name}`` refs (TimelineEvent pattern) so display survives KB
    deletion — the name is the semantic carrier, and every scene text
    field may reference entity names in free text. Therefore the
    Storyboard is affected by KB lifecycle changes only **indirectly**:

    * Scene text is user content and is NEVER rewritten (RULE-22 §7);
      the consumer surfaces soft warnings instead.
    * The storyboard itself has no refs to repair — hybrid refs are
      left as-is (stale names remain readable by design).

    Scene scan surface (per scene row): ``title``, ``purpose``,
    ``conflict``, ``resolution``, each ``beats[]`` entry,
    ``present_characters[].name`` / ``.goal``, ``pov_character_ref.name``
    and ``location_ref.name``. Issue locations use the
    ``scene_plans[{id}].{field}`` form (e.g.
    ``scene_plans[<uuid>].purpose``).

    Required behaviour:

    * ``on_kb_entity_renamed``: scan ``outline_notes`` and the scene
      scan surface for occurrences of ``old_name``. Emit
      :class:`RefIntegrityIssue` with reason ``stale_name_ref`` for
      each match. Do NOT rewrite.
    * ``on_kb_entity_deprecated``: scan the same surface for the name.
      Emit :class:`RefIntegrityIssue` with reason
      ``deprecated_ref_in_active_context`` if found.
    * ``on_kb_entity_deleted``: scan the same surface for the name.
      Emit :class:`RefIntegrityIssue` with reason
      ``deleted_ref_without_tombstone`` if found.
    """

    @property
    def consumer_feature(self) -> str:
        return "storyboard"
        ...
