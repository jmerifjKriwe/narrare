"""Voice profile extraction — character speech metadata → prompt variable.

Extracted from ``context_assembler.py`` for RULE-04 compliance.

This module contains the pure transformation logic for extracting speech
and personality data from KB character entities.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare_core.writing.context_models import KBEntity

# ---------------------------------------------------------------------------
# Helpers (module-level to avoid pyright strict-mode noise with dict access)
# ---------------------------------------------------------------------------


def _add_str_field(
    data: dict[str, object],
    key: str,
    label: str,
    parts: list[str],
) -> None:
    """Append a single string metadata field if present."""
    value = data.get(key)
    if isinstance(value, str) and value:
        parts.append(f"{label}: {value}")


def _add_list_field(
    data: dict[str, object],
    key: str,
    label: str,
    parts: list[str],
    max_items: int = 5,
) -> None:
    """Append a list metadata field if present."""
    value = data.get(key)
    if isinstance(value, list) and value:
        str_items: list[str] = []
        for item in value[:max_items]:  # pyright: ignore[reportUnknownVariableType]
            str_items.append(str(item))  # pyright: ignore[reportUnknownArgumentType]
        if str_items:
            parts.append(f"{label}: {', '.join(str_items)}")


def _extract_speech_parts(  # pyright: ignore[reportUnknownParameterType]
    metadata: object,
) -> list[str]:
    """Extract speech/personality metadata parts from a raw metadata dict.

    Accepts ``metadata: object`` to avoid pyright strict-mode noise with
    ``dict[str, Any]`` patterns.  Runtime isinstance checks ensure safety.
    """
    parts: list[str] = []

    if not isinstance(metadata, dict):
        return parts

    # Speech metadata block
    speech_raw = metadata.get("speech")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if isinstance(speech_raw, dict):
        _add_str_field(speech_raw, "dialect", "dialect", parts)  # pyright: ignore[reportUnknownArgumentType]
        _add_str_field(speech_raw, "vocabulary_quirks", "vocabulary", parts)  # pyright: ignore[reportUnknownArgumentType]
        _add_list_field(speech_raw, "typical_phrases", "typical phrases", parts)  # pyright: ignore[reportUnknownArgumentType]
        _add_str_field(speech_raw, "body_language", "body language", parts)  # pyright: ignore[reportUnknownArgumentType]

    # Personality metadata block
    personality_raw = metadata.get("personality")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if isinstance(personality_raw, dict):
        _add_list_field(personality_raw, "traits", "personality traits", parts)  # pyright: ignore[reportUnknownArgumentType]

    return parts


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_voice_profiles(entities: list[KBEntity]) -> str:
    """Extract speech/voice data from character KB entities.

    Formats character speech patterns as a dedicated voice profile block
    for prompt injection.  Falls back gracefully when no speech metadata
    is available.
    """
    characters = [e for e in entities if e.entity_type == "character"]
    if not characters:
        return ""

    profiles: list[str] = []
    for char in characters:
        speech_data = get_speech_data(char)
        if speech_data:
            profiles.append(f"**{char.name}**: {speech_data}")

    return "\n".join(profiles) if profiles else ""


def get_speech_data(entity: KBEntity) -> str:
    """Extract speech-relevant info from a character entity."""
    metadata = entity.metadata
    if not metadata:
        return ""

    parts = _extract_speech_parts(metadata)
    return "; ".join(parts) if parts else ""
