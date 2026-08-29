# Scratchpad (NOTES-001) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Scratchpad — a low-friction, novel-independent place to capture, curate, search, and discuss notes (NOTES-001), per the approved spec `docs/superpowers/specs/2026-08-21-scratchpad-design.md`.

**Architecture:** Dedicated `notes` domain module following the house pattern (core pure types/contracts → API contracts → schemas → models → repository → service → router), reusing the existing embedding infrastructure (`source_type="note"`, ADR-080 in-process dispatch, RULE-11 lexical fallback) and the CHAT-001 pipeline (note injected as runtime context; `ChatRequest.project_id` becomes optional — the only touch of existing behavior). Frontend: `/scratchpad` page + global quick-capture panel, TanStack Query hooks, existing `markdownToHtml` preview.

**Tech Stack:** Python 3.14 · FastAPI · SQLAlchemy 2.0 async · Alembic · PostgreSQL (TEXT[] + GIN) · Next.js 16 · React 19 · TanStack Query v5 · next-intl · Motion · Vitest/MSW · pytest.

---

## Global Constraints

- **Project language: English.** All code, comments, docstrings, tests, and docs in English. Exception: `packages/i18n/messages/{en,de,fr}/*.json` carry locale content.
- **RULE-01b:** No direct `import openai` / LLM clients outside `core/llm/`; embedding calls go through `narrare_core.llm.embeddings.embed_texts`.
- **RULE-02:** No prompt construction in services. The note context block is **runtime input** (user-message channel, same category as `format_history` in `narrare_core.chat.chat_service_core`), never a system/task template.
- **RULE-03:** Contract (Protocol) first — every task that adds a service/repository also adds/updates `contracts.py`.
- **RULE-04/06:** One responsibility per file; router delegates immediately; service >300 lines → split files; router >150 lines → split.
- **RULE-11:** No silent failures — log + degrade gracefully (semantic search falls back to lexical; embedding dispatch failures never block saves; missing attached note → warn + proceed).
- **RULE-14:** Model change and its Alembic migration land in the SAME task; migrations are atomic up/down pairs.
- **No `git commit --no-verify` / `-n`. Ever.** Commits use conventional messages (`feat(notes): …`, `test(chat): …`, `feat(web): …`).
- **Coverage targets:** `core/` ≥90%, `apps/api` services ≥85% / repositories ≥80% / routers ≥80%.
- **Backend test commands** (repo root): `uv run pytest tests/unit/... -v` (fast, no DB) · integration: `uv run pytest tests/integration/<file> -v` (needs the test DB on :5433; `just test` wires it).
- **Frontend test command:** `pnpm --filter narrare-web test <path-relative-to-packages/web>` · type-check: `pnpm --filter narrare-web type-check`.
- **Task size cap:** each task changes ≤3 substantive files (≤250 new LOC). Empty `__init__.py` package markers required by the pytest layout are scaffolding and do not count against the cap (flagged where they occur).
- **Do NOT invent APIs:** every symbol referenced below exists in the repo or is defined in an earlier task's Interfaces block.
- **⚠️ Frontend UI tasks (Tasks 21–23 and 25–29) carry a hard PO requirement:** the implementer MUST load the `frontend-design` skill (superpowers) BEFORE writing any UI code (spec §7, PO session 2026-08-21).
- **Gates before done:** `just verify` green, `uv run python scripts/check_architecture.py` green, i18n validation green.

### Decisions locked in this plan (the spec delegated them to the plan)

| Decision | Value | Reason |
|---|---|---|
| Quick-capture shortcut | **Ctrl/⌘+Shift+U** (match `(event.metaKey \|\| event.ctrlKey) && event.shiftKey && event.key === "U"`) | Collision audit over `packages/web`: existing bindings are Ctrl/⌘+K (command palette, `useEditorCommandPalette.ts:96`), Ctrl/⌘+S (save, `:100`), Ctrl/⌘+Enter (AI submit, `ai-action-shortcuts.ts:9`); `Shift+U` is unused anywhere. **Ctrl/⌘+Shift+N was rejected** — Chrome reserves it for the incognito window, so the page never receives the keydown. |
| Markdown preview | Reuse `markdownToHtml(md)` from `packages/web/lib/utils.ts:74` | Already vendored + tested (`utils.test.ts`); no `marked`/`react-markdown`/`markdown-it` in `package.json` — adding one would need an ADR. |
| Chat surface for global notes | `ChatPanel` gains `projectId: string \| null` + optional `noteId`/`banner` props; a `NotesChatDrawer` slide-over hosts it on `/scratchpad` | The existing chat surface is per-novel (`/novel/[id]/chat` → `ChatPanel projectId={id}`); global notes need a project-less surface without a new global route. |
| `ChatRequest.project_id` optionalization | DB migration `0042` makes `chat_conversations.project_id` nullable | The column is `NOT NULL` today (`0025_create_chat_tables.py`, `chat/models.py:33`); the API change alone would 500 on project-less conversations. |
| Note `title` storage | Store the user-supplied title verbatim (NULL when absent); display title resolved at the boundary via `effective_title()` (core, T1) / `noteDisplayTitle()` (web, T17) | Avoids an "explicit vs derived title" flag column; matches spec §4 ("empty → fallback: first content line"). |
| Missing/unowned `note_id` in chat | Log warning, proceed WITHOUT the note (no 500 mid-conversation) | RULE-11 graceful degradation; the note may have been deleted between page load and send. |
| Tag limits | Pydantic: ≤10 tags, ≤32 chars each (422 on violation); core `normalize_tags` dedupes/case-folds/clips defensively | Honest API errors; quick capture stays fast. |
| Invocation enrichment without project | When `project_id is None`, `_stream_agent_response` passes `invocation_pipeline=None` (documented no-op path) | `compose_chat_invocation` correlates evidence by project; without a project there is nothing to correlate. The no-op path is explicitly backward compatible per its docstring. |
| Search candidate prefilter | Filtered candidate ids (cap 500) → vector search with `source_type="note"` + `source_ids` | Uses the existing `EmbeddingRepository.search(source_ids=…)` parameter; keeps filter semantics identical between lexical and semantic modes. |

---

## File Map (what gets created/modified)

```
packages/core/narrare_core/notes/            T1–T2   types.py, contracts.py, __init__.py
apps/api/narrare/notes/                     T3–T11  models.py, schemas.py, contracts.py,
                                                    repository.py, service.py,
                                                    embedding_dispatch.py, dependencies.py,
                                                    search_service.py, router.py
apps/api/alembic/versions/0041_notes.py     T3      notes table (scope CHECK, GIN tags)
apps/api/alembic/versions/0042_chat_project_optional.py  T12
apps/api/narrare/chat/                      T12–T16 models.py, schemas.py, router.py,
                                                    conversation_store.py, chat_service.py,
                                                    dependencies.py
packages/core/narrare_core/chat/            T13     contracts.py, conversation_store.py
apps/api/narrare/_app/main.py               T9      notes router registration
packages/web/types/notes.ts (+index.ts)     T17
packages/web/lib/api/notes.ts               T17
packages/web/lib/hooks/notesKeys.ts, useNotes.ts  T18
packages/i18n/messages/{en,de,fr}/notes.json T19
packages/web/lib/i18n/request.ts            T20     namespace registry
packages/web/components/notes/              T21–T28 NoteFilterBar, NoteList, TagInput,
                                                    NoteEditor, NotesChatDrawer,
                                                    ScratchpadWorkspace, QuickCapturePanel,
                                                    QuickCaptureProvider (+ __tests__)
packages/web/lib/api/chat.ts                T24     project_id/note_id optional
packages/web/lib/hooks/useChat.ts           T24
packages/web/components/studio/editor/ChatPanel.tsx  T25
packages/web/app/(studio)/scratchpad/page.tsx       T26
packages/web/components/studio/Sidebar.tsx           T27, T29
packages/web/components/studio/shell/StudioWorkspaceShell.tsx  T29
docs/features/notes/NOTES-001-scratchpad.md T30     + docs/features/INDEX.md
tests/unit/core/notes/                      T1–T2
tests/integration/test_migration_0041_round_trip.py  T4
tests/unit/api/notes/                       T5–T8, T10
tests/fakes/fake_notes_repository.py         T7
tests/integration/test_notes_api.py         T9, T11
tests/integration/test_migration_0042_round_trip.py  T12
tests/unit/api/chat/                        T13–T16 (extend + new files)
packages/web/**/__tests__/                  T18, T20–T29
```

Execution order is strictly top-to-bottom (each task consumes earlier Interfaces).

---

### Task 1: Core — note types, tag normalization, fallback title

**Spec slice:** §9.1 (Core) · §4 (core half).

**Files:**
- Create: `packages/core/narrare_core/notes/types.py`
- Create: `packages/core/narrare_core/notes/__init__.py`
- Create: `packages/core/narrare_core/notes/py.typed` (empty marker — scaffolding)
- Test: `tests/unit/core/notes/test_types.py` (+ empty `tests/unit/core/notes/__init__.py` — scaffolding)

**Interfaces:**
- Consumes: nothing (pure module).
- Produces (used by T2, T5, T7, T10, T15):
  - `class NoteType(str, Enum)` with `IDEA="idea"`, `CONCEPT="concept"`, `QUESTION="question"`, `OTHER="other"`
  - `MAX_TAGS_PER_NOTE: int = 10`, `MAX_TAG_LENGTH: int = 32`, `FALLBACK_TITLE_MAX_LENGTH: int = 200`
  - `def normalize_tag(tag: str) -> str`
  - `def normalize_tags(tags: list[str]) -> list[str]`
  - `def fallback_title(content: str) -> str`
  - `def effective_title(title: str | None, content: str) -> str`
  - `class ScopeError(ValueError)` and `def validate_scope(novel_id: UUID | None, series_id: UUID | None) -> None`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/core/notes/test_types.py
"""Unit tests for narrare_core.notes.types — pure rules, no I/O (NOTES-001 §4)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare_core.notes.types import (
    MAX_TAG_LENGTH,
    MAX_TAGS_PER_NOTE,
    NoteType,
    ScopeError,
    effective_title,
    fallback_title,
    normalize_tag,
    normalize_tags,
    validate_scope,
)


class TestNoteType:
    def test_note_type_keys_are_language_neutral(self) -> None:
        assert {t.value for t in NoteType} == {"idea", "concept", "question", "other"}

    def test_note_type_is_str_enum(self) -> None:
        assert NoteType.IDEA == "idea"
        assert isinstance(NoteType.OTHER, str)


class TestNormalizeTag:
    def test_lowercases_trims_and_collapses_whitespace(self) -> None:
        assert normalize_tag("  Plot   TWIST ") == "plot twist"

    def test_empty_tag_normalizes_to_empty(self) -> None:
        assert normalize_tag("   ") == ""


class TestNormalizeTags:
    def test_dedupes_case_insensitively_keeping_first_order(self) -> None:
        assert normalize_tags(["Plot", "plot", "  PLOT ", "world"]) == ["plot", "world"]

    def test_drops_empty_entries(self) -> None:
        assert normalize_tags(["", "   ", "real"]) == ["real"]

    def test_caps_tag_count_at_max(self) -> None:
        result = normalize_tags([f"t{i}" for i in range(MAX_TAGS_PER_NOTE + 5)])
        assert len(result) == MAX_TAGS_PER_NOTE
        assert result == [f"t{i}" for i in range(MAX_TAGS_PER_NOTE)]

    def test_clips_each_tag_to_max_length(self) -> None:
        assert len(normalize_tags(["x" * 100])[0]) == MAX_TAG_LENGTH


class TestFallbackTitle:
    def test_uses_first_non_empty_line(self) -> None:
        assert fallback_title("\n\n  Twist: the aunt did it\nsecond line") == "Twist: the aunt did it"

    def test_clips_to_max_length(self) -> None:
        assert len(fallback_title("x" * 500)) == 200

    def test_returns_empty_for_blank_content(self) -> None:
        assert fallback_title(" \n \n") == ""


class TestEffectiveTitle:
    def test_prefers_explicit_title(self) -> None:
        assert effective_title("  Named  ", "first line") == "Named"

    def test_blank_title_falls_back_to_content(self) -> None:
        assert effective_title("   ", "first line") == "first line"

    def test_none_title_falls_back_to_content(self) -> None:
        assert effective_title(None, "first line") == "first line"


class TestValidateScope:
    def test_both_none_is_global_and_valid(self) -> None:
        validate_scope(None, None)  # must not raise

    def test_one_link_is_valid(self) -> None:
        validate_scope(uuid4(), None)  # must not raise
        validate_scope(None, uuid4())  # must not raise

    def test_both_links_raise_scope_error(self) -> None:
        with pytest.raises(ScopeError, match="not both"):
            validate_scope(uuid4(), uuid4())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/core/notes/test_types.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'narrare_core.notes'`

- [ ] **Step 3: Write the implementation**

```python
# packages/core/narrare_core/notes/types.py
"""Scratchpad notes — pure value types and normalization rules (NOTES-001).

Language-neutral note-type keys; display names come from the ``notes.type.*``
i18n namespace (en/de/fr). Pure module: no I/O, no frameworks, no DB.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

#: Hard limits from the spec (§4): max 10 tags × 32 chars per tag.
MAX_TAGS_PER_NOTE = 10
MAX_TAG_LENGTH = 32
#: Clip length for the derived fallback title.
FALLBACK_TITLE_MAX_LENGTH = 200

_WHITESPACE_RE = re.compile(r"\s+")


class NoteType(str, Enum):
    """Language-neutral note type keys — displayed via i18n ``notes.type.*``."""

    IDEA = "idea"
    CONCEPT = "concept"
    QUESTION = "question"
    OTHER = "other"


class ScopeError(ValueError):
    """A note cannot link to both a novel and a series (spec §4 invariant)."""


def validate_scope(novel_id: UUID | None, series_id: UUID | None) -> None:
    """Enforce the scope invariant: at most ONE of novel/series link set.

    Both ``None`` (a global note) is the normal case and always valid.
    """
    if novel_id is not None and series_id is not None:
        raise ScopeError("A note can link to a novel or a series, not both.")


def normalize_tag(tag: str) -> str:
    """Normalize a single tag: trim, lowercase, collapse inner whitespace."""
    return _WHITESPACE_RE.sub(" ", tag.strip()).lower()


def normalize_tags(tags: list[str]) -> list[str]:
    """Normalize a tag list.

    Per tag: :func:`normalize_tag` + clip to ``MAX_TAG_LENGTH``; empty results
    are dropped. Across tags: dedupe case-insensitively (first occurrence
    wins, order preserved) and cap the list at ``MAX_TAGS_PER_NOTE``.
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in tags:
        tag = normalize_tag(raw)[:MAX_TAG_LENGTH]
        if not tag or tag in seen:
            continue
        seen.add(tag)
        ordered.append(tag)
        if len(ordered) == MAX_TAGS_PER_NOTE:
            break
    return ordered


def fallback_title(content: str) -> str:
    """First non-empty content line, clipped — the title when none is given."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:FALLBACK_TITLE_MAX_LENGTH]
    return ""


def effective_title(title: str | None, content: str) -> str:
    """The display title: the given (non-blank) title, or the content fallback."""
    if title is not None and title.strip():
        return title.strip()
    return fallback_title(content)
```

```python
# packages/core/narrare_core/notes/__init__.py
"""Scratchpad notes core module (NOTES-001) — pure types and contracts."""

from narrare_core.notes.types import (
    FALLBACK_TITLE_MAX_LENGTH,
    MAX_TAG_LENGTH,
    MAX_TAGS_PER_NOTE,
    NoteType,
    ScopeError,
    effective_title,
    fallback_title,
    normalize_tag,
    normalize_tags,
    validate_scope,
)

__all__ = [
    "FALLBACK_TITLE_MAX_LENGTH",
    "MAX_TAG_LENGTH",
    "MAX_TAGS_PER_NOTE",
    "NoteType",
    "ScopeError",
    "effective_title",
    "fallback_title",
    "normalize_tag",
    "normalize_tags",
    "validate_scope",
]
```

Also create the empty marker files `packages/core/narrare_core/notes/py.typed` and `tests/unit/core/notes/__init__.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/core/notes/test_types.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add packages/core/narrare_core/notes/ tests/unit/core/notes/
git commit -m "feat(notes): add core note types, tag normalization, and fallback title (NOTES-001)"
```

---

### Task 2: Core — note contracts (snapshot, lookup protocol, context block)

**Spec slice:** §9.1 (Core) · §6b (chat loads the note "via the notes contract").

**Files:**
- Create: `packages/core/narrare_core/notes/contracts.py`
- Modify: `packages/core/narrare_core/notes/__init__.py` (add exports)
- Test: `tests/unit/core/notes/test_contracts.py`

**Interfaces:**
- Consumes: `effective_title` (T1).
- Produces (used by T7, T16):
  - `@dataclass(slots=True) class NoteSnapshot` — fields `id: UUID`, `title: str`, `content: str`, `note_type: str`, `tags: list[str]`; property `display_title: str`
  - `@runtime_checkable class NoteLookupProtocol(Protocol)` — `async def get_note_snapshot(self, note_id: UUID, user_id: UUID) -> NoteSnapshot | None`
  - `def format_note_context_block(note: NoteSnapshot) -> str`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/core/notes/test_contracts.py
"""Unit tests for narrare_core.notes.contracts (NOTES-001)."""

from __future__ import annotations

from uuid import uuid4

from narrare_core.notes.contracts import (
    NoteLookupProtocol,
    NoteSnapshot,
    format_note_context_block,
)


def _make_note(**overrides: object) -> NoteSnapshot:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "title": "Twist idea",
        "content": "The aunt is the culprit.",
        "note_type": "idea",
        "tags": ["plot"],
    }
    return NoteSnapshot(**{**defaults, **overrides})  # type: ignore[arg-type]


class TestNoteSnapshot:
    def test_display_title_uses_title_when_present(self) -> None:
        assert _make_note().display_title == "Twist idea"

    def test_display_title_falls_back_to_content(self) -> None:
        note = _make_note(title=None, content="First line of the note")
        assert note.display_title == "First line of the note"


class TestNoteLookupProtocol:
    def test_runtime_protocol_accepts_matching_shape(self) -> None:
        class _Stub:
            async def get_note_snapshot(self, note_id: object, user_id: object) -> None:
                return None

        assert isinstance(_Stub(), NoteLookupProtocol)


class TestFormatNoteContextBlock:
    def test_includes_type_tag_title_and_content(self) -> None:
        block = format_note_context_block(_make_note())
        assert block.startswith("[Note — idea [plot]]")
        assert "Twist idea" in block
        assert "The aunt is the culprit." in block

    def test_omits_empty_tag_bracket(self) -> None:
        assert format_note_context_block(_make_note(tags=[])).startswith("[Note — idea]")

    def test_uses_display_title_fallback(self) -> None:
        note = _make_note(title=None, content="Derived title line\nbody")
        assert "Derived title line" in format_note_context_block(note)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/core/notes/test_contracts.py -v`
Expected: FAIL — `ImportError: cannot import name 'NoteSnapshot'`

- [ ] **Step 3: Write the implementation**

```python
# packages/core/narrare_core/notes/contracts.py
"""Notes contracts — pure data + protocols (RULE-03, NOTES-001).

``NoteSnapshot`` is the value object other modules (chat) consume; the API
module's NoteService implements :class:`NoteLookupProtocol`. This keeps
cross-module access on contracts, never on repositories (spec §6b).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from narrare_core.notes.types import effective_title

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(slots=True)
class NoteSnapshot:
    """Pure note snapshot for cross-module consumption (e.g. chat context)."""

    id: UUID
    title: str
    content: str
    note_type: str
    tags: list[str] = field(default_factory=list)

    @property
    def display_title(self) -> str:
        """Stored title, or the content-derived fallback."""
        return effective_title(self.title, self.content)


@runtime_checkable
class NoteLookupProtocol(Protocol):
    """Async note lookup by id + owner — implemented by the API notes service."""

    async def get_note_snapshot(self, note_id: UUID, user_id: UUID) -> NoteSnapshot | None: ...


def format_note_context_block(note: NoteSnapshot) -> str:
    """Serialize a note as a runtime context block for chat injection.

    RULE-02 note: this is data serialization of RUNTIME INPUT — the same
    category as ``format_history`` in ``narrare_core.chat.chat_service_core``.
    The block travels in the user-message channel; it is never a system or
    task template and contains no instructions.
    """
    tags = f" [{', '.join(note.tags)}]" if note.tags else ""
    header = f"[Note — {note.note_type}{tags}]"
    return "\n".join([header, note.display_title, "", note.content])
```

Extend `packages/core/narrare_core/notes/__init__.py`: add to the imports

```python
from narrare_core.notes.contracts import (
    NoteLookupProtocol,
    NoteSnapshot,
    format_note_context_block,
)
```

and the three names to `__all__`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/core/notes/ -v`
Expected: PASS (types + contracts)

- [ ] **Step 5: Commit**

```bash
git add packages/core/narrare_core/notes/ tests/unit/core/notes/test_contracts.py
git commit -m "feat(notes): add core note snapshot contract and chat context block formatter"
```

---

### Task 3: DB — `notes` ORM model + Alembic migration 0041

**Spec slice:** §9.2 (DB) · §4 (table `notes`).

**Files:**
- Create: `apps/api/narrare/notes/__init__.py` (empty package marker — scaffolding)
- Create: `apps/api/narrare/notes/models.py`
- Create: `apps/api/alembic/versions/0041_notes.py`

**Interfaces:**
- Consumes: `narrare._app.database.Base` (existing); FK targets `novels.id` / `series.id` (existing tables).
- Produces (used by T6, T7, T9): `class Note(Base)` with `__tablename__ = "notes"` and columns `id, user_id, title, content, note_type, tags, novel_id, series_id, created_at, updated_at`; constraints `ck_notes_scope_invariant`, `ck_notes_note_type`; indexes `ix_notes_tags` (GIN), `ix_notes_user_updated`.

- [ ] **Step 1: Write the ORM model**

```python
# apps/api/narrare/notes/models.py
"""Note SQLAlchemy model — NOTES-001 Scratchpad.

Mirrors migration 0041_notes (RULE-14: model + migration land together).
A note is global by default; optionally linked to ONE novel OR ONE series
(never both — ``ck_notes_scope_invariant``). Links are ON DELETE SET NULL:
the note outlives the linked entity (spec §4).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from narrare._app.database import Base


class Note(Base):
    """A scratchpad note (markdown text + type + free tags)."""

    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Ownership follows the Series pattern: plain UUID column + index, no FK.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    note_type: Mapped[str] = mapped_column(
        Text, nullable=False, default="idea", server_default=text("'idea'")
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    novel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("novels.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("series.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        # Scope invariant — mirrors ck_kb_entries_scope_invariant (0037), but
        # with deliberately different semantics: both NULL = GLOBAL note,
        # the normal case (spec §4).
        CheckConstraint(
            "NOT (novel_id IS NOT NULL AND series_id IS NOT NULL)",
            name="ck_notes_scope_invariant",
        ),
        CheckConstraint(
            "note_type IN ('idea', 'concept', 'question', 'other')",
            name="ck_notes_note_type",
        ),
        # Tag autocomplete prefix filters + containment lookups.
        Index("ix_notes_tags", "tags", postgresql_using="gin"),
        Index("ix_notes_user_updated", "user_id", "updated_at"),
    )

    def __repr__(self) -> str:
        return f"Note(id={self.id}, note_type={self.note_type!r})"
```

- [ ] **Step 2: Write the migration (atomic up/down, RULE-14)**

```python
# apps/api/alembic/versions/0041_notes.py
"""notes table (NOTES-001 Scratchpad).

Creates the novel-independent scratchpad: markdown content, language-neutral
type key, free-form TEXT[] tags (GIN-indexed for autocomplete/containment),
and OPTIONAL single links to a novel OR a series — never both
(``ck_notes_scope_invariant``, the ADR-075-style scope pattern with
deliberately different NULL semantics: both NULL = global note, the normal
case). Links are ``ON DELETE SET NULL`` — the note outlives the entity.

RULE-14: lands in the SAME task batch as the ``Note`` model. The
upgrade/downgrade pair is atomic: one create_table (+ indexes) vs
drop_index×5 + drop_table — symmetric by construction.

See:
    docs/superpowers/specs/2026-08-21-scratchpad-design.md §4.
    0037_series_foundation — the scope-invariant CHECK pattern mirrored here.
    0040_series_drift_results — the migration file layout mirrored here.

Revision ID: 0041_notes
Revises: 0040_series_drift_results
Create Date: 2026-08-21 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0041_notes"
down_revision: str | None = "0040_series_drift_results"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── notes table (global scratchpad, optional single scope link) ────────
    op.create_table(
        "notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("note_type", sa.Text(), nullable=False, server_default=sa.text("'idea'")),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "novel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("novels.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "series_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("series.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "NOT (novel_id IS NOT NULL AND series_id IS NOT NULL)",
            name="ck_notes_scope_invariant",
        ),
        sa.CheckConstraint(
            "note_type IN ('idea', 'concept', 'question', 'other')",
            name="ck_notes_note_type",
        ),
    )
    op.create_index("ix_notes_user_id", "notes", ["user_id"])
    op.create_index("ix_notes_novel_id", "notes", ["novel_id"])
    op.create_index("ix_notes_series_id", "notes", ["series_id"])
    op.create_index("ix_notes_tags", "notes", ["tags"], postgresql_using="gin")
    op.create_index("ix_notes_user_updated", "notes", ["user_id", "updated_at"])


def downgrade() -> None:
    # Reverse of upgrade(): drop indexes then the table. A downgrade is an
    # explicit user action that removes the feature (spec §4 note).
    op.drop_index("ix_notes_user_updated", table_name="notes")
    op.drop_index("ix_notes_tags", table_name="notes")
    op.drop_index("ix_notes_series_id", table_name="notes")
    op.drop_index("ix_notes_novel_id", table_name="notes")
    op.drop_index("ix_notes_user_id", table_name="notes")
    op.drop_table("notes")
```

- [ ] **Step 3: Verify the model imports cleanly**

Run: `uv run python -c "from narrare.notes.models import Note; print(Note.__tablename__)"`
Expected: prints `notes` (run from repo root; `apps/api` is on `pythonpath` via pyproject).

- [ ] **Step 4: Commit**

```bash
git add apps/api/narrare/notes/__init__.py apps/api/narrare/notes/models.py apps/api/alembic/versions/0041_notes.py
git commit -m "feat(notes): add notes table model and Alembic migration 0041 (scope CHECK, GIN tags)"
```

---

### Task 4: Integration — migration 0041 round-trip test

**Spec slice:** §9.2 · §8 ("Alembic 0041 roundtrip (up/down; CHECK constraint present — RULE-14 pattern)").

**Files:**
- Test: `tests/integration/test_migration_0041_round_trip.py`

**Interfaces:**
- Consumes: migration `0041_notes` (T3); harness pattern of `tests/integration/test_migration_0040_round_trip.py` (`_run_alembic`, `@pytest.mark.schema_mutating`).
- Produces: RULE-14 proof for 0041 (up/down symmetric, constraints enforced by the DB).

- [ ] **Step 1: Write the test**

```python
# tests/integration/test_migration_0041_round_trip.py
"""Round-trip safety test for migration 0041 (NOTES-001 — scratchpad).

Verifies the 0041 upgrade/downgrade is round-trip safe AND that the schema
contracts the service layer relies on actually exist at head: the scope
invariant CHECK and the note-type CHECK (RULE-14 verification, mirroring
test_migration_0040_round_trip.py).

NOTE: mutates the shared test DB schema mid-run; the ``finally`` always
restores head. Carries ``@pytest.mark.schema_mutating`` so ``just test`` and
CI run it in a dedicated SERIAL phase — never concurrently with other tests.
"""

from __future__ import annotations

import os
import subprocess
import uuid as _uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import sqlalchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine
from sqlalchemy.pool import NullPool as _NullPool

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

# Downgrading to the parent revision applies ONLY 0041's downgrade.
_PARENT_REVISION = "0040_series_drift_results"


def _alembic_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "apps" / "api" / "alembic"


def _run_alembic(*args: str) -> None:
    """Run an alembic command against the test DB (mirrors integration conftest)."""
    alembic_dir = _alembic_dir()
    alembic_ini = alembic_dir.parent / "alembic.ini"
    db_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://narrare:narrare@localhost:5433/narrare_test",
    )
    env = {**os.environ, "DATABASE_URL": db_url, "PGOPTIONS": "-c lock_timeout=10s"}
    subprocess.run(
        [
            "python",
            "-m",
            "alembic",
            "-c",
            str(alembic_ini) if alembic_ini.exists() else "alembic.ini",
            *args,
        ],
        env=env,
        cwd=alembic_dir.parent,
        check=True,
        capture_output=True,
    )


async def _table_exists(conn: AsyncConnection) -> bool:
    return bool(
        (
            await conn.execute(
                sqlalchemy.text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'notes')"
                )
            )
        ).scalar()
    )


async def _constraint_exists(conn: AsyncConnection, name: str) -> bool:
    return bool(
        (
            await conn.execute(
                sqlalchemy.text(
                    "SELECT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = :name)"
                ),
                {"name": name},
            )
        ).scalar()
    )


