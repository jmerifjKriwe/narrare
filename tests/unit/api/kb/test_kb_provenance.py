"""Unit tests for KB entry provenance fields (IF-05).

Tests that:
1. Extraction service sets source="auto_extraction" and review_status="pending"
2. Manual creation uses defaults source="manual" and review_status="approved"
3. KBEntryCreate schema validates provenance fields
4. Provenance fields flow through service to model correctly
5. Migration file is syntactically valid
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import pytest

from narrare.kb.contracts import KBRepositoryProtocol
from narrare.kb.models import KBEntry
from narrare.kb.schemas import KBEntryCreate
from narrare.kb.service import KBService

if TYPE_CHECKING:
    from narrare.kb.relationship_repository import RelationshipRepository

pytestmark = pytest.mark.mutation_inert

# ---------------------------------------------------------------------------
# Schema defaults
# ---------------------------------------------------------------------------


class TestKBEntryCreateProvenanceDefaults:
    """KBEntryCreate defaults to manual/approved provenance."""

    def test_source_defaults_to_manual(self) -> None:
        data = KBEntryCreate(entity_type="character", name="Anna")
        assert data.source == "manual"

    def test_review_status_defaults_to_approved(self) -> None:
        data = KBEntryCreate(entity_type="character", name="Anna")
        assert data.review_status == "approved"

    def test_source_can_be_overridden(self) -> None:
        data = KBEntryCreate(
            entity_type="character",
            name="Anna",
            source="auto_extraction",
        )
        assert data.source == "auto_extraction"

    def test_review_status_can_be_overridden(self) -> None:
        data = KBEntryCreate(
            entity_type="character",
            name="Anna",
            review_status="pending",
        )
        assert data.review_status == "pending"

    def test_both_fields_together(self) -> None:
        data = KBEntryCreate(
            entity_type="location",
            name="Dark Forest",
            source="auto_extraction",
            review_status="pending",
        )
        assert data.source == "auto_extraction"
        assert data.review_status == "pending"


# ---------------------------------------------------------------------------
# Extraction apply provenance
# ---------------------------------------------------------------------------


class TestExtractionProvenance:
    """ExtractionApplyService sets correct provenance on new entries."""

    @pytest.mark.asyncio
    async def test_extraction_sets_auto_provenance(self) -> None:
        """Extraction apply creates KBEntryCreate with auto_extraction provenance."""
        from narrare.kb.extraction_apply_service import ExtractionApplyService
        from narrare.kb.schemas_extraction import ApplyExtractionItem
        from tests.unit.api.kb.test_apply_extraction import (
            _FakeKBRepoForApply,
            _FakeKBService,
            _FakeRelationshipRepo,
        )

        kb_service = _FakeKBService()
        rel_repo = _FakeRelationshipRepo()
        kb_repo = _FakeKBRepoForApply()

        service = ExtractionApplyService(
            kb_service=cast("KBService", kb_service),
            rel_repo=cast("RelationshipRepository", rel_repo),
            kb_repo=cast("KBRepositoryProtocol", kb_repo),
        )

        item = cast("Any", ApplyExtractionItem)(
            item_type="new_entity",
            name="Extracted Character",
            entity_type="character",
            proposed_content={"role": "protagonist"},
            source_text="Anna is a brave warrior.",
        )

        result = await service.apply(
            novel_id=uuid4(),
            user_id=uuid4(),
            items=[item],
        )

        assert len(result.created_entries) == 1
        assert result.created_entries[0].name == "Extracted Character"

        # Verify the KBEntryCreate passed to kb_service has correct provenance
        created_data = cast("Any", kb_service.created[0]["data"])
        assert created_data.source == "auto_extraction"
        assert created_data.review_status == "pending"

    @pytest.mark.asyncio
    async def test_extraction_no_todo_remains(self) -> None:
        """Verify the TODO comment has been removed from extraction_apply_service."""
        import inspect

        from narrare.kb import extraction_apply_service

        source = inspect.getsource(extraction_apply_service)
        assert "TODO" not in source
        assert "CR-AUFG-04-B3" not in source


# ---------------------------------------------------------------------------
# Manual creation provenance
# ---------------------------------------------------------------------------


class TestManualCreationProvenance:
    """Manual KB entry creation uses manual/approved defaults."""

    @pytest.mark.asyncio
    async def test_manual_create_uses_default_provenance(self) -> None:
        """KBService.create() maps schema defaults to model fields."""
        from unittest.mock import AsyncMock

        repo = AsyncMock(spec=KBRepositoryProtocol)
        repo.get_by_slug = AsyncMock(return_value=None)
        repo.create = AsyncMock(side_effect=lambda e: e)

        service = KBService(repo=repo)

        data = KBEntryCreate(entity_type="character", name="Manual Entry")
        entry = await service.create(uuid4(), uuid4(), data)

        assert isinstance(entry, KBEntry)
        assert entry.source == "manual"
        assert entry.review_status == "approved"

    @pytest.mark.asyncio
    async def test_explicit_provenance_flows_through_service(self) -> None:
        """Explicit provenance values in KBEntryCreate flow to the model."""
        from unittest.mock import AsyncMock

        repo = AsyncMock(spec=KBRepositoryProtocol)
        repo.get_by_slug = AsyncMock(return_value=None)
        repo.create = AsyncMock(side_effect=lambda e: e)

        service = KBService(repo=repo)

        data = KBEntryCreate(
            entity_type="location",
            name="Auto Forest",
            source="auto_extraction",
            review_status="pending",
        )
        entry = await service.create(uuid4(), uuid4(), data)

        assert isinstance(entry, KBEntry)
        assert entry.source == "auto_extraction"
        assert entry.review_status == "pending"


# ---------------------------------------------------------------------------
# Migration validity
# ---------------------------------------------------------------------------


class TestMigrationValidity:
    """Check the migration file is syntactically valid."""

    def test_migration_file_imports_successfully(self) -> None:
        """Migration 0029_kb_provenance can be imported without errors."""
        import importlib.util
        from pathlib import Path

        migration_path = (
            Path(__file__).resolve().parents[4]
            / "apps"
            / "api"
            / "alembic"
            / "versions"
            / "0029_kb_provenance.py"
        )
        assert migration_path.exists(), f"Migration file not found: {migration_path}"

        spec = importlib.util.spec_from_file_location("migration_0029", migration_path)
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        cast("Any", spec.loader).exec_module(mod)

        assert mod.revision == "0029_kb_provenance"
        assert mod.down_revision == "0028_invocation_evidence"
        assert callable(mod.upgrade)
        assert callable(mod.downgrade)
