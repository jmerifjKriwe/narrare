"""Detection repository — template update detection.

Provides version comparison between stored overrides and bundled defaults.
Isolated from the main CRUD repository to keep each file under size limits.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from narrare._app.base_repository import BaseRepository
from narrare.templates.models import KBTemplate, TemplateScope

if TYPE_CHECKING:
    import uuid

logger = structlog.get_logger(__name__)


class TemplateDetectionRepository(BaseRepository):
    """Repository for detecting template version mismatches.

    Compares ``based_on_version`` stored in each override with the
    current version from bundled defaults to find available updates.
    """

    async def detect_updates(
        self,
        scope: str,
        scope_id: uuid.UUID | None,
    ) -> list[dict[str, str]]:
        """Detect overrides whose bundled version has changed.

        Args:
            scope: Scope level ("user", "project", "global").
            scope_id: Scope identifier, or None for global.

        Returns:
            List of dicts with entity_type, language, override_version,
            current_bundled_version keys.
        """
        from narrare_core.templates import load_default_template, parse_template

        stmt = select(KBTemplate).where(
            KBTemplate.scope == TemplateScope(scope),
            KBTemplate.scope_id == scope_id,
        )
        result = await self._session.execute(stmt)
        overrides = result.scalars().all()

        updates: list[dict[str, str]] = []
        for override in overrides:
            if override.based_on_version is None:
                continue
            raw = load_default_template(override.entity_type, override.language)
            if raw is None:
                continue
            bundled = parse_template(raw)
            current_version = bundled.meta.template_version
            if current_version != override.based_on_version:
                updates.append(
                    {
                        "entity_type": override.entity_type,
                        "language": override.language,
                        "override_version": override.based_on_version,
                        "current_bundled_version": current_version,
                    }
                )

        return updates