@pytest.mark.schema_mutating
class TestMigration0041RoundTrip:
    """The 0041 upgrade/downgrade is round-trip safe with a seeded row."""

    async def test_seed_note_then_downgrade_then_upgrade(self) -> None:
        db_url = os.environ.get(
            "TEST_DATABASE_URL",
            "postgresql+asyncpg://narrare:narrare@localhost:5433/narrare_test",
        )

        # 1. Ensure we start at head (0041 applied).
        _run_alembic("upgrade", "head")

        # 2. Seed user + novel + series + one note (the data shape 0041 owns).
        user_id = _uuid.uuid4()
        novel_id = _uuid.uuid4()
        series_id = _uuid.uuid4()
        note_id = _uuid.uuid4()
        eng = _create_async_engine(db_url, poolclass=_NullPool)
        try:
            async with eng.begin() as conn:
                await conn.execute(
                    sqlalchemy.text(
                        "INSERT INTO users (id, email, hashed_password, created_at, updated_at) "
                        "VALUES (:id, :email, 'fake_hash', now(), now())"
                    ),
                    {"id": user_id, "email": f"u-{user_id.hex[:10]}@example.com"},
                )
                await conn.execute(
                    sqlalchemy.text(
                        "INSERT INTO novels (id, user_id, title, author, genre, "
                        "writing_language, tone, story_structure, logline, synopsis, is_demo) "
                        "VALUES (:id, :uid, 'RT Novel', '', '', 'en', '', 'three_act', "
                        "'', '', false)"
                    ),
                    {"id": novel_id, "uid": user_id},
                )
                await conn.execute(
                    sqlalchemy.text(
                        "INSERT INTO series (id, user_id, title, status) "
                        "VALUES (:id, :uid, 'RT Series', 'draft')"
                    ),
                    {"id": series_id, "uid": user_id},
                )
                await conn.execute(
                    sqlalchemy.text(
                        "INSERT INTO notes (id, user_id, title, content, note_type, tags, novel_id) "
                        "VALUES (:id, :uid, 'RT Note', 'body', 'idea', '{\"plot\"}', :nid)"
                    ),
                    {"id": note_id, "uid": user_id, "nid": novel_id},
                )
                assert await _constraint_exists(conn, "ck_notes_scope_invariant")
                assert await _constraint_exists(conn, "ck_notes_note_type")

                # 3. The scope invariant is enforced by the DB, not just the ORM:
                #    both links set → IntegrityError.
                with pytest.raises(IntegrityError):
                    await conn.execute(
                        sqlalchemy.text(
                            "INSERT INTO notes (id, user_id, content, note_type, tags, "
                            "novel_id, series_id) "
                            "VALUES (:id, :uid, 'both', 'idea', '{}', :nid, :sid)"
                        ),
                        {
                            "id": _uuid.uuid4(),
                            "uid": user_id,
                            "nid": novel_id,
                            "sid": series_id,
                        },
                    )
        finally:
            await eng.dispose()

        try:
            # 4. Downgrade to the parent revision — drops the table with its rows.
            _run_alembic("downgrade", _PARENT_REVISION)
            eng = _create_async_engine(db_url, poolclass=_NullPool)
            try:
                async with eng.begin() as conn:
                    assert not await _table_exists(conn), "table must be gone after downgrade"
            finally:
                await eng.dispose()

            # 5. Upgrade back to head — table + constraints rebuilt, rows gone.
            _run_alembic("upgrade", "head")
            eng = _create_async_engine(db_url, poolclass=_NullPool)
            try:
                async with eng.begin() as conn:
                    assert await _table_exists(conn), "table must exist at head"
                    assert await _constraint_exists(conn, "ck_notes_scope_invariant")
                    count = (
                        await conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM notes"))
                    ).scalar()
                    assert count == 0, "seeded rows do not survive the round trip"
            finally:
                await eng.dispose()
        finally:
            # Safety net: ALWAYS leave the shared test DB at head.
            _run_alembic("upgrade", "head")
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/integration/test_migration_0041_round_trip.py -v -m schema_mutating`
Expected: PASS (requires the test DB; `just test` wires it).

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_migration_0041_round_trip.py
git commit -m "test(notes): migration 0041 round-trip with scope-invariant CHECK verification"
```

---

### Task 5: API — notes schemas + contracts

**Spec slice:** §9.3 (Backend CRUD — contracts → schemas first) · §5 (API surface).

**Files:**
- Create: `apps/api/narrare/notes/schemas.py`
- Create: `apps/api/narrare/notes/contracts.py`
- Test: `tests/unit/api/notes/test_schemas.py` (+ empty `tests/unit/api/notes/__init__.py` — scaffolding)

**Interfaces:**
- Consumes: `NoteType`, `validate_scope`, `MAX_TAGS_PER_NOTE`, `MAX_TAG_LENGTH` (T1); `Note` model (T3).
- Produces (used by T6–T11):
  - `class NoteCreateRequest(BaseModel)` — `title: str | None` (≤500), `content: str` (default `""`, ≤50000), `note_type: NoteType = NoteType.IDEA`, `tags: list[str]` (default `[]`, ≤10 items, each ≤32 chars), `novel_id: UUID | None`, `series_id: UUID | None`; scope validator
  - `class NoteUpdateRequest(BaseModel)` — all optional, same limits; scope validator; explicit `null` preserved via `exclude_unset`
  - `class NoteResponse(BaseModel)` — `from_attributes=True`; `id, title, content, note_type, tags, novel_id, series_id, created_at, updated_at`
  - `class NoteTagsResponse(BaseModel)` — `tags: list[str]`
  - Protocols in `contracts.py`: `NoteRepositoryProtocol`, `NoteServiceProtocol`, `OwnedLinkLookupProtocol` (`async def get_owned(self, entity_id: UUID, user_id: UUID) -> object | None`), `NoteEmbeddingDispatchProtocol` (`async def dispatch(self, note_id: UUID, text: str) -> None`), `EmbeddingCleanupProtocol` (`async def delete(self, source_type: str, source_id: UUID) -> None`)

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/api/notes/test_schemas.py
"""Unit tests for narrare.notes.schemas — pure Pydantic validation (NOTES-001)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from narrare.notes.schemas import (
    NoteCreateRequest,
    NoteResponse,
    NoteTagsResponse,
    NoteUpdateRequest,
)


class TestNoteCreateRequest:
    def test_minimal_request_defaults(self) -> None:
        req = NoteCreateRequest(content="A thought")
        assert req.note_type == "idea"
        assert req.tags == []
        assert req.title is None
        assert req.novel_id is None and req.series_id is None

    def test_scope_validator_rejects_both_links(self) -> None:
        with pytest.raises(ValidationError, match="not both"):
            NoteCreateRequest(content="x", novel_id=uuid4(), series_id=uuid4())

    def test_tag_count_limit(self) -> None:
        with pytest.raises(ValidationError):
            NoteCreateRequest(content="x", tags=["t"] * 11)

    def test_tag_length_limit(self) -> None:
        with pytest.raises(ValidationError):
            NoteCreateRequest(content="x", tags=["x" * 33])

    def test_content_cap_50000(self) -> None:
        with pytest.raises(ValidationError):
            NoteCreateRequest(content="x" * 50_001)


class TestNoteUpdateRequest:
    def test_all_fields_optional(self) -> None:
        req = NoteUpdateRequest()
        assert req.model_dump(exclude_unset=True) == {}

    def test_explicit_none_is_preserved_by_exclude_unset(self) -> None:
        req = NoteUpdateRequest(novel_id=None)
        assert req.model_dump(exclude_unset=True) == {"novel_id": None}

    def test_scope_validator_rejects_both_links(self) -> None:
        with pytest.raises(ValidationError, match="not both"):
            NoteUpdateRequest(novel_id=uuid4(), series_id=uuid4())


class TestNoteResponse:
    def test_from_attributes_over_orm_style_object(self) -> None:
        class _Row:
            id = uuid4()
            title = None
            content = "body"
            note_type = "idea"
            tags = ["plot"]
            novel_id = None
            series_id = None
            created_at = "2026-08-21T00:00:00+00:00"
            updated_at = "2026-08-21T00:00:00+00:00"

        resp = NoteResponse.model_validate(_Row())
        assert resp.note_type == "idea"
        assert resp.tags == ["plot"]


class TestNoteTagsResponse:
    def test_holds_tag_list(self) -> None:
        assert NoteTagsResponse(tags=["a", "b"]).tags == ["a", "b"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/api/notes/test_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'narrare.notes.schemas'`

- [ ] **Step 3: Write the implementation**

```python
# apps/api/narrare/notes/schemas.py
"""Notes Pydantic schemas — request/response models (NOTES-001 §5)."""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Pydantic model resolution
from datetime import datetime  # noqa: TC003

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from narrare_core.notes.types import (
    MAX_TAG_LENGTH,
    MAX_TAGS_PER_NOTE,
    NoteType,
    validate_scope,
)


def _check_tag_lengths(value: list[str]) -> list[str]:
    for tag in value:
        if len(tag) > MAX_TAG_LENGTH:
            msg = f"Each tag must be at most {MAX_TAG_LENGTH} characters"
            raise ValueError(msg)
    return value


class NoteCreateRequest(BaseModel):
    """Create a note — used by BOTH quick capture and the full editor (spec §5)."""

    title: str | None = Field(default=None, max_length=500)
    content: str = Field(default="", max_length=50_000)
    note_type: NoteType = NoteType.IDEA
    tags: list[str] = Field(default_factory=list, max_length=MAX_TAGS_PER_NOTE)
    novel_id: uuid.UUID | None = None
    series_id: uuid.UUID | None = None

    @field_validator("tags")
    @classmethod
    def _tags_within_limit(cls, value: list[str]) -> list[str]:
        return _check_tag_lengths(value)

    @model_validator(mode="after")
    def _scope_not_both(self) -> NoteCreateRequest:
        validate_scope(self.novel_id, self.series_id)
        return self


class NoteUpdateRequest(BaseModel):
    """Partial update. Explicit ``null`` clears a field (exclude_unset semantics)."""

    title: str | None = Field(default=None, max_length=500)
    content: str | None = Field(default=None, max_length=50_000)
    note_type: NoteType | None = None
    tags: list[str] | None = Field(default=None, max_length=MAX_TAGS_PER_NOTE)
    novel_id: uuid.UUID | None = None
    series_id: uuid.UUID | None = None

    @field_validator("tags")
    @classmethod
    def _tags_within_limit(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _check_tag_lengths(value)

    @model_validator(mode="after")
    def _scope_not_both(self) -> NoteUpdateRequest:
        validate_scope(self.novel_id, self.series_id)
        return self


class NoteResponse(BaseModel):
    """API representation of a note.

    ``title`` is the stored (possibly None) title — display fallback lives
    with the client (``noteDisplayTitle``) per spec §4.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    content: str
    note_type: str
    tags: list[str]
    novel_id: uuid.UUID | None = None
    series_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class NoteTagsResponse(BaseModel):
    """Distinct existing tags for autocomplete (spec §5 GET /notes/tags)."""

    tags: list[str]
```

```python
# apps/api/narrare/notes/contracts.py
"""Notes service contracts (RULE-03) — protocols only, no logic (NOTES-001)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.notes.models import Note
    from narrare.notes.schemas import NoteCreateRequest, NoteUpdateRequest


@runtime_checkable
class NoteRepositoryProtocol(Protocol):
    async def get_by_id(self, note_id: uuid.UUID, user_id: uuid.UUID) -> Note | None: ...

    async def get_many_by_ids(
        self, note_ids: set[uuid.UUID], user_id: uuid.UUID
    ) -> list[Note]: ...

    async def list_notes(
        self,
        user_id: uuid.UUID,
        *,
        note_type: str | None = None,
        tag: str | None = None,
        novel_id: uuid.UUID | None = None,
        series_id: uuid.UUID | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Note]: ...

    async def create(
        self,
        user_id: uuid.UUID,
        *,
        title: str | None,
        content: str,
        note_type: str,
        tags: list[str],
        novel_id: uuid.UUID | None,
        series_id: uuid.UUID | None,
    ) -> Note: ...

    async def update(self, note: Note, **patch: object) -> Note: ...

    async def delete(self, note: Note) -> None: ...

    async def distinct_tags(self, user_id: uuid.UUID, *, q: str | None = None) -> list[str]: ...


@runtime_checkable
class OwnedLinkLookupProtocol(Protocol):
    """Ownership check for an optional novel/series link.

    Implemented by thin adapters in ``narrare.notes.dependencies``; returns
    the entity when it exists AND belongs to the user, else ``None``.
    """

    async def get_owned(self, entity_id: uuid.UUID, user_id: uuid.UUID) -> object | None: ...


@runtime_checkable
class NoteEmbeddingDispatchProtocol(Protocol):
    """Fire-and-forget embedding dispatch (ADR-080 in-process pattern, §6a)."""

    async def dispatch(self, note_id: uuid.UUID, text: str) -> None: ...


@runtime_checkable
class EmbeddingCleanupProtocol(Protocol):
    """Deletes embeddings for a source (spec §6a: no ghost embeddings).

    Structurally satisfied by ``narrare.embeddings.service.EmbeddingService.delete``.
    """

    async def delete(self, source_type: str, source_id: uuid.UUID) -> None: ...


@runtime_checkable
class NoteServiceProtocol(Protocol):
    async def get(self, note_id: uuid.UUID, user_id: uuid.UUID) -> Note: ...

    async def list_notes(
        self,
        user_id: uuid.UUID,
        *,
        note_type: str | None = None,
        tag: str | None = None,
        novel_id: uuid.UUID | None = None,
        series_id: uuid.UUID | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Note]: ...

    async def create(self, user_id: uuid.UUID, request: NoteCreateRequest) -> Note: ...

    async def update(
        self, note_id: uuid.UUID, user_id: uuid.UUID, request: NoteUpdateRequest
    ) -> Note: ...

    async def delete(self, note_id: uuid.UUID, user_id: uuid.UUID) -> None: ...

    async def list_tags(self, user_id: uuid.UUID, q: str | None = None) -> list[str]: ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/api/notes/test_schemas.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/notes/schemas.py apps/api/narrare/notes/contracts.py tests/unit/api/notes/
git commit -m "feat(notes): add API schemas and service/repository contracts with scope validation"
```

---

### Task 6: API — notes repository

**Spec slice:** §9.3 · §5 (filters, ILIKE, tag distinct).

**Files:**
- Create: `apps/api/narrare/notes/repository.py`
- Modify: `tests/factories` (add `make_note`)
- Test: `tests/unit/api/notes/test_repository.py`

**Interfaces:**
- Consumes: `Note` model (T3); `BaseRepository` (`narrare._app.base_repository`, helpers `_flush_and_refresh` / `_flush`); fake-session pattern `tests/fakes/fake_db_session.FakeDbSession` / `FakeResult`; `make_novel` factory pattern in `tests/factories`.
- Produces: `class NoteRepository(BaseRepository)` implementing `NoteRepositoryProtocol` (exact signatures in T5); `tests.factories.make_note`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/api/notes/test_repository.py
"""Unit tests for ``NoteRepository`` query wiring (fake session).

Mirrors ``tests/unit/api/novels/test_novel_repository.py``: the repository is
a thin SQLAlchemy wrapper — these tests exercise the query/return path and
flush bookkeeping without a real database.
"""

from __future__ import annotations

from typing import cast
from uuid import uuid4

from narrare.notes.repository import NoteRepository
from tests.factories import make_note
from tests.fakes.fake_db_session import FakeDbSession, FakeResult


def _make_repo(results: list[FakeResult]) -> NoteRepository:
    return NoteRepository(cast("object", FakeDbSession(results)))  # type: ignore[arg-type]


class TestGetById:
    async def test_returns_note_when_found(self) -> None:
        note = make_note()
        repo = _make_repo([FakeResult(value=note)])
        assert await repo.get_by_id(note.id, note.user_id) is note

    async def test_returns_none_when_missing(self) -> None:
        repo = _make_repo([FakeResult(value=None)])
        assert await repo.get_by_id(uuid4(), uuid4()) is None


class TestListNotes:
    async def test_returns_scalar_list(self) -> None:
        notes = [make_note(), make_note()]
        repo = _make_repo([FakeResult(value=notes)])
        assert await repo.list_notes(notes[0].user_id) == notes


class TestDistinctTags:
    async def test_returns_string_list(self) -> None:
        repo = _make_repo([FakeResult(value=[("alpha",), ("beta",)])])
        assert await repo.distinct_tags(uuid4()) == ["alpha", "beta"]

    async def test_with_prefix_filter(self) -> None:
        repo = _make_repo([FakeResult(value=[("plot",)])])
        assert await repo.distinct_tags(uuid4(), q="pl") == ["plot"]


class TestCreateUpdateDelete:
    async def test_create_flushes_and_returns_note(self) -> None:
        repo = _make_repo([])
        user_id = uuid4()
        note = await repo.create(
            user_id,
            title=None,
            content="body",
            note_type="idea",
            tags=["plot"],
            novel_id=None,
            series_id=None,
        )
        assert note.user_id == user_id
        assert note.content == "body"
        assert note.tags == ["plot"]

    async def test_update_sets_patched_fields(self) -> None:
        note = make_note()
        repo = _make_repo([FakeResult(value=note)])
        updated = await repo.update(note, content="new body", tags=["x"])
        assert updated is note
        assert updated.content == "new body"
        assert updated.tags == ["x"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/api/notes/test_repository.py -v`
Expected: FAIL — `ModuleNotFoundError` (`narrare.notes.repository`) and `ImportError` (`make_note`).

- [ ] **Step 3: Write the implementation + factory**

```python
# apps/api/narrare/notes/repository.py
"""Note repository — DB queries only (RULE-06: no business logic here)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, or_, select

from narrare._app.base_repository import BaseRepository
from narrare.notes.models import Note

if TYPE_CHECKING:
    import uuid


