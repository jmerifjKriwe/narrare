"""
Demo content loader.

Reads bundled Markdown demo files from scripts/demo_data/ and creates
the corresponding DB records (novel, chapters, KB entries).

All loading is atomic — if any step fails, the entire operation rolls back.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from narrare.chapters.models import Chapter
from narrare.setup.schemas import DemoProjectInfo, StarterContent
from narrare_core.shared.frontmatter import parse_frontmatter

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# Root of demo data files — relative to project root
_DEMO_ROOT = Path(__file__).parent.parent.parent.parent.parent / "scripts" / "demo_data"

_DEMO_DIRS: dict[StarterContent, str] = {
    StarterContent.DEMO_FANTASY: "fantasy",
    StarterContent.DEMO_SCIFI: "scifi",
    StarterContent.DEMO_GERMAN: "german",
}

# Metadata for display in the wizard Step 3 cards
_DEMO_INFO: dict[StarterContent, DemoProjectInfo] = {
    StarterContent.DEMO_FANTASY: DemoProjectInfo(
        id=StarterContent.DEMO_FANTASY,
        title="Echoes of the Thornwall",
        language="en",
        genre="High Fantasy",
        chapter_count=4,
        character_count=5,
        word_count=3130,
        description=(
            "A young mage discovers that the magical barrier protecting her village "
            "is slowly failing — and that someone inside may be responsible."
        ),
    ),
    StarterContent.DEMO_SCIFI: DemoProjectInfo(
        id=StarterContent.DEMO_SCIFI,
        title="Dead Signal",
        language="en",
        genre="Science Fiction",
        chapter_count=3,
        character_count=3,
        word_count=3450,
        description=(
            "A deep-space crew receives a signal from a ship that disappeared "
            "forty years ago — and the signal contains their own voices."
        ),
    ),
    StarterContent.DEMO_GERMAN: DemoProjectInfo(
        id=StarterContent.DEMO_GERMAN,
        title="Im stillen Wald",
        language="de",
        genre="Literarische Fiktion",
        chapter_count=2,
        character_count=3,
        word_count=2660,
        description=(
            "Eine Lehrerin sucht Beweise für das Übernatürliche und findet "
            "stattdessen sich selbst — und einen Förster, der den Wald versteht."
        ),
    ),
}


class DemoLoader:
    """Loads demo project files into the database."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def get_info(self, starter: StarterContent) -> DemoProjectInfo:
        """
        Return display metadata for a demo project.

        Args:
            starter: The demo project identifier.

        Returns:
            DemoProjectInfo for display in the wizard.

        Raises:
            KeyError: If starter is not a demo project.
        """
        if starter not in _DEMO_INFO:
            raise KeyError(f"No demo info for starter: {starter}")
        return _DEMO_INFO[starter]

    def all_demo_info(self) -> list[DemoProjectInfo]:
        """Return info for all available demo projects."""
        return list(_DEMO_INFO.values())

    async def load(
        self,
        starter: StarterContent,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """
        Load demo content into the database for the given novel.

        Reads files from scripts/demo_data/{starter_dir}/ and creates
        Chapter and KB records. All within the caller's transaction —
        rollback is handled by the session context.

        Args:
            starter: Which demo project to load.
            novel_id: The novel to populate.
            user_id: The owning user (for ownership validation).

        Raises:
            ValueError: If starter is not a demo project type.
            FileNotFoundError: If demo data files are missing.
        """
        if starter not in _DEMO_DIRS:
            raise ValueError(f"Not a demo starter: {starter}")

        demo_dir = _DEMO_ROOT / _DEMO_DIRS[starter]
        if not demo_dir.exists():
            raise FileNotFoundError(
                f"Demo data directory not found: {demo_dir}. "
                "Run the demo content generation script first."
            )

        logger.info("demo_load_start", starter=starter.value, novel_id=str(novel_id))

        await self._load_chapters(demo_dir / "chapters", novel_id)
        await self._load_kb_entries(demo_dir / "kb", novel_id)

        logger.info("demo_load_complete", starter=starter.value, novel_id=str(novel_id))

    async def _load_chapters(self, chapters_dir: Path, novel_id: uuid.UUID) -> None:
        """Load chapter Markdown files into Chapter records."""
        if not chapters_dir.exists():
            logger.warning("demo_chapters_dir_missing", path=str(chapters_dir))
            return

        chapter_files = sorted(chapters_dir.glob("*.md"))
        for position, chapter_file in enumerate(chapter_files):
            raw = chapter_file.read_text(encoding="utf-8")
            parsed = parse_frontmatter(raw)

            title = parsed.get("title", chapter_file.stem.replace("-", " ").title())
            content = parsed.content
            word_count = len(content.split()) if content.strip() else 0
            status = parsed.get("status", "draft")
            pov_character = str(parsed.get("pov_character", ""))
            timeline_pos = str(parsed.get("timeline_position", ""))

            chapter = Chapter(
                novel_id=novel_id,
                title=title,
                content=content,
                position=position,
                word_count=word_count,
                status=status,
                pov_character_id=pov_character,
                timeline_position=timeline_pos,
            )
            self._session.add(chapter)

        await self._session.flush()
        logger.debug("demo_chapters_loaded", count=len(chapter_files))

    async def _load_kb_entries(self, kb_dir: Path, novel_id: uuid.UUID) -> None:
        """
        Load KB Markdown files into KBEntry records.

        KB module is not yet implemented in Phase 2/3 — we store the
        raw content and metadata for when KB is built in a later phase.
        This uses a deferred import so the module can compile without KB.
        """
        if not kb_dir.exists():
            logger.debug("demo_kb_dir_missing", path=str(kb_dir))
            return

        kb_files = list(kb_dir.glob("*.md"))
        if not kb_files:
            return

        # Attempt to import KB model — not yet available in Phase 3
        try:
            from narrare.kb.models import KBEntry  # type: ignore[import-not-found]
        except ImportError:
            logger.info(
                "kb_module_not_yet_available",
                message="KB entries will be loaded when KB module is implemented (Phase 4+)",
                count=len(kb_files),
            )
            return

        for kb_file in kb_files:
            raw = kb_file.read_text(encoding="utf-8")
            parsed = parse_frontmatter(raw)

            entry: KBEntry = KBEntry(  # type: ignore[reportUnknownVariableType]
                novel_id=novel_id,
                entity_type=parsed.get("type", "character"),
                name=parsed.get("name", kb_file.stem),
                content=parsed.content,
                status=parsed.get("status", "draft"),
            )
            self._session.add(entry)  # type: ignore[reportUnknownArgumentType]

        await self._session.flush()
        logger.debug("demo_kb_loaded", count=len(kb_files))
