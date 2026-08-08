"""Integration tests for demo KB entry metadata and body content.

Verifies that type-specific metadata lands in the JSONB column (not system
columns) and that Markdown body content is correctly extracted.

Shared fixtures are in test_demo_kb_fields.py.

These tests require a running PostgreSQL instance (TEST_DATABASE_URL).
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
)

from narrare.kb.models import KBEntry
from narrare.novels.models import Novel
from narrare.setup.demo_loader import DemoLoader

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# Path to real demo data
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEMO_DATA_ROOT = _REPO_ROOT / "apps" / "api" / "narrare" / "setup" / "demo_data"

FANTASY_KB = _DEMO_DATA_ROOT / "en" / "echoes-of-the-thornwall" / "kb"

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://narrare:narrare@localhost:5433/narrare_test",
)


@pytest_asyncio.fixture
async def kb_session() -> AsyncGenerator[AsyncSession]:
    """Provide a transaction-wrapped session against the migrated schema.

    The integration session fixture (``tests/integration/conftest.py``) runs
    ``alembic upgrade head`` once per session, so ``novels`` and ``kb_entries``
    already exist with the current migrated shape. RULE-14: no ``create_all()``
    or manual ``CREATE TABLE`` — rely exclusively on migrations.
    """
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)

    async with engine.connect() as conn:
        transaction = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        yield session
        await session.close()
        await transaction.rollback()

    await engine.dispose()


@pytest_asyncio.fixture
async def loaded_fantasy_entries(kb_session: AsyncSession) -> list[KBEntry]:
    """Load all fantasy demo KB entries and return them for assertion."""
    if not FANTASY_KB.exists():
        pytest.skip("Fantasy demo data not available")

    novel_id = uuid.uuid4()
    novel = Novel(
        id=novel_id,
        user_id=uuid.uuid4(),
        title="KB Demo Test Novel (Content)",
        author="Test Author",
        genre="fantasy",
        language="en",
        tone="epic",
        story_structure="three-act",
        logline="A test novel.",
        synopsis="A test novel for KB loading.",
        is_demo=True,
    )
    kb_session.add(novel)
    await kb_session.flush()

    loader = DemoLoader(kb_session)
    await loader._load_kb_entries(FANTASY_KB, novel_id)

    result = await kb_session.execute(select(KBEntry).where(KBEntry.novel_id == novel_id))
    return list(result.scalars().all())


def _find_by_name(entries: list[KBEntry], name: str) -> KBEntry | None:
    """Find a KBEntry by its name field."""
    return next((e for e in entries if e.name == name), None)


# ---------------------------------------------------------------------------
# Metadata separation tests
# ---------------------------------------------------------------------------


class TestDemoKBMetadataSeparation:
    """Verify system fields are in columns, type-specific fields in metadata JSONB."""

    async def test_elara_age_in_metadata(self, loaded_fantasy_entries: list[KBEntry]) -> None:
        """Elara's age (19) should be in metadata JSONB, not a column."""
        elara = _find_by_name(loaded_fantasy_entries, "Elara Thornwind")
        assert elara is not None
        assert elara.metadata_ is not None
        assert elara.metadata_.get("age") == 19

    async def test_elara_role_in_metadata(self, loaded_fantasy_entries: list[KBEntry]) -> None:
        """Elara's role should be in metadata JSONB."""
        elara = _find_by_name(loaded_fantasy_entries, "Elara Thornwind")
        assert elara is not None
        assert elara.metadata_ is not None
        assert elara.metadata_.get("role") == "protagonist"

    async def test_elara_arc_in_metadata(self, loaded_fantasy_entries: list[KBEntry]) -> None:
        """Elara's arc description should be in metadata JSONB."""
        elara = _find_by_name(loaded_fantasy_entries, "Elara Thornwind")
        assert elara is not None
        assert elara.metadata_ is not None
        assert "obedient" in str(elara.metadata_.get("arc", ""))

    async def test_elara_affiliation_in_metadata(
        self, loaded_fantasy_entries: list[KBEntry]
    ) -> None:
        """Elara's affiliation should be in metadata JSONB."""
        elara = _find_by_name(loaded_fantasy_entries, "Elara Thornwind")
        assert elara is not None
        assert elara.metadata_ is not None
        assert "Silver Flame" in str(elara.metadata_.get("affiliation", ""))

    async def test_system_fields_not_in_metadata(
        self, loaded_fantasy_entries: list[KBEntry]
    ) -> None:
        """System fields (id, name, type, tags) should NOT be in metadata."""
        elara = _find_by_name(loaded_fantasy_entries, "Elara Thornwind")
        assert elara is not None
        assert elara.metadata_ is not None
        assert "id" not in elara.metadata_
        assert "name" not in elara.metadata_
        assert "type" not in elara.metadata_
        assert "tags" not in elara.metadata_

    async def test_thornwall_location_type_in_metadata(
        self, loaded_fantasy_entries: list[KBEntry]
    ) -> None:
        """Thornwall's location_type should be in metadata JSONB."""
        thornwall = _find_by_name(loaded_fantasy_entries, "Thornwall Ruins")
        assert thornwall is not None
        assert thornwall.metadata_ is not None
        assert thornwall.metadata_.get("location_type") == "ruins"

    async def test_compass_object_type_in_metadata(
        self, loaded_fantasy_entries: list[KBEntry]
    ) -> None:
        """Compass's object_type should be in metadata JSONB."""
        compass = _find_by_name(loaded_fantasy_entries, "The Thornwell Compass")
        assert compass is not None
        assert compass.metadata_ is not None
        assert compass.metadata_.get("object_type") == "artifact"

    async def test_compass_owner_in_metadata(self, loaded_fantasy_entries: list[KBEntry]) -> None:
        """Compass's owner field should be in metadata JSONB."""
        compass = _find_by_name(loaded_fantasy_entries, "The Thornwell Compass")
        assert compass is not None
        assert compass.metadata_ is not None
        assert compass.metadata_.get("owner") == "char-elara"