class NoteRepository(BaseRepository):
    """Persistence operations for scratchpad notes."""

    async def get_by_id(self, note_id: uuid.UUID, user_id: uuid.UUID) -> Note | None:
        result = await self._session.execute(
            select(Note).where(Note.id == note_id, Note.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_many_by_ids(
        self, note_ids: set[uuid.UUID], user_id: uuid.UUID
    ) -> list[Note]:
        if not note_ids:
            return []
        result = await self._session.execute(
            select(Note).where(Note.id.in_(note_ids), Note.user_id == user_id)
        )
        return list(result.scalars())

    async def list_notes(
        self,
        user_id: uuid.UUID,
        *,
        note_type: str | None = None,
        tag: str | None = None,
        novel_id: uuid.UUID | None = None,
        series_id: uuid.UUID | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Note]:
        """Filtered list, default sort ``updated_at DESC`` (spec §5)."""
        stmt = select(Note).where(Note.user_id == user_id)
        if note_type is not None:
            stmt = stmt.where(Note.note_type == note_type)
        if tag is not None:
            # tag = ANY(tags) — containment in the TEXT[] column
            stmt = stmt.where(Note.tags.any(tag))
        if novel_id is not None:
            stmt = stmt.where(Note.novel_id == novel_id)
        if series_id is not None:
            stmt = stmt.where(Note.series_id == series_id)
        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(or_(Note.title.ilike(pattern), Note.content.ilike(pattern)))
        stmt = stmt.order_by(Note.updated_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars())

    async def create(
        self,
        user_id: uuid.UUID,
        *,
        title: str | None,
        content: str,
        note_type: str,
        tags: list[str],
        novel_id: uuid.UUID | None,
        series_id: uuid.UUID | None,
    ) -> Note:
        note = Note(
            user_id=user_id,
            title=title,
            content=content,
            note_type=note_type,
            tags=tags,
            novel_id=novel_id,
            series_id=series_id,
        )
        self._session.add(note)
        await self._flush_and_refresh(note)
        return note

    async def update(self, note: Note, **patch: object) -> Note:
        """Apply a partial patch (explicit ``None`` values clear the field)."""
        for field, value in patch.items():
            setattr(note, field, value)
        await self._flush_and_refresh(note)
        return note

    async def delete(self, note: Note) -> None:
        await self._session.delete(note)
        await self._flush()

    async def distinct_tags(self, user_id: uuid.UUID, *, q: str | None = None) -> list[str]:
        """Distinct existing tags via ``DISTINCT unnest`` (spec §4), optional prefix."""
        tag_col = func.unnest(Note.tags).label("tag")
        stmt = select(func.distinct(tag_col)).where(Note.user_id == user_id)
        if q:
            stmt = stmt.where(tag_col.ilike(f"{q}%"))
        stmt = stmt.order_by(tag_col)
        result = await self._session.execute(stmt)
        return [row[0] for row in result.fetchall()]
```

Add the note factory to the existing `tests/factories` package — inspect how `make_novel` is exposed there (single `__init__.py` or split modules) and follow the same style:

```python
# the make_note body (place per the existing factory layout)
from narrare.notes.models import Note as NoteModel


def make_note(**overrides: object) -> NoteModel:
    """Build an unsaved Note ORM instance with sane defaults."""
    defaults: dict[str, object] = {
        "user_id": uuid4(),
        "title": None,
        "content": "note body",
        "note_type": "idea",
        "tags": [],
        "novel_id": None,
        "series_id": None,
    }
    return NoteModel(**{**defaults, **overrides})  # type: ignore[arg-type]
```

(`uuid4` is already imported by the factories module — reuse the existing import.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/api/notes/test_repository.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/notes/repository.py tests/unit/api/notes/test_repository.py tests/factories/
git commit -m "feat(notes): add note repository with filters, tag containment, and distinct tags"
```

---

### Task 7: API — notes service (embedding dispatch, cleanup, snapshot)

**Spec slice:** §9.3 · §6a (dispatch on create/update, cleanup on delete) · §6b (`get_note_snapshot`).

**Files:**
- Create: `apps/api/narrare/notes/service.py`
- Create: `tests/fakes/fake_notes_repository.py`
- Test: `tests/unit/api/notes/test_service.py`

**Interfaces:**
- Consumes: contracts + schemas (T5); `normalize_tags`, `effective_title`, `validate_scope`, `NoteType` (T1); `NoteSnapshot` (T2); `NotFoundError` (`narrare_core.shared.errors`); `make_note` (T6).
- Produces (used by T8–T9, T15): `class NoteService` with
  - `__init__(self, repo: NoteRepositoryProtocol, *, novel_lookup: OwnedLinkLookupProtocol | None = None, series_lookup: OwnedLinkLookupProtocol | None = None, embedding_dispatch: NoteEmbeddingDispatchProtocol | None = None, embedding_cleanup: EmbeddingCleanupProtocol | None = None) -> None`
  - `async def get(note_id, user_id) -> Note` (raises `NotFoundError`)
  - `async def list_notes(user_id, *, note_type=None, tag=None, novel_id=None, series_id=None, q=None, limit=50, offset=0) -> list[Note]`
  - `async def create(user_id, request: NoteCreateRequest) -> Note`
  - `async def update(note_id, user_id, request: NoteUpdateRequest) -> Note`
  - `async def delete(note_id, user_id) -> None`
  - `async def list_tags(user_id, q=None) -> list[str]`
  - `async def get_note_snapshot(note_id, user_id) -> NoteSnapshot | None` (implements `NoteLookupProtocol`)

- [ ] **Step 1: Write the fake repository**

```python
# tests/fakes/fake_notes_repository.py
"""Fake NoteRepository for service-level unit tests (ADR-030 fake pattern).

Implements NoteRepositoryProtocol with in-memory storage; records calls so
tests can assert create/update/delete bookkeeping.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid

    from narrare.notes.models import Note


class FakeNotesRepository:
    """In-memory NoteRepository double (ADR-030: fakes over MagicMock)."""

    def __init__(self, notes: list[Note] | None = None) -> None:
        self._notes: dict[uuid.UUID, Note] = {n.id: n for n in (notes or [])}
        self.created: list[Note] = []
        self.deleted: list[Note] = []
        self.update_calls: list[tuple[uuid.UUID, dict[str, object]]] = []

    def seed(self, note: Note) -> None:
        self._notes[note.id] = note

    async def get_by_id(self, note_id: uuid.UUID, user_id: uuid.UUID) -> Note | None:
        note = self._notes.get(note_id)
        if note is not None and note.user_id == user_id:
            return note
        return None

    async def get_many_by_ids(
        self, note_ids: set[uuid.UUID], user_id: uuid.UUID
    ) -> list[Note]:
        return [n for i, n in self._notes.items() if i in note_ids and n.user_id == user_id]

    async def list_notes(
        self,
        user_id: uuid.UUID,
        *,
        note_type: str | None = None,
        tag: str | None = None,
        novel_id: uuid.UUID | None = None,
        series_id: uuid.UUID | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Note]:
        result = [
            n
            for n in self._notes.values()
            if n.user_id == user_id
            and (note_type is None or n.note_type == note_type)
            and (tag is None or tag in (n.tags or []))
            and (novel_id is None or n.novel_id == novel_id)
            and (series_id is None or n.series_id == series_id)
            and (
                q is None
                or q.lower() in (n.title or "").lower()
                or q.lower() in n.content.lower()
            )
        ]
        return result[offset : offset + limit]

    async def create(
        self,
        user_id: uuid.UUID,
        *,
        title: str | None,
        content: str,
        note_type: str,
        tags: list[str],
        novel_id: uuid.UUID | None,
        series_id: uuid.UUID | None,
    ) -> Note:
        from narrare.notes.models import Note

        note = Note(
            user_id=user_id,
            title=title,
            content=content,
            note_type=note_type,
            tags=tags,
            novel_id=novel_id,
            series_id=series_id,
        )
        self._notes[note.id] = note
        self.created.append(note)
        return note

    async def update(self, note: Note, **patch: object) -> Note:
        for field, value in patch.items():
            setattr(note, field, value)
        self.update_calls.append((note.id, patch))
        return note

    async def delete(self, note: Note) -> None:
        self._notes.pop(note.id, None)
        self.deleted.append(note)

    async def distinct_tags(self, user_id: uuid.UUID, *, q: str | None = None) -> list[str]:
        tags: set[str] = set()
        for n in self._notes.values():
            if n.user_id == user_id:
                tags.update(n.tags or [])
        return sorted(t for t in tags if q is None or t.startswith(q.lower()))
```

- [ ] **Step 2: Write the failing service tests**

```python
# tests/unit/api/notes/test_service.py
"""Unit tests for NoteService — business rules with fakes (NOTES-001 §6a/§6b)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from narrare.notes.schemas import NoteCreateRequest, NoteUpdateRequest
from narrare.notes.service import NoteService
from narrare_core.notes.contracts import NoteSnapshot
from narrare_core.shared.errors import NotFoundError
from tests.factories import make_note
from tests.fakes.fake_notes_repository import FakeNotesRepository

if TYPE_CHECKING:
    from narrare.notes.models import Note


class FakeDispatch:
    """NoteEmbeddingDispatchProtocol double — records dispatches, never fails."""

    def __init__(self) -> None:
        self.calls: list[tuple[UUID, str]] = []

    async def dispatch(self, note_id: UUID, text: str) -> None:
        self.calls.append((note_id, text))


class FailingDispatch:
    """NoteEmbeddingDispatchProtocol double — always raises (RULE-11 path)."""

    async def dispatch(self, note_id: UUID, text: str) -> None:
        msg = "boom"
        raise RuntimeError(msg)


class FakeCleanup:
    """EmbeddingCleanupProtocol double — records deletions."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, UUID]] = []

    async def delete(self, source_type: str, source_id: UUID) -> None:
        self.calls.append((source_type, source_id))


class FakeOwnedLookup:
    """OwnedLinkLookupProtocol double — only the listed ids are 'owned'."""

    def __init__(self, *owned: UUID) -> None:
        self._owned = set(owned)

    async def get_owned(self, entity_id: UUID, user_id: UUID) -> object | None:
        return object() if entity_id in self._owned else None


def _service(
    *,
    novel_ids: tuple[UUID, ...] = (),
    series_ids: tuple[UUID, ...] = (),
) -> tuple[NoteService, FakeNotesRepository, FakeDispatch, FakeCleanup]:
    repo = FakeNotesRepository()
    dispatch = FakeDispatch()
    cleanup = FakeCleanup()
    service = NoteService(
        repo,
        novel_lookup=FakeOwnedLookup(*novel_ids),
        series_lookup=FakeOwnedLookup(*series_ids),
        embedding_dispatch=dispatch,
        embedding_cleanup=cleanup,
    )
    return service, repo, dispatch, cleanup


class TestCreate:
    async def test_create_dispatches_embedding_with_title_plus_content(self) -> None:
        service, _, dispatch, _ = _service()
        user_id = uuid4()
        request = NoteCreateRequest(title="Twist", content="The aunt did it")
        note = await service.create(user_id, request)
        assert dispatch.calls == [(note.id, "Twist\nThe aunt did it")]

    async def test_normalizes_tags_before_persisting(self) -> None:
        service, _, _, _ = _service()
        note = await service.create(
            uuid4(), NoteCreateRequest(content="x", tags=["Plot", "plot", " world "])
        )
        assert note.tags == ["plot", "world"]

    async def test_unknown_novel_link_raises_not_found(self) -> None:
        service, _, _, _ = _service()  # no ids owned
        with pytest.raises(NotFoundError):
            await service.create(uuid4(), NoteCreateRequest(content="x", novel_id=uuid4()))

    async def test_dispatch_failure_does_not_block_create(self) -> None:
        service, _, _, _ = _service()
        service._embedding_dispatch = FailingDispatch()  # type: ignore[assignment]
        note = await service.create(uuid4(), NoteCreateRequest(content="x"))
        assert note.content == "x"


class TestUpdate:
    async def test_reembeds_when_content_changes(self) -> None:
        service, repo, dispatch, _ = _service()
        note = make_note()
        repo.seed(note)
        await service.update(note.id, note.user_id, NoteUpdateRequest(content="new body"))
        assert dispatch.calls and dispatch.calls[-1][1].endswith("new body")

    async def test_no_dispatch_when_content_unchanged(self) -> None:
        service, repo, dispatch, _ = _service()
        note = make_note(content="stable")
        repo.seed(note)
        await service.update(note.id, note.user_id, NoteUpdateRequest(tags=[]))
        assert dispatch.calls == []

    async def test_explicit_null_clears_link(self) -> None:
        service, repo, _, _ = _service()
        note = make_note(novel_id=uuid4())
        repo.seed(note)
        updated = await service.update(note.id, note.user_id, NoteUpdateRequest(novel_id=None))
        assert updated.novel_id is None

    async def test_merged_scope_conflict_raises(self) -> None:
        service, repo, _, _ = _service()
        note = make_note(novel_id=uuid4())
        repo.seed(note)
        with pytest.raises(Exception, match="not both"):
            await service.update(note.id, note.user_id, NoteUpdateRequest(series_id=uuid4()))


class TestDelete:
    async def test_deletes_note_and_cleans_embeddings(self) -> None:
        service, repo, _, cleanup = _service()
        note = make_note()
        repo.seed(note)
        await service.delete(note.id, note.user_id)
        assert repo.deleted == [note]
        assert cleanup.calls == [("note", note.id)]

    async def test_missing_note_raises_not_found(self) -> None:
        service, _, _, _ = _service()
        with pytest.raises(NotFoundError):
            await service.delete(uuid4(), uuid4())


class TestSnapshot:
    async def test_get_note_snapshot_maps_orm_to_core_snapshot(self) -> None:
        service, repo, _, _ = _service()
        note = make_note(title=None, content="Derived title\nbody", tags=["plot"])
        repo.seed(note)
        snapshot = await service.get_note_snapshot(note.id, note.user_id)
        assert isinstance(snapshot, NoteSnapshot)
        assert snapshot.note_type == note.note_type
        assert snapshot.display_title == "Derived title"

    async def test_get_note_snapshot_none_for_other_user(self) -> None:
        service, repo, _, _ = _service()
        note = make_note()
        repo.seed(note)
        assert await service.get_note_snapshot(note.id, uuid4()) is None


class TestListTags:
    async def test_delegates_to_repository(self) -> None:
        service, repo, _, _ = _service()
        note = make_note(tags=["alpha", "beta"])
        repo.seed(note)
        assert await service.list_tags(note.user_id) == ["alpha", "beta"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/api/notes/test_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'narrare.notes.service'`

- [ ] **Step 4: Write the implementation**

```python
# apps/api/narrare/notes/service.py
"""Note service — business logic (NOTES-001).

Owns: tag normalization, scope validation (incl. merged PATCH state), link
ownership checks, embedding dispatch on create/update, embedding cleanup on
delete, and the core NoteSnapshot mapping for chat (§6b).
RULE-06: no SQL, no HTTP.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.notes.contracts import NoteSnapshot
from narrare_core.notes.types import (
    NoteType,
    effective_title,
    normalize_tags,
    validate_scope,
)
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare.notes.contracts import (
        EmbeddingCleanupProtocol,
        NoteEmbeddingDispatchProtocol,
        NoteRepositoryProtocol,
        OwnedLinkLookupProtocol,
    )
    from narrare.notes.models import Note
    from narrare.notes.schemas import NoteCreateRequest, NoteUpdateRequest

logger = structlog.get_logger(__name__)


class NoteService:
    """Business logic for scratchpad notes."""

    def __init__(
        self,
        repo: NoteRepositoryProtocol,
        *,
        novel_lookup: OwnedLinkLookupProtocol | None = None,
        series_lookup: OwnedLinkLookupProtocol | None = None,
        embedding_dispatch: NoteEmbeddingDispatchProtocol | None = None,
        embedding_cleanup: EmbeddingCleanupProtocol | None = None,
    ) -> None:
        self._repo = repo
        self._novel_lookup = novel_lookup
        self._series_lookup = series_lookup
        self._embedding_dispatch = embedding_dispatch
        self._embedding_cleanup = embedding_cleanup

    async def get(self, note_id: uuid.UUID, user_id: uuid.UUID) -> Note:
        """Load a note, verifying ownership.

        Raises:
            NotFoundError: If the note does not exist or is not owned by the user.
        """
        note = await self._repo.get_by_id(note_id, user_id)
        if note is None:
            raise NotFoundError("Note", identifier=str(note_id))
        return note

    async def list_notes(
        self,
        user_id: uuid.UUID,
        *,
        note_type: str | None = None,
        tag: str | None = None,
        novel_id: uuid.UUID | None = None,
        series_id: uuid.UUID | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Note]:
        return await self._repo.list_notes(
            user_id,
            note_type=note_type,
            tag=tag,
            novel_id=novel_id,
            series_id=series_id,
            q=q,
            limit=limit,
            offset=offset,
        )

    async def create(self, user_id: uuid.UUID, request: NoteCreateRequest) -> Note:
        """Create a note and dispatch embedding generation (fire-and-forget, §6a)."""
        validate_scope(request.novel_id, request.series_id)
        await self._validate_link(self._novel_lookup, "Novel", request.novel_id, user_id)
        await self._validate_link(self._series_lookup, "Series", request.series_id, user_id)
        note = await self._repo.create(
            user_id,
            title=request.title,
            content=request.content,
            note_type=request.note_type.value,
            tags=normalize_tags(request.tags),
            novel_id=request.novel_id,
            series_id=request.series_id,
        )
        await self._dispatch_embedding(note)
        logger.info("note_created", note_id=str(note.id))
        return note

    async def update(
        self, note_id: uuid.UUID, user_id: uuid.UUID, request: NoteUpdateRequest
    ) -> Note:
        """Partially update a note; re-embed only when title/content changed."""
        note = await self.get(note_id, user_id)
        patch: dict[str, object] = request.model_dump(exclude_unset=True)

        # Merge PATCH state with stored state before validating the invariant:
        # setting series_id on a novel-linked note is a conflict too.
        merged_novel = patch.get("novel_id", note.novel_id)
        merged_series = patch.get("series_id", note.series_id)
        validate_scope(merged_novel, merged_series)  # type: ignore[arg-type]
        if "novel_id" in patch and merged_novel is not None:
            await self._validate_link(self._novel_lookup, "Novel", merged_novel, user_id)
        if "series_id" in patch and merged_series is not None:
            await self._validate_link(self._series_lookup, "Series", merged_series, user_id)

        if "note_type" in patch and patch["note_type"] is not None:
            patch["note_type"] = NoteType(patch["note_type"]).value
        if "tags" in patch and patch["tags"] is not None:
            patch["tags"] = normalize_tags(patch["tags"])  # type: ignore[arg-type]

        content_changed = "content" in patch and patch["content"] != note.content
        title_changed = "title" in patch and patch["title"] != note.title
        updated = await self._repo.update(note, **patch)
        if content_changed or title_changed:
            await self._dispatch_embedding(updated)
        logger.info("note_updated", note_id=str(note_id))
        return updated

    async def delete(self, note_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Hard-delete a note and clean up its embeddings (§6a, no ghosts)."""
        note = await self.get(note_id, user_id)
        await self._repo.delete(note)
        if self._embedding_cleanup is not None:
            try:
                await self._embedding_cleanup.delete("note", note_id)
            except Exception:
                logger.warning(
                    "note_embedding_cleanup_failed", note_id=str(note_id), exc_info=True
                )
        logger.info("note_deleted", note_id=str(note_id))

    async def list_tags(self, user_id: uuid.UUID, q: str | None = None) -> list[str]:
        """Distinct existing tags for autocomplete (spec §5)."""
        return await self._repo.distinct_tags(user_id, q=q)

    async def get_note_snapshot(
        self, note_id: uuid.UUID, user_id: uuid.UUID
    ) -> NoteSnapshot | None:
        """Core NoteLookupProtocol implementation — consumed by chat (§6b)."""
        note = await self._repo.get_by_id(note_id, user_id)
        if note is None:
            return None
        return NoteSnapshot(
            id=note.id,
            title=note.title or "",
            content=note.content,
            note_type=note.note_type,
            tags=list(note.tags or []),
        )

    async def _validate_link(
        self,
        lookup: OwnedLinkLookupProtocol | None,
        resource: str,
        entity_id: uuid.UUID | None,
        user_id: uuid.UUID,
    ) -> None:
        """A linked novel/series must exist AND belong to the user (ownership)."""
        if entity_id is None or lookup is None:
            return
        if await lookup.get_owned(entity_id, user_id) is None:
            raise NotFoundError(resource, identifier=str(entity_id))

    async def _dispatch_embedding(self, note: Note) -> None:
        """Fire-and-forget embedding dispatch; failures never block saves (RULE-11)."""
        if self._embedding_dispatch is None:
            return
        text = f"{effective_title(note.title, note.content)}\n{note.content}"
        try:
            await self._embedding_dispatch.dispatch(note.id, text)
        except Exception:
            logger.warning(
                "note_embedding_dispatch_failed", note_id=str(note.id), exc_info=True
            )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/api/notes/test_service.py -v`
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add apps/api/narrare/notes/service.py tests/fakes/fake_notes_repository.py tests/unit/api/notes/test_service.py
git commit -m "feat(notes): add note service with embedding dispatch, cleanup, and core snapshot mapping"
```

---

### Task 8: API — embedding dispatch (ADR-080) + dependencies wiring

**Spec slice:** §9.3 · §6a · §3 ("a thin dispatch in the service suffices").

**Files:**
- Create: `apps/api/narrare/notes/embedding_dispatch.py`
- Create: `apps/api/narrare/notes/dependencies.py`
- Test: `tests/unit/api/notes/test_embedding_dispatch.py`

**Interfaces:**
- Consumes: `run_embed_source_inprocess(source_type: str, source_id: str, content: str)` from `narrare.embeddings.tasks` (existing); `EmbeddingService`/`EmbeddingRepository` (existing); `NovelRepository.get_by_id`, `SeriesRepository.get` (existing); `NoteService` (T7).
- Produces (used by T9, T11, T15):
  - `class InProcessNoteEmbeddingDispatch` — `async def dispatch(self, note_id: UUID, text: str) -> None`
  - `def get_note_service(session: SessionDep) -> NoteService`
  - module-private `_NovelOwnedLookup`, `_SeriesOwnedLookup` (implement `OwnedLinkLookupProtocol`)

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/api/notes/test_embedding_dispatch.py
"""Unit tests for the notes in-process embedding dispatch (ADR-080, §6a)."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from narrare.notes import embedding_dispatch as dispatch_module
from narrare.notes.embedding_dispatch import InProcessNoteEmbeddingDispatch


async def _drain() -> None:
    """Yield enough event-loop turns for created tasks to complete."""
    for _ in range(3):
        await asyncio.sleep(0)


class TestInProcessNoteEmbeddingDispatch:
    async def test_dispatches_run_embed_source_inprocess_with_note_source(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[tuple[str, str, str]] = []

        async def _fake_run(source_type: str, source_id: str, content: str) -> None:
            calls.append((source_type, source_id, content))

        monkeypatch.setattr(dispatch_module, "run_embed_source_inprocess", _fake_run)
        dispatch = InProcessNoteEmbeddingDispatch()

        note_id = uuid4()
        await dispatch.dispatch(note_id, "title\nbody")
        await _drain()

        assert calls == [("note", str(note_id), "title\nbody")]

    async def test_completes_without_leaking_inflight_references(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _fake_run(source_type: str, source_id: str, content: str) -> None:
            return None

        monkeypatch.setattr(dispatch_module, "run_embed_source_inprocess", _fake_run)
        dispatch = InProcessNoteEmbeddingDispatch()
        await dispatch.dispatch(uuid4(), "text")
        await _drain()

        assert not dispatch_module._INFLIGHT_TASKS
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/api/notes/test_embedding_dispatch.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'narrare.notes.embedding_dispatch'`

- [ ] **Step 3: Write the implementation**

```python
# apps/api/narrare/notes/embedding_dispatch.py
"""In-process embedding dispatch for notes (ADR-080, NOTES-001 §6a).

Thin mirror of ``narrare.kb.embedding_hooks``: schedules
``run_embed_source_inprocess("note", ...)`` via ``asyncio.create_task``
fire-and-forget and holds a strong reference against GC. The task itself
performs content-hash idempotency (skips unchanged content), so no hook
manager is needed (spec §3).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from narrare.embeddings.tasks import run_embed_source_inprocess

if TYPE_CHECKING:
    from uuid import UUID

logger = structlog.get_logger(__name__)

#: Strong references to in-flight embedding coroutines (ADR-080 GC guard).
_INFLIGHT_TASKS: set[asyncio.Task[None]] = set()


def _on_done(task: asyncio.Task[None]) -> None:
    """Discard the GC-guard reference; log surfaced failures (RULE-11)."""
    _INFLIGHT_TASKS.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("note_background_task_failed", error=str(exc), exc_info=exc)


class InProcessNoteEmbeddingDispatch:
    """Dispatches note embeddings in-process; swappable seam (ADR-080)."""

    async def dispatch(self, note_id: UUID, text: str) -> None:
        task = asyncio.create_task(run_embed_source_inprocess("note", str(note_id), text))
        _INFLIGHT_TASKS.add(task)
        task.add_done_callback(_on_done)
        logger.info("note_embedding_task_dispatched", note_id=str(note_id))
```

```python
# apps/api/narrare/notes/dependencies.py
"""Notes dependency injection factories — wiring only, no business logic."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep

if TYPE_CHECKING:
    import uuid

    from narrare.notes.service import NoteService
    from narrare.novels.repository import NovelRepository
    from narrare.series.repository import SeriesRepository


class _NovelOwnedLookup:
    """OwnedLinkLookupProtocol adapter over NovelRepository.get_by_id."""

    def __init__(self, repo: NovelRepository) -> None:
        self._repo = repo

    async def get_owned(self, entity_id: uuid.UUID, user_id: uuid.UUID) -> object | None:
        return await self._repo.get_by_id(entity_id, user_id)


class _SeriesOwnedLookup:
    """OwnedLinkLookupProtocol adapter — SeriesRepository.get has no user
    check, so ownership is compared here (wiring-level adapter, RULE-06)."""

    def __init__(self, repo: SeriesRepository) -> None:
        self._repo = repo

    async def get_owned(self, entity_id: uuid.UUID, user_id: uuid.UUID) -> object | None:
        series = await self._repo.get(entity_id)
        if series is not None and series.user_id == user_id:
            return series
        return None


def get_note_service(session: SessionDep) -> NoteService:
    """Production wiring: NoteRepository + lookups + embedding dispatch/cleanup."""
    from narrare.embeddings.repository import EmbeddingRepository
    from narrare.embeddings.service import EmbeddingService
    from narrare.notes.embedding_dispatch import InProcessNoteEmbeddingDispatch
    from narrare.notes.repository import NoteRepository
    from narrare.notes.service import NoteService
    from narrare.novels.repository import NovelRepository
    from narrare.series.repository import SeriesRepository

    return NoteService(
        NoteRepository(session),
        novel_lookup=_NovelOwnedLookup(NovelRepository(session)),
        series_lookup=_SeriesOwnedLookup(SeriesRepository(session)),
        embedding_dispatch=InProcessNoteEmbeddingDispatch(),
        embedding_cleanup=EmbeddingService(EmbeddingRepository(session)),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/api/notes/ -v`
Expected: PASS (all notes unit tests)

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/notes/embedding_dispatch.py apps/api/narrare/notes/dependencies.py tests/unit/api/notes/test_embedding_dispatch.py
git commit -m "feat(notes): add in-process embedding dispatch (ADR-080) and service wiring"
```

---

### Task 9: API — notes router (CRUD + tags) + app registration

**Spec slice:** §9.3 · §5 (endpoints 1–6 minus search).

**Files:**
- Create: `apps/api/narrare/notes/router.py`
- Modify: `apps/api/narrare/_app/main.py` (router import + include)
- Test: `tests/integration/test_notes_api.py`

**Interfaces:**
- Consumes: `get_note_service` (T8); schemas (T5); `CurrentUserIdDep`, `SessionDep` (`narrare._app.dependencies`); `client` / `auth_headers` fixtures from `tests/integration/conftest.py`.
- Produces (used by T11, T17 — the frontend client): `router = APIRouter(prefix="/notes", tags=["notes"])` with `GET ""`, `POST ""`, `GET "/tags"`, `GET "/{note_id}"`, `PATCH "/{note_id}"`, `DELETE "/{note_id}"`.

- [ ] **Step 1: Write the failing integration tests**

```python
# tests/integration/test_notes_api.py
"""Integration tests for the notes endpoints (NOTES-001 §5).

CRUD + filters + tags endpoint + ownership/404/422 paths. Embedding dispatch
runs through the real wiring but is fire-and-forget (RULE-11): without a
configured provider the background task fails and logs — CRUD assertions are
unaffected either way.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestListAndCreate:
    async def test_create_and_list_roundtrip(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        create = await client.post(
            "/api/v1/notes",
            json={"content": "First thought", "note_type": "idea", "tags": ["Plot"]},
            headers=auth_headers,
        )
        assert create.status_code == 201
        body = create.json()
        assert body["content"] == "First thought"
        assert body["note_type"] == "idea"
        assert body["tags"] == ["plot"]  # normalized

        listing = await client.get("/api/v1/notes", headers=auth_headers)
        assert listing.status_code == 200
        assert [n["id"] for n in listing.json()] == [body["id"]]

    async def test_list_without_auth_returns_401(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/notes")
        assert response.status_code == 401

    async def test_scope_violation_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        novel = await client.post("/api/v1/novels", json={"title": "N"}, headers=auth_headers)
        series = await client.post("/api/v1/series", json={"title": "S"}, headers=auth_headers)
        response = await client.post(
            "/api/v1/notes",
            json={
                "content": "x",
                "novel_id": novel.json()["id"],
                "series_id": series.json()["id"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestFilters:
    async def test_filter_by_type_tag_and_q(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        await client.post(
            "/api/v1/notes", json={"content": "a", "note_type": "question"}, headers=auth_headers
        )
        await client.post(
            "/api/v1/notes", json={"content": "b", "tags": ["world"]}, headers=auth_headers
        )
        by_type = await client.get(
            "/api/v1/notes", params={"note_type": "question"}, headers=auth_headers
        )
        assert [n["content"] for n in by_type.json()] == ["a"]
        by_tag = await client.get("/api/v1/notes", params={"tag": "world"}, headers=auth_headers)
        assert [n["content"] for n in by_tag.json()] == ["b"]
        by_q = await client.get("/api/v1/notes", params={"q": "b"}, headers=auth_headers)
        assert [n["content"] for n in by_q.json()] == ["b"]


class TestTagsEndpoint:
    async def test_distinct_tags_with_prefix(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        await client.post(
            "/api/v1/notes", json={"content": "a", "tags": ["plot", "world"]}, headers=auth_headers
        )
        await client.post(
            "/api/v1/notes", json={"content": "b", "tags": ["Plot Twist"]}, headers=auth_headers
        )
        response = await client.get(
            "/api/v1/notes/tags", params={"q": "pl"}, headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["tags"] == ["plot", "plot twist"]


class TestDetailUpdateDelete:
    async def test_get_patch_delete_lifecycle(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        create = await client.post(
            "/api/v1/notes", json={"content": "original"}, headers=auth_headers
        )
        note_id = create.json()["id"]

        detail = await client.get(f"/api/v1/notes/{note_id}", headers=auth_headers)
        assert detail.status_code == 200

        patch = await client.patch(
            f"/api/v1/notes/{note_id}", json={"content": "edited"}, headers=auth_headers
        )
        assert patch.status_code == 200
        assert patch.json()["content"] == "edited"

        delete = await client.delete(f"/api/v1/notes/{note_id}", headers=auth_headers)
        assert delete.status_code == 204

        gone = await client.get(f"/api/v1/notes/{note_id}", headers=auth_headers)
        assert gone.status_code == 404

    async def test_patch_missing_returns_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.patch(
            "/api/v1/notes/00000000-0000-0000-0000-000000000000",
            json={"content": "x"},
            headers=auth_headers,
        )
        assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_notes_api.py -v`
Expected: FAIL — 404 on every route (router not registered).

- [ ] **Step 3: Write the router**

```python
# apps/api/narrare/notes/router.py
"""Notes routes — thin delegation (RULE-06: no business logic here).

Route order: the literal ``/tags`` path is declared BEFORE the ``/{note_id}``
path-parameter routes.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, status

from narrare._app.dependencies import CurrentUserIdDep
from narrare.notes.dependencies import get_note_service
from narrare.notes.schemas import (
    NoteCreateRequest,
    NoteResponse,
    NoteTagsResponse,
    NoteUpdateRequest,
)

if TYPE_CHECKING:
    from narrare.notes.service import NoteService

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("/tags", response_model=NoteTagsResponse)
async def list_tags(
    q: str | None = Query(default=None, max_length=32),
    user_id: CurrentUserIdDep = None,
    service: NoteService = Depends(get_note_service),
) -> NoteTagsResponse:
    """Distinct existing tags (autocomplete; optional prefix ``q``)."""
    tags = await service.list_tags(uuid.UUID(user_id), q)
    return NoteTagsResponse(tags=tags)


@router.get("", response_model=list[NoteResponse])
async def list_notes(
    note_type: str | None = Query(default=None),
    tag: str | None = Query(default=None, max_length=32),
    novel_id: uuid.UUID | None = Query(default=None),
    series_id: uuid.UUID | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: CurrentUserIdDep = None,
    service: NoteService = Depends(get_note_service),
) -> list[NoteResponse]:
    """List notes, default sort ``updated_at DESC`` (spec §5)."""
    notes = await service.list_notes(
        uuid.UUID(user_id),
        note_type=note_type,
        tag=tag,
        novel_id=novel_id,
        series_id=series_id,
        q=q,
        limit=limit,
        offset=offset,
    )
    return [NoteResponse.model_validate(n) for n in notes]


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    request: NoteCreateRequest,
    user_id: CurrentUserIdDep = None,
    service: NoteService = Depends(get_note_service),
) -> NoteResponse:
    """Create a note (quick capture and full editor both use this)."""
    note = await service.create(uuid.UUID(user_id), request)
    return NoteResponse.model_validate(note)


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: uuid.UUID,
    user_id: CurrentUserIdDep = None,
    service: NoteService = Depends(get_note_service),
) -> NoteResponse:
    note = await service.get(note_id, uuid.UUID(user_id))
    return NoteResponse.model_validate(note)


@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: uuid.UUID,
    request: NoteUpdateRequest,
    user_id: CurrentUserIdDep = None,
    service: NoteService = Depends(get_note_service),
) -> NoteResponse:
    note = await service.update(note_id, uuid.UUID(user_id), request)
    return NoteResponse.model_validate(note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: uuid.UUID,
    user_id: CurrentUserIdDep = None,
    service: NoteService = Depends(get_note_service),
) -> None:
    await service.delete(note_id, uuid.UUID(user_id))
```

Wire into `apps/api/narrare/_app/main.py` (two one-line edits):
1. In the router-import block — alphabetical position between `narrare.metrics.router` (line ~211) and `narrare.novels.router`:
   `from narrare.notes.router import router as notes_router`
2. In the `include_router` block — next to `app.include_router(novels_router, prefix=prefix)` (line ~250):
   `app.include_router(notes_router, prefix=prefix)`

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_notes_api.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/notes/router.py apps/api/narrare/_app/main.py tests/integration/test_notes_api.py
git commit -m "feat(notes): add notes router (CRUD, filters, tags) and register it in the app"
```

---

### Task 10: API — semantic search service with lexical fallback

**Spec slice:** §9.4 (Search) · §6a (vector search + RULE-11 fallback).

**Files:**
- Create: `apps/api/narrare/notes/search_service.py`
- Modify: `apps/api/narrare/notes/schemas.py` (append search models + `Literal` import)
- Test: `tests/unit/api/notes/test_search_service.py`

**Interfaces:**
- Consumes: `NoteRepositoryProtocol` (T5); `EmbeddingRepositoryProtocol` + `DEFAULT_EMBEDDING_SEARCH_THRESHOLD`/`DEFAULT_EMBEDDING_SEARCH_LIMIT` from `narrare.embeddings.contracts` (existing); `SearchRow`/`Embedding` from `narrare.embeddings.search_queries`/`models` (existing); `embed_texts` from `narrare_core.llm.embeddings` (existing); `get_core_settings()` (existing).
- Produces (used by T11):
  - Schemas: `NoteSearchRequest` (`query` 1–500, `note_type/tag/novel_id/series_id?`, `limit` default 20, 1–100), `NoteSearchHit(NoteResponse)` + `similarity: float | None`, `NoteSearchResponse` (`mode: Literal["lexical","semantic"]`, `query: str`, `results: list[NoteSearchHit]`)
  - `class NoteSearchService` — `__init__(self, notes_repo: NoteRepositoryProtocol, embedding_repo: EmbeddingRepositoryProtocol, *, model: str | None = None)`; `async def search(self, user_id: UUID, request: NoteSearchRequest) -> NoteSearchResponse`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/api/notes/test_search_service.py
"""Unit tests for NoteSearchService — semantic + RULE-11 lexical fallback (§6a)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

import narrare.notes.search_service as search_module
from narrare.notes.schemas import NoteSearchRequest
from narrare.notes.search_service import NoteSearchService
from tests.factories import make_note
from tests.fakes.fake_notes_repository import FakeNotesRepository

if TYPE_CHECKING:
    from narrare.embeddings.search_queries import SearchRow


class FakeEmbeddingRepo:
    """EmbeddingRepositoryProtocol.search double — canned rows keyed by marker."""

    def __init__(self, rows_by_marker: dict[float, list[tuple[UUID, float]]]) -> None:
        self._rows_by_marker = rows_by_marker
        self.calls: list[dict[str, object]] = []

    async def search(
        self,
        query_embedding: list[float],
        *,
        source_type: str | None = None,
        source_ids: set[UUID] | None = None,
        threshold: float = 0.7,
        limit: int = 20,
        model: str | None = None,
    ) -> list[SearchRow]:
        self.calls.append(
            {
                "source_type": source_type,
                "source_ids": source_ids,
                "limit": limit,
                "vector": query_embedding,
            }
        )
        from narrare.embeddings.models import Embedding
        from narrare.embeddings.search_queries import SearchRow as Row

        return [
            Row(
                embedding=Embedding(
                    id=uuid4(),
                    source_type="note",
                    source_id=sid,
                    content_hash="h",
                    embedding=[0.0],
                    model="m",
                    dimension=1,
                    generated_at=None,  # type: ignore[arg-type]
                ),
                similarity=sim,
                usage_count=0,
                last_referenced_at=None,
            )
            for sid, sim in self._rows_by_marker.get(query_embedding[0], [])
        ]


async def _fake_embed(texts: list[str], *, model: str | None = None) -> list[list[float]]:
    # Marker 1.0 identifies the "magic" query; anything else maps to 0.0.
    marker = 1.0 if texts[0] == "magic" else 0.0
    return [[marker, 0.5]]


@pytest.fixture
def patched_embed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search_module, "embed_texts", _fake_embed)


class TestSemanticSearch:
    async def test_returns_semantic_hits_ordered_by_similarity(self, patched_embed: None) -> None:
        note_a = make_note(content="alpha")
        note_b = make_note(content="beta")
        repo = FakeNotesRepository([note_a, note_b])
        embedding_repo = FakeEmbeddingRepo({1.0: [(note_b.id, 0.9), (note_a.id, 0.8)]})
        service = NoteSearchService(repo, embedding_repo)  # type: ignore[arg-type]

        response = await service.search(note_a.user_id, NoteSearchRequest(query="magic"))

        assert response.mode == "semantic"
        assert [r.id for r in response.results] == [note_b.id, note_a.id]
        assert response.results[0].similarity == pytest.approx(0.9)

    async def test_filters_candidates_before_vector_search(self, patched_embed: None) -> None:
        note_a = make_note(content="alpha", note_type="question")
        note_b = make_note(content="beta")
        repo = FakeNotesRepository([note_a, note_b])
        embedding_repo = FakeEmbeddingRepo({})
        service = NoteSearchService(repo, embedding_repo)  # type: ignore[arg-type]

        await service.search(
            note_a.user_id, NoteSearchRequest(query="magic", note_type="question")
        )

        call = embedding_repo.calls[0]
        assert call["source_type"] == "note"
        assert call["source_ids"] == {note_a.id}


class TestLexicalFallback:
    async def test_embedding_failure_falls_back_to_lexical(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _boom(texts: list[str], *, model: str | None = None) -> list[list[float]]:
            msg = "no provider"
            raise RuntimeError(msg)

        monkeypatch.setattr(search_module, "embed_texts", _boom)
        note = make_note(content="the aunt did it")
        repo = FakeNotesRepository([note])
        service = NoteSearchService(repo, FakeEmbeddingRepo({}))  # type: ignore[arg-type]

        response = await service.search(note.user_id, NoteSearchRequest(query="aunt"))

        assert response.mode == "lexical"
        assert [r.id for r in response.results] == [note.id]
        assert response.results[0].similarity is None

    async def test_no_candidates_returns_empty_lexical(self, patched_embed: None) -> None:
        repo = FakeNotesRepository([])
        service = NoteSearchService(repo, FakeEmbeddingRepo({}))  # type: ignore[arg-type]

        response = await service.search(uuid4(), NoteSearchRequest(query="magic"))

        assert response.mode == "lexical"
        assert response.results == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/api/notes/test_search_service.py -v`
Expected: FAIL — `ImportError` for `NoteSearchRequest` / `search_service`.

- [ ] **Step 3: Write the implementation**

Append to `apps/api/narrare/notes/schemas.py` (and add `Literal` to the imports: `from typing import Literal`):

```python
class NoteSearchRequest(BaseModel):
    """Semantic search body — same optional filters as the list endpoint (§6a)."""

    query: str = Field(min_length=1, max_length=500)
    note_type: NoteType | None = None
    tag: str | None = Field(default=None, max_length=32)
    novel_id: uuid.UUID | None = None
    series_id: uuid.UUID | None = None
    limit: int = Field(default=20, ge=1, le=100)


class NoteSearchHit(NoteResponse):
    """A note plus its similarity score (None in lexical mode)."""

    similarity: float | None = None


class NoteSearchResponse(BaseModel):
    """Search result with an honest mode badge (RULE-11 spirit, §6a)."""

    mode: Literal["lexical", "semantic"]
    query: str
    results: list[NoteSearchHit]
```

```python
# apps/api/narrare/notes/search_service.py
"""Semantic note search with RULE-11 lexical fallback (NOTES-001 §6a).

