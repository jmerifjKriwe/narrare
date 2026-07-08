"""Cross-feature integration contracts for shared KB-related data.

This package defines the **RULE-22 integration contracts** between the
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

Structure (split per RULE-04 preventive modularization — review-01
AUFG-01-03; the former monolithic ``integration_contracts.py`` sat
exactly at the 400-line hard limit):

* :mod:`._vocab` — shared ``Literal`` vocabulary
  (:data:`KBLifecycleState`, :data:`RefResolutionStatus`,
  :data:`ContradictionReason`).
* :mod:`._kb_lifecycle` — ref-integrity dataclass + the two core
  Protocols + promotion policy.
* :mod:`._planning_consumer` — Timeline + Storyboard consumer
  specialisations.
* :mod:`._chapters_consumer` — Chapter frontmatter consumer
  specialisation.

Public API unchanged: every name previously importable from
``narrare_core.context.integration_contracts`` is still importable from
there via this ``__init__.py`` (backward compatibility by re-export).

Reference: ADR-050 P1-B — CR-AUFG-04-06.
"""

from __future__ import annotations

from narrare_core.context.integration_contracts._chapters_consumer import (
    ChapterFrontmatterRefConsumer,
)
from narrare_core.context.integration_contracts._kb_lifecycle import (
    ContradictionPromotionPolicy,
    CrossFeatureRefIndex,
    KBEntityLifecycleObserver,
    RefIntegrityIssue,
)
from narrare_core.context.integration_contracts._planning_consumer import (
    StoryboardRefConsumer,
    TimelineRefConsumer,
)
from narrare_core.context.integration_contracts._vocab import (
    ContradictionReason,
    KBLifecycleState,
    RefResolutionStatus,
)

__all__ = [
    "ChapterFrontmatterRefConsumer",
    "ContradictionPromotionPolicy",
    "ContradictionReason",
    "CrossFeatureRefIndex",
    "KBEntityLifecycleObserver",
    "KBLifecycleState",
    "RefIntegrityIssue",
    "RefResolutionStatus",
    "StoryboardRefConsumer",
    "TimelineRefConsumer",
]
