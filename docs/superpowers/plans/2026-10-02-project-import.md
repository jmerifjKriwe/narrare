# Project Import v1 (SETUP-003) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship browser-based Markdown/TXT chapter import (stateless preview → commit) into new and existing novels, and remove the dormant server-side `import_path` stub.

**Architecture:** A pure-Core deterministic parser (`narrare_core/importing/`) feeds a new API module (`apps/api/narrare/importing/`) exposing two authenticated multipart endpoints — `POST /import/preview` (parse only, no DB writes) and `POST /import/commit` (deterministic re-parse + atomic append with ownership gate). The frontend gets one shared surface (`ImportPreviewPanel`/`ImportModal`) consumed by both the sidebar (existing novels) and the Setup Wizard (Step 2 inline; committed at Step 5 after novel creation). See ADR-091 + design spec `docs/superpowers/specs/2026-10-02-project-import-design.md`.

**Tech Stack:** Python 3.14 · FastAPI `UploadFile` (first multipart surface) · SQLAlchemy 2.0 async · `narrare_core.shared.frontmatter` · Next.js 16 · React 19 · TanStack Query · Zustand · Radix alert-dialog (installed) · next-intl (en/de/fr).

## Global Constraints

- Project language: **English** — all code, comments, tests, i18n keys' values follow existing locale files.
- **RULE-03:** `apps/api/narrare/importing/contracts.py` is written BEFORE `service.py`/`repository.py` (Task 2 Step 1).
- **RULE-04:** hard file-size limits apply (`service.py` ≤ 300, `router.py` ≤ 150, `schemas.py` ≤ 200, any module ≤ 400).
- **RULE-06:** routers delegate immediately; services hold no SQLAlchemy; repositories hold no business logic.
- **RULE-07:** `narrare_core/importing/` imports nothing from `apps/`, no FastAPI, no SQLAlchemy, no I/O.
- **RULE-16:** new `importing` i18n namespace must be registered in `packages/web/lib/i18n/request.ts` AND exist in `en`/`de`/`fr` (same task as first use — Task 7).
- **RULE-17:** `packages/web/types/importing.ts` field names EXACTLY match the Pydantic schemas (same commit as Task 2's backend schemas → Task 6 mirrors).
- **RULE-19:** dependency factories use `SessionDep`, never bare `AsyncSession`.
- **RULE-20:** no stubs — each task ships complete, tested behavior.
- Errors: raise `narrare_core.shared.errors.ValidationError` (→ 422) / `NotFoundError` (→ 404); never router-level try/except.
- Ownership gate: reuse `narrare.novels.ownership.verify_novel_owned` — do NOT write a local gate.
- Git writes (add/commit/push) are executed by the coordinator via **NarrarePlatformSpecialist**.
- Verification commands (repo root unless noted): backend unit `uv run --all-packages pytest <path> -v`; integration needs services: `just _ensure-services` first; frontend `cd packages/web && pnpm test -- <filter>`; architecture `just check-architecture`; final gate `just verify`.

## Task sizing deviations (deliberate)

- Task 1 creates 4 small source files (`__init__`, `models`, `splitting`, `detector`) — RULE-06 one-responsibility beats the ≤3-files heuristic; total ≈ 170 LOC, one testable unit.
- Task 2 scaffolds the whole API module (8 small files) — every sub-slice boundary would produce non-independently-testable fragments (a contracts file alone tests nothing).
- Tasks 4/5 and 9/10 are each single-sliced removals/additions whose halves are independently reviewable (backend vs frontend; store/step-2 vs completion/step-5).

---

### Task 1: Pure Core chapter detector + golden tests

**Files:**
- Create: `packages/core/narrare_core/importing/__init__.py`
- Create: `packages/core/narrare_core/importing/models.py`
- Create: `packages/core/narrare_core/importing/splitting.py`
- Create: `packages/core/narrare_core/importing/detector.py`
- Test: `tests/unit/core/importing/__init__.py` (empty)
- Test: `tests/unit/core/importing/test_splitting.py`
- Test: `tests/unit/core/importing/test_detector.py`

**Interfaces:**
- Consumes: `narrare_core.shared.frontmatter.parse_frontmatter` (existing).
- Produces (later tasks rely on these exact names):
  - `detect_chapters(filename: str, text: str) -> list[DetectedChapter]` (pure, deterministic)
  - `DetectedChapter` frozen dataclass: `title: str` (1..500 chars), `content: str`, `word_count: int`, `status: str` (`draft|reviewed|final`), `source_file: str`
  - `CHAPTER_STATUSES: frozenset[str]`, `TITLE_MAX_LENGTH: Final[int] = 500`
  - `split_markdown_sections(text: str) -> list[tuple[str, str]]` (heading, body; `("", preamble)` for preamble)
  - `split_marker_sections(text: str) -> list[tuple[str, str]]`
  - `fallback_title(filename: str) -> str`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/core/importing/test_splitting.py
"""Golden tests for import section splitting (SETUP-003 v1)."""

from __future__ import annotations

from narrare_core.importing.splitting import (
    fallback_title,
    split_marker_sections,
    split_markdown_sections,
)


class TestSplitMarkdownSections:
    def test_no_headings_returns_single_preamble_section(self) -> None:
        assert split_markdown_sections("Just prose.\nMore prose.") == [("", "Just prose.\nMore prose.")]

    def test_h1_and_h2_split_deeper_headings_stay_inside(self) -> None:
        text = "# One\nbody one\n### deep\nstill one\n## Two\nbody two"
        sections = split_markdown_sections(text)
        assert [h for h, _ in sections] == ["One", "Two"]
        assert "### deep" in sections[0][1]
        assert sections[1][1] == "body two"

    def test_nonempty_preamble_becomes_own_section(self) -> None:
        sections = split_markdown_sections("Intro text\n# One\nbody")
        assert sections[0] == ("", "Intro text")
        assert sections[1] == ("One", "body")

    def test_empty_preamble_is_dropped(self) -> None:
        assert split_markdown_sections("# One\nbody")[0] == ("One", "body")


class TestSplitMarkerSections:
    def test_english_arabic_marker(self) -> None:
        sections = split_marker_sections("Chapter 1\nalpha\nChapter 2\nbeta")
        assert [t for t, _ in sections] == ["Chapter 1", "Chapter 2"]
        assert sections[0][1] == "alpha"

    def test_german_roman_marker_case_insensitive(self) -> None:
        sections = split_marker_sections("kapitel iv\ntext")
        assert sections == [("kapitel iv", "text")]

    def test_marker_with_trailing_text_keeps_whole_line_title(self) -> None:
        sections = split_marker_sections("Chapter 12 — The Storm\nwind")
        assert sections[0][0] == "Chapter 12 — The Storm"

    def test_spelled_out_number_is_not_a_marker(self) -> None:
        assert split_marker_sections("Chapter one\nprose") == [("", "Chapter one\nprose")]

    def test_no_markers_returns_single_section(self) -> None:
        assert split_marker_sections("plain text file body") == [("", "plain text file body")]


class TestFallbackTitle:
    def test_dashes_become_spaces_and_title_case(self) -> None:
        assert fallback_title("my-chapter.md") == "My Chapter"

    def test_no_extension(self) -> None:
        assert fallback_title("notes") == "Notes"

    def test_empty_stem_gets_untitled(self) -> None:
        assert fallback_title("") == "Untitled Chapter"
```

```python
# tests/unit/core/importing/test_detector.py
"""Golden tests for chapter detection (SETUP-003 v1, ADR-091)."""

from __future__ import annotations

from narrare_core.importing.detector import detect_chapters


class TestDetectMarkdown:
    def test_frontmatter_title_and_status_honored(self) -> None:
        text = "---\ntitle: The Thorn Wall\nstatus: final\n---\n\nBody text here."
        chapters = detect_chapters("ch-01.md", text)
        assert len(chapters) == 1
        assert chapters[0].title == "The Thorn Wall"
        assert chapters[0].status == "final"
        assert chapters[0].word_count == 3
        assert chapters[0].source_file == "ch-01.md"
        assert "title:" not in chapters[0].content

    def test_heading_split_per_chapter_with_preamble(self) -> None:
        text = "Preamble prose.\n# One\nbody one\n# Two\nbody two"
        chapters = detect_chapters("book.md", text)
        assert [c.title for c in chapters] == ["Book", "One", "Two"]
        assert chapters[0].content == "Preamble prose."
        assert chapters[1].content == "body one"

    def test_no_heading_no_frontmatter_uses_filename_stem(self) -> None:
        chapters = detect_chapters("my-chapter.md", "just body")
        assert chapters[0].title == "My Chapter"
        assert chapters[0].status == "draft"

    def test_invalid_status_coerces_to_draft(self) -> None:
        text = "---\nstatus: banana\n---\nbody"
        assert detect_chapters("a.md", text)[0].status == "draft"

    def test_heading_without_body_is_skipped(self) -> None:
        chapters = detect_chapters("a.md", "# Empty\n# Full\nbody")
        assert [c.title for c in chapters] == ["Full"]

    def test_whitespace_only_file_yields_no_chapters(self) -> None:
        assert detect_chapters("empty.md", "  \n\t\n") == []

    def test_long_title_is_truncated_to_limit(self) -> None:
        chapters = detect_chapters("a.md", f"# {'x' * 600}\nbody")
        assert len(chapters[0].title) == 500


class TestDetectTxt:
    def test_markers_split_and_marker_line_is_title(self) -> None:
        chapters = detect_chapters("novel.txt", "Chapter 1\na b c\nChapter 2\nd e f")
        assert [c.title for c in chapters] == ["Chapter 1", "Chapter 2"]
        assert [c.word_count for c in chapters] == [3, 3]
        assert all(c.status == "draft" for c in chapters)

    def test_no_marker_single_chapter_from_stem(self) -> None:
        chapters = detect_chapters("draft-notes.txt", "one two three")
        assert len(chapters) == 1
        assert chapters[0].title == "Draft Notes"

    def test_marker_preamble_gets_fallback_title(self) -> None:
        chapters = detect_chapters("book.txt", "intro text\nChapter 1\nbody")
        assert chapters[0].title == "Book"
        assert chapters[1].title == "Chapter 1"


class TestDeterminism:
    def test_identical_input_yields_identical_output(self) -> None:
        text = "---\ntitle: T\n---\n# A\nx\n# B\ny"
        assert detect_chapters("f.md", text) == detect_chapters("f.md", text)

    def test_unknown_extension_yields_no_chapters(self) -> None:
        assert detect_chapters("file.docx", "# H\nbody") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --all-packages pytest tests/unit/core/importing/ -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'narrare_core.importing'`

- [ ] **Step 3: Write the implementation**

```python
# packages/core/narrare_core/importing/models.py
"""Data shapes for chapter detection (SETUP-003 v1 — pure, I/O-free)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

#: Chapter statuses v1 can produce (Chapter.status is String(20)).
CHAPTER_STATUSES: frozenset[str] = frozenset({"draft", "reviewed", "final"})

#: Chapter.title column limit — titles are clamped here so the preview the
#: user sees is storable as-is (user edits can still shorten).
TITLE_MAX_LENGTH: Final[int] = 500


@dataclass(frozen=True, slots=True)
class DetectedChapter:
    """One chapter detected in an uploaded file (deterministic parse result)."""

    title: str
    content: str
    word_count: int
    status: str
    source_file: str
```

```python
# packages/core/narrare_core/importing/splitting.py
"""Section splitting for Markdown headings and TXT chapter markers (pure).

The regexes are the SSOT of the v1 detection heuristics (ADR-091 / spec §5):
ATX h1/h2 lines split Markdown; "Chapter X"/"Kapitel X" lines (EN/DE,
Arabic or Roman numerals, case-insensitive) split plain text.
"""

from __future__ import annotations

import re

# ATX h1/h2 heading line: 1-2 '#' + whitespace + visible text.
ATX_HEADING_RE = re.compile(r"^(#{1,2})\s+(.+?)\s*$", re.MULTILINE)

# TXT chapter marker: optional indent, chapter|kapitel, Arabic or Roman
# numeral, optional trailing text on the same line (kept in the title).
CHAPTER_MARKER_RE = re.compile(
    r"^[ \t]*(?:chapter|kapitel)[ \t]+([0-9]+|[ivxlcdm]+)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)


def split_markdown_sections(text: str) -> list[tuple[str, str]]:
    """Split a Markdown body on ATX h1/h2 heading lines.

    Returns (heading_text, section_body) pairs in document order. Text before
    the first heading is returned as ("", preamble) when non-empty after
    stripping. With no headings the whole text is a single ("", text) pair.
    """
    matches = list(ATX_HEADING_RE.finditer(text))
    if not matches:
        return [("", text)]

    sections: list[tuple[str, str]] = []
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append(("", preamble))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((match.group(2).strip(), text[match.end() : end].strip()))
    return sections


def split_marker_sections(text: str) -> list[tuple[str, str]]:
    """Split plain text on "Chapter X"/"Kapitel X" marker lines.

    Returns (marker_line, section_body) pairs in document order; the whole
    marker line (trimmed) is the title. Preamble handling mirrors
    :func:`split_markdown_sections`.
    """
    matches = list(CHAPTER_MARKER_RE.finditer(text))
    if not matches:
        return [("", text)]

    sections: list[tuple[str, str]] = []
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append(("", preamble))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((match.group(0).strip(), text[match.end() : end].strip()))
    return sections


def fallback_title(filename: str) -> str:
    """DemoLoader-style title from a filename stem (dashes → spaces, Title Case)."""
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    formatted = stem.replace("-", " ").title()
    return formatted or "Untitled Chapter"
```

```python
# packages/core/narrare_core/importing/detector.py
"""Chapter detection — deterministic, pure orchestration (ADR-091).

Same (filename, text) always yields the same chapter list: the stateless
preview/commit pair relies on this (re-parse contract, spec §4.2).
"""

from __future__ import annotations

from narrare_core.importing.models import (
    CHAPTER_STATUSES,
    TITLE_MAX_LENGTH,
    DetectedChapter,
)
from narrare_core.importing.splitting import (
    fallback_title,
    split_marker_sections,
    split_markdown_sections,
)
from narrare_core.shared.frontmatter import parse_frontmatter


def detect_chapters(filename: str, text: str) -> list[DetectedChapter]:
    """Detect chapters in one uploaded file's decoded text.

    Extension dispatch is case-insensitive (.md/.txt); anything else yields
    [] — extension guardrails are the API layer's job (spec §4.1).
    """
    lowered = filename.lower()
    if lowered.endswith(".md"):
        return _detect_markdown(filename, text)
    if lowered.endswith(".txt"):
        return _detect_txt(filename, text)
    return []


def _count_words(content: str) -> int:
    """Mirror of DemoLoader / chapters.repository.count_words."""
    return len(content.split()) if content.strip() else 0


def _clamp_title(title: str) -> str:
    """Clamp to the Chapter.title column limit (visible — preview shows it)."""
    return title[:TITLE_MAX_LENGTH]


def _detect_markdown(filename: str, text: str) -> list[DetectedChapter]:
    parsed = parse_frontmatter(text)
    fm_title = str(parsed.get("title", "")).strip() or None
    raw_status = parsed.get("status")
    status = raw_status if isinstance(raw_status, str) and raw_status in CHAPTER_STATUSES else "draft"

    chapters: list[DetectedChapter] = []
    for heading, body in split_markdown_sections(parsed.content):
        if not body:
            continue
        title = heading if heading else (fm_title or fallback_title(filename))
        chapters.append(
            DetectedChapter(
                title=_clamp_title(title),
                content=body,
                word_count=_count_words(body),
                status=status,
                source_file=filename,
            )
        )
    return chapters


def _detect_txt(filename: str, text: str) -> list[DetectedChapter]:
    chapters: list[DetectedChapter] = []
    for marker, body in split_marker_sections(text):
        if not body:
            continue
        title = marker if marker else fallback_title(filename)
        chapters.append(
            DetectedChapter(
                title=_clamp_title(title),
                content=body,
                word_count=_count_words(body),
                status="draft",
                source_file=filename,
            )
        )
    return chapters
```

```python
# packages/core/narrare_core/importing/__init__.py
"""Pure chapter-detection engine for project import (SETUP-003, ADR-091)."""

from narrare_core.importing.detector import detect_chapters
from narrare_core.importing.models import CHAPTER_STATUSES, TITLE_MAX_LENGTH, DetectedChapter

__all__ = ["CHAPTER_STATUSES", "DetectedChapter", "TITLE_MAX_LENGTH", "detect_chapters"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --all-packages pytest tests/unit/core/importing/ -v`
Expected: PASS (all tests in `test_splitting.py` + `test_detector.py`)

- [ ] **Step 5: Commit**

```bash
git add packages/core/narrare_core/importing/ tests/unit/core/importing/
git commit -m "feat(importing): pure Core chapter detector with golden tests (SETUP-003 v1)"
```

---

### Task 2: API module scaffold + `POST /import/preview` endpoint

**Files:**
- Create: `apps/api/narrare/importing/__init__.py` (empty)
- Create: `apps/api/narrare/importing/contracts.py`
- Create: `apps/api/narrare/importing/schemas.py`
- Create: `apps/api/narrare/importing/constants.py`
- Create: `apps/api/narrare/importing/service.py`
- Create: `apps/api/narrare/importing/router.py`
- Create: `apps/api/narrare/importing/dependencies.py`
- Modify: `apps/api/narrare/_app/main.py` (router registration, next to the `setup_router` import block + `include_router` list)
- Test: `tests/unit/api/importing/__init__.py` (empty)
- Test: `tests/unit/api/importing/test_import_service_preview.py`
- Test: `tests/integration/importing/__init__.py` (empty)
- Test: `tests/integration/importing/test_import_preview_api.py`

**Interfaces:**
- Consumes: `detect_chapters` / `DetectedChapter` (Task 1); `narrare._app.dependencies.{SessionDep, get_current_user_id, CurrentUserIdDep}`; `narrare_core.shared.errors.ValidationError`.
- Produces (Task 3 + frontend rely on these):
  - `ImportService(session, chapter_repo, novel_repo)` with `async preview(files: Sequence[UploadFile]) -> ImportPreviewResponse`
  - Schemas (exact JSON field names — RULE-17): `ImportPreviewItem{index, suggested_title, word_count, source_file}`, `ImportPreviewResponse{items, file_count, chapter_count, total_word_count}`
  - Constants: `MAX_FILES=100`, `MAX_FILE_BYTES=5*1024*1024`, `MAX_TOTAL_BYTES=25*1024*1024`, `ALLOWED_EXTENSIONS=frozenset({".md",".txt"})`

- [ ] **Step 1: Write contracts FIRST (RULE-03), then the failing service test**

```python
# apps/api/narrare/importing/contracts.py
"""Import module service contracts (RULE-03 — written before implementation)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fastapi import UploadFile
    from narrare.chapters.models import Chapter
    from narrare.importing.schemas import (
        ImportCommitAdjustments,
        ImportCommitResponse,
        ImportPreviewResponse,
    )
    from narrare_core.importing.models import DetectedChapter
    from sqlalchemy.ext.asyncio import AsyncSession


class ImportPreviewerProtocol(Protocol):
    """Parse uploaded files into a preview — no DB writes, idempotent."""

    async def preview(self, files: Sequence[UploadFile]) -> ImportPreviewResponse: ...


class ImportCommitterProtocol(Protocol):
    """Re-parse uploaded files and append chapters atomically (ADR-091)."""

    async def commit(
        self,
        files: Sequence[UploadFile],
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        adjustments: "ImportCommitAdjustments",
    ) -> ImportCommitResponse: ...


class ImportChapterRepositoryProtocol(Protocol):
    """Bulk chapter append seam (repository owns all SQLAlchemy)."""

    async def max_position(self, novel_id: uuid.UUID) -> int: ...

    async def append_chapters(
        self,
        novel_id: uuid.UUID,
        chapters: Sequence["DetectedChapter"],
        start_position: int,
    ) -> list["Chapter"]: ...


class ImportServiceProtocol(ImportPreviewerProtocol, ImportCommitterProtocol, Protocol):
    """Full import service surface (preview + commit)."""


def build_import_service(
    session: "AsyncSession",
) -> "ImportServiceProtocol":
    """Default composition root (re-exported seam for tests)."""
    from narrare.importing.repository import ImportChapterRepository
    from narrare.importing.service import ImportService
    from narrare.novels.repository import NovelRepository

    return ImportService(
        session=session,
        chapter_repo=ImportChapterRepository(session),
        novel_repo=NovelRepository(session),
    )
```

```python
# tests/unit/api/importing/test_import_service_preview.py
"""Unit tests for ImportService.preview guard pipeline (no DB, no HTTP)."""

from __future__ import annotations

import io

from fastapi import UploadFile
from narrare.importing.constants import MAX_FILES
from narrare.importing.service import ImportService
from narrare_core.shared.errors import ValidationError
from starlette.datastructures import Headers


def _upload(name: str, data: bytes) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(data),
        size=len(data),
        filename=name,
        headers=Headers({"content-type": "application/octet-stream"}),
    )