Flow: resolve filtered candidate note ids (lexical repository filters) →
embed the query → vector search restricted to ``source_type="note"`` and the
candidate ids → map hits back to notes with similarity scores. When no
embedding provider is configured or embedding fails, transparently fall
back to ILIKE search and report ``mode="lexical"`` — notes are ALWAYS
searchable (RULE-11). The lexical ``GET /notes?q=`` filter remains
independent (spec §6a).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.notes.schemas import (
    NoteResponse,
    NoteSearchHit,
    NoteSearchRequest,
    NoteSearchResponse,
)
from narrare_core.llm.embeddings import embed_texts
from narrare_core.settings import get_core_settings

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.embeddings.contracts import EmbeddingRepositoryProtocol
    from narrare.notes.contracts import NoteRepositoryProtocol

logger = structlog.get_logger(__name__)

#: Upper bound of candidate notes fed into the vector search after filtering.
_MAX_FILTER_CANDIDATES = 500


class NoteSearchService:
    """Business logic for note search (semantic + lexical fallback)."""

    def __init__(
        self,
        notes_repo: NoteRepositoryProtocol,
        embedding_repo: EmbeddingRepositoryProtocol,
        *,
        model: str | None = None,
    ) -> None:
        self._notes_repo = notes_repo
        self._embedding_repo = embedding_repo
        # Default model owned by CoreSettings (ADR-071 §3).
        self._model = model or get_core_settings().default_embedding_model

    async def search(
        self, user_id: UUID, request: NoteSearchRequest
    ) -> NoteSearchResponse:
        """Search notes semantically; degrade lexically on embedding failure."""
        candidates = await self._notes_repo.list_notes(
            user_id,
            note_type=request.note_type.value if request.note_type else None,
            tag=request.tag,
            novel_id=request.novel_id,
            series_id=request.series_id,
            q=None,
            limit=_MAX_FILTER_CANDIDATES,
        )
        if not candidates:
            return await self._lexical(user_id, request)

        try:
            vectors = await embed_texts([request.query], model=self._model)
        except Exception as exc:
            logger.warning("note_semantic_search_fallback", error=str(exc))
            return await self._lexical(user_id, request)

        rows = await self._embedding_repo.search(
            vectors[0],
            source_type="note",
            source_ids={n.id for n in candidates},
            limit=request.limit,
        )
        by_id = {n.id: n for n in candidates}
        hits: list[NoteSearchHit] = []
        for row in rows:
            note = by_id.get(row.embedding.source_id)
            if note is None:
                continue
            hits.append(
                NoteSearchHit(
                    **NoteResponse.model_validate(note).model_dump(),
                    similarity=row.similarity,
                )
            )
        return NoteSearchResponse(mode="semantic", query=request.query, results=hits)

    async def _lexical(
        self, user_id: UUID, request: NoteSearchRequest
    ) -> NoteSearchResponse:
        """ILIKE fallback over the same filters — always available (RULE-11)."""
        notes = await self._notes_repo.list_notes(
            user_id,
            note_type=request.note_type.value if request.note_type else None,
            tag=request.tag,
            novel_id=request.novel_id,
            series_id=request.series_id,
            q=request.query,
            limit=request.limit,
        )
        results = [
            NoteSearchHit(**NoteResponse.model_validate(n).model_dump(), similarity=None)
            for n in notes
        ]
        return NoteSearchResponse(mode="lexical", query=request.query, results=results)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/api/notes/test_search_service.py tests/unit/api/notes/test_schemas.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/notes/search_service.py apps/api/narrare/notes/schemas.py tests/unit/api/notes/test_search_service.py
git commit -m "feat(notes): add semantic search service with RULE-11 lexical fallback"
```

---

### Task 11: API — search route + wiring + integration tests

**Spec slice:** §9.4 · §5 (`POST /api/v1/notes/search`).

**Files:**
- Modify: `apps/api/narrare/notes/router.py` (add `POST /search`)
- Modify: `apps/api/narrare/notes/dependencies.py` (add `get_note_search_service`)
- Test: `tests/integration/test_notes_api.py` (append `TestSearch`)

**Interfaces:**
- Consumes: `NoteSearchService`, search schemas (T10).
- Produces: `POST /api/v1/notes/search` → `NoteSearchResponse`; `def get_note_search_service(session: SessionDep) -> NoteSearchService`.

- [ ] **Step 1: Write the failing integration tests (append to test_notes_api.py)**

```python
class TestSearch:
    async def test_search_without_provider_returns_lexical_mode(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """RULE-11 regression: no embedding provider → lexical, no 500."""
        await client.post(
            "/api/v1/notes", json={"content": "The aunt is the culprit"}, headers=auth_headers
        )
        response = await client.post(
            "/api/v1/notes/search", json={"query": "aunt"}, headers=auth_headers
        )
        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "lexical"
        assert [r["content"] for r in body["results"]] == ["The aunt is the culprit"]
        assert body["results"][0]["similarity"] is None

    async def test_search_respects_type_filter(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        await client.post(
            "/api/v1/notes", json={"content": "alpha", "note_type": "question"}, headers=auth_headers
        )
        await client.post(
            "/api/v1/notes", json={"content": "beta", "note_type": "idea"}, headers=auth_headers
        )
        response = await client.post(
            "/api/v1/notes/search",
            json={"query": "a", "note_type": "idea"},
            headers=auth_headers,
        )
        assert [r["content"] for r in response.json()["results"]] == ["beta"]

    async def test_search_empty_query_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            "/api/v1/notes/search", json={"query": ""}, headers=auth_headers
        )
        assert response.status_code == 422

    async def test_search_without_auth_returns_401(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/notes/search", json={"query": "x"})
        assert response.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_notes_api.py::TestSearch -v`
Expected: FAIL — 404/405 (route missing).

- [ ] **Step 3: Implement route + wiring**

In `apps/api/narrare/notes/router.py` — add imports (`NoteSearchRequest`, `NoteSearchResponse` to the schemas import; `get_note_search_service` to the dependencies import; `NoteSearchService` to the `TYPE_CHECKING` import) and insert this route directly after `create_note` (literal path, before the `/{note_id}` routes):

```python
@router.post("/search", response_model=NoteSearchResponse)
async def search_notes(
    request: NoteSearchRequest,
    user_id: CurrentUserIdDep = None,
    service: NoteSearchService = Depends(get_note_search_service),
) -> NoteSearchResponse:
    """Semantic search with honest lexical fallback (spec §6a)."""
    return await service.search(uuid.UUID(user_id), request)
```

Append to `apps/api/narrare/notes/dependencies.py` (and add `NoteSearchService` to its `TYPE_CHECKING` imports):

```python
def get_note_search_service(session: SessionDep) -> NoteSearchService:
    """Production wiring for the search service (notes + embeddings repos)."""
    from narrare.embeddings.repository import EmbeddingRepository
    from narrare.notes.repository import NoteRepository
    from narrare.notes.search_service import NoteSearchService

    return NoteSearchService(NoteRepository(session), EmbeddingRepository(session))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_notes_api.py -v`
Expected: PASS (all classes including the earlier CRUD ones)

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/notes/router.py apps/api/narrare/notes/dependencies.py tests/integration/test_notes_api.py
git commit -m "feat(notes): add POST /notes/search endpoint with mode-aware response"
```

---

### Task 12: DB — migration 0042: `chat_conversations.project_id` nullable

**Spec slice:** §9.5 (Chat integration) · §6b · §10 risk ("project_id optionalization").

**Files:**
- Create: `apps/api/alembic/versions/0042_chat_project_optional.py`
- Modify: `apps/api/narrare/chat/models.py` (`project_id` column → nullable)
- Test: `tests/integration/test_migration_0042_round_trip.py`

**Interfaces:**
- Consumes: `chat_conversations` table (0025); `ChatConversation` model.
- Produces (used by T14): `chat_conversations.project_id` nullable at head.

- [ ] **Step 1: Write the failing round-trip test**

```python
# tests/integration/test_migration_0042_round_trip.py
"""Round-trip test for migration 0042 (NOTES-001 — chat project optional).

Verifies: at head, a conversation with NULL project_id can be inserted
(global notes chat, spec §6b); downgrading to 0041 removes project-less
conversations and their messages (documented data loss — meaningless without
the feature) and restores NOT NULL; re-upgrading re-allows NULL.
"""

from __future__ import annotations

import os
import subprocess
import uuid as _uuid
from pathlib import Path

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine
from sqlalchemy.pool import NullPool as _NullPool

_PARENT_REVISION = "0041_notes"


def _alembic_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "apps" / "api" / "alembic"


def _run_alembic(*args: str) -> None:
    alembic_dir = _alembic_dir()
    alembic_ini = alembic_dir.parent / "alembic.ini"
    db_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://narrare:narrare@localhost:5433/narrare_test",
    )
    env = {**os.environ, "DATABASE_URL": db_url, "PGOPTIONS": "-c lock_timeout=10s"}
    subprocess.run(
        [
            "python",
            "-m",
            "alembic",
            "-c",
            str(alembic_ini) if alembic_ini.exists() else "alembic.ini",
            *args,
        ],
        env=env,
        cwd=alembic_dir.parent,
        check=True,
        capture_output=True,
    )


@pytest.mark.schema_mutating
class TestMigration0042RoundTrip:
    async def test_null_project_conversation_survives_up_and_down(self) -> None:
        db_url = os.environ.get(
            "TEST_DATABASE_URL",
            "postgresql+asyncpg://narrare:narrare@localhost:5433/narrare_test",
        )
        _run_alembic("upgrade", "head")

        user_id = _uuid.uuid4()
        conv_id = _uuid.uuid4()
        eng = _create_async_engine(db_url, poolclass=_NullPool)
        try:
            async with eng.begin() as conn:
                await conn.execute(
                    sqlalchemy.text(
                        "INSERT INTO users (id, email, hashed_password, created_at, updated_at) "
                        "VALUES (:id, :email, 'fake_hash', now(), now())"
                    ),
                    {"id": user_id, "email": f"u-{user_id.hex[:10]}@example.com"},
                )
                await conn.execute(
                    sqlalchemy.text(
                        "INSERT INTO chat_conversations (id, project_id, user_id) "
                        "VALUES (:id, NULL, :uid)"
                    ),
                    {"id": conv_id, "uid": user_id},
                )
        finally:
            await eng.dispose()

        try:
            # Downgrade removes project-less conversations, restores NOT NULL.
            _run_alembic("downgrade", _PARENT_REVISION)
            eng = _create_async_engine(db_url, poolclass=_NullPool)
            try:
                async with eng.begin() as conn:
                    count = (
                        await conn.execute(
                            sqlalchemy.text(
                                "SELECT COUNT(*) FROM chat_conversations WHERE id = :id"
                            ),
                            {"id": conv_id},
                        )
                    ).scalar()
                    assert count == 0, "project-less conversations removed on downgrade"
            finally:
                await eng.dispose()

            _run_alembic("upgrade", "head")
        finally:
            # Safety net: ALWAYS leave the shared test DB at head.
            _run_alembic("upgrade", "head")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/integration/test_migration_0042_round_trip.py -v -m schema_mutating`
Expected: FAIL — `IntegrityError` on the NULL-project insert (column still NOT NULL).

- [ ] **Step 3: Write the migration + model change**

```python
# apps/api/alembic/versions/0042_chat_project_optional.py
"""chat_conversations.project_id becomes nullable (NOTES-001 §6b).

Global notes have no project; chatting about them requires conversations
without a novel reference. This is the ONLY deliberate change to existing
chat behavior in NOTES-001 (spec §10) and is backward compatible: requests
carrying project_id behave exactly as before.

Downgrade data policy: project-less conversations (and their messages) are
DELETED before the NOT NULL restore — mirroring the 0037 pattern of removing
feature-dependent rows before constraint restoration; without the feature
they have no meaningful scope.

RULE-14: lands in the SAME task batch as the ChatConversation model change.

Revision ID: 0042_chat_project_optional
Revises: 0041_notes
Create Date: 2026-08-21 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0042_chat_project_optional"
down_revision: str | None = "0041_notes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("chat_conversations", "project_id", nullable=True)


def downgrade() -> None:
    # Remove rows the restored constraint would reject (documented data loss).
    op.execute(
        "DELETE FROM chat_messages WHERE conversation_id IN "
        "(SELECT id FROM chat_conversations WHERE project_id IS NULL)"
    )
    op.execute("DELETE FROM chat_conversations WHERE project_id IS NULL")
    op.alter_column("chat_conversations", "project_id", nullable=False)
```

In `apps/api/narrare/chat/models.py` (RULE-14 — same batch), change the `project_id` column of `ChatConversation` to:

```python
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("novels.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_migration_0042_round_trip.py -v -m schema_mutating && uv run pytest tests/unit/api/chat/ -v`
Expected: PASS (round trip + existing chat unit suite still green).

- [ ] **Step 5: Commit**

```bash
git add apps/api/alembic/versions/0042_chat_project_optional.py apps/api/narrare/chat/models.py tests/integration/test_migration_0042_round_trip.py
git commit -m "feat(chat): make chat_conversations.project_id nullable for project-less notes chat (0042)"
```

---

### Task 13: Core — ChatRequest dataclass + ConversationStore ABC accept optional project

**Spec slice:** §9.5 · §6b.

**Files:**
- Modify: `packages/core/narrare_core/chat/contracts.py` (`ChatRequest`)
- Modify: `packages/core/narrare_core/chat/conversation_store.py` (`create_conversation` abstract signature — the `InMemoryConversationStore` in the same file inherits the change)
- Test: `tests/unit/core/chat/test_contracts.py` (new)

**Interfaces:**
- Consumes: existing core chat contracts.
- Produces (used by T14–T16):
  - `ChatRequest` dataclass: `project_id: UUID | None = None`, `message: str = ""`, `conversation_id: UUID | None = None`, `note_id: UUID | None = None`
  - `ConversationStore.create_conversation(self, project_id: UUID | None, user_id: UUID, first_message: str) -> UUID` (abstract)

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/core/chat/test_contracts.py
"""Unit tests for core chat contracts after NOTES-001 §6b changes."""

from __future__ import annotations

import inspect
from uuid import uuid4

from narrare_core.chat.contracts import ChatRequest


class TestChatRequestOptionals:
    def test_legacy_positional_shape_still_works(self) -> None:
        """Regression: existing callers pass (project_id, message) positionally."""
        project_id = uuid4()
        request = ChatRequest(project_id, "hello")
        assert request.project_id == project_id
        assert request.message == "hello"
        assert request.conversation_id is None
        assert request.note_id is None

    def test_projectless_request_for_global_note_chat(self) -> None:
        request = ChatRequest(message="discuss this", note_id=uuid4())
        assert request.project_id is None
        assert request.note_id is not None

    def test_all_defaults_construct(self) -> None:
        request = ChatRequest()
        assert request.project_id is None
        assert request.message == ""


class TestConversationStoreSignature:
    def test_abstract_create_conversation_accepts_none_project(self) -> None:
        """The ABC must allow project-less conversations (NOTES-001 §6b)."""
        from narrare_core.chat.conversation_store import ConversationStore

        annotation = inspect.signature(
            ConversationStore.create_conversation
        ).parameters["project_id"].annotation
        assert "None" in annotation or "Optional" in annotation
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/core/chat/test_contracts.py -v`
Expected: FAIL — `ChatRequest() missing 2 required positional arguments` / annotation assertion.

- [ ] **Step 3: Apply the changes**

In `packages/core/narrare_core/chat/contracts.py`, replace the `ChatRequest` dataclass:

```python
@dataclass
class ChatRequest:
    """Request to send a chat message.

    ``project_id`` is optional since NOTES-001: chatting about a global note
    has no project (KB/project context tiers are skipped then). ``note_id``
    attaches a scratchpad note as runtime context (spec §6b).
    """

    project_id: UUID | None = None
    message: str = ""
    conversation_id: UUID | None = None
    note_id: UUID | None = None
```

(The `UUID` import stays behind `TYPE_CHECKING` — dataclass annotations are strings under `from __future__ import annotations`.)

In `packages/core/narrare_core/chat/conversation_store.py`, change the abstract `create_conversation` signature to:

```python
    async def create_conversation(
        self,
        project_id: UUID | None,
        user_id: UUID,
        first_message: str,
    ) -> UUID:
```

and extend its docstring with: "``project_id`` may be ``None`` for project-less conversations (NOTES-001 §6b)."

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/core/chat/ -v && uv run pytest tests/unit/api/chat/ -v`
Expected: PASS (core chat suite + backend chat suite — the API-level `ChatRequest` is unchanged at this point).

- [ ] **Step 5: Commit**

```bash
git add packages/core/narrare_core/chat/contracts.py packages/core/narrare_core/chat/conversation_store.py tests/unit/core/chat/test_contracts.py
git commit -m "feat(chat): core ChatRequest gains optional project_id and note_id (NOTES-001)"
```

---

### Task 14: API — chat schemas (`project_id` optional, `note_id`) + router passthrough

**Spec slice:** §9.5 · §6b · §8 ("legacy requests unchanged").

**Files:**
- Modify: `apps/api/narrare/chat/schemas.py` (`ChatRequest`, `ChatHistoryResponse.project_id`)
- Modify: `apps/api/narrare/chat/router.py` (core conversion + history response)
- Test: `tests/unit/api/chat/test_chat_schemas.py` (extend)

**Interfaces:**
- Consumes: core `ChatRequest` (T13).
- Produces (used by T24 — the frontend chat API): API `ChatRequest` with `project_id: UUID | None = None`, `note_id: UUID | None = None`; `ChatHistoryResponse.project_id: UUID | None = None`.

- [ ] **Step 1: Write the failing tests (append to tests/unit/api/chat/test_chat_schemas.py)**

```python
class TestChatRequestNotesExtension:
    """NOTES-001 §6b: project_id optional + note_id context attachment."""

    def test_legacy_request_with_project_unchanged(self) -> None:
        """Regression: the pre-NOTES-001 shape validates identically."""
        project_id = uuid4()
        req = ChatRequest(project_id=project_id, message="How do I write dialogue?")
        assert req.project_id == project_id
        assert req.note_id is None

    def test_projectless_request_valid(self) -> None:
        req = ChatRequest(message="Discuss this global note")
        assert req.project_id is None

    def test_note_id_optional(self) -> None:
        note_id = uuid4()
        req = ChatRequest(message="Discuss", note_id=note_id)
        assert req.note_id == note_id


class TestChatHistoryResponseOptionalProject:
    def test_project_id_may_be_none(self) -> None:
        resp = ChatHistoryResponse(
            conversation_id=uuid4(),
            project_id=None,
            messages=[],
        )
        assert resp.project_id is None
```

(`ChatHistoryResponse` must be added to the file's existing import from `narrare.chat.schemas` — it is already imported there.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/api/chat/test_chat_schemas.py -v`
Expected: FAIL — `ChatRequest` still requires `project_id` (422-equivalent `ValidationError`).

- [ ] **Step 3: Apply the changes**

In `apps/api/narrare/chat/schemas.py`:

```python
class ChatRequest(BaseModel):
    """Request to send a chat message.

    Extends the core ``ChatRequestSchema`` with FastAPI-specific validation.
    ``project_id`` is optional since NOTES-001 (global notes have no
    project); ``note_id`` attaches a scratchpad note as runtime context.
    """

    project_id: UUID | None = Field(
        default=None,
        description="Project (novel) scope. Omit for project-less chat (e.g. global notes).",
    )
    message: str = Field(
        min_length=1,
        max_length=4000,
        description="The user's chat message (1-4000 characters).",
    )
    conversation_id: UUID | None = Field(
        default=None,
        description="Existing conversation ID. Omit to start a new conversation.",
    )
    note_id: UUID | None = Field(
        default=None,
        description="Scratchpad note attached as runtime context (NOTES-001 §6b).",
    )
```

and in `ChatHistoryResponse` change `project_id: UUID` to `project_id: UUID | None = None`.

In `apps/api/narrare/chat/router.py`, update the core conversion (lines ~53–60):

```python
    core_request = CoreChatRequest(
        project_id=request.project_id,
        message=request.message,
        conversation_id=request.conversation_id,
        note_id=request.note_id,
    )
```

and the history response (lines ~99–111) — replace the `UUID(int=0)` fallback with the honest nullable value:

```python
    return ChatHistoryResponse(
        conversation_id=conversation_id,
        project_id=project_id,
        messages=[
            ChatMessageSchema(
                message_id=m.conversation_id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/api/chat/ -v`
Expected: PASS (the existing `TestGetHistoryEndpointProjectId` tests simulate the router pattern themselves and remain valid).

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/chat/schemas.py apps/api/narrare/chat/router.py tests/unit/api/chat/test_chat_schemas.py
git commit -m "feat(chat): ChatRequest gains optional project_id and note_id; history exposes nullable project"
```

---

### Task 15: API — conversation store + ChatService project-less flow

**Spec slice:** §9.5 · §6b ("without project_id, KB/project context tiers are skipped").

**Files:**
- Modify: `apps/api/narrare/chat/conversation_store.py` (`create_conversation` accepts `None`)
- Modify: `apps/api/narrare/chat/chat_service.py` (`_stream_agent_response` accepts `UUID | None`; skip invocation enrichment when project-less)
- Test: `tests/unit/api/chat/test_chat_service_projectless.py` (new; reuses the conftest fixtures `service`, `in_memory_store`, `mock_composer`, `mock_registry`, `mock_config`)

**Interfaces:**
- Consumes: core ABC signature (T13); nullable DB column (T12); core `ChatRequest` (T13).
- Produces (used by T16): ChatService.ask works with `project_id=None` (note injection itself lands in T16).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/api/chat/test_chat_service_projectless.py
"""Unit tests for project-less chat flow (NOTES-001 §6b).

Without project_id the service must still create a conversation, compose a
prompt, and stream a response — KB/project enrichment is skipped. Uses the
shared fixtures from tests/unit/api/chat/conftest.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from narrare_core.chat.contracts import ChatRequest

if TYPE_CHECKING:
    from narrare.chat.chat_service import ChatService
    from narrare_core.chat.conversation_store import InMemoryConversationStore


class TestProjectlessAsk:
    async def test_ask_without_project_creates_conversation_and_streams(
        self,
        service: object,
        in_memory_store: object,
    ) -> None:
        user_id = uuid4()
        request = ChatRequest(message="Craft question without a project")

        events = []
        stream = await cast("ChatService", service).ask(request, user_id)
        async for event in stream:
            events.append(event)

        assert events[0]["type"] == "meta"
        conv_id = UUID(str(events[0]["conversation_id"]))
        assert events[-1]["type"] == "done"

        # The conversation persists with a NULL project.
        stored_project = await cast("InMemoryConversationStore", (
            in_memory_store
        )).get_conversation_project_id(conv_id)
        assert stored_project is None

    async def test_ask_with_project_still_enriches(
        self,
        service: object,
        in_memory_store: object,
    ) -> None:
        """Regression: legacy project-scoped flow unchanged."""
        user_id = uuid4()
        project_id = uuid4()
        request = ChatRequest(project_id=project_id, message="Hello")

        events = []
        stream = await cast("ChatService", service).ask(request, user_id)
        async for event in stream:
            events.append(event)

        conv_id = UUID(str(events[0]["conversation_id"]))
        stored_project = await cast("InMemoryConversationStore", (
            in_memory_store
        )).get_conversation_project_id(conv_id)
        assert stored_project == project_id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/api/chat/test_chat_service_projectless.py -v`
Expected: FAIL — the store's `create_conversation`/`ChatConversation(project_id=None)` path raises (ORM column still typed NOT NULL in the model — T12 already made it nullable, so the actual failure here is the service passing `request.project_id` typed as `UUID`; the failing assertion is `stored_project is None` because `InMemoryConversationStore` is unchanged only in annotation — verify the failure mode is the missing project-less support and fix forward).

- [ ] **Step 3: Apply the changes**

In `apps/api/narrare/chat/conversation_store.py`, relax the SQLAlchemy store signature:

```python
    async def create_conversation(
        self,
        project_id: UUID | None,
        user_id: UUID,
        first_message: str,
    ) -> UUID:
        """Create a new conversation and add the first message.

        ``project_id`` may be ``None`` for project-less conversations
        (NOTES-001 §6b — the column is nullable since migration 0042).
        """
```

(body unchanged — `ChatConversationModel(project_id=project_id, …)` already forwards `None`.)

In `apps/api/narrare/chat/chat_service.py`:

1. `_stream_agent_response` signature: `project_id: UUID | None` (update its docstring: "``None`` for project-less conversations — invocation enrichment is skipped").
2. Inside `_stream_agent_response`, skip project-correlated enrichment when project-less (documented no-op path in `compose_chat_invocation`):

```python
        # NOTES-001 §6b: without a project there is nothing to correlate —
        # pass no pipeline so compose_chat_invocation takes its documented
        # no-op path (backward compatible).
        effective_context = await compose_chat_invocation(
            invocation_pipeline=self._invocation_pipeline if project_id is not None else None,
            prompt_ctx=context,
            user_id=user_id,
            project_id=project_id,
            conv_id=conv_id,
            invocation_id=invocation_id,
        )
```

(`ask()` itself already forwards `request.project_id` — no change needed there beyond what exists.)

Also relax `compose_chat_invocation`'s `project_id` annotation in `apps/api/narrare/chat/_invocation.py` to `UUID | None` (annotation-only change; the None case never reaches it because the pipeline is `None` then — this keeps the type checker honest).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/api/chat/ -v`
Expected: PASS (all chat unit tests, old and new).

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/chat/conversation_store.py apps/api/narrare/chat/chat_service.py apps/api/narrare/chat/_invocation.py tests/unit/api/chat/test_chat_service_projectless.py
git commit -m "feat(chat): support project-less conversations end to end (NOTES-001)"
```

---

### Task 16: API — note context injection into chat + wiring

**Spec slice:** §9.5 · §6b (note as runtime context block, RULE-02-safe).

**Files:**
- Modify: `apps/api/narrare/chat/chat_service.py` (note lookup + context block)
- Modify: `apps/api/narrare/chat/dependencies.py` (inject `NoteLookupProtocol`)
- Test: `tests/unit/api/notes/../chat/test_chat_service_note.py` → create as `tests/unit/api/chat/test_chat_service_note.py`

**Interfaces:**
- Consumes: `NoteLookupProtocol`, `format_note_context_block`, `NoteSnapshot` (T2); core `ChatRequest.note_id` (T13); `get_note_service` (T8).
- Produces: `ChatService.__init__(…, note_lookup: NoteLookupProtocol | None = None)`; behavior: note text prepended to the persisted user message and the composer `user_prompt` (runtime-input channel).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/api/chat/test_chat_service_note.py
"""Unit tests for note context injection into chat (NOTES-001 §6b, RULE-02).

The note must travel as RUNTIME INPUT: the context block appears in the
persisted user message and in the composer's user_prompt — never in a
system/task template. A missing/unowned note degrades gracefully (warn +
proceed, RULE-11).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from narrare_core.chat.contracts import ChatRequest
from narrare_core.notes.contracts import NoteSnapshot

if TYPE_CHECKING:
    from narrare.chat.chat_service import ChatService
    from narrare_core.chat.conversation_store import InMemoryConversationStore


class FakeNoteLookup:
    """NoteLookupProtocol double with one owned note."""

    def __init__(self, snapshot: NoteSnapshot | None) -> None:
        self._snapshot = snapshot
        self.calls: list[tuple[object, object]] = []

    async def get_note_snapshot(self, note_id: object, user_id: object) -> NoteSnapshot | None:
        self.calls.append((note_id, user_id))
        return self._snapshot


def _make_snapshot(note_id: UUID) -> NoteSnapshot:
    return NoteSnapshot(
        id=note_id,
        title="Twist",
        content="The aunt is the culprit.",
        note_type="idea",
        tags=["plot"],
    )


def _make_service(
    mock_composer: object,
    mock_registry: object,
    in_memory_store: object,
    mock_config: object,
    lookup: FakeNoteLookup,
) -> "ChatService":
    from narrare.chat.chat_service import ChatService

    return ChatService(
        prompt_composer=cast("object", mock_composer),  # type: ignore[arg-type]
        model_registry=cast("object", mock_registry),  # type: ignore[arg-type]
        conversation_store=cast("object", in_memory_store),  # type: ignore[arg-type]
        config=cast("object", mock_config),  # type: ignore[arg-type]
        note_lookup=lookup,
    )


class TestNoteInjection:
    async def test_note_block_prepended_to_persisted_user_message(
        self,
        mock_composer: object,
        mock_registry: object,
        in_memory_store: object,
        mock_config: object,
    ) -> None:
        note_id = uuid4()
        service = _make_service(
            mock_composer, mock_registry, in_memory_store, mock_config,
            FakeNoteLookup(_make_snapshot(note_id)),
        )
        user_id = uuid4()
        request = ChatRequest(message="What do you think?", note_id=note_id)

        events = []
        stream = await service.ask(request, user_id)
        async for event in stream:
            events.append(event)

        history = await cast("InMemoryConversationStore", in_memory_store).get_history(
            UUID(str(events[0]["conversation_id"]))
        )
        user_messages = [m for m in history if m.role == "user"]
        assert len(user_messages) == 1
        assert user_messages[0].content.startswith("[Note — idea [plot]]")
        assert "The aunt is the culprit." in user_messages[0].content
        assert user_messages[0].content.endswith("What do you think?")

    async def test_user_prompt_passed_to_composer_contains_note(
        self,
        in_memory_store: object,
        mock_registry: object,
        mock_config: object,
    ) -> None:
        from tests.unit.api.chat.conftest import _make_mock_composer

        composer = _make_mock_composer()
        note_id = uuid4()
        service = _make_service(
            composer, mock_registry, in_memory_store, mock_config,
            FakeNoteLookup(_make_snapshot(note_id)),
        )
        request = ChatRequest(message="Discuss", note_id=note_id)

        stream = await service.ask(request, uuid4())
        async for _event in stream:
            pass

        composer.build.assert_called()
        kwargs = composer.build.call_args.kwargs
        assert kwargs["user_prompt"].startswith("[Note — idea [plot]]")

    async def test_missing_note_degrades_gracefully(
        self,
        mock_composer: object,
        mock_registry: object,
        in_memory_store: object,
        mock_config: object,
    ) -> None:
        service = _make_service(
            mock_composer, mock_registry, in_memory_store, mock_config,
            FakeNoteLookup(None),
        )
        request = ChatRequest(message="Discuss", note_id=uuid4())

        events = []
        stream = await service.ask(request, uuid4())
        async for event in stream:
            events.append(event)

        assert events[0]["type"] == "meta"  # no raise — RULE-11

    async def test_no_note_id_no_lookup(
        self,
        mock_composer: object,
        mock_registry: object,
        in_memory_store: object,
        mock_config: object,
    ) -> None:
        lookup = FakeNoteLookup(_make_snapshot(uuid4()))
        service = _make_service(
            mock_composer, mock_registry, in_memory_store, mock_config, lookup
        )
        request = ChatRequest(message="Just chatting")

        stream = await service.ask(request, uuid4())
        async for _event in stream:
            pass

        assert lookup.calls == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/api/chat/test_chat_service_note.py -v`
Expected: FAIL — `ChatService.__init__() got an unexpected keyword argument 'note_lookup'`.

- [ ] **Step 3: Apply the changes**

In `apps/api/narrare/chat/chat_service.py`:

1. Constructor gains the optional dependency:

```python
    def __init__(
        self,
        prompt_composer: PromptComposer,
        model_registry: ModelRegistry,
        conversation_store: SQLAlchemyConversationStore,
        config: ResolvedModelConfig,
        invocation_pipeline: InvocationPipeline | None = None,
        run_limit_resolver: DefaultRunLimitResolver | None = None,
        note_lookup: NoteLookupProtocol | None = None,
    ) -> None:
```

(store as `self._note_lookup = note_lookup`; add `from narrare_core.notes.contracts import NoteLookupProtocol, format_note_context_block` to the module imports — a core-contract import, no cross-repository access, spec §6b).

2. In `ask()`, resolve the note and build the effective message BEFORE persistence:

```python
        # NOTES-001 §6b: attach the note as RUNTIME INPUT (user-message
        # channel) — never as a prompt template (RULE-02). A missing or
        # unowned note degrades gracefully (warn + proceed, RULE-11).
        message = request.message
        if request.note_id is not None:
            snapshot = None
            if self._note_lookup is not None:
                snapshot = await self._note_lookup.get_note_snapshot(
                    request.note_id, user_id
                )
            if snapshot is not None:
                message = f"{format_note_context_block(snapshot)}\n\n{request.message}"
            else:
                logger.warning(
                    "chat_note_unavailable",
                    note_id=str(request.note_id),
                )
```

then use `message` everywhere `request.message` was used in `ask()`: `create_conversation(..., message)`, `add_message(conv_id, "user", message)`, `composer.build(..., user_prompt=message)`, and the `_stream_agent_response(..., message, ...)` call (`user_prompt` parameter).

In `apps/api/narrare/chat/dependencies.py`, wire the lookup (wiring-level import of the notes service — precedented by `narrare.novels.router` importing `narrare.volumes.repository`):

```python
    from narrare.notes.dependencies import get_note_service

    return ChatService(
        prompt_composer=composer,
        model_registry=registry,
        conversation_store=store,
        config=config,
        invocation_pipeline=invocation_pipeline,
        run_limit_resolver=run_limit_resolver,
        note_lookup=get_note_service(session),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/api/chat/ tests/unit/api/notes/ -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add apps/api/narrare/chat/chat_service.py apps/api/narrare/chat/dependencies.py tests/unit/api/chat/test_chat_service_note.py
git commit -m "feat(chat): inject scratchpad note as runtime context block (NOTES-001, RULE-02-safe)"
```

---

### Task 17: Web — note types + API client

**Spec slice:** §7 (Tech: typed API wrappers). Not UI code — no frontend-design skill needed for this task.

**Files:**
- Create: `packages/web/types/notes.ts`
- Modify: `packages/web/types/index.ts` (barrel re-export)
- Create: `packages/web/lib/api/notes.ts`

**Interfaces:**
- Consumes: `fetchApi<T>(endpoint, options)` from `@/lib/api/core` (existing; prefixes `/api/v1`, injects auth).
- Produces (used by T18+):
  - Types: `NoteTypeKey`, `Note`, `NoteCreate`, `NoteUpdate`, `NoteListParams`, `NoteTagsResponse`, `NoteSearchMode`, `NoteSearchHit`, `NoteSearchRequest`, `NoteSearchResponse`; helpers `noteDisplayTitle(note)`, `NOTE_TYPE_KEYS`
  - `notesApi` object: `list(params?)`, `get(id)`, `create(body)`, `update(id, body)`, `delete(id)`, `tags(q?)`, `search(body)`

- [ ] **Step 1: Write the types + client**

```typescript
// packages/web/types/notes.ts
/**
 * Scratchpad note types (NOTES-001).
 *
 * Mirrors apps/api/narrare/notes/schemas.py. `title` is the stored
 * (possibly null) title — use `noteDisplayTitle` for display (spec §4:
 * empty title → first content line).
 */

export type NoteTypeKey = "idea" | "concept" | "question" | "other";

export const NOTE_TYPE_KEYS: readonly NoteTypeKey[] = [
  "idea",
  "concept",
  "question",
  "other",
] as const;

export interface Note {
  readonly id: string;
  readonly title: string | null;
  readonly content: string;
  readonly note_type: NoteTypeKey;
  readonly tags: readonly string[];
  readonly novel_id: string | null;
  readonly series_id: string | null;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface NoteCreate {
  title?: string | null;
  content: string;
  note_type?: NoteTypeKey;
  tags?: string[];
  novel_id?: string | null;
  series_id?: string | null;
}

export type NoteUpdate = Partial<NoteCreate>;

export interface NoteListParams {
  note_type?: NoteTypeKey;
  tag?: string;
  novel_id?: string;
  series_id?: string;
  q?: string;
  limit?: number;
  offset?: number;
}

export interface NoteTagsResponse {
  readonly tags: string[];
}

export type NoteSearchMode = "lexical" | "semantic";

export interface NoteSearchHit extends Note {
  readonly similarity: number | null;
}

export interface NoteSearchRequest {
  query: string;
  note_type?: NoteTypeKey;
  tag?: string;
  novel_id?: string;
  series_id?: string;
  limit?: number;
}

export interface NoteSearchResponse {
  readonly mode: NoteSearchMode;
  readonly query: string;
  readonly results: NoteSearchHit[];
}

/** Display title: the stored title, or the first non-empty content line. */
export function noteDisplayTitle(note: Pick<Note, "title" | "content">): string {
  if (note.title && note.title.trim()) return note.title;
  const firstLine = note.content
    .split("\n")
    .find((line) => line.trim());
  return firstLine ? firstLine.trim().slice(0, 200) : "";
}
```

Add to `packages/web/types/index.ts` (barrel, follows the existing `export type { … } from "./series"` blocks):

```typescript
// Scratchpad notes (NOTES-001)
export type {
  Note,
  NoteCreate,
  NoteListParams,
  NoteSearchHit,
  NoteSearchMode,
  NoteSearchRequest,
  NoteSearchResponse,
  NoteTagsResponse,
  NoteTypeKey,
  NoteUpdate,
} from "./notes";
export { NOTE_TYPE_KEYS, noteDisplayTitle } from "./notes";
```

```typescript
// packages/web/lib/api/notes.ts
/**
 * Notes API client (NOTES-001).
 *
 * Typed wrappers around apps/api/narrare/notes/router.py: CRUD, filters,
 * tag autocomplete, semantic search with lexical fallback. Every call goes
 * through `fetchApi` from ./core (auth-token injection, 401 auto-refresh,
 * `/api/v1` prefixing, unified error parsing).
 */

import type {
  Note,
  NoteCreate,
  NoteListParams,
  NoteSearchRequest,
  NoteSearchResponse,
  NoteTagsResponse,
  NoteUpdate,
} from "@/types";
import { fetchApi } from "./core";

function toQuery(params: NoteListParams | undefined): string {
  if (!params) return "";
  const search = new URLSearchParams();
  if (params.note_type) search.set("note_type", params.note_type);
  if (params.tag) search.set("tag", params.tag);
  if (params.novel_id) search.set("novel_id", params.novel_id);
  if (params.series_id) search.set("series_id", params.series_id);
  if (params.q) search.set("q", params.q);
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  if (params.offset !== undefined) search.set("offset", String(params.offset));
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export const notesApi = {
  /** GET /notes — filtered list, updated_at DESC. */
  list: (params?: NoteListParams) => fetchApi<Note[]>(`/notes${toQuery(params)}`),

  /** GET /notes/{id} */
  get: (noteId: string) => fetchApi<Note>(`/notes/${noteId}`),

  /** POST /notes — used by quick capture AND the full editor. */
  create: (body: NoteCreate) =>
    fetchApi<Note>("/notes", { method: "POST", body: JSON.stringify(body) }),

  /** PATCH /notes/{id} — explicit null clears a field. */
  update: (noteId: string, body: NoteUpdate) =>
    fetchApi<Note>(`/notes/${noteId}`, { method: "PATCH", body: JSON.stringify(body) }),

  /** DELETE /notes/{id} */
  delete: (noteId: string) => fetchApi<void>(`/notes/${noteId}`, { method: "DELETE" }),

  /** GET /notes/tags — distinct existing tags, optional prefix. */
  tags: (q?: string) =>
    fetchApi<NoteTagsResponse>(`/notes/tags${q ? `?q=${encodeURIComponent(q)}` : ""}`),

  /** POST /notes/search — semantic with honest lexical fallback. */
  search: (body: NoteSearchRequest) =>
    fetchApi<NoteSearchResponse>("/notes/search", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
```

(Hooks import `notesApi` directly from `@/lib/api/notes` — the barrel `lib/api/index.ts` is intentionally left untouched to keep this task at three files.)

- [ ] **Step 2: Verify types compile**

Run: `pnpm --filter narrare-web type-check`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add packages/web/types/notes.ts packages/web/types/index.ts packages/web/lib/api/notes.ts
git commit -m "feat(web): add note types and notes API client (NOTES-001)"
```

---

### Task 18: Web — query keys + TanStack hooks

**Spec slice:** §7 (hooks list + invalidation).

**Files:**
- Create: `packages/web/lib/hooks/notesKeys.ts`
- Create: `packages/web/lib/hooks/useNotes.ts`
- Test: `packages/web/lib/hooks/__tests__/useNotes.test.tsx`

**Interfaces:**
- Consumes: `notesApi` (T17); TanStack Query (`useQuery`, `useMutation`, `useQueryClient`).
- Produces (used by T23, T26, T28):
  - `notesKeys` — `all`, `list(filters?)`, `detail(id)`, `tags(q?)`, `search(body)`
  - Hooks: `useNotes(params?)`, `useNote(id)`, `useCreateNote()`, `useUpdateNote()`, `useDeleteNote()`, `useNoteTags(q?)`, `useSemanticNoteSearch()`

- [ ] **Step 1: Write the query keys + hooks**

```typescript
// packages/web/lib/hooks/notesKeys.ts
/**
 * TanStack Query keys for the Notes domain (NOTES-001).
 *
 * Centralized (mirrors seriesKeys.ts / kbKeys.ts) so invalidations stay
 * consistent across hooks.
 *
 * Key shape:
 *   ["notes"]                    — list + wildcard prefix
 *   ["notes", "list", filters]   — filtered list
 *   ["notes", "detail", noteId]  — single note
 *   ["notes", "tags", q]         — tag autocomplete
 *   ["notes", "search", body]    — semantic search
 */

export const notesKeys = {
  all: ["notes"] as const,
  list: (filters?: object) => [...notesKeys.all, "list", filters ?? {}] as const,
  detail: (noteId: string) => [...notesKeys.all, "detail", noteId] as const,
  tags: (q?: string) => [...notesKeys.all, "tags", q ?? ""] as const,
  search: (body: object) => [...notesKeys.all, "search", body] as const,
};
```

```typescript
// packages/web/lib/hooks/useNotes.ts
"use client";

/**
 * TanStack Query hooks for scratchpad notes (NOTES-001 §7).
 *
 * - useNotes / useNote / useNoteTags — reads (disabled while ids are empty).
 * - useCreateNote / useUpdateNote / useDeleteNote — mutations invalidating
 *   the notes + tags queries.
 * - useSemanticNoteSearch — explicit-trigger search (mutation semantics),
 *   returns the honest lexical/semantic mode badge.
 *
 * Mirrors the established Narrare pattern (useBandSummary): reads use
 * useQuery; mutations use useMutation + notesKeys.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { notesApi } from "@/lib/api/notes";
import type { NoteCreate, NoteListParams, NoteSearchRequest, NoteUpdate } from "@/types";
import { notesKeys } from "./notesKeys";

/** GET /notes — filtered list. */
export function useNotes(params?: NoteListParams) {
  return useQuery({
    queryKey: notesKeys.list(params),
    queryFn: () => notesApi.list(params),
  });
}

/** GET /notes/{id} — disabled while id is empty. */
export function useNote(noteId: string) {
  return useQuery({
    queryKey: notesKeys.detail(noteId),
    queryFn: () => notesApi.get(noteId),
    enabled: !!noteId,
  });
}

/** GET /notes/tags — autocomplete source. */
export function useNoteTags(q?: string) {
  return useQuery({
    queryKey: notesKeys.tags(q),
    queryFn: () => notesApi.tags(q),
  });
}

/** POST /notes — used by the editor and quick capture. */
export function useCreateNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: NoteCreate) => notesApi.create(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: notesKeys.all });
    },
  });
}

