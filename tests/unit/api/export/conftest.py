"""Shared fakes + fixtures for export unit tests (ADR-030 Fake-class convention).

Domain dependencies (renderers, normalizer, enqueuer) get real behavioural
fakes — never bare ``MagicMock`` — so a refactor that changes an internal call
shape still fails the test instead of silently passing.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from narrare.export import registry
from narrare.export.contracts import Artifact
from narrare.export.options import ExportFormat, ExportOptions
from narrare.export.repository import ChapterRow, ManuscriptSource
from narrare_core.export.contracts import (
    ManuscriptMetadata,
    NormalizedManuscript,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


class FakeRenderer:
    """Behavioural fake of the ``ManuscriptRenderer`` Protocol.

    Records every ``render`` call and returns a real on-disk temp-file
    :class:`Artifact` (so the registry/router file-cleanup paths are exercised
    against a real path). Availability is configurable for the fast-fail test.
    """

    def __init__(self, fmt: ExportFormat, *, available: bool = True) -> None:
        self._format = fmt
        self._available = available
        self.render_calls: list[tuple[NormalizedManuscript, ExportOptions]] = []

    @property
    def format(self) -> ExportFormat:
        return self._format

    def is_available(self) -> bool:
        return self._available

    async def render(
        self,
        manuscript: NormalizedManuscript,
        options: ExportOptions,
    ) -> Artifact:
        self.render_calls.append((manuscript, options))
        fd, raw_path = tempfile.mkstemp(suffix=f"-fake.{self._format.value}")
        os.close(fd)
        path = Path(raw_path)
        path.write_text(f"FAKE {self._format.value} artifact", encoding="utf-8")
        return Artifact(
            format=self._format,
            path=path,
            media_type=f"application/x-{self._format.value}",
            suggested_filename=f"fake-output.{self._format.value}",
        )


class FailingRenderer(FakeRenderer):
    """Renderer that raises on ``render`` (simulates a subprocess failure)."""

    def __init__(self, fmt: ExportFormat, error: Exception) -> None:
        super().__init__(fmt)
        self._error = error

    async def render(self, manuscript: NormalizedManuscript, options: ExportOptions) -> Artifact:
        self.render_calls.append((manuscript, options))
        raise self._error


class FakeNormalizer:
    """Behavioural fake of ``ManuscriptNormalizer``.

    Records the raw HTML + metadata it received (so the assembly decision is
    assertable) and returns a passthrough :class:`NormalizedManuscript`.
    """

    def __init__(self) -> None:
        self.normalize_calls: list[tuple[str, ManuscriptMetadata]] = []

    async def normalize(
        self,
        raw_tiptap_html: str,
        metadata: ManuscriptMetadata,
    ) -> NormalizedManuscript:
        self.normalize_calls.append((raw_tiptap_html, metadata))
        return NormalizedManuscript(
            semantic_html=raw_tiptap_html,
            title=metadata.title,
            author=metadata.author,
            language=metadata.language,
            chapters=metadata.chapters,
            # Mirrors NarrareNormalizer: optional EPUB metadata passes through
            # unmodified (asserted by the wiring test for isbn/description).
            isbn=metadata.isbn,
            description=metadata.description,
        )


class FakeNovelLookup:
    """In-memory fake of ``OwnedLinkLookupProtocol`` (ADR-030, mirrors chat's).

    Returns a truthy sentinel only for a seeded ``(novel_id, owner_id)`` pair —
    foreign or unknown ids resolve to ``None`` (the service then raises
    ``NotFoundError``: foreign ≡ unknown anti-enumeration).
    """

    def __init__(self) -> None:
        self._owned: dict[UUID, UUID] = {}
        self.calls: list[tuple[UUID, UUID]] = []

    def seed_owned(self, novel_id: UUID, owner_id: UUID) -> None:
        """Register a novel as owned by ``owner_id``."""
        self._owned[novel_id] = owner_id

    async def get_owned(self, entity_id: UUID, user_id: UUID) -> object | None:
        self.calls.append((entity_id, user_id))
        if self._owned.get(entity_id) == user_id:
            return object()
        return None


@dataclass
class RecordingEnqueuer:
    """Records dispatches instead of scheduling real asyncio tasks.

    Assignable to ``ExportServiceImpl(enqueue=...)`` (the DI injection point)
    so tests assert ``export()`` dispatched without touching the event loop.
    """

    calls: list[tuple[str, UUID, ExportOptions]] = field(default_factory=list)

    async def __call__(self, job_id: str, novel_id: UUID, options: ExportOptions) -> None:
        self.calls.append((job_id, novel_id, options))


def make_source(
    *,
    novel_id: UUID | None = None,
    title: str = "Test Novel",
    author: str = "Test Author",
    language: str = "en",
    chapters: list[ChapterRow] | None = None,
) -> ManuscriptSource:
    """Build a :class:`ManuscriptSource` with sensible defaults for tests."""
    return ManuscriptSource(
        novel_id=novel_id if novel_id is not None else uuid4(),
        title=title,
        author=author,
        language=language,
        chapters=chapters if chapters is not None else [],
    )


def make_chapter(
    *,
    title: str = "Chapter One",
    position: int = 0,
    content: str = "<p>Hello world.</p>",
    volume_id: UUID | None = None,
    chapter_id: UUID | None = None,
) -> ChapterRow:
    return ChapterRow(
        chapter_id=chapter_id if chapter_id is not None else uuid4(),
        title=title,
        position=position,
        volume_id=volume_id,
        content=content,
    )


def make_options(fmt: ExportFormat = ExportFormat.MARKDOWN) -> ExportOptions:
    return ExportOptions(format=fmt)


@pytest.fixture(autouse=True)
def _clear_registry() -> Iterator[None]:
    """Start every test from an empty in-memory job registry."""
    registry._JOBS.clear()
    yield
    registry._JOBS.clear()