def _service() -> ImportService:
    return ImportService(session=None, chapter_repo=None, novel_repo=None)  # type: ignore[arg-type]  # reason: preview path touches no collaborator


class TestPreviewGuards:
    async def test_preview_with_empty_file_list_raises_422(self) -> None:
        try:
            await _service().preview([])
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "No files" in str(exc)

    async def test_preview_with_too_many_files_raises_422(self) -> None:
        files = [_upload(f"f{i}.md", b"# H\nbody") for i in range(MAX_FILES + 1)]
        try:
            await _service().preview(files)
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "Too many files" in str(exc)

    async def test_preview_with_oversize_file_raises_422(self) -> None:
        big = _upload("big.md", b"x" * (5 * 1024 * 1024 + 1))
        try:
            await _service().preview([big])
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "big.md" in str(exc)

    async def test_preview_with_unsupported_extension_raises_422(self) -> None:
        try:
            await _service().preview([_upload("ch.docx", b"pk\x03\x04")])
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "ch.docx" in str(exc)

    async def test_preview_with_latin1_bytes_raises_422_naming_file(self) -> None:
        try:
            await _service().preview([_upload("bad.md", "café".encode("latin-1"))])
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "bad.md" in str(exc)
            assert "UTF-8" in str(exc)

    async def test_preview_with_zero_chapters_raises_422(self) -> None:
        try:
            await _service().preview([_upload("empty.md", b"   \n")])
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "No chapters" in str(exc)


