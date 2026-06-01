"""Context validators — reference integrity and freshness checks.

Validation helpers extracted from ``context_assembler.py`` for RULE-04
compliance.  Pure data transformations — no I/O, no database, no LLM
calls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.writing._voice_profiles import extract_voice_profiles

if TYPE_CHECKING:
    from narrare_core.writing.context_models import KBEntity

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Orphan reference check
# ---------------------------------------------------------------------------


def check_orphan_references(
    ref_ids: set[str],
    classified_entities: list[KBEntity],
) -> list[str]:
    """Check for frontmatter references that don't exist in the KB.

    When the frontmatter mentions entities that aren't found in the
    classified entity list, they are orphan references — either they
    don't exist in the KB or they have been deprecated.

    Returns a list of human-readable warning strings.
    """
    classified_ids = {e.entity_id for e in classified_entities}
    orphan_refs = ref_ids - classified_ids
    warnings: list[str] = []
    if orphan_refs:
        for orphan_id in orphan_refs:
            logger.warning(
                "orphan_reference_in_frontmatter",
                entity_id=orphan_id,
            )
            warnings.append(
                f"Frontmatter references entity '{orphan_id}' which is not in "
                f"the knowledge base or was excluded (deprecated)",
            )
    return warnings


# ---------------------------------------------------------------------------
# Voice profile freshness check
# ---------------------------------------------------------------------------


def check_voice_profile_freshness(
    entities: list[KBEntity],
    max_age_days: int = 30,
) -> list[str]:
    """Check if character voice profiles are stale (not updated recently).

    Delegates freshness detection to ``extract_voice_profiles``.
    Returns only the list of warning strings (empty when all profiles
    are current or when no character entities exist).
    """
    _, warnings = extract_voice_profiles(entities, max_age_days)
    return warnings


# ---------------------------------------------------------------------------
# Entity name extraction
# ---------------------------------------------------------------------------


def extract_entity_names(
    entities: list[KBEntity],
) -> tuple[list[str], list[str], list[str]]:
    """Extract character, location, and faction names from entities.

    Returns:
        Tuple of (character_names, location_names, faction_names).
    """
    chars = [e.name for e in entities if e.entity_type == "character"]
    locs = [e.name for e in entities if e.entity_type == "location"]
    facs = [e.name for e in entities if e.entity_type == "faction"]
    return chars, locs, facs
