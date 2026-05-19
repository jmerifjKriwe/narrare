"""Template storage protocol — defines interface for CRUD operations.

Written before implementation (RULE-03).  The repository protocol
abstracts the DB storage of template overrides so the service layer
can be tested without a real database.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare_core.templates import Template


@runtime_checkable
class TemplateRepositoryProtocol(Protocol):
    """Protocol for template override storage.

    Implementations provide CRUD access to persisted template overrides
    in the ``kb_templates`` table.  All methods are async.  Templates
    are keyed by ``(entity_type, scope, scope_id)`` — no language dimension.
    """

    async def get_override(
        self,
        entity_type: str,
        scope: str,
        scope_id: uuid.UUID | None,
    ) -> Template | None:
        """Look up a single template override by its cascade key.

        Args:
            entity_type: Entity type (e.g. "character").
            scope: Scope level ("user", "project", or "global").
            scope_id: Scope identifier (user or project UUID), or None for global.

        Returns:
            Parsed Template if found, or None.
        """
        ...

    async def list_overrides(
        self,
        scope: str,
        scope_id: uuid.UUID | None,
    ) -> list[Template]:
        """List all template overrides for a given scope.

        Args:
            scope: Scope level ("user", "project", or "global").
            scope_id: Scope identifier, or None for global.

        Returns:
            List of parsed Templates.
        """
        ...

    async def save_override(
        self,
        entity_type: str,
        scope: str,
        scope_id: uuid.UUID | None,
        content: str,
        *,
        based_on_version: str | None = None,
    ) -> Template:
        """Insert or update a template override (upsert).

        Uses the unique constraint on (entity_type, scope, scope_id)
        to perform an upsert.

        Args:
            entity_type: Entity type (e.g. "character").
            scope: Scope level ("user", "project", or "global").
            scope_id: Scope identifier, or None for global.
            content: Full template content (YAML frontmatter + body markdown).
            based_on_version: The bundled template version this override is based on.

        Returns:
            The parsed, persisted Template.
        """
        ...

    async def delete_override(
        self,
        entity_type: str,
        scope: str,
        scope_id: uuid.UUID | None,
    ) -> bool:
        """Delete a template override.

        Args:
            entity_type: Entity type (e.g. "character").
            scope: Scope level ("user", "project", or "global").
            scope_id: Scope identifier, or None for global.

        Returns:
            True if a row was deleted, False if none matched.
        """
        ...

    # Note: detect_updates lives in TemplateDetectionRepository
    # (detection_repository.py) to keep each file under size limits.