class TestPreviewHappyPath:
    async def test_preview_returns_indexed_items_across_files(self) -> None:
        result = await _service().preview(
            [
                _upload("b.md", b"# Second\nbody two words here"),
                _upload("a.md", b"# First\none two"),
            ]
        )
        assert result.file_count == 2
        assert result.chapter_count == 2
        # Order = multipart part order (client sorts; server does not re-order)
        assert [i.suggested_title for i in result.items] == ["Second", "First"]
        assert result.items[0].index == 0
        assert result.items[0].source_file == "b.md"
        assert result.total_word_count == 5

    async def test_preview_is_idempotent(self) -> None:
        files = [_upload("a.md", b"# T\nbody")]
        assert await _service().preview(files) == await _service().preview(files)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --all-packages pytest tests/unit/api/importing/ -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'narrare.importing'`

- [ ] **Step 3: Write schemas, constants, service, router, dependencies**

```python
# apps/api/narrare/importing/schemas.py
"""Import module Pydantic schemas (request/response) — RULE-17 mirror of
packages/web/types/importing.ts (added in the frontend client task)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ImportPreviewItem(BaseModel):
    """One detected chapter in a preview (index = commit adjustment key)."""

    index: int = Field(ge=0)
    suggested_title: str = Field(min_length=1, max_length=500)
    word_count: int = Field(ge=0)
    source_file: str


class ImportPreviewResponse(BaseModel):
    items: list[ImportPreviewItem]
    file_count: int = Field(ge=1)
    chapter_count: int = Field(ge=1)
    total_word_count: int = Field(ge=0)


class ImportCommitAdjustments(BaseModel):
    """User edits applied on top of the deterministic re-parse."""

    excluded_indices: list[int] = Field(default_factory=list)
    title_overrides: dict[str, str] = Field(default_factory=dict)


class ImportCommitChapterInfo(BaseModel):
    id: str
    title: str
    position: int
    word_count: int


class ImportCommitResponse(BaseModel):
    novel_id: str
    created_count: int = Field(ge=1)
    first_position: int = Field(ge=0)
    last_position: int = Field(ge=0)
    chapters: list[ImportCommitChapterInfo]
```

```python
# apps/api/narrare/importing/constants.py
"""Import guardrails (ADR-091) — protocol constants, NOT user settings."""

from __future__ import annotations

from typing import Final

MAX_FILES: Final[int] = 100
MAX_FILE_BYTES: Final[int] = 5 * 1024 * 1024
MAX_TOTAL_BYTES: Final[int] = 25 * 1024 * 1024
ALLOWED_EXTENSIONS: Final[frozenset[str]] = frozenset({".md", ".txt"})
```

```python
# apps/api/narrare/importing/service.py
"""Import service — guard pipeline, parse orchestration, atomic append.

Preview is stateless (no DB writes). Commit re-parses deterministically and
appends chapters in the caller's request transaction (ADR-091).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import structlog
from narrare.importing.constants import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
)
from narrare.importing.schemas import (
    ImportCommitAdjustments,
    ImportCommitChapterInfo,
    ImportCommitResponse,
    ImportPreviewItem,
    ImportPreviewResponse,
)
from narrare_core.importing.detector import detect_chapters
from narrare_core.importing.models import DetectedChapter
from narrare_core.shared.errors import ValidationError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fastapi import UploadFile
    from narrare.chapters.models import Chapter
    from narrare.novels.contracts import NovelRepositoryProtocol
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.importing.contracts import ImportChapterRepositoryProtocol

logger = structlog.get_logger(__name__)


class ImportService:
    """Implements ImportServiceProtocol (contracts.py) implicitly."""

    def __init__(
        self,
        session: AsyncSession,
        chapter_repo: ImportChapterRepositoryProtocol,
        novel_repo: NovelRepositoryProtocol,
    ) -> None:
        self._session = session
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo

    async def preview(self, files: Sequence[UploadFile]) -> ImportPreviewResponse:
        """Guard + parse uploads; NO DB writes (safe to repeat)."""
        texts = await self._read_and_validate(files)
        detected = self._detect_all(files, texts)
        if not detected:
            raise ValidationError("No chapters detected in the uploaded files.")
        items = [
            ImportPreviewItem(
                index=i,
                suggested_title=c.title,
                word_count=c.word_count,
                source_file=c.source_file,
            )
            for i, c in enumerate(detected)
        ]
        return ImportPreviewResponse(
            items=items,
            file_count=len(files),
            chapter_count=len(detected),
            total_word_count=sum(c.word_count for c in detected),
        )

    async def _read_and_validate(self, files: Sequence[UploadFile]) -> list[str]:
        """Guards 1-5 of spec §4.1, then decode utf-8-sig strict."""
        if not files:
            raise ValidationError("No files uploaded.")
        if len(files) > MAX_FILES:
            raise ValidationError(f"Too many files: {len(files)} (max {MAX_FILES}).")
        total = 0
        for upload in files:
            size = upload.size or 0
            if size > MAX_FILE_BYTES:
                raise ValidationError(
                    f"File '{upload.filename}' exceeds the 5 MB per-file limit."
                )
            total += size
            if total > MAX_TOTAL_BYTES:
                raise ValidationError("Upload exceeds the 25 MB total size limit.")
            extension = Path(upload.filename or "").suffix.lower()
            if extension not in ALLOWED_EXTENSIONS:
                raise ValidationError(
                    f"File '{upload.filename}': unsupported type (allowed: .md, .txt)."
                )
        texts: list[str] = []
        for upload in files:
            raw = await upload.read()
            try:
                texts.append(raw.decode("utf-8-sig"))
            except UnicodeDecodeError as exc:
                raise ValidationError(
                    f"File '{upload.filename}' is not valid UTF-8."
                ) from exc
        return texts

    @staticmethod
    def _detect_all(files: Sequence[UploadFile], texts: list[str]) -> list[DetectedChapter]:
        """Deterministic parse — multipart part order is the chapter order."""
        detected: list[DetectedChapter] = []
        for upload, text in zip(files, texts):
            detected.extend(detect_chapters(upload.filename or "", text))
        return detected
```

(Add `from __future__ import annotations` compatible TYPE_CHECKING block exactly as above — `commit` arrives in Task 3.)

```python
# apps/api/narrare/importing/dependencies.py
"""Import service FastAPI factories (RULE-19: SessionDep, never bare AsyncSession)."""

from __future__ import annotations

from narrare._app.dependencies import SessionDep
from narrare.importing.contracts import build_import_service, ImportServiceProtocol


def get_import_service(
    session: SessionDep,
) -> ImportServiceProtocol:
    return build_import_service(session)
```

```python
# apps/api/narrare/importing/router.py
"""Import routes — thin, delegates immediately (RULE-06)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from narrare._app.dependencies import get_current_user_id
from narrare.importing.dependencies import get_import_service
from narrare.importing.schemas import ImportPreviewResponse

router = APIRouter(prefix="/import", tags=["import"])


@router.post(
    "/preview",
    response_model=ImportPreviewResponse,
    dependencies=[Depends(get_current_user_id)],
)
async def preview_import(
    files: list[UploadFile] = File(...),
    service: ImportServiceProtocol = Depends(get_import_service),
) -> ImportPreviewResponse:
    """Parse uploaded manuscript files — preview only, no DB writes."""
    return await service.preview(files)
```

Register in `apps/api/narrare/_app/main.py`: import `from narrare.importing.router import router as import_router` with the other router imports and add `app.include_router(import_router, prefix=prefix)` next to `setup_router`.

- [ ] **Step 4: Run unit tests to verify they pass**

Run: `uv run --all-packages pytest tests/unit/api/importing/ -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Write the integration test and run it**

```python
# tests/integration/importing/test_import_preview_api.py
"""Integration tests for POST /api/v1/import/preview (multipart)."""

from __future__ import annotations


class TestPreviewEndpoint:
    async def test_preview_requires_auth(self, client) -> None:
        response = await client.post("/api/v1/import/preview", files=[])
        assert response.status_code == 401

    async def test_preview_returns_items(self, client, auth_headers) -> None:
        response = await client.post(
            "/api/v1/import/preview",
            headers=auth_headers,
            files=[
                ("files", ("ch-01.md", b"# The Thorn Wall\nbody words here", "text/markdown")),
                ("files", ("ch-02.txt", b"Chapter 2\nmore words", "text/plain")),
            ],
        )
        assert response.status_code == 200
        body = response.json()
        assert body["file_count"] == 2
        assert body["chapter_count"] == 2
        assert body["items"][0]["suggested_title"] == "The Thorn Wall"
        assert body["items"][1]["source_file"] == "ch-02.txt"
        assert body["items"][1]["index"] == 1

    async def test_preview_rejects_docx_with_422(self, client, auth_headers) -> None:
        response = await client.post(
            "/api/v1/import/preview",
            headers=auth_headers,
            files=[("files", ("manuscript.docx", b"PK\x03\x04", "application/octet-stream"))],
        )
        assert response.status_code == 422
        assert "manuscript.docx" in response.json()["detail"]

    async def test_preview_zero_chapters_422(self, client, auth_headers) -> None:
        response = await client.post(
            "/api/v1/import/preview",
            headers=auth_headers,
            files=[("files", ("empty.md", b"   \n", "text/markdown"))],
        )
        assert response.status_code == 422
```

Run: `just _ensure-services && uv run --all-packages pytest tests/integration/importing/ -v`
Expected: PASS (4 tests). Type hints per file convention: add `from httpx import AsyncClient` under `TYPE_CHECKING` and annotate `client: AsyncClient`, `auth_headers: dict[str, str]` as in `tests/integration/setup/test_setup_api.py`.

- [ ] **Step 6: Verify multipart through the Next.js rewrite (spec §7 R1 — mandatory)**

Start the dev stack (`just dev` or the API + `cd packages/web && pnpm dev` in another terminal). Then:

```bash
# >1 MB file so any body-size ceiling would trip
head -c 2000000 /dev/urandom | base64 | tr -d '\n' > /tmp/opencode/big-chapter.txt
TOKEN=<paste an access token from the browser devtools>
curl -s -o /tmp/opencode/preview-response.json -w "%{http_code}\n" \
  -X POST http://localhost:3000/api/v1/import/preview \
  -H "Authorization: Bearer $TOKEN" \
  -F "files=@/tmp/opencode/big-chapter.txt"
```

Expected: HTTP `200` or `422` (JSON `{"detail": ...}`) — anything else (`413`, `502`, connection reset, HTML error page) means the rewrite mangles multipart bodies → STOP and escalate to Architecture (RULE-21). Record the observed status in the task's PR description. Repeat once with a ~5 MB file to pin the per-file guard response (expect 422 naming the file).

- [ ] **Step 7: Run the architecture gate**

Run: `just check-architecture`
Expected: exit 0.

- [ ] **Step 8: Commit**

```bash
git add apps/api/narrare/importing/ apps/api/narrare/_app/main.py tests/unit/api/importing/ tests/integration/importing/
git commit -m "feat(importing): POST /import/preview multipart endpoint with guard pipeline"
```

---

### Task 3: `POST /import/commit` — atomic append with ownership gate

**Files:**
- Create: `apps/api/narrare/importing/repository.py`
- Modify: `apps/api/narrare/importing/service.py` (add `commit` + adjustment validation)
- Modify: `apps/api/narrare/importing/router.py` (add commit route)
- Test: `tests/unit/api/importing/test_import_service_commit.py`
- Test: `tests/integration/importing/test_import_commit_api.py`

**Interfaces:**
- Consumes: `verify_novel_owned` from `narrare.novels.ownership`; `NovelRepository`; `ImportCommitAdjustments` (Task 2).
- Produces: `ImportService.commit(files, novel_id, user_id, adjustments) -> ImportCommitResponse`; `ImportChapterRepository(session).max_position(novel_id) -> int` / `.append_chapters(novel_id, chapters, start_position) -> list[Chapter]`.

- [ ] **Step 1: Write the failing unit test**

```python
# tests/unit/api/importing/test_import_service_commit.py
"""Unit tests for ImportService.commit — adjustment validation (fakes, no DB)."""

from __future__ import annotations

import dataclasses
import io
import uuid

from fastapi import UploadFile
from narrare.importing.schemas import ImportCommitAdjustments
from narrare.importing.service import ImportService
from narrare_core.importing.models import DetectedChapter
from narrare_core.shared.errors import ValidationError
from starlette.datastructures import Headers


def _upload(name: str, data: bytes) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(data), size=len(data), filename=name,
        headers=Headers({"content-type": "application/octet-stream"}),
    )


class _FakeChapterRepo:
    def __init__(self) -> None:
        self.appended: list[DetectedChapter] = []
        self.start_position = -1

    async def max_position(self, novel_id: uuid.UUID) -> int:
        return 4  # novel has 5 chapters at positions 0..4

    async def append_chapters(self, novel_id, chapters, start_position):
        self.appended = list(chapters)
        self.start_position = start_position
        return []


class _FakeNovelRepo:
    async def get_by_id(self, novel_id, user_id):
        return object()  # owned


def _service() -> tuple[ImportService, _FakeChapterRepo]:
    repo = _FakeChapterRepo()
    return ImportService(session=None, chapter_repo=repo, novel_repo=_FakeNovelRepo()), repo  # type: ignore[arg-type]  # reason: unit test injects fakes


FILES = [_upload("a.md", b"# One\nbody one"), _upload("b.md", b"# Two\nbody two")]


class TestCommitValidation:
    async def test_out_of_range_excluded_index_raises_422(self) -> None:
        service, _ = _service()
        try:
            await service.commit(FILES, uuid.uuid4(), uuid.uuid4(),
                                 ImportCommitAdjustments(excluded_indices=[5]))
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "5" in str(exc)

    async def test_out_of_range_title_override_key_raises_422(self) -> None:
        service, _ = _service()
        try:
            await service.commit(FILES, uuid.uuid4(), uuid.uuid4(),
                                 ImportCommitAdjustments(title_overrides={"9": "X"}))
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "9" in str(exc)

    async def test_overlong_title_override_raises_422(self) -> None:
        service, _ = _service()
        try:
            await service.commit(FILES, uuid.uuid4(), uuid.uuid4(),
                                 ImportCommitAdjustments(title_overrides={"0": "x" * 501}))
            raise AssertionError("expected ValidationError")
        except ValidationError:
            pass

    async def test_empty_title_override_raises_422(self) -> None:
        service, _ = _service()
        try:
            await service.commit(FILES, uuid.uuid4(), uuid.uuid4(),
                                 ImportCommitAdjustments(title_overrides={"0": "  "}))
            raise AssertionError("expected ValidationError")
        except ValidationError:
            pass


class TestCommitAppend:
    async def test_exclusion_rename_and_positions(self) -> None:
        service, repo = _service()
        result = await service.commit(
            FILES, uuid.uuid4(), uuid.uuid4(),
            ImportCommitAdjustments(excluded_indices=[1], title_overrides={"0": "Renamed"}),
        )
        assert result.created_count == 1
        assert [c.title for c in repo.appended] == ["Renamed"]
        assert repo.start_position == 5  # max_position 4 + 1
        assert result.first_position == 5 and result.last_position == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --all-packages pytest tests/unit/api/importing/test_import_service_commit.py -v`
Expected: FAIL — `AttributeError: 'ImportService' object has no attribute 'commit'`

- [ ] **Step 3: Implement repository + commit**

```python
# apps/api/narrare/importing/repository.py
"""Import chapter repository — bulk append (DB only, RULE-06)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from narrare.chapters.models import Chapter

