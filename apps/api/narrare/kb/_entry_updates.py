"""Shared KB-entry update builder (RULE-04 extraction).

Builds the repository-ready ``dict`` of changed fields from a PATCH request,
shared by the novel-scoped :class:`~narrare.kb.service.KBService` and the
Series-Canon :class:`~narrare.kb.canon_service.KBCanonService` so the two CRUD
paths cannot drift on field-mapping semantics (CR-04 / DRY). The scope-specific
slug-uniqueness check stays in each caller — the novel path looks up by novel
scope, the canon path by series scope (``novel_id IS NULL``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.kb._utils import slugify
from narrare.kb._validators import validate_entry_metadata

if TYPE_CHECKING:
    from narrare.kb.models import KBEntry
    from narrare.kb.schemas import KBEntryUpdate


def build_entry_updates(entry: KBEntry, data: KBEntryUpdate) -> dict[str, object]:
    """Build the repo-ready update dict from a PATCH request.

    Mirrors PATCH semantics: only explicitly-set fields appear. When ``name``
    changes and ``slug`` is not supplied, the slug is regenerated from the new
    name. Metadata is re-validated against the effective entity type.

    Args:
        entry: The current ORM entry (used for the existing slug / entity type).
        data: The PATCH body (all fields optional).

    Returns:
        A ``{column: value}`` dict for ``KBRepository.update``. Empty if no
        field was set.
    """
    updates: dict[str, object] = {}

    if data.name is not None:
        updates["name"] = data.name
        # Regenerate slug when name changes (unless slug also provided)
        if data.slug is None:
            new_slug = slugify(data.name)
            if new_slug and new_slug != entry.slug:
                updates["slug"] = new_slug

    if data.slug is not None:
        updates["slug"] = data.slug

    if data.entity_type is not None:
        updates["entity_type"] = data.entity_type

    if data.status is not None:
        updates["status"] = data.status

    if data.tags is not None:
        updates["tags"] = data.tags

    if data.body is not None:
        updates["body"] = data.body

    if data.template_version is not None:
        updates["template_version"] = data.template_version

    # Re-validate metadata if changed (against the effective entity type).
    effective_type = updates.get("entity_type", entry.entity_type)
    if data.metadata is not None:
        validate_entry_metadata(str(effective_type), data.metadata)
        updates["metadata_"] = data.metadata

    return updates
