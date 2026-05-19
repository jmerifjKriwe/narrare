"""Knowledge Base relationship type definitions.

Defines constants for relationship types organized by entity-type pair,
inverse relationship suggestions, and a lookup helper for discovering
applicable relationship types between entity types.
"""

from __future__ import annotations


class RelationshipType:
    """String constants for relationship types, organized by source→target pair.

    These are **suggestions** — the UI offers them as options, but users
    can define custom relationships.  Constants exist for discoverability
    and consistency.
    """

    # ── Character → Character ────────────────────────────────────────────
    ALLY = "ally"
    RIVAL = "rival"
    MENTOR = "mentor"
    MENTEE = "mentee"
    FAMILY = "family"
    ROMANTIC = "romantic"
    ENEMY = "enemy"
    NEUTRAL = "neutral"
    COLLEAGUE = "colleague"

    # ── Character → Location ─────────────────────────────────────────────
    BORN_IN = "born_in"
    LIVES_IN = "lives_in"
    VISITS = "visits"
    RULES = "rules"
    GUARDS = "guards"

    # ── Character → Faction ──────────────────────────────────────────────
    MEMBER_OF = "member_of"
    LEADER_OF = "leader_of"
    OPPOSES = "opposes"
    FOUNDED_FACTION = "founded_faction"

    # ── Character → Object ───────────────────────────────────────────────
    OWNS = "owns"
    SEEKS = "seeks"
    CREATED = "created"
    DESTROYED = "destroyed"

    # ── Character → System ───────────────────────────────────────────────
    PRACTITIONER_OF = "practitioner_of"
    AFFECTED_BY = "affected_by"

    # ── Location → Location ──────────────────────────────────────────────
    CONTAINS = "contains"
    BORDERS = "borders"
    CONNECTED_TO = "connected_to"

    # ── Faction → Faction ────────────────────────────────────────────────
    FACTION_ALLIES = "faction_allies"
    FACTION_RIVALS = "faction_rivals"
    SUBORDINATE_OF = "subordinate_of"

    # ── Faction → Location ───────────────────────────────────────────────
    HEADQUARTERED_IN = "headquartered_in"
    CONTROLS = "controls"
    CLAIMS = "claims"

    # ── Object → Object ──────────────────────────────────────────────────
    PART_OF = "part_of"
    TRANSFORMS_INTO = "transforms_into"

    # ── Object → System ──────────────────────────────────────────────────
    POWERED_BY = "powered_by"
    CHANNEL_FOR = "channel_for"

    # ── System → System ──────────────────────────────────────────────────
    COUNTERS = "counters"
    ENHANCES = "enhances"
    SUBSET_OF = "subset_of"


# ---------------------------------------------------------------------------
# Inverse relationship suggestions
# ---------------------------------------------------------------------------

INVERSE_SUGGESTIONS: dict[str, str | None] = {
    # Character ↔ Character
    RelationshipType.MENTOR: RelationshipType.MENTEE,
    RelationshipType.MENTEE: RelationshipType.MENTOR,
    RelationshipType.ALLY: RelationshipType.ALLY,
    RelationshipType.RIVAL: RelationshipType.RIVAL,
    RelationshipType.FAMILY: RelationshipType.FAMILY,
    RelationshipType.ROMANTIC: RelationshipType.ROMANTIC,
    RelationshipType.ENEMY: RelationshipType.ENEMY,
    RelationshipType.NEUTRAL: RelationshipType.NEUTRAL,
    RelationshipType.COLLEAGUE: RelationshipType.COLLEAGUE,
    # Character → Location
    RelationshipType.BORN_IN: "birthplace_of",
    RelationshipType.LIVES_IN: "home_of",
    RelationshipType.VISITS: "visited_by",
    RelationshipType.RULES: "ruled_by",
    RelationshipType.GUARDS: "guarded_by",
    # Character → Faction
    RelationshipType.MEMBER_OF: "has_member",
    RelationshipType.LEADER_OF: "led_by",
    RelationshipType.OPPOSES: "opposed_by",
    RelationshipType.FOUNDED_FACTION: "founded_by",
    # Character → Object
    RelationshipType.OWNS: "owned_by",
    RelationshipType.SEEKS: "sought_by",
    RelationshipType.CREATED: "created_by",
    RelationshipType.DESTROYED: "destroyed_by",
    # Character → System
    RelationshipType.PRACTITIONER_OF: "has_practitioner",
    RelationshipType.AFFECTED_BY: "affects",
    # Location → Location
    RelationshipType.CONTAINS: "contained_by",
    RelationshipType.BORDERS: RelationshipType.BORDERS,
    RelationshipType.CONNECTED_TO: RelationshipType.CONNECTED_TO,
    # Faction → Faction
    RelationshipType.FACTION_ALLIES: RelationshipType.FACTION_ALLIES,
    RelationshipType.FACTION_RIVALS: RelationshipType.FACTION_RIVALS,
    RelationshipType.SUBORDINATE_OF: "superior_of",
    # Faction → Location
    RelationshipType.HEADQUARTERED_IN: "headquarters_of",
    RelationshipType.CONTROLS: "controlled_by",
    RelationshipType.CLAIMS: "claimed_by",
    # Object → Object
    RelationshipType.PART_OF: "has_part",
    RelationshipType.TRANSFORMS_INTO: RelationshipType.TRANSFORMS_INTO,
    # Object → System
    RelationshipType.POWERED_BY: "powers",
    RelationshipType.CHANNEL_FOR: "has_channel",
    # System → System
    RelationshipType.COUNTERS: "countered_by",
    RelationshipType.ENHANCES: "enhanced_by",
    RelationshipType.SUBSET_OF: "superset_of",
}
"""Mapping of relationship types to their suggested inverse type strings.

Values are inverse type strings (which may not have constants) or ``None``
if no inverse makes sense.  The UI can offer to create the inverse
automatically when the user adds a relationship.
"""


