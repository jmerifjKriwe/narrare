"""Integration tests for demo KB entry field loading.

Verifies entity types, slugs, tags, and status defaults from demo KB data.
For metadata and body content tests, see test_demo_kb_content.py.

These tests require a running PostgreSQL instance (TEST_DATABASE_URL).
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
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
SCIFI_KB = _DEMO_DATA_ROOT / "en" / "dead-signal" / "kb"

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://narrare:narrare@localhost:5433/narrare_test",
)

pytestmark = pytest.mark.requires_db


async def _create_tables_if_needed(engine: AsyncEngine) -> None:
    """Create novels + kb_entries tables if they don't exist yet."""
    async with engine.begin() as conn:
        await conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS novels (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL,
                title VARCHAR(500) NOT NULL,
                author VARCHAR(200) NOT NULL DEFAULT '',
                genre VARCHAR(100) NOT NULL DEFAULT '',
                language VARCHAR(10) NOT NULL DEFAULT 'en',
                tone VARCHAR(100) NOT NULL DEFAULT '',
                story_structure VARCHAR(100) NOT NULL DEFAULT '',
                logline TEXT NOT NULL DEFAULT '',
                synopsis TEXT NOT NULL DEFAULT '',
                is_demo BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        )
        await conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS kb_entries (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                novel_id UUID NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
                entity_type VARCHAR(50) NOT NULL,
                name VARCHAR(500) NOT NULL,
                slug VARCHAR(500) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'draft',
                tags JSONB,
                metadata JSONB,
                body TEXT,
                template_version VARCHAR(20),
                embeddings_dirty BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CONSTRAINT ck_kb_entries_entity_type
                    CHECK (entity_type IN (
                        'character','location','faction',
                        'object','system','timeline'
                    )),
                CONSTRAINT ck_kb_entries_status
                    CHECK (status IN ('draft','reviewed','canon','deprecated')),
                CONSTRAINT uq_kb_entries_novel_slug UNIQUE (novel_id, slug)
            )
        """)
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_kb_entries_novel_id ON kb_entries (novel_id)")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_kb_entries_entity_type ON kb_entries (entity_type)")
        )
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_kb_entries_novel_type "
                "ON kb_entries (novel_id, entity_type)"
            )
        )


@pytest_asyncio.fixture
async def kb_session() -> AsyncGenerator[AsyncSession]:
    """Provide a transaction-wrapped session with KB tables created."""
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    await _create_tables_if_needed(engine)

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
        title="KB Demo Test Novel",
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


@pytest_asyncio.fixture
async def loaded_scifi_entries(kb_session: AsyncSession) -> list[KBEntry]:
    """Load all sci-fi demo KB entries and return them for assertion."""
    if not SCIFI_KB.exists():
        pytest.skip("Sci-fi demo data not available")

    novel_id = uuid.uuid4()
    novel = Novel(
        id=novel_id,
        user_id=uuid.uuid4(),
        title="KB Demo Test Novel (SciFi)",
        author="Test Author",
        genre="sci-fi",
        language="en",
        tone="suspenseful",
        story_structure="three-act",
        logline="A test novel.",
        synopsis="A test novel for KB loading.",
        is_demo=True,
    )
    kb_session.add(novel)
    await kb_session.flush()

    loader = DemoLoader(kb_session)
    await loader._load_kb_entries(SCIFI_KB, novel_id)

    result = await kb_session.execute(select(KBEntry).where(KBEntry.novel_id == novel_id))
    return list(result.scalars().all())


def _find_by_name(entries: list[KBEntry], name: str) -> KBEntry | None:
    """Find a KBEntry by its name field."""
    return next((e for e in entries if e.name == name), None)


# ---------------------------------------------------------------------------
# Entity type tests
# ---------------------------------------------------------------------------


class TestDemoKBEntityTypes:
    """Verify entity types are correctly set from frontmatter."""

    async def test_fantasy_has_multiple_entity_types(
        self, loaded_fantasy_entries: list[KBEntry]
    ) -> None:
        """Fantasy demo should contain characters, locations, factions, etc."""
        types = {e.entity_type for e in loaded_fantasy_entries}
        assert "character" in types
        assert "location" in types
        assert "faction" in types

    async def test_fantasy_has_5_characters(self, loaded_fantasy_entries: list[KBEntry]) -> None:
        """Fantasy demo should have exactly 5 character entries."""
        chars = [e for e in loaded_fantasy_entries if e.entity_type == "character"]
        assert len(chars) == 5

    async def test_scifi_has_character_and_location(
        self, loaded_scifi_entries: list[KBEntry]
    ) -> None:
        """Sci-fi demo should contain characters and locations."""
        types = {e.entity_type for e in loaded_scifi_entries}
        assert "character" in types
        assert "location" in types


# ---------------------------------------------------------------------------
# Slug tests
# ---------------------------------------------------------------------------


class TestDemoKBSlugs:
    """Verify slugs are set from the 'id' frontmatter field."""

    async def test_elara_slug_is_char_elara(self, loaded_fantasy_entries: list[KBEntry]) -> None:
        """Elara's slug should be 'char-elara' from frontmatter id."""
        elara = _find_by_name(loaded_fantasy_entries, "Elara Thornwind")
        assert elara is not None
        assert elara.slug == "char-elara"

    async def test_thornwall_slug_is_loc_thornwall(
        self, loaded_fantasy_entries: list[KBEntry]
    ) -> None:
        """Thornwall's slug should be 'loc-thornwall'."""
        thornwall = _find_by_name(loaded_fantasy_entries, "Thornwall Ruins")
        assert thornwall is not None
        assert thornwall.slug == "loc-thornwall"

    async def test_aria_slug_is_char_aria(self, loaded_scifi_entries: list[KBEntry]) -> None:
        """ARIA's slug should be 'char-aria'."""
        aria = _find_by_name(
            loaded_scifi_entries,
            "ARIA (Autonomous Response and Intelligence Algorithm)",
        )
        assert aria is not None
        assert aria.slug == "char-aria"


