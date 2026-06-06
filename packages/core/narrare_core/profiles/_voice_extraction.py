"""Voice profile extraction — character speech metadata → CharacterVoiceProfile.

Relocated from ``writing/_voice_profiles.py`` for P2 (CR-03).

IMPORTANT: This module must NOT import from ``writing/`` (RULE-07).
The extraction function accepts generic primitives, not KBEntity directly.
"""

from __future__ import annotations

from narrare_core.profiles._freshness import is_stale
from narrare_core.profiles.models import CharacterVoiceProfile

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


def get_speech_data(metadata: object) -> str:
    """Extract speech-relevant info from entity metadata.

    Args:
        metadata: Raw metadata dict (speech, personality sub-dicts).

    Returns:
        Semicolon-joined speech/personality parts, or empty string.
    """
    if not metadata:
        return ""
    parts = _extract_speech_parts(metadata)
    return "; ".join(parts) if parts else ""


def build_character_voice_profile(
    entity_id: str,
    name: str,
    metadata: object,
    updated_at: str | None = None,
    max_age_days: int = 30,
) -> CharacterVoiceProfile | None:
    """Build a :class:`CharacterVoiceProfile` from a KB entity's data.

    Takes individual fields rather than a full ``KBEntity`` — this keeps
    the profiles module independent of the ``writing/`` module's types
    (RULE-07).

    Returns ``None`` if no speech data is available.
    """
    speech_summary = get_speech_data(metadata)
    if not speech_summary:
        return None

    fresh = not is_stale(updated_at, max_age_days)
    return CharacterVoiceProfile(
        character_id=entity_id,
        name=name,
        speech_summary=speech_summary,
        updated_at=updated_at,
        is_fresh=fresh,
    )
