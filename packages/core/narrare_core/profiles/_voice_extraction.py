"""Voice profile extraction — character speech metadata → CharacterVoiceProfile.

Relocated from ``writing/_voice_profiles.py`` for P2 (CR-03).

IMPORTANT: This module must NOT import from ``writing/`` (RULE-07).
The extraction function accepts generic primitives, not KBEntity directly.
"""

from __future__ import annotations

import structlog
from pydantic import ValidationError

from narrare_core.kb.schemas.character import VoiceMetrics
from narrare_core.profiles._freshness import is_stale
from narrare_core.profiles.models import CharacterVoiceProfile

logger = structlog.get_logger(__name__)

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


def _formality_descriptor(formality: float) -> str:
    """Map a 0.0-1.0 formality score to a prompt-friendly register word.

    Used by the voice_analysis consumer (ADR-055). The numeric value itself
    is never rendered into generation — only this descriptor.
    """
    if formality < 0.34:
        return "casual"
    if formality < 0.67:
        return "balanced"
    return "formal"


def _add_voice_analysis_parts(  # pyright: ignore[reportUnknownParameterType]
    voice_analysis_raw: dict[str, object],
    parts: list[str],
) -> None:
    """Render the machine-derived ``voice_analysis`` DESCRIPTIVE group.

    ADR-055 constraint: this renders ONLY the descriptive fields (formality,
    vocabulary_level, sentence_profile, emotional_range,
    cultural_regional_markers, voice_examples). The metric block
    (``voice_metrics``) is NEVER rendered — raw deterministic metrics never
    reach generation (they are comparison-only for ANAL-009/WRITE-010).
    """
    # Formality (float 0.0-1.0) → register descriptor (number not rendered).
    # bool is a subclass of int, so exclude it explicitly.
    formality = voice_analysis_raw.get("formality")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if not isinstance(formality, bool) and isinstance(formality, (int, float)):
        parts.append(f"voice: {_formality_descriptor(float(formality))}")

    _add_str_field(voice_analysis_raw, "vocabulary_level", "vocabulary level", parts)  # pyright: ignore[reportUnknownArgumentType]
    _add_str_field(voice_analysis_raw, "sentence_profile", "sentence profile", parts)  # pyright: ignore[reportUnknownArgumentType]
    _add_str_field(voice_analysis_raw, "emotional_range", "emotional range", parts)  # pyright: ignore[reportUnknownArgumentType]
    _add_str_field(voice_analysis_raw, "cultural_regional_markers", "markers", parts)  # pyright: ignore[reportUnknownArgumentType]
    _add_list_field(voice_analysis_raw, "voice_examples", "voice examples", parts)  # pyright: ignore[reportUnknownArgumentType]


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
        # Machine-derived descriptive group (ADR-055). Metrics excluded.
        voice_analysis_raw = speech_raw.get("voice_analysis")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if isinstance(voice_analysis_raw, dict):
            _add_voice_analysis_parts(voice_analysis_raw, parts)  # pyright: ignore[reportUnknownArgumentType]

    # Personality metadata block
    personality_raw = metadata.get("personality")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if isinstance(personality_raw, dict):
        _add_list_field(personality_raw, "traits", "personality traits", parts)  # pyright: ignore[reportUnknownArgumentType]

    return parts


def _extract_voice_metrics(  # pyright: ignore[reportUnknownParameterType]
    metadata: object,
) -> VoiceMetrics | None:
    """Extract the structured ``voice_metrics`` block for the checking path.

    ADR-057 Decision 1: the checking consumer reads deterministic metrics via
    this path. Reads ``speech.voice_analysis.voice_metrics`` and constructs a
    :class:`VoiceMetrics` when that block is a non-empty dict. Returns
    ``None`` when the block is absent, empty, not a dict, or malformed
    (RULE-11 graceful — never raises).

    This does NOT participate in generation rendering; the descriptive
    ``speech_summary`` is produced independently by :func:`get_speech_data`
    (which intentionally excludes the metric block, ADR-055).
    """
    if not isinstance(metadata, dict):
        return None
    speech_raw = metadata.get("speech")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if not isinstance(speech_raw, dict):
        return None
    voice_analysis_raw = speech_raw.get("voice_analysis")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if not isinstance(voice_analysis_raw, dict):
        return None
    metrics_raw = voice_analysis_raw.get("voice_metrics")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if not isinstance(metrics_raw, dict) or not metrics_raw:  # pyright: ignore[reportUnknownArgumentType]
        return None
    try:
        return VoiceMetrics.model_validate(metrics_raw)  # pyright: ignore[reportUnknownArgumentType]
    except ValidationError:
        # Malformed metric block → graceful None (RULE-11). The descriptive
        # speech_summary is built independently and is unaffected.
        logger.debug("voice_metrics_malformed_ignored", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def has_speech_block(metadata: object) -> bool:
    """Return True if metadata contains a non-empty ``speech`` sub-dict.

    Unlike :func:`get_speech_data`, this ignores ``personality`` data.
    Voice-profile *freshness* tracking only applies to characters with
    explicit speech patterns (dialect, vocabulary, phrases, body
    language); a personality-only character has no voice profile that
    can go stale.
    """
    if not isinstance(metadata, dict):
        return False
    speech_raw = metadata.get("speech")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if not isinstance(speech_raw, dict):
        return False
    return bool(speech_raw)  # pyright: ignore[reportUnknownArgumentType]


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

    # ADR-057 Decision 1: surface structured metrics on the checking path.
    # Parsed independently of the descriptive summary; None when absent/
    # malformed. Never rendered into generation (see formatted_voice_profiles).
    voice_metrics = _extract_voice_metrics(metadata)
    fresh = not is_stale(updated_at, max_age_days)
    return CharacterVoiceProfile(
        character_id=entity_id,
        name=name,
        speech_summary=speech_summary,
        updated_at=updated_at,
        is_fresh=fresh,
        voice_metrics=voice_metrics,
    )
