"""Voice profile extraction — backward-compat re-exports.

New code should import from :mod:`narrare_core.profiles` instead.
This module is kept for backward compatibility with existing callers
in ``writing/`` and tests.

The actual implementation now lives in:

- :mod:`narrare_core.profiles._voice_extraction`  — extraction helpers
- :mod:`narrare_core.profiles._freshness`          — staleness checks
- :mod:`narrare_core.profiles.models`              — data models
- :mod:`narrare_core.profiles.assembly`            — ProfileAssembler
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.profiles._freshness import is_stale as _is_stale
from narrare_core.profiles._voice_extraction import (
    build_character_voice_profile,
    get_speech_data,
)

__all__ = [
    "_is_stale",
    "extract_voice_profiles",
    "get_speech_data",
]

if TYPE_CHECKING:
    from narrare_core.writing.context_models import KBEntity

logger = structlog.get_logger(__name__)


def extract_voice_profiles(
    entities: list[KBEntity],
    max_age_days: int = 30,
) -> tuple[str, list[str]]:
    """Extract voice profiles from KB entities (backward-compat wrapper).

    New code should use :class:`~narrare_core.profiles.assembly.ProfileAssembler`
    instead.

    Args:
        entities: All KB entities to scan for character voice profiles.
        max_age_days: Maximum age in days for a profile to be considered
            current.  Default 30.

    Returns:
        Tuple of (formatted_voice_profiles_text, warning_list).
    """
    characters = [e for e in entities if e.entity_type == "character"]
    if not characters:
        return "", []

    profiles: list[str] = []
    warnings: list[str] = []
    for char in characters:
        vp = build_character_voice_profile(
            entity_id=char.entity_id,
            name=char.name,
            metadata=char.metadata,
            updated_at=char.updated_at,
            max_age_days=max_age_days,
        )
        if vp is None:
            continue

        line = f"**{vp.name}**: {vp.speech_summary}"
        if not vp.is_fresh and vp.updated_at:
            line += f" [\u26a0\ufe0f last updated: {vp.updated_at}]"
            warnings.append(
                f"Voice profile for '{vp.name}' last updated {vp.updated_at} "
                f"(>{max_age_days} days ago)"
            )
            logger.warning(
                "voice_profile_stale",
                entity_id=char.entity_id,
                entity_name=char.name,
                updated_at=char.updated_at,
                max_age_days=max_age_days,
            )
        profiles.append(line)

    return "\n".join(profiles) if profiles else "", warnings