/** PATCH /notes/{id}. */
export function useUpdateNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: NoteUpdate }) =>
      notesApi.update(id, body),
    onSuccess: (note) => {
      void queryClient.invalidateQueries({ queryKey: notesKeys.detail(note.id) });
      void queryClient.invalidateQueries({ queryKey: notesKeys.all });
    },
  });
}

/** DELETE /notes/{id}. */
export function useDeleteNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => notesApi.delete(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: notesKeys.all });
    },
  });
}

/** POST /notes/search — explicit trigger; carries the mode badge. */
export function useSemanticNoteSearch() {
  return useMutation({
    mutationFn: (body: NoteSearchRequest) => notesApi.search(body),
  });
}
```

- [ ] **Step 2: Write the tests**

```typescript
// packages/web/lib/hooks/__tests__/useNotes.test.tsx
/**
 * useNotes hook tests (NOTES-001) — MSW-backed read + invalidation cycle.
 *
 * Conventions: centralized setupTests.ts neutralizes motion and returns
 * i18n keys; the MSW guard requires handlers for every request made.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { server } from "@/mocks/server";
import { useCreateNote, useNoteTags, useNotes } from "../useNotes";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

describe("useNotes", () => {
  it("fetches the filtered note list", async () => {
    server.use(
      http.get("*/api/v1/notes", ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get("note_type")).toBe("idea");
        return HttpResponse.json([
          {
            id: "n1",
            title: null,
            content: "first line\nbody",
            note_type: "idea",
            tags: ["plot"],
            novel_id: null,
            series_id: null,
            created_at: "2026-08-21T00:00:00Z",
            updated_at: "2026-08-21T00:00:00Z",
          },
        ]);
      }),
    );

    const { result } = renderHook(() => useNotes({ note_type: "idea" }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.[0]?.note_type).toBe("idea");
  });
});

describe("useNoteTags", () => {
  it("fetches distinct tags with prefix", async () => {
    server.use(
      http.get("*/api/v1/notes/tags", ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get("q")).toBe("pl");
        return HttpResponse.json({ tags: ["plot"] });
      }),
    );

    const { result } = renderHook(() => useNoteTags("pl"), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.data?.tags).toEqual(["plot"]));
  });
});

describe("useCreateNote invalidation", () => {
  it("invalidates the notes list after create", async () => {
    let listCalls = 0;
    server.use(
      http.get("*/api/v1/notes", () => {
        listCalls += 1;
        return HttpResponse.json([]);
      }),
      http.post("*/api/v1/notes", async () =>
        HttpResponse.json(
          {
            id: "n2",
            title: null,
            content: "captured",
            note_type: "idea",
            tags: [],
            novel_id: null,
            series_id: null,
            created_at: "2026-08-21T00:00:00Z",
            updated_at: "2026-08-21T00:00:00Z",
          },
          { status: 201 },
        ),
      ),
    );

    const wrapper = createWrapper();
    const list = renderHook(() => useNotes(), { wrapper });
    await waitFor(() => expect(listCalls).toBeGreaterThanOrEqual(1));

    const create = renderHook(() => useCreateNote(), { wrapper });
    await act(async () => {
      await create.result.current.mutateAsync({ content: "captured" });
    });

    await waitFor(() => expect(listCalls).toBeGreaterThanOrEqual(2));
  });
});
```

- [ ] **Step 3: Run the tests**

Run: `pnpm --filter narrare-web test lib/hooks/__tests__/useNotes.test.tsx`
Expected: PASS (3 tests)

- [ ] **Step 4: Commit**

```bash
git add packages/web/lib/hooks/notesKeys.ts packages/web/lib/hooks/useNotes.ts packages/web/lib/hooks/__tests__/useNotes.test.tsx
git commit -m "feat(web): add TanStack Query hooks and keys for notes (NOTES-001)"
```

---

### Task 19: i18n — `notes.*` namespace in en/de/fr

**Spec slice:** §7 (i18n) · §9.8 (first half — catalogs; the registry lands in T20, docs in T30).

**Files:**
- Create: `packages/i18n/messages/en/notes.json`
- Create: `packages/i18n/messages/de/notes.json`
- Create: `packages/i18n/messages/fr/notes.json`

**Interfaces:**
- Consumes: nothing.
- Produces (used by T21–T28): the `notes.*` message tree — exact keys used by components: `notes.nav.label`, `notes.page.title`, `notes.page.subtitle`, `notes.empty.title`, `notes.empty.description`, `notes.empty.cta`, `notes.list.searchPlaceholder`, `notes.list.typeFilterLabel`, `notes.list.allTypes`, `notes.list.tagFilterLabel`, `notes.list.noResults`, `notes.list.untitled`, `notes.list.updated`, `notes.type.idea`, `notes.type.concept`, `notes.type.question`, `notes.type.other`, `notes.editor.*` (newNote, titlePlaceholder, contentLabel, contentPlaceholder, preview, edit, typeLabel, tagsLabel, tagPlaceholder, addTag, tagSuggestions, linkLabel, noLink, novelLink, seriesLink, discuss, delete, deleteTitle, deleteDescription, save, saveFailed, deleted), `notes.search.semanticToggle`, `notes.search.semanticBadge`, `notes.search.lexicalBadge`, `notes.quickCapture.*` (open, title, titlePlaceholder, textPlaceholder, tagPlaceholder, save, saved, openInScratchpad, shortcutHint), `notes.chat.attachedNote`.

- [ ] **Step 1: Write the three catalogs**

```json
// packages/i18n/messages/en/notes.json
{
  "nav": { "label": "Scratchpad" },
  "page": {
    "title": "Scratchpad",
    "subtitle": "Capture thoughts before they escape — ideas, concepts, questions."
  },
  "empty": {
    "title": "Nothing captured yet",
    "description": "Save your first thought — a plot twist, a worldbuilding idea, a craft question.",
    "cta": "Capture a thought"
  },
  "list": {
    "searchPlaceholder": "Search notes…",
    "typeFilterLabel": "Type",
    "allTypes": "All types",
    "tagFilterLabel": "Tag",
    "allTags": "All tags",
    "noResults": "No notes match these filters.",
    "untitled": "Untitled",
    "updated": "Updated {date}"
  },
  "type": { "idea": "Idea", "concept": "Concept", "question": "Question", "other": "Other" },
  "editor": {
    "newNote": "New note",
    "titlePlaceholder": "Title (optional — first line is used otherwise)",
    "contentLabel": "Note",
    "contentPlaceholder": "Write it down… (Markdown supported)",
    "preview": "Preview",
    "edit": "Edit",
    "typeLabel": "Type",
    "tagsLabel": "Tags",
    "tagPlaceholder": "Add a tag…",
    "addTag": "Add",
    "tagSuggestions": "Suggestions",
    "linkLabel": "Link (optional)",
    "noLink": "Not linked",
    "novelLink": "Linked novel",
    "seriesLink": "Linked series",
    "discuss": "Discuss in chat",
    "delete": "Delete note",
    "deleteTitle": "Delete this note?",
    "deleteDescription": "This permanently removes the note. It cannot be undone.",
    "save": "Save",
    "saveFailed": "Could not save the note.",
    "deleted": "Note deleted."
  },
  "search": {
    "semanticToggle": "Semantic",
    "semanticBadge": "semantic",
    "lexicalBadge": "lexical"
  },
  "quickCapture": {
    "open": "Quick capture",
    "title": "Capture a thought",
    "titlePlaceholder": "Title (optional)",
    "textPlaceholder": "What's on your mind?",
    "tagPlaceholder": "Tag (optional)",
    "save": "Save note",
    "saved": "Thought captured.",
    "openInScratchpad": "Open in scratchpad",
    "shortcutHint": "Ctrl/⌘+Shift+U"
  },
  "chat": { "attachedNote": "Discussing note: {title}" }
}
```

```json
// packages/i18n/messages/de/notes.json
{
  "nav": { "label": "Notizblock" },
  "page": {
    "title": "Notizblock",
    "subtitle": "Gedanken festhalten, bevor sie entgleiten — Ideen, Konzepte, Fragen."
  },
  "empty": {
    "title": "Noch nichts festgehalten",
    "description": "Speichere deinen ersten Gedanken — einen Plot-Twist, eine Weltbau-Idee, eine Handwerksfrage.",
    "cta": "Gedanken festhalten"
  },
  "list": {
    "searchPlaceholder": "Notizen durchsuchen…",
    "typeFilterLabel": "Typ",
    "allTypes": "Alle Typen",
    "tagFilterLabel": "Tag",
    "allTags": "Alle Tags",
    "noResults": "Keine Notizen passen zu diesen Filtern.",
    "untitled": "Ohne Titel",
    "updated": "Aktualisiert {date}"
  },
  "type": { "idea": "Idee", "concept": "Konzept", "question": "Frage", "other": "Sonstiges" },
  "editor": {
    "newNote": "Neue Notiz",
    "titlePlaceholder": "Titel (optional — sonst wird die erste Zeile verwendet)",
    "contentLabel": "Notiz",
    "contentPlaceholder": "Schreib es auf… (Markdown möglich)",
    "preview": "Vorschau",
    "edit": "Bearbeiten",
    "typeLabel": "Typ",
    "tagsLabel": "Tags",
    "tagPlaceholder": "Tag hinzufügen…",
    "addTag": "Hinzufügen",
    "tagSuggestions": "Vorschläge",
    "linkLabel": "Verknüpfung (optional)",
    "noLink": "Nicht verknüpft",
    "novelLink": "Verknüpfter Roman",
    "seriesLink": "Verknüpfte Reihe",
    "discuss": "Im Chat besprechen",
    "delete": "Notiz löschen",
    "deleteTitle": "Diese Notiz löschen?",
    "deleteDescription": "Die Notiz wird endgültig entfernt. Das kann nicht rückgängig gemacht werden.",
    "save": "Speichern",
    "saveFailed": "Notiz konnte nicht gespeichert werden.",
    "deleted": "Notiz gelöscht."
  },
  "search": {
    "semanticToggle": "Semantisch",
    "semanticBadge": "semantisch",
    "lexicalBadge": "lexikalisch"
  },
  "quickCapture": {
    "open": "Schnellerfassung",
    "title": "Gedanken erfassen",
    "titlePlaceholder": "Titel (optional)",
    "textPlaceholder": "Was liegt dir im Kopf?",
    "tagPlaceholder": "Tag (optional)",
    "save": "Notiz speichern",
    "saved": "Gedanke festgehalten.",
    "openInScratchpad": "Im Notizblock öffnen",
    "shortcutHint": "Strg/⌘+Shift+U"
  },
  "chat": { "attachedNote": "Zur Notiz: {title}" }
}
```

```json
// packages/i18n/messages/fr/notes.json
{
  "nav": { "label": "Bloc-notes" },
  "page": {
    "title": "Bloc-notes",
    "subtitle": "Captez vos pensées avant qu'elles s'échappent — idées, concepts, questions."
  },
  "empty": {
    "title": "Rien de capturé pour l'instant",
    "description": "Sauvegardez votre première pensée — un rebondissement, une idée d'univers, une question d'écriture.",
    "cta": "Capter une pensée"
  },
  "list": {
    "searchPlaceholder": "Rechercher des notes…",
    "typeFilterLabel": "Type",
    "allTypes": "Tous les types",
    "tagFilterLabel": "Étiquette",
    "allTags": "Toutes les étiquettes",
    "noResults": "Aucune note ne correspond à ces filtres.",
    "untitled": "Sans titre",
    "updated": "Mis à jour {date}"
  },
  "type": { "idea": "Idée", "concept": "Concept", "question": "Question", "other": "Autre" },
  "editor": {
    "newNote": "Nouvelle note",
    "titlePlaceholder": "Titre (facultatif — sinon la première ligne est utilisée)",
    "contentLabel": "Note",
    "contentPlaceholder": "Notez-la… (Markdown pris en charge)",
    "preview": "Aperçu",
    "edit": "Modifier",
    "typeLabel": "Type",
    "tagsLabel": "Étiquettes",
    "tagPlaceholder": "Ajouter une étiquette…",
    "addTag": "Ajouter",
    "tagSuggestions": "Suggestions",
    "linkLabel": "Lien (facultatif)",
    "noLink": "Non liée",
    "novelLink": "Roman lié",
    "seriesLink": "Série liée",
    "discuss": "Discuter dans le chat",
    "delete": "Supprimer la note",
    "deleteTitle": "Supprimer cette note ?",
    "deleteDescription": "La note sera définitivement supprimée. Cette action est irréversible.",
    "save": "Enregistrer",
    "saveFailed": "Impossible d'enregistrer la note.",
    "deleted": "Note supprimée."
  },
  "search": {
    "semanticToggle": "Sémantique",
    "semanticBadge": "sémantique",
    "lexicalBadge": "lexicale"
  },
  "quickCapture": {
    "open": "Capture rapide",
    "title": "Capter une pensée",
    "titlePlaceholder": "Titre (facultatif)",
    "textPlaceholder": "À quoi pensez-vous ?",
    "tagPlaceholder": "Étiquette (facultatif)",
    "save": "Enregistrer la note",
    "saved": "Pensée capturée.",
    "openInScratchpad": "Ouvrir dans le bloc-notes",
    "shortcutHint": "Ctrl/⌘+Maj+U"
  },
  "chat": { "attachedNote": "À propos de la note : {title}" }
}
```

- [ ] **Step 2: Validate catalog parity**

Run: `uv run python scripts/validate-i18n.ts 2>/dev/null || npx tsx scripts/validate-i18n.ts` — inspect `scripts/validate-i18n.ts` for its exact invocation (`just` recipe or `npx tsx`) and run it from the repo root. All three locales must have identical key sets.
Expected: no missing-key errors.

- [ ] **Step 3: Commit**

```bash
git add packages/i18n/messages/en/notes.json packages/i18n/messages/de/notes.json packages/i18n/messages/fr/notes.json
git commit -m "feat(i18n): add notes namespace catalogs for en/de/fr (NOTES-001)"
```

---

### Task 20: i18n — register the `notes` namespace + label parity test

**Spec slice:** §7 (i18n) · §8 ("type labels per locale").

**Files:**
- Modify: `packages/web/lib/i18n/request.ts` (add `"notes"` to the `namespaces` array, line ~6)
- Test: `packages/web/__tests__/notes-i18n-labels.test.ts` (new)

**Interfaces:**
- Consumes: catalogs (T19); the registry regression pattern in `packages/web/__tests__/i18n-namespace-registry.test.ts`.
- Produces: `useTranslations("notes")` resolves real strings in the app.

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/__tests__/notes-i18n-labels.test.ts
/**
 * Notes i18n coverage (NOTES-001 §7/§8).
 *
 * The centralized setupTests mock returns i18n keys verbatim, so component
 * tests cannot verify real copy — this data-level test asserts that every
 * key the notes components use exists and is non-empty in ALL three locales
 * (the spec's "type labels per locale" requirement generalized to the whole
 * namespace), and that the namespace is registered in request.ts.
 */

import { existsSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const WEB_ROOT = resolve(__dirname, "..");
const I18N_MESSAGES = resolve(WEB_ROOT, "..", "i18n", "messages");
const LOCALES = ["en", "de", "fr"] as const;

const EXPECTED_KEYS = [
  "nav.label",
  "page.title",
  "page.subtitle",
  "empty.title",
  "empty.description",
  "empty.cta",
  "list.searchPlaceholder",
  "list.typeFilterLabel",
  "list.allTypes",
  "list.tagFilterLabel",
  "list.allTags",
  "list.noResults",
  "list.untitled",
  "list.updated",
  "type.idea",
  "type.concept",
  "type.question",
  "type.other",
  "editor.newNote",
  "editor.titlePlaceholder",
  "editor.contentLabel",
  "editor.contentPlaceholder",
  "editor.preview",
  "editor.edit",
  "editor.typeLabel",
  "editor.tagsLabel",
  "editor.tagPlaceholder",
  "editor.addTag",
  "editor.tagSuggestions",
  "editor.linkLabel",
  "editor.noLink",
  "editor.novelLink",
  "editor.seriesLink",
  "editor.discuss",
  "editor.delete",
  "editor.deleteTitle",
  "editor.deleteDescription",
  "editor.save",
  "editor.saveFailed",
  "editor.deleted",
  "search.semanticToggle",
  "search.semanticBadge",
  "search.lexicalBadge",
  "quickCapture.open",
  "quickCapture.title",
  "quickCapture.titlePlaceholder",
  "quickCapture.textPlaceholder",
  "quickCapture.tagPlaceholder",
  "quickCapture.save",
  "quickCapture.saved",
  "quickCapture.openInScratchpad",
  "quickCapture.shortcutHint",
  "chat.attachedNote",
] as const;

function flatten(obj: Record<string, unknown>, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return value && typeof value === "object"
      ? flatten(value as Record<string, unknown>, path)
      : [path];
  });
}

describe("notes i18n labels", () => {
  it.each(LOCALES)("locale %s has every expected notes key, non-empty", (locale) => {
    const file = join(I18N_MESSAGES, locale, "notes.json");
    expect(existsSync(file), `${file} must exist`).toBe(true);
    const flat = new Set(flatten(JSON.parse(readFileSync(file, "utf8"))));
    for (const key of EXPECTED_KEYS) {
      expect(flat.has(key), `${locale} missing notes.${key}`).toBe(true);
    }
  });

  it("registers the notes namespace in request.ts", () => {
    const requestTs = readFileSync(join(WEB_ROOT, "lib", "i18n", "request.ts"), "utf8");
    expect(requestTs).toMatch(/"notes"/);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm --filter narrare-web test __tests__/notes-i18n-labels.test.ts`
