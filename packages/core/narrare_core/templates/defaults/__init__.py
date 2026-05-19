"""Bundled default template access via importlib.resources.

Provides functions to load and list the default entity-type templates
bundled with the package.  Templates are language-neutral Markdown +
YAML frontmatter files stored flat in the ``defaults/`` directory.
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


def _read_resource(entity_type: str) -> str | None:
    """Read a template resource file, returning None if not found."""
    filename = f"{entity_type}.md"
    try:
        resource_path = importlib.resources.files(
            "narrare_core.templates.defaults",
        ).joinpath(filename)
        data = resource_path.read_text(encoding="utf-8")
        return data
    except FileNotFoundError, TypeError:
        return None


def load_default_template(entity_type: str) -> str | None:
    """Load a bundled default template for the given entity type.

    Args:
        entity_type: Entity type string (e.g. "character").

    Returns:
        The raw template string, or ``None`` if no template exists
        for the given entity type.
    """
    return _read_resource(entity_type)


def list_default_templates() -> list[str]:
    """List all available bundled default templates.

    Returns:
        List of entity type strings for every bundled template.
    """
    results: list[str] = []
    for entity_type in sorted(_ENTITY_TYPES):
        if _read_resource(entity_type) is not None:
            results.append(entity_type)
    return results
