"""AdaptiveSettingsRepository — load/save adaptive_settings JSONB (ADR-069 D2).

Persistence layer for ``ProjectSettings.adaptive_settings``. Maps between
the Core ``AdaptiveSettings`` dataclass and the JSONB column added by
migration 0033. All SQLAlchemy queries live here — services never write
SQL directly (RULE-07).

Mirrors the established settings-repository pattern (read by project_id,
upsert on save).

See:
    ADR-069 Decision 2 (extend ProjectSettings, not new table),
    CONSTRAINTS.md RULE-07 / RULE-14.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import select, update

from narrare.settings.models import ProjectSettings

if TYPE_CHECKING:
    from sqlalchemy.engine import CursorResult
from narrare_core.ai_invocation.adaptive_context import (
    AdaptiveSettings,
    AdaptiveWeights,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


def _adaptive_settings_to_json(settings: AdaptiveSettings) -> dict[str, object]:
    """Serialise AdaptiveSettings to a JSONB-compatible dict."""
    return {
        "enabled": settings.enabled,
        "weights": {
            "preference": settings.weights.preference,
            "voice_fidelity": settings.weights.voice_fidelity,
            "style_constraints": settings.weights.style_constraints,
            "avoidance": settings.weights.avoidance,
        },
    }


def _json_to_adaptive_settings(data: object) -> AdaptiveSettings | None:
    """Deserialise AdaptiveSettings from a JSONB-loaded dict.

    Returns ``None`` when the input is ``None`` or malformed (graceful
    degradation per RULE-11).
    """
    if not isinstance(data, dict):
        return None
    # isinstance() on ``object`` narrows to ``dict[Unknown, Unknown]`` under
    # pyright strict mode; cast to ``dict[str, Any]`` (the JSONB-loaded shape)
    # following the established pattern in ``generation/name_parsing.py``.
    settings_dict: dict[str, Any] = cast("dict[str, Any]", data)
    try:
        enabled = bool(settings_dict.get("enabled", True))
        weights_data_raw: Any = settings_dict.get("weights", {})
        if not isinstance(weights_data_raw, dict):
            weights_data_raw = {}
        weights_data: dict[str, Any] = cast("dict[str, Any]", weights_data_raw)
        weights = AdaptiveWeights(
            preference=float(weights_data.get("preference", 0.7)),
            voice_fidelity=float(weights_data.get("voice_fidelity", 0.9)),
            style_constraints=float(weights_data.get("style_constraints", 1.0)),
            avoidance=float(weights_data.get("avoidance", 1.0)),
        ).validated()
        return AdaptiveSettings(enabled=enabled, weights=weights)
    except TypeError, ValueError:
        return None


class AdaptiveSettingsRepository:
    """Repository for the ``ProjectSettings.adaptive_settings`` column.

    Args:
        session: SQLAlchemy async session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load(self, project_id: UUID) -> AdaptiveSettings | None:
        """Load adaptive settings for a project.

        Returns:
            The stored settings, or ``None`` when no row exists yet or the
            JSONB column is NULL. Callers fall back to defaults.
        """
        stmt = select(ProjectSettings.adaptive_settings).where(
            ProjectSettings.novel_id == project_id
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _json_to_adaptive_settings(row)

    async def save(
        self,
        project_id: UUID,
        settings: AdaptiveSettings,
    ) -> None:
        """Upsert adaptive settings for a project.

        If no ``ProjectSettings`` row exists for this project, one is created
        with the supplied adaptive settings. If a row exists, only
        ``adaptive_settings`` is updated.
        """
        json_payload = _adaptive_settings_to_json(settings)
        stmt = (
            update(ProjectSettings)
            .where(ProjectSettings.novel_id == project_id)
            .values(adaptive_settings=json_payload)
        )
        result = cast("CursorResult[Any]", await self._session.execute(stmt))
        if result.rowcount == 0:
            model = ProjectSettings(
                novel_id=project_id,
                adaptive_settings=json_payload,
            )
            self._session.add(model)
        await self._session.flush()
