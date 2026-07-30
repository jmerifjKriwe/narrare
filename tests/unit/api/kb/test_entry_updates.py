"""Unit tests for ``build_entry_updates`` — shared KB update-field builder.

Series Foundation Spec 1, Slice 3 Task 3.8.

Extracted from ``test_canon_service.py`` to respect the RULE-04 300-line file
limit. ``build_entry_updates`` is a DRY helper shared by the novel CRUD
(``KBService.update``) and the canon CRUD (``KBCanonService.update_canon``);
its tests belong to the helper, not to either service, so they get their own
module.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from narrare.kb._entry_updates import build_entry_updates
from narrare.kb.models import KBEntry
from narrare.kb.schemas import KBEntryUpdate
from narrare_core.shared.errors import ValidationError


class TestBuildEntryUpdates:
    def _entry(self) -> MagicMock:
        entry = MagicMock(spec=KBEntry)
        entry.slug = "old"
        entry.entity_type = "character"
        return entry

    def test_name_regenerates_slug_when_slug_omitted(self) -> None:
        updates = build_entry_updates(self._entry(), KBEntryUpdate(name="New Name"))
        assert updates["name"] == "New Name"
        assert updates["slug"] == "new-name"

    def test_explicit_slug_takes_precedence(self) -> None:
        updates = build_entry_updates(self._entry(), KBEntryUpdate(name="New Name", slug="fixed"))
        assert updates["slug"] == "fixed"

    def test_empty_request_yields_empty_dict(self) -> None:
        assert build_entry_updates(self._entry(), KBEntryUpdate()) == {}

    def test_invalid_metadata_raises_validation(self) -> None:
        with pytest.raises(ValidationError, match="Invalid metadata"):
            build_entry_updates(self._entry(), KBEntryUpdate(metadata={"age": "x"}))