# ---------------------------------------------------------------------------
# Tags tests
# ---------------------------------------------------------------------------


class TestDemoKBTags:
    """Verify tags are correctly parsed from frontmatter."""

    async def test_elara_has_protagonist_tag(self, loaded_fantasy_entries: list[KBEntry]) -> None:
        """Elara should have 'protagonist' in tags."""
        elara = _find_by_name(loaded_fantasy_entries, "Elara Thornwind")
        assert elara is not None
        assert "protagonist" in (elara.tags or [])

    async def test_elara_has_mage_tag(self, loaded_fantasy_entries: list[KBEntry]) -> None:
        """Elara should have 'mage' in tags."""
        elara = _find_by_name(loaded_fantasy_entries, "Elara Thornwind")
        assert elara is not None
        assert "mage" in (elara.tags or [])

    async def test_thornwall_has_forbidden_zone_tag(
        self, loaded_fantasy_entries: list[KBEntry]
    ) -> None:
        """Thornwall should have 'forbidden-zone' in tags."""
        thornwall = _find_by_name(loaded_fantasy_entries, "Thornwall Ruins")
        assert thornwall is not None
        assert "forbidden-zone" in (thornwall.tags or [])

    async def test_tags_are_lists(self, loaded_fantasy_entries: list[KBEntry]) -> None:
        """All entries should have tags as a list (not None)."""
        for entry in loaded_fantasy_entries:
            assert isinstance(entry.tags, list), (
                f"Entry '{entry.name}' has non-list tags: {type(entry.tags)}"
            )


# ---------------------------------------------------------------------------
# Status defaults
# ---------------------------------------------------------------------------


class TestDemoKBStatus:
    """Verify status defaults are correctly applied."""

    async def test_fantasy_entries_have_draft_status(
        self, loaded_fantasy_entries: list[KBEntry]
    ) -> None:
        """All fantasy entries default to 'draft' status."""
        for entry in loaded_fantasy_entries:
            assert entry.status == "draft", (
                f"Entry '{entry.name}' has status '{entry.status}', expected 'draft'"
            )
