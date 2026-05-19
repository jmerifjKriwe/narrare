"""Cascade resolver — resolves entity-type templates with DB override support.

Implements the core ``TemplateResolver`` protocol.  Resolution cascade:
1. DB user override (if repository and user_id provided)
2. DB project override (if repository and project_id provided)
3. Bundled defaults (loaded by entity_type only).

Templates are language-neutral — display text comes from the i18n system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.templates import (
    Template,
    TemplateMeta,
    list_default_templates,
    load_default_template,
    parse_template,
)

if TYPE_CHECKING:
    import uuid

    from narrare.templates.contracts import TemplateRepositoryProtocol


class CascadeResolver:
    """Resolve templates using DB overrides → bundled defaults.

    Injects an optional repository to check for user/project-level overrides
    before falling back to bundled defaults.  Resolution is by entity_type
    only — there is no language dimension.

    Implements ``TemplateResolver`` protocol from core.
    """

    def __init__(self, repository: TemplateRepositoryProtocol | None = None) -> None:
        """Initialize resolver with optional repository for DB override lookups.

        Args:
            repository: Optional template repository for DB-backed overrides.
        """
        self._repository = repository

    async def resolve(
        self,
        entity_type: str,
        *,
        user_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
    ) -> Template | None:
        """Resolve a template with cascade: user → project → bundled.

        Tries user override first (if user_id provided and repository configured),
        then project override (if project_id provided), then falls back to
        bundled defaults.

        Args:
            entity_type: Entity type string (e.g. "character").
            user_id: Optional user UUID for user-scope overrides.
            project_id: Optional project UUID for project-scope overrides.

        Returns:
            Parsed template, or ``None`` if not found.
        """
        # Try user override first (highest priority)
        if self._repository is not None and user_id is not None:
            user_tpl = await self._repository.get_override(
                entity_type,
                "user",
                user_id,
            )
            if user_tpl is not None:
                return user_tpl

        # Try project override
        if self._repository is not None and project_id is not None:
            proj_tpl = await self._repository.get_override(
                entity_type,
                "project",
                project_id,
            )
            if proj_tpl is not None:
                return proj_tpl

        # Fall back to bundled defaults
        raw = load_default_template(entity_type)
        if raw is None:
            return None
        return parse_template(raw)

    def resolve_sync(self, entity_type: str) -> Template | None:
        """Synchronous resolve — bundled defaults only.

        This is the sync variant for contexts where async DB lookup is
        not available.

        Args:
            entity_type: Entity type string (e.g. "character").

        Returns:
            Parsed template, or ``None`` if not found.
        """
        raw = load_default_template(entity_type)
        if raw is None:
            return None
        return parse_template(raw)

    def list_available(self) -> list[TemplateMeta]:
        """Return metadata for all bundled default templates."""
        results: list[TemplateMeta] = []
        seen: set[str] = set()

        for entity_type in list_default_templates():
            if entity_type in seen:
                continue
            seen.add(entity_type)

            raw = load_default_template(entity_type)
            if raw is None:
                continue

            template = parse_template(raw)
            results.append(template.meta)

        return results