if TYPE_CHECKING:
    from collections.abc import Sequence

    from narrare_core.importing.models import DetectedChapter
    from sqlalchemy.ext.asyncio import AsyncSession


class ImportChapterRepository:
    """Implements ImportChapterRepositoryProtocol implicitly."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def max_position(self, novel_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.max(Chapter.position)).where(Chapter.novel_id == novel_id)
        )
        value = result.scalar_one_or_none()
        # Explicit None check: `value or -1` maps a legitimate max of 0 to -1.
        return -1 if value is None else value

    async def append_chapters(
        self,
        novel_id: uuid.UUID,
        chapters: Sequence[DetectedChapter],
        start_position: int,
    ) -> list[Chapter]:
        """Add all chapters in one flush — atomic within the request transaction."""
        rows = [
            Chapter(
                novel_id=novel_id,
                title=chapter.title,
                content=chapter.content,
                position=start_position + offset,
                word_count=chapter.word_count,
                status=chapter.status,
            )
            for offset, chapter in enumerate(chapters)
        ]
        self._session.add_all(rows)
        await self._session.flush()
        return rows
```

Append to `service.py` (imports at top: `dataclasses`, `NarrareError`-free — only `ValidationError` + `NotFoundError` paths; `verify_novel_owned`):

```python
# additions to apps/api/narrare/importing/service.py
import dataclasses

from narrare.novels.ownership import verify_novel_owned


class ImportService:
    # ... preview unchanged ...

    async def commit(
        self,
        files: Sequence[UploadFile],
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        adjustments: ImportCommitAdjustments,
    ) -> ImportCommitResponse:
        """Ownership gate → deterministic re-parse → validate → atomic append."""
        await verify_novel_owned(self._novel_repo, novel_id, user_id)

        texts = await self._read_and_validate(files)
        detected = self._detect_all(files, texts)
        if not detected:
            raise ValidationError("No chapters detected in the uploaded files.")
        self._validate_adjustments(adjustments, len(detected))

        selected = [
            dataclasses.replace(
                chapter,
                title=adjustments.title_overrides.get(str(index), chapter.title),
            )
            for index, chapter in enumerate(detected)
            if index not in adjustments.excluded_indices
        ]
        if not selected:
            raise ValidationError("All detected chapters are excluded — nothing to import.")

        start_position = (await self._chapter_repo.max_position(novel_id)) + 1
        rows = await self._chapter_repo.append_chapters(novel_id, selected, start_position)

        logger.info(
            "import_committed",
            novel_id=str(novel_id),
            created=len(rows),
            first_position=start_position,
        )
        return ImportCommitResponse(
            novel_id=str(novel_id),
            created_count=len(rows),
            first_position=start_position,
            last_position=start_position + len(rows) - 1,
            chapters=[
                ImportCommitChapterInfo(
                    id=str(row.id),
                    title=row.title,
                    position=row.position,
                    word_count=row.word_count,
                )
                for row in rows
            ],
        )

    @staticmethod
    def _validate_adjustments(adjustments: ImportCommitAdjustments, chapter_count: int) -> None:
        for index in adjustments.excluded_indices:
            if not 0 <= index < chapter_count:
                raise ValidationError(
                    f"Excluded index {index} is out of range (0..{chapter_count - 1})."
                )
        for key, title in adjustments.title_overrides.items():
            if not key.isdigit() or not 0 <= int(key) < chapter_count:
                raise ValidationError(
                    f"Title override key '{key}' is not a valid chapter index."
                )
            if not 1 <= len(title.strip()) <= 500:
                raise ValidationError(f"Title override for chapter {key} must be 1-500 characters.")
```

Add to `router.py`:

```python
from uuid import UUID

from fastapi import Form
from narrare._app.dependencies import CurrentUserIdDep
from narrare.importing.schemas import ImportCommitResponse


@router.post("/commit", response_model=ImportCommitResponse)
async def commit_import(
    files: list[UploadFile] = File(...),
    novel_id: UUID = Form(...),
    adjustments: ImportCommitAdjustments = Form(...),
    user_id: CurrentUserIdDep = None,
    service: ImportServiceProtocol = Depends(get_import_service),
) -> ImportCommitResponse:
    """Re-parse files and append chapters atomically (ADR-091 contract)."""
    return await service.commit(files, novel_id, uuid.UUID(user_id), adjustments)
```

> Note: FastAPI ≥0.100 supports a Pydantic model directly as a `Form(...)`-annotated JSON-string field only via `Annotated`; if the installed version rejects `ImportCommitAdjustments = Form(...)`, parse explicitly instead — keep the router thin either way:

```python
# fallback variant if Form-Pydantic is unsupported by the installed FastAPI:
adjustments_raw: str = Form(...),
...
parsed = ImportCommitAdjustments.model_validate_json(adjustments_raw)
```

Use whichever variant compiles + passes tests on the installed FastAPI; do NOT invent a third. Router top needs `import uuid` for the chosen variant.

- [ ] **Step 4: Run unit tests to verify they pass**

Run: `uv run --all-packages pytest tests/unit/api/importing/ -v`
Expected: PASS (Task 2 + Task 3 tests)

- [ ] **Step 5: Write the integration test and run it**

```python
# tests/integration/importing/test_import_commit_api.py
"""Integration tests for POST /api/v1/import/commit — ownership + atomic append."""

from __future__ import annotations

import uuid

from narrare.novels.models import Novel


async def _create_novel(db_session, user_id: uuid.UUID, title: str = "Import Target") -> Novel:
    novel = Novel(user_id=user_id, title=title)
    db_session.add(novel)
    await db_session.flush()
    return novel


def _files():
    return [
        ("files", ("ch-01.md", b"# One\nfirst body", "text/markdown")),
        ("files", ("ch-02.md", b"# Two\nsecond body", "text/markdown")),
    ]


class TestCommitEndpoint:
    async def test_commit_appends_atomically(self, client, auth_headers, db_session, user_id) -> None:
        novel = await _create_novel(db_session, user_id)
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={"novel_id": str(novel.id), "adjustments": '{"excluded_indices": [1], "title_overrides": {"0": "Renamed"}}'},
            files=_files(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["created_count"] == 1
        assert body["chapters"][0]["title"] == "Renamed"

        chapters = await client.get(f"/api/v1/novels/{novel.id}/chapters", headers=auth_headers)
        titles = [c["title"] for c in chapters.json()]
        assert titles == ["Renamed"]

    async def test_commit_unknown_novel_404(self, client, auth_headers) -> None:
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={"novel_id": str(uuid.uuid4()), "adjustments": "{}"},
            files=_files(),
        )
        assert response.status_code == 404

    async def test_commit_foreign_novel_404(self, client, auth_headers, db_session, second_user_id) -> None:
        novel = await _create_novel(db_session, second_user_id, title="Foreign")
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={"novel_id": str(novel.id), "adjustments": "{}"},
            files=_files(),
        )
        assert response.status_code == 404  # foreign ≡ unknown (IDOR pattern)

    async def test_commit_requires_auth(self, client) -> None:
        response = await client.post(
            "/api/v1/import/commit",
            data={"novel_id": str(uuid.uuid4()), "adjustments": "{}"},
            files=_files(),
        )
        assert response.status_code == 401

    async def test_commit_out_of_range_adjustment_422(self, client, auth_headers, db_session, user_id) -> None:
        novel = await _create_novel(db_session, user_id)
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={"novel_id": str(novel.id), "adjustments": '{"excluded_indices": [99]}'},
            files=_files(),
        )
        assert response.status_code == 422
        # rollback proof: nothing was written
        chapters = await client.get(f"/api/v1/novels/{novel.id}/chapters", headers=auth_headers)
        assert chapters.json() == []
```

> Fixture note: `user_id`/`second_user_id` — reuse the conftest patterns from `tests/integration/novels/` (the `_extract_user_id(auth_headers)` helper from `tests/integration/setup/test_setup_api.py` derives `user_id` from the token; create the second user directly via `narrare.users`... if no `second_user_id` fixture exists, insert a `User` row via `db_session` following the existing novels integration tests). Check the chapters list endpoint path (`GET /api/v1/novels/{id}/chapters`) against `apps/api/narrare/chapters/router.py` and use the actual route.

Run: `just _ensure-services && uv run --all-packages pytest tests/integration/importing/ -v`
Expected: PASS (Task 2 + Task 3 integration tests)

- [ ] **Step 6: Run architecture gate**

Run: `just check-architecture`
Expected: exit 0.

- [ ] **Step 7: Commit**

```bash
git add apps/api/narrare/importing/ tests/unit/api/importing/test_import_service_commit.py tests/integration/importing/test_import_commit_api.py
git commit -m "feat(importing): POST /import/commit atomic append with ownership gate"
```

---

### Task 4: Backend `import_path` removal (RULE-20 slice, backend half)

**Files:**
- Modify: `apps/api/narrare/setup/base_schemas.py:108-116` (remove `import_path` field + no-op validator)
- Modify: `apps/api/narrare/setup/provider_schemas.py:102` (remove `WizardState.import_path`)
- Modify: `apps/api/narrare/setup/_validation.py:87-93` (remove IMPORT branch; drop the now-unused `pathlib.Path` import)
- Modify: `apps/api/narrare/setup/service.py` (docstring note: `starter="import"` intentionally creates an empty novel — frontend commits via `/import/commit`; no logic change)
- Test: adjust existing tests referencing `import_path` (find via grep below)

**Interfaces:**
- Consumes: nothing new.
- Produces: `Step3StarterRequest` without `import_path`; `WizardState` without `import_path`. `StarterContent.IMPORT` enum value STAYS (frontend sends `starter="import"`; complete() creates an empty novel by design).

- [ ] **Step 1: Write the failing regression test**

```python
# tests/unit/api/setup/test_import_path_removed.py
"""Regression: the dormant server-side import_path stub is gone (ADR-091)."""

from __future__ import annotations

import inspect

from narrare.setup.base_schemas import Step3StarterRequest
from narrare.setup.provider_schemas import WizardState


def test_step3_request_has_no_import_path_field() -> None:
    assert "import_path" not in Step3StarterRequest.model_fields


def test_wizard_state_has_no_import_path_field() -> None:
    assert "import_path" not in WizardState.model_fields


def test_starter_import_enum_value_remains() -> None:
    # The starter CHOICE stays; only the server-path mechanism is gone.
    from narrare.setup.schemas import StarterContent

    assert StarterContent.IMPORT.value == "import"


async def test_validate_step3_accepts_import_without_path() -> None:
    from narrare.setup._validation import validate_step3

    result = await validate_step3(Step3StarterRequest(starter="import"), demo_loader=None)  # type: ignore[arg-type]  # reason: import branch no longer touches the loader
    assert result.valid is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --all-packages pytest tests/unit/api/setup/test_import_path_removed.py -v`
Expected: FAIL (fields still exist / validation still requires a path)

- [ ] **Step 3: Remove the stub**

1. `base_schemas.py`: delete `import_path: str | None = Field(default=None, max_length=500)` and the `validate_import_path` field_validator from `Step3StarterRequest`; drop `field_validator` from the pydantic import if now unused.
2. `provider_schemas.py`: delete `import_path: str | None` from `WizardState`.
3. `_validation.py`: delete the whole `if request.starter == StarterContent.IMPORT:` block (lines ~87-93) and the `from pathlib import Path` import; fix the docstring's `Raises:` section.
4. `service.py` `complete()`: add one docstring line — `starter="import"` creates an empty novel; the frontend then calls ``POST /import/commit`` (ADR-091). No code change.
5. Sweep: `grep -rn "import_path" apps/ tests/` → update every hit (setup unit/integration tests asserting the old validation → assert the new acceptance instead, mirroring the regression test above).

- [ ] **Step 4: Run the full setup test suites**

Run: `uv run --all-packages pytest tests/unit/api/setup/ tests/unit/setup/ tests/integration/setup/ -v 2>/dev/null || uv run --all-packages pytest tests/unit/api/setup/ tests/integration/setup/ -v`
Expected: PASS (plus the new regression test)

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/setup/ tests/
git commit -m "refactor(setup): remove dormant import_path mechanism (backend half, ADR-091)"
```

---

### Task 5: Frontend `import_path` removal (RULE-20 slice, frontend half)

**Files:**
- Modify: `packages/web/types/wizard.ts:93` (remove `import_path` from `WizardState`)
- Modify: `packages/web/lib/stores/wizardStore.ts` (remove from `defaultState` + `updateStep3` signature)
- Modify: `packages/web/components/studio/wizard/WizardStep2.tsx` (remove import card + path input + `importPath` state + `import_path` payloads)
- Modify: `packages/web/components/studio/wizard/WizardStep5.tsx:50` (remove `importFrom` starterLabel entry)
- Modify: `packages/web/lib/api/setup.ts:32-36` (drop `import_path` from `validateStep3`)
- Modify: `packages/i18n/messages/{en,de,fr}/studio.json` (remove `wizard.step2.importPath`, `wizard.step2.importPathPlaceholder`, `wizard.step5.importFrom`)
- Test: adjust `packages/web/components/studio/wizard/wizard.test.tsx` (drop/adjust import-path assertions)

**Interfaces:**
- Produces: `WizardState` (TS) without `import_path`; wizard has NO import card until Task 9 re-adds it with upload semantics (single feature branch — RULE-20 satisfied at merge, noted in the plan header).

- [ ] **Step 1: Update tests first**

In `wizard.test.tsx`: remove tests (or assertions) covering the import path input / `import_path` state. Run them red is not applicable for pure removal — instead run the suite after each edit below and keep it green.

- [ ] **Step 2: Remove the plumbing**

1. `types/wizard.ts`: delete `import_path: string | null;` and its comment line.
2. `wizardStore.ts`: delete `import_path: null,` from `defaultState`; change `updateStep3` to `(data: { starter: StarterContent }) => void;`.
3. `WizardStep2.tsx`: delete `const [importPath, setImportPath] = useState(...)`; delete the `{selected === "import" && (...)}` input block; remove `import_path` from the `validateStep3` + `updateStep3` calls; delete the import `StarterCard` block (re-added in Task 9).
4. `WizardStep5.tsx`: delete the `import: t("wizard.step5.importFrom", ...)` entry from `starterLabel`.
5. `lib/api/setup.ts`: `validateStep3: (data: { starter: string }) => ...`.
6. i18n: remove the three keys in all three locales (exact lines: en 652-653 + 710, de 652-653 + 710, fr 652-653 + 710 — keep `wizard.step2.import` + `importDescription` for Task 9).
7. Sweep: `grep -rn "import_path\|importPath\|importFrom" packages/web packages/i18n` → must return only this plan/spec references.

- [ ] **Step 3: Run frontend tests + typecheck**

Run: `cd packages/web && pnpm test -- wizard && pnpm type-check`
Expected: PASS / 0 errors. Also `pnpm test -- i18n` (namespace/key parity — RULE-16 enforcer).

- [ ] **Step 4: Commit**

```bash
git add packages/web/types/wizard.ts packages/web/lib/stores/wizardStore.ts packages/web/components/studio/wizard/ packages/web/lib/api/setup.ts packages/i18n/messages/
git commit -m "refactor(web): remove dormant import_path UI + state (frontend half, ADR-091)"
```

---

### Task 6: Multipart API client (`fetchApiUpload` + types + `importApi`)

**Files:**
- Modify: `packages/web/lib/api/core.ts` (add `fetchApiUpload`)
- Create: `packages/web/types/importing.ts`
- Create: `packages/web/lib/api/importing.ts`
- Modify: `packages/web/lib/api/index.ts` (barrel exports)
- Test: `packages/web/lib/api/importing.test.ts`

**Interfaces:**
- Consumes: auth/refresh internals of `core.ts`.
- Produces (Task 7+ rely on these exact names):
  - `fetchApiUpload<T>(endpoint: string, options: { body: FormData }): Promise<T>`
  - `importApi.preview(files: File[]): Promise<ImportPreviewResponse>`
  - `importApi.commit(files: File[], novelId: string, adjustments: ImportCommitAdjustments): Promise<ImportCommitResponse>`
  - Types (RULE-17 — mirror Task 2 schemas exactly): `ImportPreviewItem`, `ImportPreviewResponse`, `ImportCommitAdjustments`, `ImportCommitChapterInfo`, `ImportCommitResponse`, plus FE-only `ImportSelection { files: File[]; excludedIndices: number[]; titleOverrides: Record<string, string>; includedCount: number }`

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/lib/api/importing.test.ts
/**
 * Tests for the importing API client (multipart encoding, RULE-17 shapes).
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { importApi } from "./importing";

const fetchMock = vi.fn();

beforeEach(() => {
  vi.unstubAllGlobals();
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
});

describe("importApi", () => {
  it("preview posts multipart with files under the 'files' key", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ items: [], file_count: 1, chapter_count: 1, total_word_count: 0 }), { status: 200 }),
    );
    const file = new File(["# T\nbody"], "a.md", { type: "text/markdown" });
    await importApi.preview([file]);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = init.body as FormData;
    expect(body.getAll("files")).toHaveLength(1);
    expect(init.method).toBe("POST");
    // MUST NOT set a JSON Content-Type — the browser sets the multipart boundary
    expect((init.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
  });

  it("commit posts files + novel_id + adjustments JSON", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({ novel_id: "n", created_count: 1, first_position: 0, last_position: 0, chapters: [] }),
        { status: 200 },
      ),
    );
    const file = new File(["Chapter 1\nx"], "a.txt", { type: "text/plain" });
    await importApi.commit([file], "novel-uuid", { excluded_indices: [], title_overrides: {} });
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = init.body as FormData;
    expect(body.getAll("files")).toHaveLength(1);
    expect(body.get("novel_id")).toBe("novel-uuid");
    expect(JSON.parse(body.get("adjustments") as string)).toEqual({
      excluded_indices: [],
      title_overrides: {},
    });
  });

  it("preview surfaces the backend detail message on 422", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "File 'a.docx': unsupported type (allowed: .md, .txt).", code: "..." }), { status: 422 }),
    );
    const file = new File(["x"], "a.docx");
    await expect(importApi.preview([file])).rejects.toThrow("unsupported type");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && pnpm test -- importing`
Expected: FAIL — module `./importing` not found

- [ ] **Step 3: Implement**

```typescript
// packages/web/types/importing.ts
// Project Import types — RULE-17 mirror of apps/api/narrare/importing/schemas.py.
// ImportSelection is frontend-only (File objects never cross the wire via JSON).

export interface ImportPreviewItem {
  index: number;
  suggested_title: string;
  word_count: number;
  source_file: string;
}

export interface ImportPreviewResponse {
  items: ImportPreviewItem[];
  file_count: number;
  chapter_count: number;
  total_word_count: number;
}

export interface ImportCommitAdjustments {
  excluded_indices: number[];
  title_overrides: Record<string, string>;
}

export interface ImportCommitChapterInfo {
  id: string;
  title: string;
  position: number;
  word_count: number;
}

export interface ImportCommitResponse {
  novel_id: string;
  created_count: number;
  first_position: number;
  last_position: number;
  chapters: ImportCommitChapterInfo[];
}

/** Current pick state of the shared import panel (frontend-only). */
export interface ImportSelection {
  files: File[];
  excludedIndices: number[];
  titleOverrides: Record<string, string>;
  includedCount: number;
}
```

Add to `packages/web/lib/api/core.ts` (after `fetchApiRaw`):

```typescript
/**
 * Multipart upload wrapper (SETUP-003 import).
 *
 * Mirrors fetchApi's auth header + one 401-refresh retry, but intentionally
 * sets NO Content-Type — the browser must generate the multipart boundary.
 * FormData bodies are re-usable, so the retry re-sends the same object.
 */
export async function fetchApiUpload<T>(endpoint: string, options: { body: FormData }): Promise<T> {
  const url = `/api/v1${endpoint}`;
  const headers: Record<string, string> = {};
  if (_accessToken) headers.Authorization = `Bearer ${_accessToken}`;

  const response = await fetch(url, {
    method: "POST",
    headers,
    credentials: "include",
    body: options.body,
  });

  if (response.status === 401) {
    await refreshAccessToken();
    headers.Authorization = `Bearer ${_accessToken}`;
    const retry = await fetch(url, {
      method: "POST",
      headers,
      credentials: "include",
      body: options.body,
    });
    if (!retry.ok) throw new Error(`HTTP ${retry.status}`);
    return retry.json() as Promise<T>;
  }

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    if (typeof err.detail === "string") throw new Error(err.detail);
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}
```

```typescript
// packages/web/lib/api/importing.ts
/**
 * Project Import API — stateless two-phase multipart (ADR-091).
 */

import type { ImportCommitAdjustments, ImportCommitResponse, ImportPreviewResponse } from "@/types";
import { fetchApiUpload } from "./core";

function filesBody(files: File[]): FormData {
  const body = new FormData();
  for (const file of files) body.append("files", file);
  return body;
}

export const importApi = {
  preview: (files: File[]) => fetchApiUpload<ImportPreviewResponse>("/import/preview", { body: filesBody(files) }),

  commit: (files: File[], novelId: string, adjustments: ImportCommitAdjustments) => {
    const body = filesBody(files);
    body.append("novel_id", novelId);
    body.append("adjustments", JSON.stringify(adjustments));
    return fetchApiUpload<ImportCommitResponse>("/import/commit", { body });
  },
};
```

Barrel additions to `packages/web/lib/api/index.ts`: `export { fetchApiUpload } from "./core";` (inside the existing core export block), `export { importApi } from "./importing";`. Check `packages/web/types/index.ts` re-exports `./importing` types like the other type modules (add `export * from "./importing";` following the existing pattern).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/web && pnpm test -- importing && pnpm type-check`
Expected: PASS / 0 errors

- [ ] **Step 5: Commit**

```bash
git add packages/web/lib/api/core.ts packages/web/lib/api/importing.ts packages/web/lib/api/index.ts packages/web/types/importing.ts packages/web/types/index.ts packages/web/lib/api/importing.test.ts
git commit -m "feat(web): multipart upload client + importing API types (RULE-17 mirror)"
```

---

### Task 7: `ImportPreviewPanel` + `ImportModal` + `importing` i18n namespace

**Files:**
- Create: `packages/web/components/studio/importing/ImportPreviewPanel.tsx`
- Create: `packages/web/components/studio/importing/ImportModal.tsx`
- Create: `packages/i18n/messages/en/importing.json`, `de/importing.json`, `fr/importing.json`
- Modify: `packages/web/lib/i18n/request.ts` (register `"importing"` namespace)
- Test: `packages/web/components/studio/importing/ImportPreviewPanel.test.tsx`
- Test: `packages/web/components/studio/importing/ImportModal.test.tsx`

**Interfaces:**
- Consumes: `importApi` (Task 6), Radix alert-dialog (installed), `useTranslations("importing")`.
- Produces (Tasks 8-10 rely on these):
  - `<ImportPreviewPanel onSelectionChange={(selection: ImportSelection | null) => void} />`
  - `<ImportModal novelId={string} open={boolean} onOpenChange={(open: boolean) => void} />`
  - `ImportModal` clears `sessionStorage["narrare:importFailed:{novelId}"]` on success and invalidates `["novels", novelId, "chapters"]`.

- [ ] **Step 1: Create the i18n namespace (RULE-16 — same task as first use)**

```json
// packages/i18n/messages/en/importing.json
{
  "title": "Import chapters",
  "description": "Select Markdown (.md) or plain-text (.txt) files. Chapters are detected from frontmatter, headings, and chapter markers.",
  "chooseFiles": "Choose files",
  "loading": "Analyzing files…",
  "column": { "include": "Include", "title": "Chapter title", "words": "Words", "source": "File" },
  "summary": "{files} files · {chapters} chapters · {words} words",
  "confirm": "Import {count, plural, one {# chapter} other {# chapters}}",
  "importing": "Importing…",
  "cancel": "Cancel",
  "errors": {
    "previewFailed": "Could not analyze the files: {message}",
    "commitFailed": "Import failed: {message}"
  },
  "failedBanner": {
    "title": "Chapter import failed",
    "body": "Your novel was created, but the chapters could not be imported. You can retry the import here.",
    "retry": "Retry import",
    "dismiss": "Dismiss"
  }
}
```

```json
// packages/i18n/messages/de/importing.json
{
  "title": "Kapitel importieren",
  "description": "Wähle Markdown- (.md) oder Textdateien (.txt). Kapitel werden aus Frontmatter, Überschriften und Kapitel-Markierungen erkannt.",
  "chooseFiles": "Dateien auswählen",
  "loading": "Dateien werden analysiert…",
  "column": { "include": "Einbinden", "title": "Kapiteltitel", "words": "Wörter", "source": "Datei" },
  "summary": "{files} Dateien · {chapters} Kapitel · {words} Wörter",
  "confirm": "{count, plural, one {# Kapitel} other {# Kapitel}} importieren",
  "importing": "Import läuft…",
  "cancel": "Abbrechen",
  "errors": {
    "previewFailed": "Dateien konnten nicht analysiert werden: {message}",
    "commitFailed": "Import fehlgeschlagen: {message}"
  },
  "failedBanner": {
    "title": "Kapitel-Import fehlgeschlagen",
    "body": "Dein Roman wurde erstellt, aber die Kapitel konnten nicht importiert werden. Du kannst den Import hier erneut versuchen.",
    "retry": "Import erneut versuchen",
    "dismiss": "Verwerfen"
  }
}
```

```json
// packages/i18n/messages/fr/importing.json
{
  "title": "Importer des chapitres",
  "description": "Sélectionnez des fichiers Markdown (.md) ou texte (.txt). Les chapitres sont détectés à partir du frontmatter, des titres et des marqueurs de chapitre.",
  "chooseFiles": "Choisir des fichiers",
  "loading": "Analyse des fichiers…",
  "column": { "include": "Inclure", "title": "Titre du chapitre", "words": "Mots", "source": "Fichier" },
  "summary": "{files} fichiers · {chapters} chapitres · {words} mots",
  "confirm": "Importer {count, plural, one {# chapitre} other {# chapitres}}",
  "importing": "Import en cours…",
  "cancel": "Annuler",
  "errors": {
    "previewFailed": "Impossible d'analyser les fichiers : {message}",
    "commitFailed": "Échec de l'import : {message}"
  },
  "failedBanner": {
    "title": "Échec de l'import des chapitres",
    "body": "Votre roman a été créé, mais les chapitres n'ont pas pu être importés. Vous pouvez réessayer l'import ici.",
    "retry": "Réessayer l'import",
    "dismiss": "Ignorer"
  }
}
```

Register in `packages/web/lib/i18n/request.ts`: add `"importing",` to the `namespaces` array (after `"generation"`).

- [ ] **Step 2: Write the failing component tests**

```tsx
// packages/web/components/studio/importing/ImportPreviewPanel.test.tsx
/**
 * Tests for the shared import preview panel (SETUP-003 v1).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ImportPreviewPanel } from "./ImportPreviewPanel";

vi.mock("@/lib/api/client", () => ({
  importApi: {
    preview: vi.fn(),
    commit: vi.fn(),
  },
}));

import { importApi } from "@/lib/api/client";

function renderPanel(onSelectionChange: (s: unknown) => void = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ImportPreviewPanel onSelectionChange={onSelectionChange} />
    </QueryClientProvider>,
  );
}

const PREVIEW = {
  items: [
    { index: 0, suggested_title: "One", word_count: 10, source_file: "a.md" },
    { index: 1, suggested_title: "Two", word_count: 20, source_file: "a.md" },
  ],
  file_count: 1,
  chapter_count: 2,
  total_word_count: 30,
};

describe("ImportPreviewPanel", () => {
  beforeEach(() => vi.clearAllMocks());

  it("previews picked files and publishes the full selection", async () => {
    const onSelectionChange = vi.fn();
    vi.mocked(importApi.preview).mockResolvedValueOnce(PREVIEW);
    renderPanel(onSelectionChange);

    const input = screen.getByLabelText(/choose files/i) as HTMLInputElement;
    const file = new File(["# One\nbody"], "a.md", { type: "text/markdown" });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => expect(screen.getByText("a.md")).toBeInTheDocument());
    expect(onSelectionChange).toHaveBeenLastCalledWith({
      files: [file],
      excludedIndices: [],
      titleOverrides: {},
      includedCount: 2,
    });
  });

  it("excluding a chapter updates the published selection", async () => {
    const onSelectionChange = vi.fn();
    vi.mocked(importApi.preview).mockResolvedValueOnce(PREVIEW);
    renderPanel(onSelectionChange);

    const input = screen.getByLabelText(/choose files/i) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["x"], "a.md")] } });
    await waitFor(() => expect(screen.getByText("One")).toBeInTheDocument());

    fireEvent.click(screen.getAllByRole("checkbox")[1]);
    expect(onSelectionChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ excludedIndices: [1], includedCount: 1 }),
    );
  });

  it("renaming updates titleOverrides", async () => {
    const onSelectionChange = vi.fn();
    vi.mocked(importApi.preview).mockResolvedValueOnce(PREVIEW);
    renderPanel(onSelectionChange);

    const input = screen.getByLabelText(/choose files/i) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["x"], "a.md")] } });
    await waitFor(() => expect(screen.getByDisplayValue("One")).toBeInTheDocument());

    fireEvent.change(screen.getByDisplayValue("One"), { target: { value: "Renamed" } });
    expect(onSelectionChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ titleOverrides: { "0": "Renamed" } }),
    );
  });

  it("preview failure surfaces the error and publishes null", async () => {
    const onSelectionChange = vi.fn();
    vi.mocked(importApi.preview).mockRejectedValueOnce(new Error("bad UTF-8"));
    renderPanel(onSelectionChange);

    fireEvent.change(screen.getByLabelText(/choose files/i) as HTMLInputElement, {
      target: { files: [new File(["x"], "a.md")] },
    });
    await waitFor(() => expect(screen.getByText(/bad UTF-8/)).toBeInTheDocument());
    expect(onSelectionChange).toHaveBeenLastCalledWith(null);
  });
});
```

```tsx
// packages/web/components/studio/importing/ImportModal.test.tsx
/**
 * Tests for the import modal (commit + invalidation + failure retry path).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ImportModal } from "./ImportModal";

vi.mock("@/lib/api/client", () => ({
  importApi: {
    preview: vi.fn(),
    commit: vi.fn(),
  },
}));

import { importApi } from "@/lib/api/client";

function renderModal(open = true) {
  const client = new QueryClient();
  const onOpenChange = vi.fn();
  render(
    <QueryClientProvider client={client}>
      <ImportModal novelId="novel-1" open={open} onOpenChange={onOpenChange} />
    </QueryClientProvider>,
  );
  return { onOpenChange, client };
}

describe("ImportModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it("clears the failure flag and closes on successful commit", async () => {
    sessionStorage.setItem("narrare:importFailed:novel-1", "1");
    vi.mocked(importApi.commit).mockResolvedValueOnce({
      novel_id: "novel-1", created_count: 2, first_position: 0, last_position: 1, chapters: [],
    });
    const { onOpenChange } = renderModal();

    // Select a file through the embedded panel
    const input = screen.getByLabelText(/choose files/i) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["# A\nb"], "a.md")] } });

    const confirm = await screen.findByRole("button", { name: /import/i });
    fireEvent.click(confirm);

    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
    expect(sessionStorage.getItem("narrare:importFailed:novel-1")).toBeNull();
    expect(importApi.commit).toHaveBeenCalledWith(
      [expect.any(File)],
      "novel-1",
      { excluded_indices: [], title_overrides: {} },
    );
  });

  it("keeps the modal open with the error on commit failure", async () => {
    vi.mocked(importApi.commit).mockRejectedValueOnce(new Error("boom"));
    renderModal();

    const input = screen.getByLabelText(/choose files/i) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["# A\nb"], "a.md")] } });

    fireEvent.click(await screen.findByRole("button", { name: /import/i }));
    expect(await screen.findByText(/boom/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd packages/web && pnpm test -- ImportPreviewPanel ImportModal`
Expected: FAIL — modules not found

- [ ] **Step 4: Implement the components**

```tsx
// packages/web/components/studio/importing/ImportPreviewPanel.tsx
"use client";

import { useTranslations } from "next-intl";
import { useCallback, useRef, useState } from "react";
import { importApi } from "@/lib/api/client";
import type { ImportPreviewResponse, ImportSelection } from "@/types";

/**
 * Shared import surface: pick files → server preview → per-chapter title
 * edit + include/exclude. Publishes the full selection upward; performs NO
 * commit itself (the modal commits for existing novels, the wizard commits
 * at Step-5 completion) — ADR-091 / spec §6.1.
 */
interface ImportPreviewPanelProps {
  readonly onSelectionChange: (selection: ImportSelection | null) => void;
}

export function ImportPreviewPanel({ onSelectionChange }: ImportPreviewPanelProps) {
  const t = useTranslations("importing");
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [excluded, setExcluded] = useState<Set<number>>(new Set());
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const publish = useCallback(
    (nextFiles: File[], nextExcluded: Set<number>, nextOverrides: Record<string, string>, chapterCount: number) => {
      if (nextFiles.length === 0 || chapterCount === 0) {
        onSelectionChange(null);
        return;
      }
      onSelectionChange({
        files: nextFiles,
        excludedIndices: [...nextExcluded],
        titleOverrides: nextOverrides,
        includedCount: chapterCount - nextExcluded.size,
      });
    },
    [onSelectionChange],
  );

  const handleFiles = async (picked: FileList | null) => {
    if (!picked || picked.length === 0) return;
    // Deterministic order BEFORE upload — the server never re-orders (spec §5.1)
    const sorted = [...picked].sort((a, b) =>
      a.name.localeCompare(b.name, undefined, { numeric: true }),
    );
    setFiles(sorted);
    setExcluded(new Set());
    setOverrides({});
    setError(null);
    setPreview(null);
    setIsLoading(true);
    try {
      const result = await importApi.preview(sorted);
      setPreview(result);
      publish(sorted, new Set(), {}, result.chapter_count);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      onSelectionChange(null);
    } finally {
      setIsLoading(false);
    }
  };

  const toggle = (index: number) => {
    const next = new Set(excluded);
    if (next.has(index)) next.delete(index);
    else next.add(index);
    setExcluded(next);
    if (preview) publish(files, next, overrides, preview.chapter_count);
  };

  const rename = (index: number, title: string) => {
    const next = { ...overrides, [String(index)]: title };
    setOverrides(next);
    if (preview) publish(files, excluded, next, preview.chapter_count);
  };

  return (
    <div className="flex flex-col gap-3" data-testid="import-preview-panel">
      <input
        ref={inputRef}
        id="import-file-input"
        type="file"
        multiple
        accept=".md,.txt"
        aria-label={t("chooseFiles")}
        className="block w-full text-sm text-muted-foreground file:mr-3 file:rounded-md file:border-0 file:bg-primary file:px-3 file:py-1.5 file:text-sm file:text-primary-foreground"
        onChange={(e) => void handleFiles(e.target.files)}
      />

      {isLoading && <p className="text-sm text-muted-foreground animate-pulse">{t("loading")}</p>}
      {error && (
        <p className="bg-destructive/10 text-destructive rounded-lg p-3 text-sm" role="alert">
          {t("errors.previewFailed", { message: error })}
        </p>
      )}

      {preview && (
        <>
          <p className="text-xs text-muted-foreground">
            {t("summary", {
              files: preview.file_count,
              chapters: preview.chapter_count,
              words: preview.total_word_count.toLocaleString(),
            })}
          </p>
          <ul className="max-h-72 overflow-y-auto rounded-md border border-border">
            {preview.items.map((item) => (
              <li
                key={item.index}
                className="flex items-center gap-2 border-b border-border/50 px-3 py-2 last:border-b-0"
                data-testid={`import-preview-item-${item.index}`}
              >
                <input
                  type="checkbox"
                  checked={!excluded.has(item.index)}
                  onChange={() => toggle(item.index)}
                  aria-label={t("column.include")}
                  className="h-4 w-4"
                />
                <input
                  type="text"
                  value={overrides[String(item.index)] ?? item.suggested_title}
                  onChange={(e) => rename(item.index, e.target.value)}
                  aria-label={t("column.title")}
                  className="min-w-0 flex-1 rounded border border-border bg-background px-2 py-1 text-sm"
                />
                <span className="shrink-0 text-xs text-muted-foreground">
                  {t("column.words", { count: item.word_count })}
                </span>
                <span className="shrink-0 max-w-32 truncate text-xs text-muted-foreground/70" title={item.source_file}>
                  {item.source_file}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
```

```tsx
// packages/web/components/studio/importing/ImportModal.tsx
"use client";

import * as AlertDialog from "@radix-ui/react-alert-dialog";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { importApi } from "@/lib/api/client";
import type { ImportSelection } from "@/types";
import { ImportPreviewPanel } from "./ImportPreviewPanel";

/**
 * Import dialog for EXISTING novels (sidebar entry). Commit + chapters-query
 * invalidation + failure-flag cleanup live here; the panel is shared with
 * the wizard (spec §6). Alert-dialog semantics are intentional: the append
 * is irreversible (no undo).
 */
interface ImportModalProps {
  readonly novelId: string;
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
}

export function ImportModal({ novelId, open, onOpenChange }: ImportModalProps) {
  const t = useTranslations("importing");
  const queryClient = useQueryClient();
  const [selection, setSelection] = useState<ImportSelection | null>(null);
  const [isCommitting, setIsCommitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCommit = async () => {
    if (!selection || selection.includedCount === 0) return;
    setIsCommitting(true);
    setError(null);
    try {
      await importApi.commit(selection.files, novelId, {
        excluded_indices: selection.excludedIndices,
        title_overrides: selection.titleOverrides,
      });
      sessionStorage.removeItem(`narrare:importFailed:${novelId}`);
      await queryClient.invalidateQueries({ queryKey: ["novels", novelId, "chapters"] });
      onOpenChange(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setIsCommitting(false);
    }
  };

  return (
    <AlertDialog.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm" />
        <AlertDialog.Content className="fixed left-1/2 top-1/2 z-50 flex w-full max-w-xl -translate-x-1/2 -translate-y-1/2 flex-col rounded-xl border border-border bg-card p-6 shadow-2xl">
          <AlertDialog.Title className="text-lg font-medium text-foreground">{t("title")}</AlertDialog.Title>
          <AlertDialog.Description className="mt-1 text-sm text-muted-foreground">
            {t("description")}
          </AlertDialog.Description>

          <div className="mt-4">
            <ImportPreviewPanel onSelectionChange={setSelection} />
          </div>

          {error && (
            <p className="bg-destructive/10 text-destructive mt-3 rounded-lg p-3 text-sm" role="alert">
              {t("errors.commitFailed", { message: error })}
            </p>
          )}

          <div className="mt-6 flex justify-end gap-3">
            <AlertDialog.Cancel asChild>
              <button
                type="button"
                className="rounded-md bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground hover:bg-accent transition-colors"
              >
                {t("cancel")}
              </button>
            </AlertDialog.Cancel>
            <button
              type="button"
              data-testid="import-commit-btn"
              disabled={!selection || selection.includedCount === 0 || isCommitting}
              onClick={() => void handleCommit()}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {isCommitting
                ? t("importing")
                : selection
                  ? t("confirm", { count: selection.includedCount })
                  : t("confirm", { count: 0 })}
            </button>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd packages/web && pnpm test -- ImportPreviewPanel ImportModal && pnpm test -- i18n`
Expected: PASS (component tests + RULE-16 namespace registry test)

- [ ] **Step 6: Commit**

```bash
git add packages/web/components/studio/importing/ packages/i18n/messages/ packages/web/lib/i18n/request.ts
git commit -m "feat(web): shared ImportPreviewPanel + ImportModal with importing i18n namespace"
```

---

### Task 8: Sidebar "Import chapters" entry + failure banner

**Files:**
- Modify: `packages/web/components/studio/SidebarChapterList.tsx`
- Modify: `packages/i18n/messages/{en,de,fr}/studio.json` (`sidebar.importChapters` + banner keys — reuse `importing.failedBanner.*` from Task 7 for the banner text; only the action label is new)
- Test: `packages/web/components/studio/SidebarChapterList.test.tsx` (create if absent; extend if present)

**Interfaces:**
- Consumes: `ImportModal` (Task 7), `sessionStorage` key `narrare:importFailed:{novelId}` (set by Task 10's wizard path; also defensive if a commit crashes mid-modal).
- Produces: `<SidebarChapterList novelId>` renders the action + banner + modal.

- [ ] **Step 1: Write the failing test**

```tsx
// packages/web/components/studio/SidebarChapterList.test.tsx (new or extended)
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SidebarChapterList } from "./SidebarChapterList";

vi.mock("@/lib/api/client", () => ({
  chaptersApi: { list: vi.fn().mockResolvedValue([]), create: vi.fn() },
  volumesApi: { list: vi.fn().mockResolvedValue([]) },
  importApi: { preview: vi.fn(), commit: vi.fn() },
}));

function renderList() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SidebarChapterList novelId="novel-1" />
    </QueryClientProvider>,
  );
}

describe("SidebarChapterList import entry", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it("shows an import action that opens the ImportModal", async () => {
    renderList();
    const action = await screen.findByRole("button", { name: /import chapters/i });
    fireEvent.click(action);
    await waitFor(() => expect(screen.getByText(/detected from frontmatter/i)).toBeInTheDocument());
  });

  it("renders the failure banner from the sessionStorage flag", async () => {
    sessionStorage.setItem("narrare:importFailed:novel-1", "1");
    renderList();
    expect(await screen.findByText(/chapters could not be imported/i)).toBeInTheDocument();
  });

  it("dismissing clears the banner", async () => {
    sessionStorage.setItem("narrare:importFailed:novel-1", "1");
    renderList();
    fireEvent.click(await screen.findByRole("button", { name: /dismiss/i }));
    await waitFor(() =>
      expect(screen.queryByText(/chapters could not be imported/i)).not.toBeInTheDocument(),
    );
    expect(sessionStorage.getItem("narrare:importFailed:novel-1")).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && pnpm test -- SidebarChapterList`
Expected: FAIL — no import action found

- [ ] **Step 3: Implement**

In `SidebarChapterList.tsx`: add `const [importOpen, setImportOpen] = useState(false);` and `const [importFailed, setImportFailed] = useState(() => sessionStorage.getItem(\`narrare:importFailed:${novelId}\`) === "1");`. Below the "New chapter" button block add:

```tsx
{importFailed && (
  <div className="mt-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-xs" data-testid="import-failed-banner">
    <p className="font-medium text-destructive">{t("importingBanner.title")}</p>
    <p className="mt-1 text-muted-foreground">{t("importingBanner.body")}</p>
    <div className="mt-2 flex gap-2">
      <button
        type="button"
        onClick={() => setImportOpen(true)}
        className="rounded bg-primary px-2 py-1 text-primary-foreground"
      >
        {t("importingBanner.retry")}
      </button>
      <button
        type="button"
        onClick={() => {
          sessionStorage.removeItem(`narrare:importFailed:${novelId}`);
          setImportFailed(false);
        }}
      >
        {t("importingBanner.dismiss")}
      </button>
    </div>
  </div>
)}
<button
  type="button"
  data-testid="import-chapters-btn"
  onClick={() => setImportOpen(true)}
  className="mt-2 w-full rounded-md border border-border px-4 py-2 text-sm hover:bg-accent transition-colors"
>
  {t("sidebar.importChapters")}
</button>
<ImportModal novelId={novelId} open={importOpen} onOpenChange={setImportOpen} />
```

(Use the `importing.failedBanner.*` strings from Task 7 via `useTranslations("importing")` instead of duplicating — preferred: `const tImport = useTranslations("importing.failedBanner");` and drop the `importingBanner.*` studio keys. Adjust the test matchers to the chosen strings. Keep ONE copy of the banner text.)

i18n addition to `studio.json` (all three locales, inside `sidebar`): `"importChapters": "Import chapters"` / `"Kapitel importieren"` / `"Importer des chapitres"`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/web && pnpm test -- SidebarChapterList && pnpm test -- i18n`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/studio/SidebarChapterList.tsx packages/web/components/studio/SidebarChapterList.test.tsx packages/i18n/messages/
git commit -m "feat(web): sidebar Import chapters action with retry banner"
```

---

### Task 9: wizardStore selection + WizardStep2 inline import section

**Files:**
- Modify: `packages/web/lib/stores/wizardStore.ts`
- Modify: `packages/web/lib/stores/wizardStore.test.ts`
- Modify: `packages/web/components/studio/wizard/WizardStep2.tsx`
- Modify: `packages/i18n/messages/{en,de,fr}/studio.json` (update `wizard.step2.importDescription` wording)
- Test: `packages/web/components/studio/wizard/wizard.test.tsx` (Step-2 import cases)

**Interfaces:**
- Consumes: `ImportPreviewPanel` (Task 7), `ImportSelection` (Task 6).
- Produces (Task 10 relies on): `useWizardStore` gains `importSelection: ImportSelection | null` + `setImportSelection(selection)`; `reset()` clears it. `WizardStep2` renders the panel inline when the "import" starter card is selected and calls `validateStep3({ starter })` on Next.

- [ ] **Step 1: Write the failing store test (extend `wizardStore.test.ts`)**

```typescript
// append to packages/web/lib/stores/wizardStore.test.ts
describe("importSelection", () => {
  it("starts null and is settable", () => {
    useWizardStore.getState().reset();
    expect(useWizardStore.getState().importSelection).toBeNull();
    const file = new File(["# A\nb"], "a.md");
    const selection = { files: [file], excludedIndices: [], titleOverrides: {}, includedCount: 1 };
    useWizardStore.getState().setImportSelection(selection);
    expect(useWizardStore.getState().importSelection).toEqual(selection);
  });

  it("reset() clears importSelection", () => {
    useWizardStore.getState().setImportSelection({
      files: [], excludedIndices: [], titleOverrides: {}, includedCount: 0,
    });
    useWizardStore.getState().reset();
    expect(useWizardStore.getState().importSelection).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && pnpm test -- wizardStore`
Expected: FAIL — no `importSelection` on the store

- [ ] **Step 3: Implement store + step**

`wizardStore.ts`: import `type { ImportSelection } from "@/types"`; add to the interface `importSelection: ImportSelection | null;` + `setImportSelection: (selection: ImportSelection | null) => void;`; add initial state `importSelection: null,`; implementation `setImportSelection: (selection) => set({ importSelection: selection }),`; extend `reset` to `set({ currentStep: 1, state: { ...defaultState }, importSelection: null })`.

`WizardStep2.tsx`: re-add the import `StarterCard` (title `t("wizard.step2.import")`) and below the cards:

```tsx
{selected === "import" && (
  <div className="rounded-lg border border-border bg-background/50 p-4" data-testid="wizard-import-section">
    <ImportPreviewPanel onSelectionChange={setImportSelection} />
  </div>
)}
```

with `const setImportSelection = useWizardStore((s) => s.setImportSelection);` and `import { ImportPreviewPanel } from "@/components/studio/importing/ImportPreviewPanel";`. `handleNext` calls `setupApi.validateStep3({ starter: selected })` then `updateStep3({ starter: selected })` (no import_path — removed in Task 5). Update `wizard.step2.importDescription` in all locales to: "Upload Markdown (.md) or text (.txt) files from your computer — chapters are detected automatically" (DE/FR equivalents).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/web && pnpm test -- wizard && pnpm type-check`
Expected: PASS — including a new Step-2 test asserting that selecting the import card renders the panel (add it to `wizard.test.tsx` mirroring the Task 7 panel mocks: mock `@/lib/api/client`'s `importApi.preview`).

- [ ] **Step 5: Commit**

```bash
git add packages/web/lib/stores/wizardStore.ts packages/web/lib/stores/wizardStore.test.ts packages/web/components/studio/wizard/ packages/i18n/messages/
git commit -m "feat(web): wizard Step 2 inline import section with store-held selection"
```

---

### Task 10: Wizard completion sequence + Step 5 summary

**Files:**
- Modify: `packages/web/components/studio/wizard/WizardShell.tsx` (`handleComplete`)
- Modify: `packages/web/components/studio/wizard/WizardStep5.tsx` (import summary row)
- Modify: `packages/i18n/messages/{en,de,fr}/studio.json` (`wizard.step5.importSummary`)
- Test: `packages/web/components/studio/wizard/wizard.test.tsx` (completion cases)

**Interfaces:**
- Consumes: `importApi.commit` (Task 6), `useWizardStore().importSelection` (Task 9), failure key `narrare:importFailed:{novel_id}` (Task 8 banner).
- Produces: complete → (import?) commit → reset → navigate; failure degrades to banner path (spec §6.3).

- [ ] **Step 1: Write the failing tests (append to `wizard.test.tsx` `WizardStep5`/shell describes)**

```typescript
// Step-5 summary shows file/chapter counts from the store selection
it("shows import summary counts when starter is import", () => {
  useWizardStore.setState({
    state: { ...useWizardStore.getState().state, starter: "import" },
    importSelection: { files: [new File(["x"], "a.md"), new File(["x"], "b.md")], excludedIndices: [1], titleOverrides: {}, includedCount: 2 },
  });
  renderWithProviders(<WizardStep5 onComplete={vi.fn()} onBack={vi.fn()} />);
  expect(screen.getByText(/2 files/i)).toBeInTheDocument();
  expect(screen.getByText(/2 chapters/i)).toBeInTheDocument();
});

// Shell completion: novel created, then commit called with the new novel_id
it("commits the import after setup completion", async () => {
  const file = new File(["# A\nb"], "a.md");
  useWizardStore.setState({
    state: { ...useWizardStore.getState().state, starter: "import" },
    importSelection: { files: [file], excludedIndices: [], titleOverrides: {}, includedCount: 1 },
  });
  setupApi.complete = vi.fn().mockResolvedValue({ novel_id: "novel-9", redirect_to: "/dashboard", message: "" });
  importApi.commit = vi.fn().mockResolvedValue({ novel_id: "novel-9", created_count: 1, first_position: 0, last_position: 0, chapters: [] });
  // ...render shell, drive to step 5, click complete (mirror existing completion tests)
  await waitFor(() => expect(importApi.commit).toHaveBeenCalledWith([file], "novel-9", { excluded_indices: [], title_overrides: {} }));
});

// Degrade path: commit failure sets the flag and still navigates
it("sets importFailed flag and navigates when commit fails", async () => {
  useWizardStore.setState({
    state: { ...useWizardStore.getState().state, starter: "import" },
    importSelection: { files: [new File(["x"], "a.md")], excludedIndices: [], titleOverrides: {}, includedCount: 1 },
  });
  setupApi.complete = vi.fn().mockResolvedValue({ novel_id: "novel-9", redirect_to: "/dashboard", message: "" });
  importApi.commit = vi.fn().mockRejectedValue(new Error("boom"));
  // ...drive completion
  await waitFor(() => expect(sessionStorage.getItem("narrare:importFailed:novel-9")).toBe("1"));
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/web && pnpm test -- wizard`
Expected: FAIL

- [ ] **Step 3: Implement**

`WizardShell.tsx` `handleComplete` becomes:

```tsx
const handleComplete = async () => {
  // Capture BEFORE reset() clears the store (spec §6.3 — order matters)
  const currentState = useWizardStore.getState().state;
  const importSelection = useWizardStore.getState().importSelection;
  if (hasProviders) {
    useWizardStore.setState({ state: { ...currentState, skip_provider: true } });
  }
  const { state: updatedState } = useWizardStore.getState();
  const result = await setupApi.complete(updatedState);

  // starter="import": the backend created an EMPTY novel — commit the files now
  if (updatedState.starter === "import" && importSelection) {
    try {
      await importApi.commit(importSelection.files, result.novel_id, {
        excluded_indices: importSelection.excludedIndices,
        title_overrides: importSelection.titleOverrides,
      });
    } catch {
      // Documented degrade path (ADR-091): user lands in the empty novel,
      // the sidebar banner offers a retry via the ImportModal.
      sessionStorage.setItem(`narrare:importFailed:${result.novel_id}`, "1");
    }
  }

  reset();
  router.push(`/novel/${result.novel_id}` as Parameters<typeof router.push>[0]);
};
```

(`import { importApi } from "@/lib/api/client";` — extend the existing mock surface in tests.)

`WizardStep5.tsx`: add `const importSelection = useWizardStore((s) => s.importSelection);` and restore an import entry in `starterLabel`:

```tsx
import: state.starter === "import" && importSelection
  ? t("wizard.step5.importSummary", {
      files: importSelection.files.length,
      chapters: importSelection.includedCount,
    })
  : t("wizard.step2.import"),
```

i18n `studio.json` → `wizard.step5.importSummary`: `"{files} files · {chapters} chapters"` / `"{files} Dateien · {chapters} Kapitel"` / `"{files} fichiers · {chapters} chapitres"`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/web && pnpm test -- wizard && pnpm type-check`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/studio/wizard/ packages/i18n/messages/
git commit -m "feat(web): wizard completion commits import after novel creation (degrade path documented)"
```

---

### Task 11: Docs closure + full verification gate

**Files:**
- Modify: `docs/features/INDEX.md` (SETUP-003 row → ✅; extend the 2026-10-02 note with the shipped scope)
- Modify: `docs/features/setup/SETUP-003-import.md` (frontmatter `status: stable`; Status section history row)
- Modify: `docs/architecture/decisions/INDEX.md` (ADR-091 status → ✅ Implemented)
- Modify: `docs/_shared/CURRENT_STATE.md` (new dated entry following the established format: scope, ADR/spec/plan links, verification evidence)
- No CHANGELOG hand-edit — release-please generates it from the conventional commits above.

- [ ] **Step 1: Update the four docs files** (content per above; CURRENT_STATE entry summarizes: ADR-091 implemented, module pair, two-phase API, removal slice, guardrails, proxy-verification result from Task 2 Step 6, test counts).

- [ ] **Step 2: Run the full gate**

Run: `just verify`
Expected: `check` (run_checks.py incl. architecture + type gates) + all backend tests + all frontend tests green; zero new `# type: ignore` (RULE-23 ratchet); no RULE-04 file-size violations in the new modules.

- [ ] **Step 3: Final sweep**

Run: `grep -rn "import_path" apps/ packages/ tests/ | grep -v "\.md\|plans\|specs"`
Expected: no matches (docs references only).

- [ ] **Step 4: Commit**

```bash
git add docs/features/INDEX.md docs/features/setup/SETUP-003-import.md docs/architecture/decisions/INDEX.md docs/_shared/CURRENT_STATE.md
git commit -m "docs: SETUP-003 Project Import v1 shipped (ADR-091 implemented)"
```

---

## Self-Review (executed by the plan author)

1. **Spec coverage:** formats MD+TXT (T1), guardrails incl. encoding + zero-chapters (T2), preview (T2), deterministic re-parse + adjustments + ownership + atomic append (T3), import_path removal BE/FE (T4/T5), multipart client + RULE-17 types (T6), shared panel/modal + i18n namespace (T7), sidebar entry + banner (T8), wizard inline section + store (T9), completion sequence + Step-5 summary + degrade path (T10), docs (T11) + my ADR/spec/feature updates. Gap check: proxy verification (T2 Step 6) covers spec §7 R1. ✔
2. **Placeholder scan:** the two conditional notes (FastAPI Form-Pydantic variant; `second_user_id` fixture derivation) name exact fallbacks with sources to check — not "TBD"s. ✔
3. **Type consistency:** `DetectedChapter` fields (T1) ↔ repository/service (T3) ✔; `ImportPreviewItem`/`ImportCommit*` JSON names (T2) ↔ `types/importing.ts` (T6) ✔; `ImportSelection` (T6) ↔ panel publish (T7) ↔ store (T9) ↔ completion (T10) ✔; failure key `narrare:importFailed:{id}` (T7 modal clear ↔ T8 banner ↔ T10 set) ✔.
