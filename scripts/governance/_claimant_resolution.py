"""Claimant resolution for the review→registry linking checker.

Single responsibility (RULE-06 / RULE-04 extraction): given a review task
header, find the registry entry that claims it — by direct id match (with
CR-prefix dual-match), or via a documented re-homing. Split out of
:mod:`governance._review_registry_link` so the linking checker stays under the
RULE-04 script file-size limit.

RULE-07: reads registry metadata only. Imports no application runtime modules.

ADR: docs/architecture/decisions/ADR-062-governance-drift-phase2-status-ssot.md
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from governance._review_registry_link import RegistryMeta, ReviewTaskHeader

__all__ = [
    "REHOME_TOKEN",
    "claimant",
    "id_candidates",
]

#: Keyword indicating a documented re-homing in a registry section.
REHOME_TOKEN = "re-hom"  # nosec B105 — re-homing documentation marker, not a credential


def claimant(
    header: ReviewTaskHeader,
    registry: dict[str, RegistryMeta],
) -> tuple[RegistryMeta | None, bool]:
    """Find the registry entry claiming *header*.

    Preference order:
      1. A documented re-homing: an entry (any id) whose source references the
         review AND whose section marks a re-homing from the header's id. This
         is the authoritative, intentional link (preferred over a coincidental
         same-id entry).
      2. The direct same-id entry whose source references the review. CR-prefix
         dual-match (CR-AUFG-01-08): a ``CR-AUFG-NN-MM`` header also matches an
         ``AUFG-NN-MM`` registry key, because CR-02/03/04 content tasks are
         stored unprefixed while the review files write the ``CR-`` prefix.

    Returns ``(entry, via_rehoming)`` or ``(None, False)``.
    """
    rehome = _find_rehoming(header, registry)
    if rehome is not None:
        return rehome, True

    for candidate_id in id_candidates(header.task_id):
        direct = registry.get(candidate_id)
        if direct is not None and _source_references(direct, header.review_file):
            return direct, False
    # Fall back to any same-id hit (without source match) so the caller can
    # report a source_mismatch rather than a missing_entry.
    for candidate_id in id_candidates(header.task_id):
        if candidate_id in registry:
            return registry[candidate_id], False
    return None, False


def id_candidates(task_id: str) -> tuple[str, ...]:
    """Return the registry keys to try for *task_id* (CR-prefix dual-match).

    A ``CR-AUFG-NN-MM`` header matches its own key first, then the unprefixed
    ``AUFG-NN-MM`` key (CR-02/03/04 are stored unprefixed). The identical match
    is tried first so a deliberately CR-prefixed registry entry wins over an
    unprefixed one. Non-CR ids yield just themselves.
    """
    if task_id.startswith("CR-"):
        return (task_id, task_id[3:])
    return (task_id,)


def _find_rehoming(
    header: ReviewTaskHeader,
    registry: dict[str, RegistryMeta],
) -> RegistryMeta | None:
    """Return the entry that documents a re-homing of *header*'s id."""
    for entry in registry.values():
        if entry.entry_id == header.task_id:
            continue
        if not _source_references(entry, header.review_file):
            continue
        if REHOME_TOKEN in entry.section_text.lower() and header.task_id in entry.section_text:
            return entry
    return None


def _source_references(entry: RegistryMeta, review_file: str) -> bool:
    """Return ``True`` when the entry's source cites *review_file* (basename)."""
    return review_file in entry.source
