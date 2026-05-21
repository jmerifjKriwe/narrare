"""Tone resolution — resolves bundled vs custom tone instructions.

Extracted from service.py per RULE-04 (file size limit 300 lines).
This module handles the logic of determining whether a tone name refers
to a bundled built-in tone or a user-defined custom tone, and returns
the appropriate instructions string.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.settings.custom_tone_service import CustomToneService

logger = structlog.get_logger(__name__)


async def resolve_tone_instructions(
    tone: str,
    user_id: UUID,
    tone_service: CustomToneService | None = None,
) -> str | None:
    """Resolve tone instructions for bundled or custom tones.

    For bundled tones (defined in ``_TONE_INSTRUCTIONS``), returns
    ``None`` so the pipeline uses its built-in lookup.  For custom
    tones, looks up instructions from :class:`CustomToneService`.

    Args:
        tone: Tone name or identifier from the request.
        user_id: The user who owns potential custom tones.
        tone_service: Optional custom tone service for user-defined tones.

    Returns:
        Custom instructions string, or ``None`` for bundled tones.
    """
    from narrare_core.writing.pipeline import is_bundled_tone

    if is_bundled_tone(tone):
        return None

    if tone_service is None:
        logger.warning(
            "custom_tone_without_service",
            tone=tone,
            message="Custom tone requested but no tone service configured",
        )
        return ""

    try:
        custom_tones = await tone_service.list_tones(user_id)
        matching = [t for t in custom_tones if t.name == tone or str(t.id) == tone]
        if matching:
            return matching[0].instructions
    except Exception as exc:
        logger.error(
            "custom_tone_resolution_failed",
            tone=tone,
            error=str(exc),
        )

    return ""
