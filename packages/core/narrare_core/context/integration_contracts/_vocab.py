"""Shared vocabulary for cross-feature KB integration contracts.

Type aliases (``Literal``) shared by every consumer of KB entity
references. These are the Core-level vocabulary every consumer uses so
that rename/deprecate/delete semantics are identical across Timeline,
Storyboard and Chapter frontmatter (ADR-050 Decision 2).

Extracted from the former monolithic ``integration_contracts.py`` per
RULE-04 (preventive modularization — see review-01 AUFG-01-03). The
lifecycle Protocols and per-consumer specialisations live in the
sibling modules; the package ``__init__.py`` re-exports the full public
API for backward compatibility.

Reference: ADR-050 P1-B — CR-AUFG-04-06.
"""

from __future__ import annotations

from typing import Literal

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
