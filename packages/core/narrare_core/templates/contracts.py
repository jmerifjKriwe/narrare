"""Template system contracts — Protocol definitions.

Defines the ``TemplateResolver`` protocol that any template resolution
implementation must satisfy.  The core layer defines the contract; the
API layer provides the concrete implementation (cascade resolver).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .models import Template, TemplateMeta


class TemplateResolver(Protocol):
    """Protocol for resolving entity-type templates.

    Implementations may use a cascade (user project → user global →
    bundled defaults) or a simple bundled-only lookup.
    """

    def resolve(self, entity_type: str, language: str) -> Template | None:
        """Resolve a template for the given entity type and language.

        Args:
            entity_type: Entity type string (e.g. "character").
            language: Language code (e.g. "en", "de", "fr").

        Returns:
            The resolved template, or ``None`` if not found.
        """
        ...

    def list_available(self) -> list[TemplateMeta]:
        """Return metadata for all available templates.

        Returns:
            List of TemplateMeta for every resolvable template.
        """
        ...