# ---------------------------------------------------------------------------
# Entity-type pair to relationship types mapping
# ---------------------------------------------------------------------------

_PAIR_SUGGESTIONS: dict[tuple[str, str], list[str]] = {
    ("character", "character"): [
        RelationshipType.ALLY,
        RelationshipType.RIVAL,
        RelationshipType.MENTOR,
        RelationshipType.MENTEE,
        RelationshipType.FAMILY,
        RelationshipType.ROMANTIC,
        RelationshipType.ENEMY,
        RelationshipType.NEUTRAL,
        RelationshipType.COLLEAGUE,
    ],
    ("character", "location"): [
        RelationshipType.BORN_IN,
        RelationshipType.LIVES_IN,
        RelationshipType.VISITS,
        RelationshipType.RULES,
        RelationshipType.GUARDS,
    ],
    ("character", "faction"): [
        RelationshipType.MEMBER_OF,
        RelationshipType.LEADER_OF,
        RelationshipType.OPPOSES,
        RelationshipType.FOUNDED_FACTION,
    ],
    ("character", "object"): [
        RelationshipType.OWNS,
        RelationshipType.SEEKS,
        RelationshipType.CREATED,
        RelationshipType.DESTROYED,
    ],
    ("character", "system"): [
        RelationshipType.PRACTITIONER_OF,
        RelationshipType.AFFECTED_BY,
    ],
    ("location", "location"): [
        RelationshipType.CONTAINS,
        RelationshipType.BORDERS,
        RelationshipType.CONNECTED_TO,
    ],
    ("faction", "faction"): [
        RelationshipType.FACTION_ALLIES,
        RelationshipType.FACTION_RIVALS,
        RelationshipType.SUBORDINATE_OF,
    ],
    ("faction", "location"): [
        RelationshipType.HEADQUARTERED_IN,
        RelationshipType.CONTROLS,
        RelationshipType.CLAIMS,
    ],
    ("object", "object"): [
        RelationshipType.PART_OF,
        RelationshipType.TRANSFORMS_INTO,
    ],
    ("object", "system"): [
        RelationshipType.POWERED_BY,
        RelationshipType.CHANNEL_FOR,
    ],
    ("system", "system"): [
        RelationshipType.COUNTERS,
        RelationshipType.ENHANCES,
        RelationshipType.SUBSET_OF,
    ],
}


def suggested_for(source_type: str, target_type: str) -> list[str]:
    """Return relationship types applicable for a given entity-type pair.

    Args:
        source_type: Entity type of the source (e.g. "character").
        target_type: Entity type of the target (e.g. "location").

    Returns:
        List of suggested relationship type strings.  Empty list for
        unknown combinations (the user can still enter a custom type).
    """
    return list(_PAIR_SUGGESTIONS.get((source_type, target_type), []))