Expected: FAIL — the namespace registration assertion (`request.ts` does not contain `"notes"`).

- [ ] **Step 3: Register the namespace**

In `packages/web/lib/i18n/request.ts`, add `"notes",` to the `namespaces` array (keep the existing ordering style — append after `"aiAssist",`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pnpm --filter narrare-web test __tests__/notes-i18n-labels.test.ts __tests__/i18n-namespace-registry.test.ts`
Expected: PASS (both — the registry test now finds `notes` registered).

- [ ] **Step 5: Commit**

```bash
git add packages/web/lib/i18n/request.ts packages/web/__tests__/notes-i18n-labels.test.ts
git commit -m "feat(i18n): register notes namespace and lock label parity across locales"
```

---

### Task 21: Web — NoteList + NoteFilterBar components

> **⚠️ MANDATORY (PO requirement):** load the `frontend-design` skill (superpowers) BEFORE writing any UI code in this task.

**Spec slice:** §9.6 (Frontend page — list/filter) · §7.

**Files:**
- Create: `packages/web/components/notes/NoteFilterBar.tsx`
- Create: `packages/web/components/notes/NoteList.tsx`
- Test: `packages/web/components/notes/__tests__/NoteList.test.tsx`

**Interfaces:**
- Consumes: `Note`, `NoteTypeKey`, `NOTE_TYPE_KEYS`, `noteDisplayTitle` (T17); `listItemVariants`/`listContainerVariants` (`@/lib/motion-variants`); `useTranslations("notes")`.
- Produces (used by T26 ScratchpadWorkspace):
  - `NoteFilterBarProps` / `NoteFilterBar` — controlled filter bar with search field, semantic toggle, type dropdown, tag filter
  - `NoteListProps` / `NoteList` — selectable note list with type badge + tags + updated timestamp

- [ ] **Step 1: Write the failing component tests**

```tsx
// packages/web/components/notes/__tests__/NoteList.test.tsx
/**
 * NoteList component tests (NOTES-001).
 *
 * Conventions (mirrors series/__tests__): the centralized setupTests mock
 * returns i18n KEY STRINGS verbatim — assertions check keys; motion/react is
 * neutralized globally so list items mount immediately.
 */

import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NoteList } from "../NoteList";
import type { Note } from "@/types";

function makeNote(overrides: Partial<Note> = {}): Note {
  return {
    id: "n1",
    title: null,
    content: "First line\nbody",
    note_type: "idea",
    tags: ["plot"],
    novel_id: null,
    series_id: null,
    created_at: "2026-08-21T00:00:00Z",
    updated_at: "2026-08-21T00:00:00Z",
    ...overrides,
  };
}

