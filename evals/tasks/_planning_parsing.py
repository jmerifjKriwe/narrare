"""Deterministic text-extraction helpers for the planning_structure smoke task.

Pure functions that derive structured signals (character names, state pairs,
chapter segments, entities, arc-type keywords) from plain prompt text. They
hold no model knowledge and make no LLM calls — they exist so the
``planning_structure_smoke`` producers stay compact and within the RULE-04
file-size limit while still producing varied, schema-valid outputs that
exercise the metadata-aware evaluators on real properties.
"""

from __future__ import annotations

import re

# Deterministic keyword → arc_type routing for the character arc producer.
# Mirrors the documented arc_type vocabulary (growth, fall, transformation,
# flat) from character_arc_types.CharacterArcOutput.
_ARC_TYPE_KEYWORDS: list[tuple[str, str]] = [
    ("flat", "flat"),
    ("unchanging", "flat"),
    ("steady", "flat"),
    ("fall", "fall"),
    ("downfall", "fall"),
    ("corrupt", "fall"),
    ("transform", "transformation"),
    ("redemption", "transformation"),
    ("redeem", "transformation"),
]

# Common tokens that look capitalized but are not character names.
_NON_NAME_TOKENS: frozenset[str] = frozenset(
    {"the", "a", "an", "she", "he", "they", "from", "chapter"}
)


def split_sentences(text: str) -> list[str]:
    """Split *text* into trimmed, non-empty sentences (best-effort)."""

    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def capitalized_tokens(text: str, *, min_length: int = 3) -> list[str]:
    """Return distinct capitalized tokens from *text* (order-preserving)."""

    names: list[str] = []
    for token in text.replace(".", " ").replace(",", " ").split():
        candidate = token.strip("“”\"';:!?")
        if len(candidate) < min_length or not candidate[:1].isupper():
            continue
        if candidate.lower() in _NON_NAME_TOKENS:
            continue
        if candidate not in names:
            names.append(candidate)
    return names


def detect_arc_type(text: str) -> str:
    """Map keywords in *text* to a documented arc_type (default growth)."""

    lowered = text.lower()
    for keyword, arc_type in _ARC_TYPE_KEYWORDS:
        if keyword in lowered:
            return arc_type
    return "growth"


def first_character_name(text: str) -> str:
    """Return the first ``Name:`` value or first capitalized token."""

    match = re.search(r"\b([A-Z][a-z]+)\s*:", text)
    if match:
        return match.group(1)
    tokens = capitalized_tokens(text, min_length=1)
    return tokens[0] if tokens else "Protagonist"


def extract_state_pair(text: str) -> tuple[str, str]:
    """Extract ``from X to Y`` states; fall back to deterministic defaults."""

    match = re.search(r"\bfrom\s+(.+?)\s+to\s+(.+?)[.\n]", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return "A tentative starting state.", "A resolved ending state."


def extract_relationships(text: str) -> list[str]:
    """Return capitalized tokens beyond the protagonist as relationships."""

    names = capitalized_tokens(text)
    # Drop the protagonist (first detected name) to list only relationships.
    return names[1:] if len(names) > 1 else []


def event_name_from(summary: str) -> str:
    """Derive a short, non-empty event name from a summary sentence."""

    head = summary.split(",")[0].split(":")[-1].strip()
    return head[:80] if head else "Unnamed event"


def parse_entities(text: str) -> list[dict[str, str]]:
    """Parse ``Type: Name`` lines into entity dicts with stable ids."""

    entities: list[dict[str, str]] = []
    for match in re.finditer(r"(?im)^\s*([a-z]+)\s*:\s*(.+?)\s*$", text):
        entity_type = match.group(1).strip().lower()
        name = match.group(2).strip().strip("“”\"';:!?.")
        if not name:
            continue
        entities.append({"id": f"ent-{len(entities) + 1}", "name": name, "type": entity_type})
    return entities
