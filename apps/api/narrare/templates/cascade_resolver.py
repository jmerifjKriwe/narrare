"""Cascade resolver — resolves entity-type templates.

Implements the core ``TemplateResolver`` protocol.  Resolution cascade:
bundled defaults only (project/global overrides are future scope).

Language fallback: requested language → "en".
"""

from __future__ import annotations

from narrare_core.templates import (
    Template,
    TemplateMeta,
    list_default_templates,
    load_default_template,
    parse_template,
)


class CascadeResolver:
    """Resolve templates using bundled defaults with language fallback.

    Implements ``TemplateResolver`` protocol from core.
    """

    def resolve(self, entity_type: str, language: str) -> Template | None:
        """Resolve a template for the given entity type and language.

        Falls back to English if the requested language is not available.

        Args:
            entity_type: Entity type string (e.g. "character").
            language: Language code (e.g. "en", "de", "fr").

        Returns:
            Parsed template, or ``None`` if not found.
        """
        raw = load_default_template(entity_type, language)
        if raw is None:
            return None
        return parse_template(raw)

    def list_available(self) -> list[TemplateMeta]:
        """Return metadata for all bundled default templates."""
        results: list[TemplateMeta] = []
        seen: set[tuple[str, str]] = set()

        for entity_type, language in list_default_templates():
            key = (entity_type, language)
            if key in seen:
                continue
            seen.add(key)

            raw = load_default_template(entity_type, language)
            if raw is None:
                continue

            template = parse_template(raw)
            results.append(template.meta)

        return results