describe("NoteList", () => {
  it("renders display title via fallback and the localized type label key", () => {
    render(
      <NoteList
        notes={[makeNote()]}
        selectedId={null}
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByText("First line")).toBeInTheDocument();
    // setupTests i18n mock returns the key: notes.type.idea
    expect(screen.getByText("type.idea")).toBeInTheDocument();
  });

  it("marks the selected note and calls onSelect", () => {
    const onSelect = vi.fn();
    render(
      <NoteList notes={[makeNote({ id: "n1", title: "Named" }), makeNote({ id: "n2" })]} selectedId="n2" onSelect={onSelect} />,
    );
    fireEvent.click(screen.getByText("Named"));
    expect(onSelect).toHaveBeenCalledWith("n1");
  });

  it("renders tags as chips and the untitled key when nothing to show", () => {
    render(
      <NoteList
        notes={[makeNote({ tags: ["world"], title: "", content: "" })]}
        selectedId={null}
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByText("world")).toBeInTheDocument();
    expect(screen.getByText("list.untitled")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pnpm --filter narrare-web test components/notes/__tests__/NoteList.test.tsx`
Expected: FAIL — cannot resolve `../NoteList`.

- [ ] **Step 3: Write the components**

```tsx
// packages/web/components/notes/NoteFilterBar.tsx
"use client";

/**
 * NoteFilterBar — controlled filter bar for the scratchpad list (NOTES-001 §7).
 *
 * Owns no data fetching: the parent (ScratchpadWorkspace) owns filter state
 * and decides whether the list shows query results or semantic search
 * results. The semantic toggle is honest (RULE-11 spirit): the result badge
 * comes from the API response, not from this toggle.
 */

import { Search } from "lucide-react";
import { useTranslations } from "next-intl";
import { NOTE_TYPE_KEYS, type NoteTypeKey } from "@/types";

export interface NoteFilters {
  q: string;
  note_type: NoteTypeKey | "";
  tag: string;
}

export interface NoteFilterBarProps {
  readonly filters: NoteFilters;
  readonly onFiltersChange: (filters: NoteFilters) => void;
  readonly availableTags: readonly string[];
  readonly semanticMode: boolean;
  readonly onSemanticModeChange: (enabled: boolean) => void;
  readonly onSearchSubmit: () => void;
}

export function NoteFilterBar({
  filters,
  onFiltersChange,
  availableTags,
  semanticMode,
  onSemanticModeChange,
  onSearchSubmit,
}: NoteFilterBarProps) {
  const t = useTranslations("notes");

  return (
    <div
      data-testid="note-filter-bar"
      className="flex flex-wrap items-center gap-2 border-b border-border p-3"
    >
      <div className="relative min-w-48 flex-1">
        <Search className="pointer-events-none absolute left-2 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <input
          type="search"
          value={filters.q}
          aria-label={t("list.searchPlaceholder")}
          placeholder={t("list.searchPlaceholder")}
          data-testid="note-search-input"
          className="w-full rounded-md border border-border bg-background py-1.5 pl-8 pr-3 text-sm"
          onChange={(event) => onFiltersChange({ ...filters, q: event.target.value })}
          onKeyDown={(event) => {
            if (event.key === "Enter") onSearchSubmit();
          }}
        />
      </div>

      <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <span className="sr-only sm:not-sr-only">{t("list.typeFilterLabel")}</span>
        <select
          value={filters.note_type}
          data-testid="note-type-filter"
          aria-label={t("list.typeFilterLabel")}
          className="rounded-md border border-border bg-background px-2 py-1.5 text-sm"
          onChange={(event) =>
            onFiltersChange({
              ...filters,
              note_type: event.target.value as NoteTypeKey | "",
            })
          }
        >
          <option value="">{t("list.allTypes")}</option>
          {NOTE_TYPE_KEYS.map((key) => (
            <option key={key} value={key}>
              {t(`type.${key}`)}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <span className="sr-only sm:not-sr-only">{t("list.tagFilterLabel")}</span>
        <select
          value={filters.tag}
          data-testid="note-tag-filter"
          aria-label={t("list.tagFilterLabel")}
          className="rounded-md border border-border bg-background px-2 py-1.5 text-sm"
          onChange={(event) => onFiltersChange({ ...filters, tag: event.target.value })}
        >
          <option value="">{t("list.allTags")}</option>
          {availableTags.map((tag) => (
            <option key={tag} value={tag}>
              {tag}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <input
          type="checkbox"
          checked={semanticMode}
          data-testid="note-semantic-toggle"
          onChange={(event) => onSemanticModeChange(event.target.checked)}
        />
        {t("search.semanticToggle")}
      </label>
    </div>
  );
}
```

```tsx
// packages/web/components/notes/NoteList.tsx
"use client";

/**
 * NoteList — selectable list of notes (NOTES-001 §7).
 *
 * Presentational: parent owns data + selection. Uses the central Motion
 * variants; setupTests neutralizes motion in tests.
 */

import { motion } from "motion/react";
import { useTranslations } from "next-intl";
import { listContainerVariants, listItemVariants } from "@/lib/motion-variants";
import { noteDisplayTitle, type Note } from "@/types";

export interface NoteListProps {
  readonly notes: readonly Note[];
  readonly selectedId: string | null;
  readonly onSelect: (noteId: string) => void;
}

export function NoteList({ notes, selectedId, onSelect }: NoteListProps) {
  const t = useTranslations("notes");

  if (notes.length === 0) {
    return (
      <p data-testid="note-list-empty" className="p-6 text-sm text-muted-foreground">
        {t("list.noResults")}
      </p>
    );
  }

  return (
    <motion.ul
      variants={listContainerVariants}
      initial="hidden"
      animate="visible"
      aria-label={t("page.title")}
      className="flex-1 overflow-y-auto"
    >
      {notes.map((note) => {
        const displayTitle = noteDisplayTitle(note) || t("list.untitled");
        const active = note.id === selectedId;
        return (
          <motion.li key={note.id} variants={listItemVariants}>
            <button
              type="button"
              data-testid={`note-list-item-${note.id}`}
              aria-current={active ? "true" : undefined}
              onClick={() => onSelect(note.id)}
              className={`w-full border-b border-border px-4 py-3 text-left transition-colors ${
                active ? "bg-accent" : "hover:bg-accent/50"
              }`}
            >
              <span className="flex items-center gap-2">
                <span className="rounded bg-secondary px-1.5 py-0.5 text-xs text-secondary-foreground">
                  {t(`type.${note.note_type}`)}
                </span>
                <span className="min-w-0 flex-1 truncate text-sm font-medium">
                  {displayTitle}
                </span>
              </span>
              {note.tags.length > 0 && (
                <span className="mt-1 flex flex-wrap gap-1">
                  {note.tags.map((tag) => (
                    <span key={tag} className="rounded-full bg-muted px-2 py-0.5 text-xs">
                      {tag}
                    </span>
                  ))}
                </span>
              )}
              <span className="mt-1 block text-xs text-muted-foreground">
                {t("list.updated", {
                  date: new Date(note.updated_at).toLocaleDateString(),
                })}
              </span>
            </button>
          </motion.li>
        );
      })}
    </motion.ul>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pnpm --filter narrare-web test components/notes/__tests__/NoteList.test.tsx`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/notes/NoteFilterBar.tsx packages/web/components/notes/NoteList.tsx packages/web/components/notes/__tests__/NoteList.test.tsx
git commit -m "feat(web): add note list and filter bar components (NOTES-001)"
```

---

### Task 22: Web — TagInput (autocomplete, free-form)

> **⚠️ MANDATORY (PO requirement):** load the `frontend-design` skill (superpowers) BEFORE writing any UI code in this task.

**Spec slice:** §7 (tag input with autocomplete; new tags freely typable; max 10).

**Files:**
- Create: `packages/web/components/notes/TagInput.tsx`
- Test: `packages/web/components/notes/__tests__/TagInput.test.tsx`

**Interfaces:**
- Consumes: `useTranslations("notes")`.
- Produces (used by T23 NoteEditor): `TagInputProps` / `TagInput` — `value: readonly string[]`, `onChange(next: string[])`, `suggestions: readonly string[]`, `placeholder?: string`, `maxTags?: number` (default 10).

- [ ] **Step 1: Write the failing tests**

```tsx
// packages/web/components/notes/__tests__/TagInput.test.tsx
/**
 * TagInput component tests (NOTES-001) — chips + free-form entry +
 * suggestion filtering + normalization + max cap.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TagInput } from "../TagInput";

describe("TagInput", () => {
  it("adds a typed tag on Enter and normalizes it (trim + lowercase)", () => {
    const onChange = vi.fn();
    render(<TagInput value={[]} onChange={onChange} suggestions={[]} />);
    const input = screen.getByTestId("tag-input");
    fireEvent.change(input, { target: { value: "  Plot Twist " } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith(["plot twist"]);
  });

  it("filters suggestions by the current input prefix", () => {
    render(<TagInput value={[]} onChange={vi.fn()} suggestions={["plot", "world", "poem"]} />);
    const input = screen.getByTestId("tag-input");
    fireEvent.change(input, { target: { value: "po" } });
    expect(screen.getByText("poem")).toBeInTheDocument();
    expect(screen.queryByText("plot")).not.toBeInTheDocument();
  });

  it("picking a suggestion adds exactly that tag", () => {
    const onChange = vi.fn();
    render(<TagInput value={[]} onChange={onChange} suggestions={["plot"]} />);
    fireEvent.change(screen.getByTestId("tag-input"), { target: { value: "pl" } });
    fireEvent.click(screen.getByTestId("tag-suggestion-plot"));
    expect(onChange).toHaveBeenCalledWith(["plot"]);
  });

  it("removes a chip via its remove button", () => {
    const onChange = vi.fn();
    render(<TagInput value={["plot"]} onChange={onChange} suggestions={[]} />);
    fireEvent.click(screen.getByTestId("tag-remove-plot"));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("ignores duplicates and enforces the max cap", () => {
    const onChange = vi.fn();
    render(<TagInput value={["plot"]} onChange={onChange} suggestions={[]} maxTags={2} />);
    const input = screen.getByTestId("tag-input");
    fireEvent.change(input, { target: { value: "PLOT" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.change(input, { target: { value: "world" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith(["plot", "world"]);
    fireEvent.change(input, { target: { value: "third" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledTimes(1); // capped — no further calls
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pnpm --filter narrare-web test components/notes/__tests__/TagInput.test.tsx`
Expected: FAIL — cannot resolve `../TagInput`.

- [ ] **Step 3: Write the component**

```tsx
// packages/web/components/notes/TagInput.tsx
"use client";

/**
 * TagInput — chips + free-form text entry with prefix autocomplete
 * (NOTES-001 §7: "tag autocomplete over existing tags; new tags always
 * allowed"). Normalization mirrors the backend rule (trim, lowercase,
 * collapse whitespace); duplicates and the 10-tag cap are ignored silently
 * at entry — the API would reject them anyway, and quick entry stays fast.
 */

import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";

const MAX_TAG_LENGTH = 32;

function normalizeTag(tag: string): string {
  return tag.trim().replace(/\s+/g, " ").toLowerCase();
}

export interface TagInputProps {
  readonly value: readonly string[];
  readonly onChange: (next: string[]) => void;
  readonly suggestions: readonly string[];
  readonly placeholder?: string;
  readonly maxTags?: number;
}

export function TagInput({
  value,
  onChange,
  suggestions,
  placeholder,
  maxTags = 10,
}: TagInputProps) {
  const t = useTranslations("notes");
  const [draft, setDraft] = useState("");

  const filteredSuggestions = useMemo(() => {
    const prefix = draft.trim().toLowerCase();
    return suggestions
      .filter((tag) => !value.includes(tag))
      .filter((tag) => (prefix ? tag.startsWith(prefix) : true))
      .slice(0, 6);
  }, [draft, suggestions, value]);

  function addTag(raw: string) {
    const tag = normalizeTag(raw).slice(0, MAX_TAG_LENGTH);
    if (!tag || value.includes(tag) || value.length >= maxTags) return;
    onChange([...value, tag]);
    setDraft("");
  }

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-1.5" data-testid="tag-chips">
        {value.map((tag) => (
          <span
            key={tag}
            className="flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs"
          >
            {tag}
            <button
              type="button"
              data-testid={`tag-remove-${tag}`}
              aria-label={`${t("editor.delete")} ${tag}`}
              className="text-muted-foreground hover:text-foreground"
              onClick={() => onChange(value.filter((existing) => existing !== tag))}
            >
              <X className="size-3" />
            </button>
          </span>
        ))}
        <input
          type="text"
          value={draft}
          data-testid="tag-input"
          aria-label={t("editor.tagPlaceholder")}
          placeholder={placeholder ?? t("editor.tagPlaceholder")}
          className="min-w-32 flex-1 rounded-md border border-border bg-background px-2 py-1 text-sm"
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              addTag(draft);
            }
          }}
          onBlur={() => draft && addTag(draft)}
        />
      </div>
      {filteredSuggestions.length > 0 && (
        <div className="flex flex-wrap gap-1" aria-label={t("editor.tagSuggestions")}>
          {filteredSuggestions.map((tag) => (
            <button
              key={tag}
              type="button"
              data-testid={`tag-suggestion-${tag}`}
              className="rounded-full border border-border px-2 py-0.5 text-xs hover:bg-accent"
              onClick={() => addTag(tag)}
            >
              {tag}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pnpm --filter narrare-web test components/notes/__tests__/TagInput.test.tsx`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/notes/TagInput.tsx packages/web/components/notes/__tests__/TagInput.test.tsx
git commit -m "feat(web): add tag input with autocomplete and normalization (NOTES-001)"
```

---

### Task 23: Web — NoteEditor (editor, preview, links, discuss, delete)

> **⚠️ MANDATORY (PO requirement):** load the `frontend-design` skill (superpowers) BEFORE writing any UI code in this task.

**Spec slice:** §9.6 · §7 (right pane: markdown editor with preview toggle, type select, tag autocomplete, optional novel/series link, discuss button, delete with ConfirmDialog).

**Files:**
- Create: `packages/web/components/notes/NoteEditor.tsx`
- Test: `packages/web/components/notes/__tests__/NoteEditor.test.tsx`

**Interfaces:**
- Consumes: `TagInput` (T22); `ConfirmDialog` (`@/components/ui/confirm-dialog`, existing); `markdownToHtml` (`@/lib/utils`, existing); `useNotes`/`useUpdateNote`/`useDeleteNote` are NOT used here — the editor is controlled; `useNovels` / `useSeries` (existing hooks `@/lib/hooks/useNovels`, `@/lib/hooks/useSeries`) feed the link dropdowns; `toast` (`sonner`).
- Produces (used by T26): `NoteEditorProps` / `NoteEditor` — controlled editor over a `Note`, emitting `onSaved`, `onDeleted`, `onDiscuss`.

- [ ] **Step 1: Write the failing tests**

```tsx
// packages/web/components/notes/__tests__/NoteEditor.test.tsx
/**
 * NoteEditor component tests (NOTES-001).
 *
 * The editor is controlled: mutations run through the parent's hooks are
 * mocked via MSW; assertions cover edit + save callback, preview toggle
 * rendering markdownToHtml output, delete confirmation flow, and the
 * discuss callback.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { server } from "@/mocks/server";
import { NoteEditor } from "../NoteEditor";
import type { Note } from "@/types";

const baseNote: Note = {
  id: "n1",
  title: "Twist",
  content: "The **aunt** did it",
  note_type: "idea",
  tags: ["plot"],
  novel_id: null,
  series_id: null,
  created_at: "2026-08-21T00:00:00Z",
  updated_at: "2026-08-21T00:00:00Z",
};

function renderEditor(overrides: Partial<Parameters<typeof NoteEditor>[0]> = {}) {
  const onSaved = vi.fn();
  const onDeleted = vi.fn();
  const onDiscuss = vi.fn();
  render(
    <NoteEditor
      note={baseNote}
      availableTags={["plot", "world"]}
      onSaved={onSaved}
      onDeleted={onDeleted}
      onDiscuss={onDiscuss}
      {...overrides}
    />,
  );
  return { onSaved, onDeleted, onDiscuss };
}

describe("NoteEditor", () => {
  it("renders fields prefilled from the note", () => {
    renderEditor();
    expect(screen.getByDisplayValue("Twist")).toBeInTheDocument();
    expect(screen.getByDisplayValue("The **aunt** did it")).toBeInTheDocument();
    expect(screen.getByTestId("tag-chips")).toHaveTextContent("plot");
  });

  it("saves edits through PATCH and emits onSaved", async () => {
    server.use(
      http.patch("*/api/v1/notes/:id", async () =>
        HttpResponse.json({ ...baseNote, content: "edited body" }),
      ),
    );
    const { onSaved } = renderEditor();
    const content = screen.getByTestId("note-content-input");
    fireEvent.change(content, { target: { value: "edited body" } });
    fireEvent.click(screen.getByTestId("note-save-button"));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });

  it("toggles markdown preview rendered via markdownToHtml", () => {
    renderEditor();
    fireEvent.click(screen.getByTestId("note-preview-toggle"));
    const preview = screen.getByTestId("note-preview");
    expect(preview.innerHTML).toContain("<strong>aunt</strong>");
  });

  it("requires confirmation before delete and emits onDeleted", async () => {
    server.use(
      http.delete("*/api/v1/notes/:id", () => new HttpResponse(null, { status: 204 })),
    );
    const { onDeleted } = renderEditor();
    fireEvent.click(screen.getByTestId("note-delete-button"));
    expect(screen.getByText("editor.deleteTitle")).toBeInTheDocument(); // i18n key mock
    fireEvent.click(screen.getByTestId("confirm-dialog-confirm"));
    await waitFor(() => expect(onDeleted).toHaveBeenCalled());
  });

  it("emits onDiscuss with the note id", () => {
    const { onDiscuss } = renderEditor();
    fireEvent.click(screen.getByTestId("note-discuss-button"));
    expect(onDiscuss).toHaveBeenCalledWith(baseNote.id);
  });
});
```

(The test relies on the ConfirmDialog's confirm button `data-testid="confirm-dialog-confirm"` — present in `components/ui/confirm-dialog.tsx`'s confirm button; verify while implementing and assert the actual testid if it differs.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `pnpm --filter narrare-web test components/notes/__tests__/NoteEditor.test.tsx`
Expected: FAIL — cannot resolve `../NoteEditor`.

- [ ] **Step 3: Write the component**

```tsx
// packages/web/components/notes/NoteEditor.tsx
"use client";

/**
 * NoteEditor — the right pane of /scratchpad (NOTES-001 §7).
 *
 * Controlled editor: loads nothing, owns only draft state derived from the
 * note prop; mutations (update/delete) run through the shared hooks; the
 * parent receives onSaved/onDeleted/onDiscuss callbacks. Preview reuses the
 * vendored markdownToHtml (no new dependency).
 */

import { Eye, Pencil, MessageCircle, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useSeriesList } from "@/lib/hooks/useSeries";
import { useDeleteNote, useUpdateNote } from "@/lib/hooks/useNotes";
import { useNovels } from "@/lib/hooks/useNovels";
import { markdownToHtml } from "@/lib/utils";
import { NOTE_TYPE_KEYS, type Note, type NoteTypeKey } from "@/types";
import { TagInput } from "./TagInput";

export interface NoteEditorProps {
  readonly note: Note;
  readonly availableTags: readonly string[];
  readonly onSaved: () => void;
  readonly onDeleted: () => void;
  readonly onDiscuss: (noteId: string) => void;
}

export function NoteEditor({
  note,
  availableTags,
  onSaved,
  onDeleted,
  onDiscuss,
}: NoteEditorProps) {
  const t = useTranslations("notes");
  const [title, setTitle] = useState(note.title ?? "");
  const [content, setContent] = useState(note.content);
  const [noteType, setNoteType] = useState<NoteTypeKey>(note.note_type);
  const [tags, setTags] = useState<string[]>([...note.tags]);
  const [novelId, setNovelId] = useState<string>(note.novel_id ?? "");
  const [seriesId, setSeriesId] = useState<string>(note.series_id ?? "");
  const [preview, setPreview] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  useEffect(() => {
    setTitle(note.title ?? "");
    setContent(note.content);
    setNoteType(note.note_type);
    setTags([...note.tags]);
    setNovelId(note.novel_id ?? "");
    setSeriesId(note.series_id ?? "");
    setPreview(false);
  }, [note]);

  const { data: novels } = useNovels();
  const { data: seriesList } = useSeriesList();
  const updateNote = useUpdateNote();
  const deleteNote = useDeleteNote();

  function handleSave() {
    updateNote.mutate(
      {
        id: note.id,
        body: {
          title: title.trim() || null,
          content,
          note_type: noteType,
          tags,
          // "" → explicit null: clear the link (exclude_unset semantics).
          novel_id: novelId || (note.novel_id ? null : undefined),
          series_id: seriesId || (note.series_id ? null : undefined),
        },
      },
      {
        onSuccess: () => onSaved(),
        onError: () => toast.error(t("editor.saveFailed")),
      },
    );
  }

  function handleDelete() {
    deleteNote.mutate(note.id, {
      onSuccess: () => {
        toast.success(t("editor.deleted"));
        setConfirmOpen(false);
        onDeleted();
      },
    });
  }

  return (
    <section aria-label={t("editor.contentLabel")} className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-border p-3">
        <input
          type="text"
          value={title}
          aria-label={t("editor.titlePlaceholder")}
          placeholder={t("editor.titlePlaceholder")}
          className="min-w-0 flex-1 bg-transparent text-lg font-medium outline-none"
          onChange={(event) => setTitle(event.target.value)}
        />
        <button
          type="button"
          data-testid="note-preview-toggle"
          aria-pressed={preview}
          className="rounded-md p-1.5 hover:bg-accent"
          onClick={() => setPreview((value) => !value)}
          title={preview ? t("editor.edit") : t("editor.preview")}
        >
          {preview ? <Pencil className="size-4" /> : <Eye className="size-4" />}
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-3 border-b border-border px-3 py-2 text-sm">
        <label className="flex items-center gap-1.5">
          {t("editor.typeLabel")}
          <select
            value={noteType}
            aria-label={t("editor.typeLabel")}
            className="rounded-md border border-border bg-background px-2 py-1"
            onChange={(event) => setNoteType(event.target.value as NoteTypeKey)}
          >
            {NOTE_TYPE_KEYS.map((key) => (
              <option key={key} value={key}>
                {t(`type.${key}`)}
              </option>
            ))}
          </select>
        </label>

        <button
          type="button"
          data-testid="note-discuss-button"
          className="flex items-center gap-1.5 rounded-md px-2 py-1 hover:bg-accent"
          onClick={() => onDiscuss(note.id)}
        >
          <MessageCircle className="size-4" />
          {t("editor.discuss")}
        </button>

        <button
          type="button"
          data-testid="note-save-button"
          className="rounded-md bg-primary px-3 py-1 text-primary-foreground"
          onClick={handleSave}
        >
          {t("editor.save")}
        </button>

        <button
          type="button"
          data-testid="note-delete-button"
          className="ml-auto flex items-center gap-1.5 rounded-md p-1.5 text-destructive hover:bg-accent"
          onClick={() => setConfirmOpen(true)}
          title={t("editor.delete")}
        >
          <Trash2 className="size-4" />
          <span className="sr-only">{t("editor.delete")}</span>
        </button>
      </div>

      {preview ? (
        <div
          data-testid="note-preview"
          // markdownToHtml escapes nothing — it only converts the vendored
          // subset; content is the user's own note (local-first, single user).
          className="prose flex-1 overflow-y-auto p-4"
          dangerouslySetInnerHTML={{ __html: markdownToHtml(content) }}
        />
      ) : (
        <textarea
          value={content}
          data-testid="note-content-input"
          aria-label={t("editor.contentLabel")}
          placeholder={t("editor.contentPlaceholder")}
          className="flex-1 resize-none bg-transparent p-4 font-mono text-sm outline-none"
          onChange={(event) => setContent(event.target.value)}
        />
      )}

      <div className="space-y-2 border-t border-border p-3">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          {t("editor.tagsLabel")}
        </p>
        <TagInput value={tags} onChange={setTags} suggestions={availableTags} />

        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          {t("editor.linkLabel")}
        </p>
        <div className="flex gap-2">
          <select
            value={novelId}
            aria-label={t("editor.novelLink")}
            className="min-w-0 flex-1 rounded-md border border-border bg-background px-2 py-1 text-sm"
            onChange={(event) => {
              setNovelId(event.target.value);
              if (event.target.value) setSeriesId(""); // scope invariant: never both
            }}
          >
            <option value="">{t("editor.noLink")}</option>
            {(novels ?? []).map((novel) => (
              <option key={novel.id} value={novel.id}>
                {novel.title}
              </option>
            ))}
          </select>
          <select
            value={seriesId}
            aria-label={t("editor.seriesLink")}
            className="min-w-0 flex-1 rounded-md border border-border bg-background px-2 py-1 text-sm"
            onChange={(event) => {
              setSeriesId(event.target.value);
              if (event.target.value) setNovelId(""); // scope invariant: never both
            }}
          >
            <option value="">{t("editor.noLink")}</option>
            {(seriesList ?? []).map((series) => (
              <option key={series.id} value={series.id}>
                {series.title}
              </option>
            ))}
          </select>
        </div>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={t("editor.deleteTitle")}
        description={t("editor.deleteDescription")}
        confirmLabel={t("editor.delete")}
        onConfirm={handleDelete}
        variant="destructive"
      />
    </section>
  );
}
```

NOTE while implementing: verify the ConfirmDialog confirm button's testid in `components/ui/confirm-dialog.tsx` (the cancel button uses `confirm-dialog-cancel`; the confirm button may not carry one — if missing, assert on the visible confirm label `editor.delete` instead of a testid). `useSeriesList()` returns `{ data: SeriesSummary[] }` and `useNovels()` returns `{ data: NovelSummary[] }` — both expose `id`/`title` (verified in `lib/hooks/useSeries.ts` / `useNovels.ts`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pnpm --filter narrare-web test components/notes/__tests__/NoteEditor.test.tsx`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/notes/NoteEditor.tsx packages/web/components/notes/__tests__/NoteEditor.test.tsx
git commit -m "feat(web): add note editor with markdown preview, links, discuss, and confirm-delete"
```

---

### Task 24: Web — chat API + useChat accept project-less + note context

**Spec slice:** §9.7 support for §6b (frontend "discuss" flow). Not visual UI — no frontend-design skill needed.

**Files:**
- Modify: `packages/web/lib/api/chat.ts` (`streamChat` body types)
- Modify: `packages/web/lib/hooks/useChat.ts` (signature + body)
- Test: `packages/web/lib/hooks/__tests__/useChat.test.tsx` (new)

**Interfaces:**
- Consumes: `connectSSE` (existing); `useAIOperation` (existing); core ChatRequest optional fields (T13/T14 — backend accepts `project_id: null` and `note_id`).
- Produces (used by T25): `useChat(projectId: string | null, noteId?: string | null): UseChatReturn` (return type unchanged); `chatApi.streamChat(body, callbacks, signal?)` with `body: { project_id?: string | null; message: string; conversation_id?: string | null; note_id?: string | null }`.

- [ ] **Step 1: Write the failing test**

```tsx
// packages/web/lib/hooks/__tests__/useChat.test.tsx
/**
 * useChat tests (NOTES-001 §6b): project-less chat + note context
 * passthrough. chatApi is module-mocked (SSE transport is not under test).
 */

import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useChat } from "../useChat";

const streamChatMock = vi.fn();

vi.mock("@/lib/api/client", () => ({
  chatApi: {
    streamChat: (...args: unknown[]) => streamChatMock(...args),
  },
}));

async function flush() {
  await act(async () => {});
}

describe("useChat", () => {
  beforeEach(() => {
    streamChatMock.mockReset();
    streamChatMock.mockImplementation(async (_body, callbacks) => {
      callbacks.onMeta({ conversation_id: "c1", request_id: "r1" });
      callbacks.onToken("answer");
      callbacks.onDone({ type: "done", usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 } });
    });
  });

  it("sends project_id and no note_id for legacy project chat", async () => {
    const { result } = renderHook(() => useChat("p1"));
    await act(async () => {
      await result.current.sendMessage("hello");
    });
    expect(streamChatMock).toHaveBeenCalled();
    expect(streamChatMock.mock.calls[0][0]).toMatchObject({
      project_id: "p1",
      message: "hello",
    });
    expect(streamChatMock.mock.calls[0][0].note_id ?? null).toBeNull();
  });

  it("sends null project_id and note_id for project-less note chat", async () => {
    const { result } = renderHook(() => useChat(null, "note-1"));
    await act(async () => {
      await result.current.sendMessage("discuss this");
    });
    expect(streamChatMock).toHaveBeenCalled();
    expect(streamChatMock.mock.calls[0][0]).toEqual(
      expect.objectContaining({
        project_id: null,
        message: "discuss this",
        note_id: "note-1",
      }),
    );
    await waitFor(() => {
      expect(result.current.messages.at(-1)?.content).toBe("answer");
    });
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pnpm --filter narrare-web test lib/hooks/__tests__/useChat.test.tsx`
Expected: FAIL — `useChat` requires a `string` projectId / body lacks `note_id`.

- [ ] **Step 3: Apply the changes**

In `packages/web/lib/api/chat.ts`, widen the `streamChat` body type:

```typescript
  streamChat: async (
    body: {
      project_id?: string | null;
      message: string;
      conversation_id?: string | null;
      note_id?: string | null;
    },
    callbacks: { /* unchanged */ },
    signal?: AbortSignal,
  ): Promise<void> => {
```

(callbacks shape stays exactly as-is; only the body type widens.)

In `packages/web/lib/hooks/useChat.ts`:

```typescript
export function useChat(projectId: string | null, noteId?: string | null): UseChatReturn {
```

and inside `execute`, forward both fields:

```typescript
      await chatApi.streamChat(
        {
          project_id: projectId,
          message: msg,
          conversation_id: conversationIdRef.current,
          note_id: noteId ?? null,
        },
        { /* existing callbacks unchanged */ },
        signal,
      );
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pnpm --filter narrare-web test lib/hooks/__tests__/useChat.test.tsx && pnpm --filter narrare-web type-check`
Expected: PASS + no type errors (the existing ChatPage passes `id: string`, which still satisfies `string | null`).

- [ ] **Step 5: Commit**

```bash
git add packages/web/lib/api/chat.ts packages/web/lib/hooks/useChat.ts packages/web/lib/hooks/__tests__/useChat.test.tsx
git commit -m "feat(web): useChat supports project-less conversations and note context (NOTES-001)"
```

---

### Task 25: Web — ChatPanel project-less + NotesChatDrawer

> **⚠️ MANDATORY (PO requirement):** load the `frontend-design` skill (superpowers) BEFORE writing any UI code in this task.

**Spec slice:** §7 ("discuss in chat" button opens the chat panel with the note pre-loaded).

**Files:**
- Modify: `packages/web/components/studio/editor/ChatPanel.tsx` (props: `projectId: string | null`, optional `noteId`, optional `banner`)
- Create: `packages/web/components/notes/NotesChatDrawer.tsx`
- Test: `packages/web/components/notes/__tests__/NotesChatDrawer.test.tsx`

**Interfaces:**
- Consumes: `ChatPanel` (existing, modified here); `useChat(projectId, noteId)` (T24); `panelSlideRightVariants`, `overlayVariants` (`@/lib/motion-variants`); Motion `AnimatePresence`.
- Produces (used by T26): `NotesChatDrawerProps` / `NotesChatDrawer` — `open: boolean`, `onClose: () => void`, `note: Note | null`. ChatPanel's prop surface after this task: `projectId: string | null`, `noteId?: string | null`, `onClose: () => void` (the attached-note banner lives in the drawer header, so no extra ChatPanel banner prop is needed).

- [ ] **Step 1: Write the failing test**

```tsx
// packages/web/components/notes/__tests__/NotesChatDrawer.test.tsx
/**
 * NotesChatDrawer tests (NOTES-001 §6b/§7): renders the chat surface for a
 * (possibly global) note, with the attached-note banner and close handling.
 * ChatPanel internals are out of scope here — they are covered by the
 * existing editor chat tests; this test asserts composition + banner.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NotesChatDrawer } from "../NotesChatDrawer";
import type { Note } from "@/types";

const note: Note = {
  id: "n1",
  title: "Twist",
  content: "The aunt did it",
  note_type: "idea",
  tags: [],
  novel_id: null,
  series_id: null,
  created_at: "2026-08-21T00:00:00Z",
  updated_at: "2026-08-21T00:00:00Z",
};

describe("NotesChatDrawer", () => {
  it("renders nothing when closed", () => {
    const { container } = render(
      <NotesChatDrawer open={false} onClose={vi.fn()} note={note} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the attached-note banner with the note title", () => {
    render(<NotesChatDrawer open onClose={vi.fn()} note={note} />);
    expect(screen.getByTestId("note-chat-banner")).toHaveTextContent("Twist");
  });

  it("falls back to the derived title when the note has none", () => {
    render(
      <NotesChatDrawer open onClose={vi.fn()} note={{ ...note, title: null }} />,
    );
    expect(screen.getByTestId("note-chat-banner")).toHaveTextContent("The aunt did it");
  });

  it("calls onClose from the drawer close button", () => {
    const onClose = vi.fn();
    render(<NotesChatDrawer open onClose={onClose} note={note} />);
    fireEvent.click(screen.getByTestId("note-chat-close"));
    expect(onClose).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pnpm --filter narrare-web test components/notes/__tests__/NotesChatDrawer.test.tsx`
Expected: FAIL — cannot resolve `../NotesChatDrawer`.

- [ ] **Step 3: Implement**

`packages/web/components/studio/editor/ChatPanel.tsx` — two minimal prop changes (behavior identical for existing callers; the existing chat page passes `projectId={id}`, which still satisfies `string | null`):

```typescript
interface ChatPanelProps {
  readonly projectId: string | null;
  /** Optional scratchpad note attached as runtime context (NOTES-001 §6b). */
  readonly noteId?: string | null;
  readonly onClose: () => void;
}

export function ChatPanel({ projectId, noteId, onClose }: ChatPanelProps) {
  // …
  const { /* unchanged */ } = useChat(projectId, noteId);
  // … rest of the component unchanged
```

```tsx
// packages/web/components/notes/NotesChatDrawer.tsx
"use client";

/**
 * NotesChatDrawer — right-side slide-over hosting ChatPanel for a note
 * (NOTES-001 §7 "discuss in chat"). Works for global notes (projectId null)
 * and linked notes (projectId = note.novel_id) alike.
 */

import { AnimatePresence, motion } from "motion/react";
import { useTranslations } from "next-intl";
import { X } from "lucide-react";
import { ChatPanel } from "@/components/studio/editor/ChatPanel";
import { overlayVariants, panelSlideRightVariants } from "@/lib/motion-variants";
import { noteDisplayTitle, type Note } from "@/types";

export interface NotesChatDrawerProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly note: Note | null;
}

export function NotesChatDrawer({ open, onClose, note }: NotesChatDrawerProps) {
  const t = useTranslations("notes");

  if (!note) return null;

  const bannerTitle = noteDisplayTitle(note) || t("list.untitled");

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            variants={overlayVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            className="fixed inset-0 z-40 bg-black/50"
            onClick={onClose}
            aria-hidden="true"
          />
          <motion.aside
            variants={panelSlideRightVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            role="dialog"
            aria-modal="true"
            aria-label={t("editor.discuss")}
            className="fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col border-l border-border bg-card"
          >
            <header className="flex items-center justify-between border-b border-border px-3 py-2">
              <p
                data-testid="note-chat-banner"
                className="min-w-0 truncate text-sm text-muted-foreground"
              >
                {t("chat.attachedNote", { title: bannerTitle })}
              </p>
              <button
                type="button"
                data-testid="note-chat-close"
                aria-label={t("editor.discuss")}
                className="rounded-md p-1.5 hover:bg-accent"
                onClick={onClose}
              >
                <X className="size-4" />
              </button>
            </header>
            <div className="min-h-0 flex-1">
              <ChatPanel
                projectId={note.novel_id}
                noteId={note.id}
                onClose={onClose}
              />
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
```

(The banner text lives in the drawer header; `ChatPanel` itself stays unmodified beyond the two prop changes above.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pnpm --filter narrare-web test components/notes/__tests__/NotesChatDrawer.test.tsx components/studio/editor/__tests__`
Expected: PASS (new tests + existing ChatPanel suites untouched-green).

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/studio/editor/ChatPanel.tsx packages/web/components/notes/NotesChatDrawer.tsx packages/web/components/notes/__tests__/NotesChatDrawer.test.tsx
git commit -m "feat(web): project-less ChatPanel and notes chat drawer (NOTES-001)"
```

---

### Task 26: Web — ScratchpadWorkspace + `/scratchpad` page

> **⚠️ MANDATORY (PO requirement):** load the `frontend-design` skill (superpowers) BEFORE writing any UI code in this task.

**Spec slice:** §9.6 (Frontend page) · §7 (layout: list left, editor right, empty state, search-mode toggle with honest badge).

**Files:**
- Create: `packages/web/components/notes/ScratchpadWorkspace.tsx`
- Create: `packages/web/app/(studio)/scratchpad/page.tsx`
- Test: `packages/web/components/notes/__tests__/ScratchpadWorkspace.test.tsx`

**Interfaces:**
- Consumes: `useNotes`, `useNoteTags`, `useCreateNote`, `useSemanticNoteSearch` (T18); `NoteList`, `NoteFilterBar`, `NoteEditor` (T21/T23); `NotesChatDrawer` (T25); i18n `notes.*` (T19/T20).
- Produces: the `/scratchpad` route (server page rendering the client workspace; lives in the `(studio)` group so the shell + sidebar + quick capture apply).

- [ ] **Step 1: Write the failing test**

```tsx
// packages/web/components/notes/__tests__/ScratchpadWorkspace.test.tsx
/**
 * ScratchpadWorkspace tests (NOTES-001): empty state first capture, list
 * rendering + selection, semantic-mode honest badge.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "@/mocks/server";
import { ScratchpadWorkspace } from "../ScratchpadWorkspace";

const emptyNoteList = http.get("*/api/v1/notes", () => HttpResponse.json([]));
const emptyTags = http.get("*/api/v1/notes/tags", () => HttpResponse.json({ tags: [] }));
const emptyNovels = http.get("*/api/v1/novels", () => HttpResponse.json([]));
const emptySeries = http.get("*/api/v1/series", () => HttpResponse.json([]));

describe("ScratchpadWorkspace", () => {
  it("shows the empty state when no notes exist", async () => {
    server.use(emptyNoteList, emptyTags, emptyNovels, emptySeries);
    render(<ScratchpadWorkspace />);
    expect(await screen.findByTestId("scratchpad-empty")).toBeInTheDocument();
  });

  it("creates the first note from the empty-state card", async () => {
    server.use(emptyNoteList, emptyTags, emptyNovels, emptySeries);
    server.use(
      http.post("*/api/v1/notes", async () =>
        HttpResponse.json(
          {
            id: "n1",
            title: null,
            content: "captured thought",
            note_type: "idea",
            tags: [],
            novel_id: null,
            series_id: null,
            created_at: "2026-08-21T00:00:00Z",
            updated_at: "2026-08-21T00:00:00Z",
          },
          { status: 201 },
        ),
      ),
    );
    render(<ScratchpadWorkspace />);
    const textarea = await screen.findByTestId("empty-capture-text");
    fireEvent.change(textarea, { target: { value: "captured thought" } });
    fireEvent.click(screen.getByTestId("empty-capture-save"));
    // After create the list refetches and now shows the note.
    server.use(
      http.get("*/api/v1/notes", () =>
        HttpResponse.json([
          {
            id: "n1",
            title: null,
            content: "captured thought",
            note_type: "idea",
            tags: [],
            novel_id: null,
            series_id: null,
            created_at: "2026-08-21T00:00:00Z",
            updated_at: "2026-08-21T00:00:00Z",
          },
        ]),
      ),
    );
    await waitFor(() =>
      expect(screen.getByTestId("note-list-item-n1")).toBeInTheDocument(),
    );
  });

  it("shows the honest lexical badge on fallback search results", async () => {
    server.use(emptyNovels, emptySeries);
    server.use(
      http.get("*/api/v1/notes", () => HttpResponse.json([])),
      http.get("*/api/v1/notes/tags", () => HttpResponse.json({ tags: [] })),
      http.post("*/api/v1/notes/search", async () =>
        HttpResponse.json({
          mode: "lexical",
          query: "aunt",
          results: [
            {
              id: "n1",
              title: null,
              content: "the aunt did it",
              note_type: "idea",
              tags: [],
              novel_id: null,
              series_id: null,
              created_at: "2026-08-21T00:00:00Z",
              updated_at: "2026-08-21T00:00:00Z",
              similarity: null,
            },
          ],
        }),
      ),
    );
    render(<ScratchpadWorkspace />);
    const search = await screen.findByTestId("note-search-input");
    fireEvent.change(search, { target: { value: "aunt" } });
    fireEvent.click(screen.getByTestId("note-semantic-toggle"));
    fireEvent.keyDown(search, { key: "Enter" });
    expect(await screen.findByTestId("note-search-mode-badge")).toHaveTextContent(
      "search.lexicalBadge",
    );
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pnpm --filter narrare-web test components/notes/__tests__/ScratchpadWorkspace.test.tsx`
Expected: FAIL — cannot resolve `../ScratchpadWorkspace`.

- [ ] **Step 3: Implement**

```tsx
// packages/web/app/(studio)/scratchpad/page.tsx
/**
 * Scratchpad — /scratchpad (NOTES-001 §7).
 *
 * Server wrapper only; all data + interaction live in the client
 * ScratchpadWorkspace (mirrors the series canon page pattern).
 */
import { ScratchpadWorkspace } from "@/components/notes/ScratchpadWorkspace";

export default function ScratchpadPage() {
  return <ScratchpadWorkspace />;
}
```

```tsx
// packages/web/components/notes/ScratchpadWorkspace.tsx
"use client";

/**
 * ScratchpadWorkspace — the /scratchpad page body (NOTES-001 §7).
 *
 * Left: filter bar + note list (query results, or semantic search results
 * with the honest mode badge — RULE-11 spirit in the UI). Right: editor for
 * the selected note. Empty state: a single capture card. "Discuss" opens
 * the NotesChatDrawer.
 */

import { useTranslations } from "next-intl";
import { useState } from "react";
import { NotesChatDrawer } from "./NotesChatDrawer";
import { NoteEditor } from "./NoteEditor";
import { NoteFilterBar, type NoteFilters } from "./NoteFilterBar";
import { NoteList } from "./NoteList";
import { useCreateNote, useNoteTags, useNotes, useSemanticNoteSearch } from "@/lib/hooks/useNotes";
import { NOTE_TYPE_KEYS, type NoteTypeKey } from "@/types";

export function ScratchpadWorkspace() {
  const t = useTranslations("notes");
  const [filters, setFilters] = useState<NoteFilters>({ q: "", note_type: "", tag: "" });
  const [semanticMode, setSemanticMode] = useState(false);
  const [searchResults, setSearchResults] = useState<Awaited<
    ReturnType<ReturnType<typeof useSemanticNoteSearch>["mutateAsync"]>
  > | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [chatNoteId, setChatNoteId] = useState<string | null>(null);
  const [emptyDraft, setEmptyDraft] = useState("");
  const [emptyType, setEmptyType] = useState<NoteTypeKey>("idea");

  const notesQuery = useNotes({
    q: filters.q || undefined,
    note_type: (filters.note_type || undefined) as NoteTypeKey | undefined,
    tag: filters.tag || undefined,
  });
  const tagsQuery = useNoteTags();
  const createNote = useCreateNote();
  const search = useSemanticNoteSearch();

  const notes = searchResults ? searchResults.results : (notesQuery.data ?? []);
  const selectedNote =
    notes.find((note) => note.id === selectedId) ?? null;

  function submitSearch() {
    if (!semanticMode || !filters.q.trim()) {
      setSearchResults(null);
      return;
    }
    search.mutate(
      {
        query: filters.q.trim(),
        note_type: (filters.note_type || undefined) as NoteTypeKey | undefined,
        tag: filters.tag || undefined,
      },
      { onSuccess: setSearchResults },
    );
  }

  function captureFirst() {
    if (!emptyDraft.trim()) return;
    createNote.mutate(
      { content: emptyDraft.trim(), note_type: emptyType },
      {
        onSuccess: (note) => {
          setEmptyDraft("");
          setSelectedId(note.id);
        },
      },
    );
  }

  return (
    <div className="flex h-full min-h-0">
      <div className="flex min-w-72 max-w-96 flex-1 flex-col border-r border-border">
        <header className="border-b border-border p-4">
          <h1 className="text-lg font-medium">{t("page.title")}</h1>
          <p className="text-xs text-muted-foreground">{t("page.subtitle")}</p>
        </header>
        <NoteFilterBar
          filters={filters}
          onFiltersChange={(next) => {
            setFilters(next);
            setSearchResults(null);
          }}
          availableTags={tagsQuery.data?.tags ?? []}
          semanticMode={semanticMode}
          onSemanticModeChange={(enabled) => {
            setSemanticMode(enabled);
            if (!enabled) setSearchResults(null);
          }}
          onSearchSubmit={submitSearch}
        />
        {searchResults && (
          <p
            data-testid="note-search-mode-badge"
            className="border-b border-border bg-muted/50 px-4 py-1 text-xs text-muted-foreground"
          >
            {searchResults.mode === "semantic"
              ? t("search.semanticBadge")
              : t("search.lexicalBadge")}
          </p>
        )}
        <NoteList notes={notes} selectedId={selectedId} onSelect={setSelectedId} />
      </div>

      <div className="min-w-0 flex-1">
        {selectedNote ? (
          <NoteEditor
            note={selectedNote}
            availableTags={tagsQuery.data?.tags ?? []}
            onSaved={() => setSearchResults(null)}
            onDeleted={() => setSelectedId(null)}
            onDiscuss={(noteId) => setChatNoteId(noteId)}
          />
        ) : (
          <section
            data-testid="scratchpad-empty"
            aria-label={t("empty.title")}
            className="flex h-full items-center justify-center p-6"
          >
            <div className="w-full max-w-md rounded-xl border border-border bg-card p-6">
              <h2 className="text-lg font-medium">{t("empty.title")}</h2>
              <p className="mt-1 text-sm text-muted-foreground">{t("empty.description")}</p>
              <div className="mt-4 space-y-2">
                <select
                  value={emptyType}
                  aria-label={t("editor.typeLabel")}
                  className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
                  onChange={(event) => setEmptyType(event.target.value as NoteTypeKey)}
                >
                  {NOTE_TYPE_KEYS.map((key) => (
                    <option key={key} value={key}>
                      {t(`type.${key}`)}
                    </option>
                  ))}
                </select>
                <textarea
                  value={emptyDraft}
                  data-testid="empty-capture-text"
                  aria-label={t("empty.cta")}
                  placeholder={t("editor.contentPlaceholder")}
                  className="h-24 w-full resize-none rounded-md border border-border bg-background p-2 text-sm"
                  onChange={(event) => setEmptyDraft(event.target.value)}
                />
                <button
                  type="button"
                  data-testid="empty-capture-save"
                  className="w-full rounded-md bg-primary px-3 py-2 text-primary-foreground"
                  onClick={captureFirst}
                >
                  {t("empty.cta")}
                </button>
              </div>
            </div>
          </section>
        )}
      </div>

      <NotesChatDrawer
        open={chatNoteId !== null}
        onClose={() => setChatNoteId(null)}
        note={notes.find((note) => note.id === chatNoteId) ?? null}
      />
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pnpm --filter narrare-web test components/notes/__tests__/ScratchpadWorkspace.test.tsx && pnpm --filter narrare-web type-check`
Expected: PASS + no type errors.

- [ ] **Step 5: Commit**

```bash
git add "packages/web/app/(studio)/scratchpad/page.tsx" packages/web/components/notes/ScratchpadWorkspace.tsx packages/web/components/notes/__tests__/ScratchpadWorkspace.test.tsx
git commit -m "feat(web): add scratchpad page with list, editor, empty state, and search badge"
```

---

### Task 27: Web — Sidebar scratchpad entry

> **⚠️ MANDATORY (PO requirement):** load the `frontend-design` skill (superpowers) BEFORE writing any UI code in this task.

**Spec slice:** §7 ("Page `/scratchpad` (sidebar entry …)").

**Files:**
- Modify: `packages/web/components/studio/Sidebar.tsx` (always-visible nav link under the "All Novels" block)
- Test: `packages/web/components/studio/__tests__/Sidebar.scratchpad.test.tsx` (new)

**Interfaces:**
- Consumes: `useTranslations("notes")` (T19/T20); lucide `StickyNote` icon; existing Sidebar structure (`handleNavigate`).
- Produces: global `/scratchpad` nav link visible with AND without a selected novel.

- [ ] **Step 1: Write the failing test**

```tsx
// packages/web/components/studio/__tests__/Sidebar.scratchpad.test.tsx
/**
 * Sidebar scratchpad entry (NOTES-001 §7): the global nav link renders
 * regardless of novel selection and points at /scratchpad.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Sidebar } from "../Sidebar";

// Default MSW handlers already serve GET /api/v1/auth/me.
// NOTE: the setupTests next/navigation mock makes useParams() return
// { id: "novel-1" } — so these tests exercise the WITH-novel case; the
// link's always-visible placement (outside SidebarNav's novelId guard)
// structurally covers the no-novel case.

describe("Sidebar scratchpad entry", () => {
  it("renders the scratchpad link on every page load", async () => {
    render(<Sidebar />);
    const link = await screen.findByTestId("sidebar-scratchpad-link");
    expect(link).toHaveAttribute("href", "/scratchpad");
  });

  it("renders alongside the novel-scoped nav items", async () => {
    render(<Sidebar />);
    expect(await screen.findByTestId("sidebar-scratchpad-link")).toBeInTheDocument();
    // With the mocked params (id "novel-1") the novel nav is present too.
    expect(await screen.findByRole("navigation")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pnpm --filter narrare-web test components/studio/__tests__/Sidebar.scratchpad.test.tsx`
Expected: FAIL — no `sidebar-scratchpad-link` testid.

- [ ] **Step 3: Implement**

In `packages/web/components/studio/Sidebar.tsx`:

1. Import additions: `StickyNote` to the lucide import; `useTranslations as useNotesTranslations` — next-intl exposes only one `useTranslations` hook; call it twice with different namespaces instead:

```typescript
  const t = useTranslations("studio");
  const tNotes = useTranslations("notes");
```

2. Insert directly BELOW the "All Novels" back-link block (before `<SidebarNav … />`):

```tsx
      {/* Scratchpad — global, always available (NOTES-001) */}
      <div className="px-3 pt-1">
        <Link
          href="/scratchpad"
          data-testid="sidebar-scratchpad-link"
          className="w-full flex items-center gap-2 px-4 py-2 rounded-md text-sm text-muted-foreground hover:bg-accent transition-colors"
          onClick={handleNavigate}
        >
          <StickyNote className="w-4 h-4" />
          <span>{tNotes("nav.label")}</span>
        </Link>
      </div>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pnpm --filter narrare-web test components/studio/__tests__/Sidebar.scratchpad.test.tsx components/studio/__tests__/ShellOwnership.test.tsx`
Expected: PASS (new test + existing shell suite unaffected).

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/studio/Sidebar.tsx packages/web/components/studio/__tests__/Sidebar.scratchpad.test.tsx
git commit -m "feat(web): add global scratchpad sidebar entry (NOTES-001)"
```

---

### Task 28: Web — QuickCapturePanel + QuickCaptureProvider (Ctrl/⌘+Shift+U)

> **⚠️ MANDATORY (PO requirement):** load the `frontend-design` skill (superpowers) BEFORE writing any UI code in this task.

**Spec slice:** §9.7 (Quick capture) · §7 (global panel + shortcut + toast with "open in scratchpad").

**Files:**
- Create: `packages/web/components/notes/QuickCaptureProvider.tsx` (context + shortcut + drawer mount)
- Create: `packages/web/components/notes/QuickCapturePanel.tsx`
- Test: `packages/web/components/notes/__tests__/QuickCapture.test.tsx`

**Interfaces:**
- Consumes: `useCreateNote` (T18); Motion variants (existing); `toast` (`sonner`); i18n `notes.quickCapture.*`.
- Produces (used by T29): `QuickCaptureProvider` (client component wrapping children) and `useQuickCapture(): { open: () => void }`. Shortcut binding: **`(event.metaKey || event.ctrlKey) && event.shiftKey && event.key === "U"`** — collision-free per the audit in this plan's Decisions table.

- [ ] **Step 1: Write the failing tests**

```tsx
// packages/web/components/notes/__tests__/QuickCapture.test.tsx
/**
 * QuickCapture tests (NOTES-001 §7): provider shortcut opens the panel,
 * capture creates a note and toasts with the scratchpad link, save resets.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { toast } from "sonner";
import { server } from "@/mocks/server";
import {
  QuickCaptureProvider,
  useQuickCapture,
} from "../QuickCaptureProvider";

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

function OpenButton() {
  const { open } = useQuickCapture();
  return (
    <button type="button" data-testid="qc-open" onClick={open}>
      open
    </button>
  );
}

function renderProvider() {
  return render(
    <QuickCaptureProvider>
      <OpenButton />
    </QuickCaptureProvider>,
  );
}

describe("QuickCapture", () => {
  it("opens via the Ctrl/Cmd+Shift+U shortcut", () => {
    renderProvider();
    fireEvent.keyDown(window, { metaKey: true, shiftKey: true, key: "U" });
    expect(screen.getByTestId("quick-capture-panel")).toBeInTheDocument();
  });

  it("does not open on unrelated combos", () => {
    renderProvider();
    fireEvent.keyDown(window, { metaKey: true, shiftKey: true, key: "N" });
    fireEvent.keyDown(window, { metaKey: true, key: "u" });
    expect(screen.queryByTestId("quick-capture-panel")).not.toBeInTheDocument();
  });

  it("captures a note and toasts success", async () => {
    server.use(
      http.post("*/api/v1/notes", async () =>
        HttpResponse.json(
          {
            id: "n1",
            title: null,
            content: "thought",
            note_type: "idea",
            tags: [],
            novel_id: null,
            series_id: null,
            created_at: "2026-08-21T00:00:00Z",
            updated_at: "2026-08-21T00:00:00Z",
          },
          { status: 201 },
        ),
      ),
    );
    renderProvider();
    fireEvent.click(screen.getByTestId("qc-open"));
    fireEvent.change(screen.getByTestId("qc-text"), { target: { value: "thought" } });
    fireEvent.click(screen.getByTestId("qc-save"));
    await waitFor(() => expect(toast.success).toHaveBeenCalled());
    // Panel resets and closes after a successful capture.
    await waitFor(() =>
      expect(screen.queryByTestId("quick-capture-panel")).not.toBeInTheDocument(),
    );
  });

  it("keeps the panel open when saving an empty thought", () => {
    renderProvider();
    fireEvent.click(screen.getByTestId("qc-open"));
    fireEvent.click(screen.getByTestId("qc-save"));
    expect(screen.getByTestId("quick-capture-panel")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pnpm --filter narrare-web test components/notes/__tests__/QuickCapture.test.tsx`
Expected: FAIL — cannot resolve `../QuickCaptureProvider`.

- [ ] **Step 3: Implement**

```tsx
// packages/web/components/notes/QuickCaptureProvider.tsx
"use client";

/**
 * QuickCaptureProvider — global quick-capture surface (NOTES-001 §7).
 *
 * Mounts once in the studio shell. Owns: open/close state, the
 * Ctrl/⌘+Shift+U shortcut (collision audit: K = palette, S = save,
 * Enter = AI submit; Shift+N rejected — Chrome incognito), Escape-to-close,
 * and the slide-over panel itself. Any component can open it via
 * `useQuickCapture()`.
 */

import { AnimatePresence, motion } from "motion/react";
import { useTranslations } from "next-intl";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { overlayVariants, panelSlideRightVariants } from "@/lib/motion-variants";
import { QuickCapturePanel } from "./QuickCapturePanel";

interface QuickCaptureContextValue {
  open: () => void;
}

const QuickCaptureContext = createContext<QuickCaptureContextValue>({ open: () => {} });

export function useQuickCapture(): QuickCaptureContextValue {
  return useContext(QuickCaptureContext);
}

function isQuickCaptureShortcut(event: KeyboardEvent): boolean {
  return (
    (event.metaKey || event.ctrlKey) && event.shiftKey && event.key === "U"
  );
}

export function QuickCaptureProvider({ children }: { children: ReactNode }) {
  const t = useTranslations("notes");
  const [isOpen, setIsOpen] = useState(false);

  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (isQuickCaptureShortcut(event)) {
        event.preventDefault();
        setIsOpen((value) => !value);
      }
      if (event.key === "Escape") setIsOpen(false);
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <QuickCaptureContext.Provider value={{ open }}>
      {children}
      <AnimatePresence>
        {isOpen && (
          <>
            <motion.div
              variants={overlayVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="fixed inset-0 z-40 bg-black/50"
              onClick={close}
              aria-hidden="true"
            />
            <motion.div
              variants={panelSlideRightVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              role="dialog"
              aria-modal="true"
              aria-label={t("quickCapture.open")}
              className="fixed right-0 top-0 z-50 h-full w-full max-w-sm border-l border-border bg-card"
            >
              <QuickCapturePanel onClose={close} />
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </QuickCaptureContext.Provider>
  );
}
```

(`useTranslations` works here — the provider is a client component.)

```tsx
// packages/web/components/notes/QuickCapturePanel.tsx
"use client";

/**
 * QuickCapturePanel — slim capture form (NOTES-001 §7): optional title,
 * type (default idea), text, optional tag. Save creates the note and
 * toasts with an "open in scratchpad" link. Capture is fast; curation
 * lives on the page.
 */

import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { useCreateNote } from "@/lib/hooks/useNotes";
import { NOTE_TYPE_KEYS, type NoteTypeKey } from "@/types";

export interface QuickCapturePanelProps {
  readonly onClose: () => void;
}

export function QuickCapturePanel({ onClose }: QuickCapturePanelProps) {
  const t = useTranslations("notes");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [tag, setTag] = useState("");
  const [noteType, setNoteType] = useState<NoteTypeKey>("idea");
  const createNote = useCreateNote();

  function handleSave() {
    const content = text.trim();
    if (!content) return;
    createNote.mutate(
      {
        title: title.trim() || null,
        content,
        note_type: noteType,
        tags: tag.trim() ? [tag.trim()] : [],
      },
      {
        onSuccess: () => {
          toast.success(t("quickCapture.saved"), {
            action: {
              label: t("quickCapture.openInScratchpad"),
              onClick: () => onClose(),
            },
          });
          // The toast action links conceptually to /scratchpad; navigating is
          // handled by the link below in the panel footer as well.
          setTitle("");
          setText("");
          setTag("");
          setNoteType("idea");
          onClose();
        },
      },
    );
  }

  return (
    <div data-testid="quick-capture-panel" className="flex h-full flex-col p-4">
      <h2 className="text-lg font-medium">{t("quickCapture.title")}</h2>
      <p className="text-xs text-muted-foreground">{t("quickCapture.shortcutHint")}</p>

      <input
        type="text"
        value={title}
        aria-label={t("quickCapture.titlePlaceholder")}
        placeholder={t("quickCapture.titlePlaceholder")}
        className="mt-4 rounded-md border border-border bg-background px-2 py-1.5 text-sm"
        onChange={(event) => setTitle(event.target.value)}
      />

      <select
        value={noteType}
        aria-label={t("editor.typeLabel")}
        className="mt-2 rounded-md border border-border bg-background px-2 py-1.5 text-sm"
        onChange={(event) => setNoteType(event.target.value as NoteTypeKey)}
      >
        {NOTE_TYPE_KEYS.map((key) => (
          <option key={key} value={key}>
            {t(`type.${key}`)}
          </option>
        ))}
      </select>

      <textarea
        value={text}
        data-testid="qc-text"
        aria-label={t("quickCapture.textPlaceholder")}
        placeholder={t("quickCapture.textPlaceholder")}
        className="mt-2 h-32 resize-none rounded-md border border-border bg-background p-2 text-sm"
        onChange={(event) => setText(event.target.value)}
        autoFocus
      />

      <input
        type="text"
        value={tag}
        aria-label={t("quickCapture.tagPlaceholder")}
        placeholder={t("quickCapture.tagPlaceholder")}
        className="mt-2 rounded-md border border-border bg-background px-2 py-1.5 text-sm"
        onChange={(event) => setTag(event.target.value)}
      />

      <button
        type="button"
        data-testid="qc-save"
        className="mt-3 rounded-md bg-primary px-3 py-2 text-primary-foreground"
        disabled={!text.trim() || createNote.isPending}
        onClick={handleSave}
      >
        {t("quickCapture.save")}
      </button>

      <Link
        href="/scratchpad"
        className="mt-auto self-start text-sm text-muted-foreground underline-offset-4 hover:underline"
        onClick={onClose}
      >
        {t("quickCapture.openInScratchpad")}
      </Link>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pnpm --filter narrare-web test components/notes/__tests__/QuickCapture.test.tsx`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/notes/QuickCaptureProvider.tsx packages/web/components/notes/QuickCapturePanel.tsx packages/web/components/notes/__tests__/QuickCapture.test.tsx
git commit -m "feat(web): add global quick capture panel with Ctrl/Cmd+Shift+U shortcut (NOTES-001)"
```

---

### Task 29: Web — mount quick capture in the shell + sidebar button

> **⚠️ MANDATORY (PO requirement):** load the `frontend-design` skill (superpowers) BEFORE writing any UI code in this task.

**Spec slice:** §9.7 · §7 ("sidebar button (note icon) + keyboard shortcut").

**Files:**
- Modify: `packages/web/components/studio/shell/StudioWorkspaceShell.tsx` (wrap children with `QuickCaptureProvider`)
- Modify: `packages/web/components/studio/Sidebar.tsx` (quick-capture icon button next to the scratchpad link)
- Test: `packages/web/components/studio/__tests__/Sidebar.scratchpad.test.tsx` (extend)

**Interfaces:**
- Consumes: `QuickCaptureProvider`, `useQuickCapture` (T28); `IconButton` (`@/components/ui/icon-button`, existing); lucide `Zap`.
- Produces: quick capture globally available inside the `(studio)` shell (novel workspace + scratchpad page).

- [ ] **Step 1: Extend the failing test (append to Sidebar.scratchpad.test.tsx)**

```tsx
import { fireEvent, screen } from "@testing-library/react";
import { QuickCaptureProvider } from "@/components/notes/QuickCaptureProvider";

describe("Sidebar quick-capture button", () => {
  it("opens the quick capture panel from the sidebar", () => {
    render(
      <QuickCaptureProvider>
        <Sidebar />
      </QuickCaptureProvider>,
    );
    fireEvent.click(screen.getByTestId("sidebar-quick-capture-button"));
    expect(screen.getByTestId("quick-capture-panel")).toBeInTheDocument();
  });
});
```

(Merge the duplicated imports into the file's import block — `fireEvent` joins the existing testing-library import.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `pnpm --filter narrare-web test components/studio/__tests__/Sidebar.scratchpad.test.tsx`
Expected: FAIL — no `sidebar-quick-capture-button` testid.

- [ ] **Step 3: Implement**

In `packages/web/components/studio/shell/StudioWorkspaceShell.tsx`: import `QuickCaptureProvider` from `@/components/notes/QuickCaptureProvider` and wrap the main content — the `<main …>` element's children (so the sidebar stays outside and the drawer overlays content):

```tsx
        <main className="flex-1 min-h-0 min-w-0" aria-label={t("shell.workspaceMain")}>
          <QuickCaptureProvider>{children}</QuickCaptureProvider>
        </main>
```

In `packages/web/components/studio/Sidebar.tsx`, the scratchpad block becomes a flex row with the capture button (new imports: `Zap` from lucide, `useQuickCapture` from `@/components/notes/QuickCaptureProvider`):

```tsx
      {/* Scratchpad — global, always available (NOTES-001) */}
      <div className="flex items-center gap-1 px-3 pt-1">
        <Link
          href="/scratchpad"
          data-testid="sidebar-scratchpad-link"
          className="w-full flex items-center gap-2 px-4 py-2 rounded-md text-sm text-muted-foreground hover:bg-accent transition-colors"
          onClick={handleNavigate}
        >
          <StickyNote className="w-4 h-4" />
          <span>{tNotes("nav.label")}</span>
        </Link>
        <IconButton
          icon={Zap}
          label={tNotes("quickCapture.open")}
          data-testid="sidebar-quick-capture-button"
          onClick={() => quickCapture.open()}
        />
      </div>
```

with `const quickCapture = useQuickCapture();` in the component body. Check `IconButton`'s prop signature (`label`, `icon`, `onClick` — used in `StudioWorkspaceShell`) and whether it forwards `data-testid`; if it does not forward arbitrary props, wrap it in a `<span data-testid="sidebar-quick-capture-button">` and target the span in the test.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pnpm --filter narrare-web test components/studio/__tests__/ && pnpm --filter narrare-web type-check`
Expected: PASS + no type errors.

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/studio/shell/StudioWorkspaceShell.tsx packages/web/components/studio/Sidebar.tsx packages/web/components/studio/__tests__/Sidebar.scratchpad.test.tsx
git commit -m "feat(web): mount quick capture globally with sidebar trigger (NOTES-001)"
```

---

### Task 30: Docs — feature file NOTES-001 + INDEX entry

**Spec slice:** §9.8 · §10 ("registered as NOTES-001 (new feature area `notes`)").

**Files:**
- Create: `docs/features/notes/NOTES-001-scratchpad.md`
- Modify: `docs/features/INDEX.md` (new `### Notes` area with the NOTES-001 row)

**Interfaces:**
- Consumes: `docs/features/_TEMPLATE.md` frontmatter schema; INDEX area-table format.
- Produces: feature registry entry (double duty: developer reference + UI help text source).

- [ ] **Step 1: Write the feature file**

```markdown
<!-- docs/features/notes/NOTES-001-scratchpad.md -->
---
id: NOTES-001
title: "Scratchpad"
status: stable
area: notes
mvp: false

ui_tooltip: "Capture a thought before it escapes — ideas, concepts, questions, unbound to any novel."
ui_help_short: |
  The Scratchpad is a low-friction home for thoughts that do not belong to a
  novel yet: plot ideas, worldbuilding concepts, craft questions. Capture
  quickly from anywhere, curate later, and discuss notes with the chat.
ui_help_long: |
  Notes live independently of novels and series. Each note has a type
  (idea, concept, question, other), free-form tags, and Markdown content.
  A note can optionally be linked to one novel or one series — never both —
  and the link never deletes the note. Semantic search finds notes by
  meaning and always falls back to plain text search, so notes stay
  findable even without an embedding provider. The "Discuss in chat"
  button opens a chat with the note attached as context. Quick capture
  (Ctrl/Cmd+Shift+U or the sidebar bolt) saves a thought from anywhere in
  the app in seconds.
ui_available_in: ["sidebar", "quick-capture"]

service: apps/api/narrare/notes/service.py
contract: apps/api/narrare/notes/contracts.py#NoteServiceProtocol
router: apps/api/narrare/notes/router.py
prompt: ""
requires: ["INFRA-004"]
---

# [NOTES-001] — Scratchpad

## What it does

A novel-independent place to capture, curate, and discuss thoughts: ideas,
concepts, questions that do not belong to any project yet.

## Why it exists

Writers have thoughts at odd moments — shopping, commuting, mid-chapter.
Before the Scratchpad those thoughts had no home: the KB is strictly
novel/series-scoped, chapters are prose, and chat is a conversation, not
storage. The Scratchpad removes the "where do I put this?" friction.

## How it works (User perspective)

1. The writer presses Ctrl/Cmd+Shift+U (or the sidebar bolt) and types a
   thought — a title, a type, and a tag are optional.
2. A toast confirms the capture with a link to the Scratchpad.
3. On `/scratchpad` the writer curates: filter by type/tag, edit Markdown
   with a preview toggle, tag with autocomplete, optionally link to a novel
   or a series.
4. "Discuss in chat" opens a chat panel with the note pre-loaded as context.
5. Search supports a semantic mode; the result badge honestly shows
   `semantic` or `lexical`.

## How it works (Technical)

**Entry point:** `apps/api/narrare/notes/router.py` → `/api/v1/notes` (CRUD, `/tags`, `/search`)
**Service:** `NoteService` in `apps/api/narrare/notes/service.py`; `NoteSearchService` in `search_service.py`
**Contract:** `NoteServiceProtocol` in `apps/api/narrare/notes/contracts.py`; `NoteLookupProtocol` + `NoteSnapshot` in `packages/core/narrare_core/notes/contracts.py`
**Data:** `notes` table (migration `0041_notes`): scope CHECK (`NOT (novel_id IS NOT NULL AND series_id IS NOT NULL)`), GIN index on `tags TEXT[]`, FKs `ON DELETE SET NULL`
**Embeddings:** `source_type="note"` through the generic in-process pipeline (`run_embed_source_inprocess`, ADR-080); delete cleans embeddings (`delete_by_source`)
**Chat:** `ChatRequest.note_id` + optional `project_id` (migration `0042`); note text injected as runtime context via `format_note_context_block` (RULE-02-safe)
**Frontend:** `packages/web/components/notes/*`, TanStack hooks in `lib/hooks/useNotes.ts`, `notes.*` i18n namespace (en/de/fr)

## Constraints & Notes

- Notes are always searchable (RULE-11): semantic search degrades to ILIKE
  with an honest `mode` badge.
- The note outlives its link: `ON DELETE SET NULL` on novel/series.
- No pinning, soft-delete, nesting, rich text, auto-tagging, or
  promote-to-KB in v1 (spec non-goals).
```

- [ ] **Step 2: Add the INDEX entry**

In `docs/features/INDEX.md`, insert a new area section between `### Chat` and `### Knowledge Base` (keeping the table format):

```markdown
### Notes
| ID | Feature | Status | MVP |
|----|---------|--------|-----|
| [NOTES-001](notes/NOTES-001-scratchpad.md) | Scratchpad | ✅ | ❌ |
```

- [ ] **Step 3: Verify**

Run: `uv run python scripts/check_architecture.py` (docs do not affect it, but the gate must stay green) and skim `docs/features/INDEX.md § Frontmatter Schema` for compliance.
Expected: architecture check green; frontmatter keys match the schema.

- [ ] **Step 4: Commit**

```bash
git add docs/features/notes/NOTES-001-scratchpad.md docs/features/INDEX.md
git commit -m "docs(features): register NOTES-001 Scratchpad feature and notes area"
```

---

### Task 31: Final verification gate

**Spec slice:** §8 gates. No files changed — proof only.

- [ ] **Step 1: Full backend verification**

Run: `just verify`
Expected: green (lint, typecheck, unit + integration suites, coverage floors).

- [ ] **Step 2: Architecture gate**

Run: `uv run python scripts/check_architecture.py`
Expected: green — no RULE-XX violations (notably RULE-01b/02/03/04/06/11/14).

- [ ] **Step 3: Frontend verification**

Run: `pnpm --filter narrare-web test && pnpm --filter narrare-web type-check && pnpm --filter narrare-web check:testid`
Expected: all green; testid baseline updated only via the sanctioned ratchet command if new testids require it (`pnpm --filter narrare-web check:testid:update-baseline`).

- [ ] **Step 4: i18n validation**

Run the repo's i18n validation script (`scripts/validate-i18n.ts` — use its documented invocation from `just` or `npx tsx`).
Expected: en/de/fr key parity holds for the `notes` namespace.

- [ ] **Step 5: No commit**

This task produces no diff. Report results.

---

## Self-Review (performed by the plan author)

**1. Spec coverage — every spec section mapped to a task:**

| Spec § | Requirement | Task(s) |
|---|---|---|
| §4 core types/tag rules/fallback title | T1 |
| §4 NoteSnapshot + lookup contract + context block | T2 |
| §4 table `notes` + CHECK + GIN + FK SET NULL | T3 (+ T4 verification) |
| §5 list/create/detail/patch/delete + `/tags` | T5–T7, T9 |
| §5 `POST /notes/search` | T10–T11 |
| §6a embed dispatch create/update + cleanup delete | T7–T8 |
| §6a RULE-11 lexical fallback + mode badge | T10–T11 (API), T26 (UI badge) |
| §6b `project_id` optional + `note_id` | T12–T16 (backend), T24–T25 (frontend) |
| §7 page + list/filter/editor/preview/empty state | T21, T23, T26 |
| §7 quick capture + shortcut + toast link | T28–T29 |
| §7 sidebar entry | T27 |
| §7 TanStack hooks list | T18 |
| §7 i18n `notes.*` en/de/fr + type labels | T19–T20 |
| §8 core unit tests | T1–T2 tests |
| §8 backend unit tests (dispatch/cleanup/filters/fallback) | T7, T10 tests |
| §8 router roundtrips + migration roundtrips + 404/ownership | T9, T11, T4, T12 |
| §8 chat extension regression tests | T13–T16 tests |
| §8 frontend Vitest + locale labels + badge + preview | T18, T20–T26 tests |
| §9 slices 1–8 | T1–T2, T3–T4, T5–T9, T10–T11, T12–T16, T21+T23+T26, T27–T29, T30 |
| §10 feature registration NOTES-001 | T30 |

Gaps: none. Deliberate exclusions are the spec's own non-goals (§1).

**2. Placeholder scan:** searched for "TBD", "TODO", "implement later", "similar to Task N", and artifact patterns — none remain in final code blocks. Three tasks carry bounded verification instructions tied to real pre-existing unknowns, each with a fully specified resolution path (not open-ended): T6 (factory placement follows the existing `tests/factories` layout, body given), T23 (ConfirmDialog confirm-button testid → fallback assertion on the visible label given), T29 (IconButton testid forwarding → span-wrapper fallback given). The i18n key set in T19 exactly matches what components reference — `editor.saved` is intentionally absent from both catalogs and component code (post-save feedback is the parent's `onSaved`, e.g. list refetch + selection).

**3. Type consistency check (cross-task signatures):**
- `NoteRepositoryProtocol` methods (T5) == `NoteRepository` implementation (T6) == `FakeNotesRepository` (T7). ✓
- `NoteService.__init__` kwargs (T7 Interfaces) == `get_note_service` wiring (T8) == test `_service()` helper (T7). ✓
- `get_note_snapshot(note_id, user_id) -> NoteSnapshot | None` (T2 contract) == T7 implementation == T16 usage. ✓
- `NoteSearchService.search(user_id, request) -> NoteSearchResponse` (T10) == T11 route. ✓
- `ChatRequest` fields `project_id/message/conversation_id/note_id` (T13) == T14 router conversion == T15/T16 service usage == T24 frontend body. ✓
- `useChat(projectId: string | null, noteId?: string | null)` (T24) == `ChatPanel` usage (T25). ✓
- `notesKeys` shape (T18) == invalidation targets in hooks. ✓
- `NoteFilters` (T21 `NoteFilterBar`) == `ScratchpadWorkspace` state (T26). ✓
- i18n keys used in components (T21–T28) ⊆ keys defined in T19 catalogs and asserted in T20 parity test. ✓ (`editor.saved` is used by NO component — deliberately absent from catalogs and the T20 key list.)
- Frontend hook names verified against the repo: `useSeriesList()` (list), `useNovels()` (list) — T23 uses the list variants, not the detail hooks. ✓

**4. Sizing check:** every task touches ≤3 substantive files (empty `__init__.py` markers flagged as scaffolding in T1/T3/T5). Largest tasks (T3, T7, T26) stay within ~250 new LOC.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-08-21-scratchpad.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, fast iteration.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

**Chosen: 1 — Subagent-Driven.** Executed 2026-08-21 → 2026-08-24 (T1–T31 + coordinator-inserted T21b
and T29b; 33 per-task reviews + final whole-branch review + one fix wave, all clean).

---

## Deferred Follow-up Backlog (post-merge)

> **2026-08-25 update: executed in PR #190** (commits `b2947a91..25167539`, batch-reviewed clean).
> Completed: the **pre-existing chat-history ownership gap** (P-SEC — closed 3 IDOR vectors:
> history GET/DELETE user-scoping, ask() pre-write ownership gate with eager 404, foreign
> project_id rejection via always-wired owned-lookup), embedding write-model alignment with
> CoreSettings (P-EMB), the full test-depth batches (P-BT1/BT2/BT3), dead-surface removal
> (`get_many_by_ids`, unused i18n keys — P-DS/P-DOC), log-field enrichment (P-LOG), and the
> frontend polish batches (P-FE1–FE4: provider memo, locale dates via `useFormatter`, tag-list
> a11y per APG, sidebar active state, `scopeToParams` dedup, stale-searchResults clear,
> `keepPreviousData`, `noteIdRef` stabilization + documented per-turn decision, drawer own
> Escape/exit-animation). Remaining open items below are marked **[open]**.

> Triaged by the final whole-branch review (2026-08-24). None block the merge; grouped for
> future slices. DoD evidence, gates, and per-task review trails live in the branch history
> (37+ commits, `0a12b2da..0e954dad`).

**a11y / polish batch**
- ~~Quick-capture provider context value not memoized~~ (done, P-FE1)
- ~~`toLocaleDateString` → next-intl `useFormatter`~~ (done, P-FE1)
- ~~TagInput: no `onMouseLeave` highlight clear; tabbable pills~~ (done, P-FE2)
- ~~Sidebar scratchpad entry: no active-state styling~~ (done, P-FE2)
- **[open]** Quick-capture tooltip; focus management after AI output (ux-review checklist items)

**Scratchpad interaction batch**
- ~~Stale-scope reset should also clear semantic `searchResults`~~ (done, P-FE3)
- ~~`scope → params` mapping duplicated~~ (done, P-FE3 — `scopeToParams`)
- ~~`q` per-keystroke loading pulse~~ (done, P-FE3 — `keepPreviousData`)
- ~~`useChat` `noteId` not stabilized; per-turn decision undocumented~~ (done, P-FE4)
- ~~`NotesChatDrawer`: own Escape handler + exit animation~~ (done, P-FE4)
- **[open]** NotesChatDrawer double-onClose when not streaming (Escape hits ChatPanel else-branch + drawer handler — idempotent today, dedupe on next touch); focus trap in drawer
- **[open]** `useChat`/`ScratchpadWorkspace` at RULE-04 ceilings (149/150, 199/200) — next touch must extract

**Test-depth batch**
- ~~Repository per-filter SQL assertions + issubclass guard~~ (done, P-BT1)
- ~~Service same-value no-dispatch branch~~ (done, P-BT1)
- ~~Search whitespace-only query; threshold assertion; zero-hit design note~~ (done, P-BT2)
- ~~Chat unwired-lookup + agent-side prompt assertion~~ (done, P-BT3)
- ~~Core multi-tag header join test; savepoint-based 0041 probe~~ (done, P-BT3)
- **[open]** Cross-user ownership test at router level (path identical to 404; store-level covered)

**Dead surface / docs batch**
- ~~`get_many_by_ids` removed~~ (done, P-DS)
- ~~Unused i18n keys `editor.newNote`, `editor.addTag`~~ (done, P-DOC)
- ~~Embedding write model hardcoded vs CoreSettings search model~~ (done, P-EMB — `effective_model = model or core default`)
- ~~Log fields: `note_background_task_failed` note_id; chat skip log user_id~~ (done, P-LOG)
- **[open]** `dimension or 1536` literal has no CoreSettings counterpart; `memory/embedding_cascade.py` literals (RULE-18b candidates)

**Security follow-up (pre-existing)**
- ~~`chat/router.py` history ownership~~ (done, P-SEC — 3 IDOR vectors closed, adversarially reviewed)
- ~~IDOR sweep for OTHER modules accepting `novel_id`/`project_id` links~~ (done 2026-08-29 — audit found 21 GAP-CRITICALs in 12 clusters; S1–S13 remediated in PR #190 commits `f08e5d0b..b6376f07`, batch-reviewed clean; see [2026-08-26-idor-remediation.md](2026-08-26-idor-remediation.md) execution record + residual OPEN list incl. the S3/WS ticket follow-up per D1:a/D4:b)
- **[open]** `chat/router.py` message_id reports conversation id (cosmetic logging)
