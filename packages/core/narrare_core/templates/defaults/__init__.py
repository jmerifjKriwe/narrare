"""Bundled default template access via importlib.resources.

Provides functions to load and list the default entity-type templates
bundled with the package.  Templates are Markdown + YAML frontmatter
files organised by language code (en, de, fr).
"""

from __future__ import annotations

import importlib.resources

# Known entity types that have bundled templates
_ENTITY_TYPES = frozenset(
    {
        "character",
        "concept",
        "faction",
        "location",
        "object",
        "setting",
        "system",
        "timeline",
    }
)

# Supported language codes
_LANGUAGES = frozenset({"en", "de", "fr"})


def _read_resource(language: str, entity_type: str) -> str | None:
    """Read a template resource file, returning None if not found."""
    filename = f"{entity_type}.md"
    try:
        resource_path = importlib.resources.files(
            "narrare_core.templates.defaults",
        ).joinpath(language, filename)
        data = resource_path.read_text(encoding="utf-8")
        return data
    except FileNotFoundError, TypeError:
        return None


def load_default_template(entity_type: str, language: str = "en") -> str | None:
    """Load a bundled default template for the given entity type and language.

    Falls back to English (``"en"``) if the requested language template
    doesn't exist.

    Args:
        entity_type: Entity type string (e.g. "character").
        language: Language code (e.g. "en", "de", "fr").

    Returns:
        The raw template string, or ``None`` if not even the English
        fallback exists.
    """
    # Try the requested language first
    content = _read_resource(language, entity_type)
    if content is not None:
        return content

    # Fall back to English
    if language != "en":
        content = _read_resource("en", entity_type)
        if content is not None:
            return content

    return None


def list_default_templates() -> list[tuple[str, str]]:
    """List all available bundled default templates.

    Returns:
        List of (entity_type, language) pairs for every bundled template.
    """
    results: list[tuple[str, str]] = []
    for language in sorted(_LANGUAGES):
        for entity_type in sorted(_ENTITY_TYPES):
            if _read_resource(language, entity_type) is not None:
                results.append((entity_type, language))
    return results