# ---------------------------------------------------------------------------
# Body content tests
# ---------------------------------------------------------------------------


class TestDemoKBBodyContent:
    """Verify body content is correctly extracted from Markdown after frontmatter."""

    async def test_elara_body_has_heading(self, loaded_fantasy_entries: list[KBEntry]) -> None:
        """Elara's body should start with her name heading."""
        elara = _find_by_name(loaded_fantasy_entries, "Elara Thornwind")
        assert elara is not None
        assert elara.body is not None
        assert "# Elara Thornwind" in elara.body

    async def test_elara_body_has_background_section(
        self, loaded_fantasy_entries: list[KBEntry]
    ) -> None:
        """Elara's body should contain the Background section."""
        elara = _find_by_name(loaded_fantasy_entries, "Elara Thornwind")
        assert elara is not None
        assert elara.body is not None
        assert "## Background" in elara.body

    async def test_thornwall_body_has_description(
        self, loaded_fantasy_entries: list[KBEntry]
    ) -> None:
        """Thornwall's body should contain description text."""
        thornwall = _find_by_name(loaded_fantasy_entries, "Thornwall Ruins")
        assert thornwall is not None
        assert thornwall.body is not None
        assert "Void Cataclysm" in thornwall.body

    async def test_body_is_not_empty(self, loaded_fantasy_entries: list[KBEntry]) -> None:
        """All entries should have non-empty body content."""
        for entry in loaded_fantasy_entries:
            assert entry.body, f"Entry '{entry.name}' has empty body"

    async def test_body_does_not_contain_frontmatter(
        self, loaded_fantasy_entries: list[KBEntry]
    ) -> None:
        """Body should not contain frontmatter delimiters or YAML keys."""
        for entry in loaded_fantasy_entries:
            assert "---" not in (entry.body or ""), (
                f"Entry '{entry.name}' body contains frontmatter delimiter"
            )
