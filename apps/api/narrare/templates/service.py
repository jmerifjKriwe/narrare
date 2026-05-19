"""Template management API service — thin wrapper around repository.

Converts domain objects to Pydantic response schemas.
No business logic — all cascade/override logic lives in the repository
and cascade resolver.

Note: TemplateInfoService in info_service.py handles cascade_info,
detect_updates, and get_diff to keep file sizes under limits.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.templates.schemas import (
    TemplateDetailResponse,
    TemplateInfoResponse,
)
from narrare_core.templates import list_default_templates, load_default_template, parse_template

if TYPE_CHECKING:
    import uuid

    from narrare.templates.repository import TemplateRepository
    from narrare.templates.schemas import SaveOverrideRequest

logger = structlog.get_logger(__name__)


def str_to_uuid(value: str | None) -> uuid.UUID | None:
    """Convert a string to UUID, returning None if input is None or invalid."""
    import uuid

    if value is None:
        return None
    try:
        return uuid.UUID(value)
    except ValueError, AttributeError:
        return None


class TemplateApiService:
    """API service wrapping template repository.

    Converts repository results to Pydantic schemas for HTTP responses.
    All storage logic is delegated to the repository.
    """

    def __init__(self, repository: TemplateRepository) -> None:
        self._repo = repository

    async def list_templates(
        self,
        *,
        entity_type: str | None = None,
        language: str | None = None,
        scope: str = "user",
        scope_id: uuid.UUID | None = None,
    ) -> list[TemplateInfoResponse]:
        """List all templates with override status for a given scope.

        Combines bundled defaults with DB override info to show which
        templates have user/project overrides.

        Args:
            entity_type: Optional entity type filter.
            language: Optional language filter.
            scope: Scope level ("user", "project", "global").
            scope_id: Scope identifier, or None for global.

        Returns:
            List of TemplateInfoResponse schemas.
        """
        bundled = list_default_templates()
        overrides_raw = await self._repo.list_overrides(scope, scope_id)

        overrides_map: dict[tuple[str, str], TemplateInfoResponse] = {}
        for tpl in overrides_raw:
            key = (tpl.meta.template_type, tpl.meta.template_language)
            overrides_map[key] = TemplateInfoResponse(
                entity_type=tpl.meta.template_type,
                language=tpl.meta.template_language,
                scope=scope,
                scope_id=str(scope_id) if scope_id else None,
                schema_version=tpl.meta.schema_version,
                based_on_version=None,
                has_override=True,
            )

        result: list[TemplateInfoResponse] = []
        seen: set[tuple[str, str]] = set()

        for entity_type_b, language_b in bundled:
            key = (entity_type_b, language_b)
            if key in seen:
                continue
            seen.add(key)

            if entity_type is not None and entity_type_b != entity_type:
                continue
            if language is not None and language_b != language:
                continue

            raw = load_default_template(entity_type_b, language_b)
            if raw is None:
                continue
            bundled_tpl = parse_template(raw)

            if key in overrides_map:
                result.append(overrides_map[key])
            else:
                result.append(
                    TemplateInfoResponse(
                        entity_type=entity_type_b,
                        language=language_b,
                        scope=scope,
                        scope_id=str(scope_id) if scope_id else None,
                        schema_version=bundled_tpl.meta.schema_version,
                        based_on_version=bundled_tpl.meta.template_version,
                        has_override=False,
                    )
                )

        return result

    async def get_template(
        self,
        entity_type: str,
        language: str,
        *,
        scope: str = "user",
        scope_id: uuid.UUID | None = None,
    ) -> TemplateDetailResponse | None:
        """Get full template detail with cascade info.

        Shows the active template for this scope, including the base
        content from bundled defaults if it's overridden.

        Args:
            entity_type: Entity type (e.g. "character").
            language: Language code (e.g. "en").
            scope: Scope level ("user", "project", "global").
            scope_id: Scope identifier, or None for global.

        Returns:
            TemplateDetailResponse or None if not found.
        """
        raw = load_default_template(entity_type, language)
        if raw is None:
            return None

        base_content = raw
        base_tpl = parse_template(raw)

        override = await self._repo.get_override(entity_type, language, scope, scope_id)
        if override is not None:
            content = override.raw
            is_overridden = True
            based = override.meta.template_version
        else:
            content = base_content
            is_overridden = False
            based = base_tpl.meta.template_version

        return TemplateDetailResponse(
            entity_type=entity_type,
            language=language,
            scope=scope,
            content=content,
            base_content=base_content,
            schema_version=base_tpl.meta.schema_version,
            based_on_version=based,
            is_overridden=is_overridden,
        )

    async def save_override(
        self,
        entity_type: str,
        language: str,
        request: SaveOverrideRequest,
        *,
        scope: str = "user",
        scope_id: uuid.UUID | None = None,
    ) -> TemplateDetailResponse:
        """Save a template override.

        Args:
            entity_type: Entity type (e.g. "character").
            language: Language code (e.g. "en").
            request: SaveOverrideRequest with content.
            scope: Scope level ("user", "project", "global").
            scope_id: Scope identifier, or None for global.

        Returns:
            TemplateDetailResponse for the saved override.
        """
        override = await self._repo.save_override(
            entity_type=entity_type,
            language=language,
            scope=scope,
            scope_id=scope_id,
            content=request.content,
            based_on_version=request.based_on_version,
        )

        raw = load_default_template(entity_type, language)
        base_content: str | None = raw

        logger.info(
            "template_override_saved_api",
            entity_type=entity_type,
            language=language,
            scope=scope,
        )

        return TemplateDetailResponse(
            entity_type=entity_type,
            language=language,
            scope=scope,
            content=request.content,
            base_content=base_content,
            schema_version=override.meta.schema_version,
            based_on_version=request.based_on_version,
            is_overridden=True,
        )

    async def reset_override(
        self,
        entity_type: str,
        language: str,
        *,
        scope: str = "user",
        scope_id: uuid.UUID | None = None,
    ) -> bool:
        """Reset a template override, restoring the bundled default.

        Args:
            entity_type: Entity type (e.g. "character").
            language: Language code (e.g. "en").
            scope: Scope level ("user", "project", "global").
            scope_id: Scope identifier, or None for global.

        Returns:
            True if an override was deleted, False if none existed.
        """
        return await self._repo.delete_override(
            entity_type=entity_type,
            language=language,
            scope=scope,
            scope_id=scope_id,
        )
