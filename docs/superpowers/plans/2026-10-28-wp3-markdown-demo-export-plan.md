# WP3 — Markdown, Demo, Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Markdown becomes the canonical prose storage, one interchange format serves backup and demo loading, and export/import (new novel and merge-into-existing) ships end to end.

**Architecture:** The interchange engine lives in the kernel (`app/kernel/interchange/`) over the shared `kernel/contracts` models and the scoped repository base — two capabilities need it (setup: demo load; writing: HTTP surface), which is the §10 kernel test. The writing capability owns the HTTP surface and the shelf UI; the setup capability loads bundled demo archives through the same engine. The TipTap editor switches from `getHTML()` to `@tiptap/markdown`.

**Tech Stack:** FastAPI + SQLAlchemy async (backend), `pyyaml` for frontmatter (already accepted at runtime), `zipfile` (stdlib), `@tiptap/markdown` 3.31.3 (the one new frontend dependency, pre-named by the Fahrplan), Vitest for web tests.

**Spec:** `docs/superpowers/specs/2026-10-28-wp3-markdown-demo-export-design.md`. The plan argues from the spec; executors read both.

## Global Constraints

- One capability one folder; no capability imports another capability; shared domain in `app/kernel/`, shared UI in the shell (`web/ui/`).
- Every user-owned row carries `user_id`; data access through the scoped repository base.
- User-visible text in en, de and fr in the same commit, in `web/lib/i18n.ts`; a missing key is a build error.
- No LLM surface changes: no prompt edits, no provider calls, the fake is untouched. Embeddings stay the kernel's env-based path exactly as WP1 left them.
- No new rule, registry, check script, hook or justfile recipe. Existing recipes only: `just check`, `just test-file <path>`, `just db-reset`, `just verify`, `just generate` (only if a generated file changes).
- Conventional commits; `feat`/`fix` carry a real `User-visible:` line. Nothing is committed before the task's review is green.
- Import maintains WP1's invariants: `search_text` and the synchronous embedding are computed in the import's own transaction for every new or content-changed entity.
- Import never inserts foreign UUIDs: `id`/`updated` in frontmatter are match keys only; every inserted row gets a fresh UUID. (Chapters table PK is `id` alone — inserting a foreign id would collide across novels.)
- `just check` before every commit; the capability's E2E is the WP's done gate, on the real stack (real UI, real API, real DB), `assert_accessible` on every page it visits.

## Review Focus

The five input classes the spec implies but a task's happy path does not exercise; each is pinned by a test in the owning task:

1. **A stale archive must never overwrite newer prose** — file `updated` older than the row's `updated_at`, content differing → conflict, prose byte-unchanged. Pinned in Task 3 (`test_stale_revision_is_refused`) and Task 8 E2E.
2. **Re-export over an existing backup must refuse** — export to a non-empty directory is a named error, never a silent shrink of the backup WP6's delete flow depends on. Pinned in Task 4 (`test_export_refuses_non_empty_target`).
3. **A bare hand-added file must import** — a `chapters/*.md` with no frontmatter and no index entry is the outside-workflow gesture; it appends in filename order. Pinned in Task 3 (`test_bare_chapter_file_imports`) and Task 8 E2E.
4. **The editor is a second Markdown serializer** — TipTap (`getMarkdown()`) may normalise what the engine wrote byte-stably; drift must be named, not discovered. Pinned in Task 6 (round-trip over the demo corpus with a documented normalisation list).
5. **Hostile archives fail named, not loudly** — oversized ZIP, malformed `metadata.json`, unknown entity type. Pinned in Task 2 (`test_malformed_frontmatter_names_the_file`), Task 3 (`test_unknown_entity_type_is_a_conflict`), Task 4 (`test_oversized_zip_is_413`).

---

### Task 1: Novel metadata columns

**Files:**
- Modify: `app/kernel/contracts/models.py` (`class Novel`, lines 50-64)
- Modify: `app/capabilities/writing/repository.py` (`create` gains author/language)
- Modify: `app/capabilities/writing/schemas.py` (`NovelRead` gains the fields)
- Test: `app/capabilities/writing/tests/test_novel_metadata.py`

**Interfaces:**
- Consumes: existing `NovelRepository.create(novel_title)` and `NovelRead`.
- Produces: `Novel.author: Mapped[str | None] = mapped_column(String(200))`, `Novel.language: Mapped[str | None] = mapped_column(String(16))` (BCP-47-ish code, `de`/`en`; nullable — a novel without an answer does not lie). `NovelRepository.create(title: str, *, author: str | None = None, language: str | None = None) -> Novel`. `NovelRead.author: str | None`, `NovelRead.language: str | None`. Later tasks import these from `app.kernel.contracts.models`.

- [ ] **Step 1: Write the failing test**

```python
async def test_novel_carries_author_and_language(roundtrip):
    novel = await NovelRepository(session, user_id).create(
        "Im stillen Wald", author="J. Autorin", language="de"
    )
    reread = await NovelRepository(session, user_id).get(novel.id)
    assert (reread.author, reread.language) == ("J. Autorin", "de")

async def test_novel_metadata_defaults_to_none(roundtrip):
    novel = await NovelRepository(session, user_id).create("Blank")
    assert novel.author is None and novel.language is None
```

(Follow the existing writing-test fixture style for session/user; the suite runs against the real database.)

- [ ] **Step 2: Run test to verify it fails**

Run: `just test-file app/capabilities/writing/tests/test_novel_metadata.py`
Expected: FAIL — `TypeError: create() got an unexpected keyword argument 'author'`.

- [ ] **Step 3: Add the columns, widen `create`, extend `NovelRead`**

Two nullable columns on `Novel`; `create` passes them through; `NovelRead` exposes them. No default values in code — None is honest.

- [ ] **Step 4: Reset the development database, run the test**

Run: `just db-reset && just test-file app/capabilities/writing/tests/test_novel_metadata.py`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add app/kernel/contracts/models.py app/capabilities/writing/repository.py app/capabilities/writing/schemas.py app/capabilities/writing/tests/test_novel_metadata.py
git commit -m "feat(writing): novels carry author and language

User-visible: a novel's metadata grows author and language; both are
optional and travel with every export."
```

### Task 2: Interchange format and abstract tree

**Files:**
- Create: `app/kernel/interchange/__init__.py`
- Create: `app/kernel/interchange/format.py`
- Create: `app/kernel/interchange/tree.py`
- Test: `app/kernel/tests/test_interchange_format.py`

**Interfaces:**
- Consumes: `pyyaml` (runtime-accepted). No DB.
- Produces (Task 3, 4, 5 rely on exactly these):
  - `@dataclass ChapterFile`: `title: str, position: int, body: str, id: UUID | None = None, updated: datetime | None = None`
  - `@dataclass EntityFile`: `name: str, type: str, aliases: list[str], tags: list[str], body: str, id: UUID | None = None, updated: datetime | None = None`
  - `@dataclass RelationEdge`: `from_name: str, relation_type: str, to_name: str, note: str | None = None`
  - `@dataclass NovelArchive`: `title: str, author: str | None = None, genre: str | None = None, blurb: str | None = None, language: str | None = None, chapters: list[ChapterFile], entities: list[EntityFile], relations: list[RelationEdge]`
  - `parse_archive(tree: ArchiveTree) -> NovelArchive` — raises `ArchiveError(file, reason)` with the offending file named.
  - `serialize_archive(archive: NovelArchive) -> dict[str, bytes]` — deterministic: stable key order (`metadata.json` first), `\n` line endings, frontmatter keys in the fixed order `title, position, id, updated` / `type, name, aliases, tags, id, updated` (omitting None), file names `chapters/<nn>-<slug>.md`, `kb/<slug>.md` with the slug rule: lowercase, ASCII-folded, non-alphanumerics to `-`, trimmed, empty → `untitled`, collision → `-2`, `-3`; `<nn>` is the zero-padded position.
  - `class ArchiveTree`: `read_bytes(relpath: str) -> bytes`, `chapter_names() -> list[str]` (sorted), `kb_names() -> list[str]` (sorted). Built by `open_directory(path: Path) -> ArchiveTree` and `open_zip(data: bytes) -> ArchiveTree`; `write_directory(path: Path, files: dict[str, bytes]) -> None` refuses a non-empty target; `zip_bytes(files: dict[str, bytes]) -> bytes`.
  - Frontmatter: YAML between `---` delimiters via pyyaml (`yaml.safe_load`); a file without frontmatter parses with defaults (`title` = filename stem de-slugged, `position` = order of appearance, entity `type` = `generic`, empty lists). `metadata.json` keys `title, author, genre, blurb, language, chapters[{file, position}], relations[{from, type, to, note?}]`.

- [ ] **Step 1: Write the failing tests**

Test names and assertions (in `app/kernel/tests/test_interchange_format.py`):

```python
def test_round_trip_is_byte_identical(): ...          # build NovelArchive -> serialize -> write to dir -> parse -> serialize -> equal dicts
def test_zip_and_directory_parse_identically(): ...    # same files via open_zip and open_directory -> equal NovelArchive
def test_bare_md_without_frontmatter_uses_defaults(): ...
def test_malformed_frontmatter_names_the_file(): ...   # bad YAML -> ArchiveError with the relpath in str(e)
def test_serialize_is_deterministic(): ...             # serialize twice, dict equality; slug + padding rules pinned
def test_metadata_json_relations_parse(): ...          # from/type/to/note round-trips
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `just test-file app/kernel/tests/test_interchange_format.py`
Expected: FAIL — `ModuleNotFoundError: app.kernel.interchange`.

- [ ] **Step 3: Implement `format.py` and `tree.py`**

Straightforward dataclasses + pyyaml frontmatter; `zipfile.ZipFile(io.BytesIO(data))` for reading, deterministic `ZipInfo` (fixed date_time, sorted names) for writing. `write_directory` checks the target: existing and non-empty → `ArchiveError(path, "target not empty")`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `just test-file app/kernel/tests/test_interchange_format.py`
Expected: PASS (all six).

- [ ] **Step 5: Commit**

```bash
git add app/kernel/interchange/ app/kernel/tests/test_interchange_format.py
git commit -m "feat(kernel): the interchange format and its directory/ZIP tree

User-visible: none yet — the format module this WP's export and demo
loading stand on."
```

### Task 3: Export and merge engine

**Files:**
- Create: `app/kernel/interchange/engine.py`
- Test: `app/kernel/tests/test_interchange_engine.py`

**Interfaces:**
- Consumes: Task 2's `parse_archive`/`serialize_archive`/`ArchiveTree`; `Novel`, `Chapter`, `Entity`, `EntityRelation` from `app.kernel.contracts.models`; the scoped repository base; the kernel embedding path exactly as the entity write paths in `app/capabilities/knowledge/service.py` use it (same function, same cap).
- Produces (Task 4, 5 rely on exactly these):
  - `@dataclass Conflict`: `file: str, reason: str`
  - `@dataclass ImportReport`: `novel_id: UUID`, `chapters_new: int, chapters_revised: int, chapters_already_current: int`, `entities_new: int, entities_revised: int, entities_renamed: int, entities_already_current: int`, `relations_created: int, relations_already_current: int`, `conflicts: list[Conflict]` (chapters, entities, edges and metadata diffs together), `metadata_conflicts: list[str]` (field names not applied on merge)
  - `async def export_novel(session: AsyncSession, user_id: UUID, novel_id: UUID) -> tuple[str, dict[str, bytes]]` — the slug and the files; scoped to `user_id`; a missing novel raises `LookupError`.
  - `async def import_archive(session: AsyncSession, user_id: UUID, tree: ArchiveTree, novel_id: UUID | None) -> ImportReport` — `None` creates a new novel from `metadata.json` (title required; author/genre/blurb/language applied); a `novel_id` merges by the spec's eight rules. Commits once at the end.

- [ ] **Step 1: Write the failing tests**

In `app/kernel/tests/test_interchange_engine.py`, against the real database (follow `test_jobs.py`'s session/user fixtures). Seed with `NovelRepository`/direct model inserts; build archives with Task 2's `serialize_archive`.

```python
async def test_export_then_import_as_new_is_identical(): ...   # titles, types, bodies, aliases, tags, relations equal; fresh UUIDs
async def test_reimport_same_archive_is_already_current(): ... # all counts already_current, no writes (updated_at unchanged)
async def test_stale_revision_is_refused(): ...                # content differs, file updated < row updated_at -> conflict, body byte-unchanged
async def test_newer_file_revision_applies(): ...              # content differs, file updated >= row updated_at -> revised
async def test_bare_chapter_file_imports(): ...                # no id/frontmatter -> new, appended after last position, filename order
async def test_entity_rename_is_applied_and_reported(): ...    # id-match, name differs -> entities_renamed, FK edges intact (count equal)
async def test_unknown_entity_type_is_a_conflict(): ...        # type "dragon" not in ENTITY_TYPES -> conflict row, nothing created
async def test_type_discrepancy_is_a_conflict(): ...           # id-match but type differs -> conflict, row unchanged
async def test_edges_are_create_only(): ...                    # identical edge -> already_current; same edge other note -> conflict; absent target -> conflict naming the edge
async def test_merge_does_not_touch_novel_metadata(): ...      # differing title/genre in metadata.json -> metadata_conflicts lists fields, novel row unchanged
async def test_new_novel_applies_metadata(): ...               # author/language/genre/blurb land on the new row
async def test_import_maintains_search_text_and_embedding(): ...  # both set for new and content-changed entities; unchanged entity untouched
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `just test-file app/kernel/tests/test_interchange_engine.py`
Expected: FAIL — `ModuleNotFoundError: app.kernel.interchange.engine`.

- [ ] **Step 3: Implement `engine.py`**

The decision loop in the spec's order: match (`id`, else casefold `name` for entities) → already-current (field equality, no write) → revision guard (file `updated` not older than row `updated_at`; missing `updated` counts as new) → apply. Entity revision applies body, aliases, tags, `name` (renames counted separately); type discrepancy is a conflict. Chapters: new ones append after `max(position) + 1` in index-then-filename order; frontmatter position beats the index, a disagreement is a reported conflict for new files and ignored for revisions (the stock's position is the truth being merged into). Edges: resolve by name within the novel; create-only against the unique constraint `(user_id, from, to, relation_type)`. Every insert mints fresh UUIDs. Entity writes maintain `search_text` and the embedding synchronously, reusing the knowledge capability's exact helpers — if those helpers live capability-side, the engine re-implements the two-line calls against the kernel embedding module rather than importing a capability (no cross-import; the invariant, not the code, is shared).

- [ ] **Step 4: Run tests to verify they pass**

Run: `just test-file app/kernel/tests/test_interchange_engine.py`
Expected: PASS (all twelve).

- [ ] **Step 5: Commit**

```bash
git add app/kernel/interchange/engine.py app/kernel/tests/test_interchange_engine.py
git commit -m "feat(kernel): export and merge engine for the novel archive

User-visible: none yet — the rules export and import will run on:
idempotent re-import, stale-file refusal, renames reported, edges
create-only."
```

### Task 4: Writing HTTP surface

**Files:**
- Modify: `app/capabilities/writing/router.py`
- Modify: `app/capabilities/writing/schemas.py`
- Modify: `app/capabilities/writing/service.py`
- Test: `app/capabilities/writing/tests/test_interchange_api.py`

**Interfaces:**
- Consumes: Task 3's `export_novel`/`import_archive`/`ImportReport`; Task 2's `open_zip`/`zip_bytes`/`write_directory`/`open_directory`.
- Produces (Task 7 relies on exactly these):
  - `POST /api/writing/novels/{novel_id}/export` — body `ExportRequest{mode: Literal["path","zip"], path: str | None}`; `zip` → `Response` with `media_type="application/zip"` and `Content-Disposition: attachment; filename="<slug>.zip"`; `path` → `200` `ExportDone{path: str, chapters: int, entities: int}`. Validation: `mode="path"` without `path` → 422 named field; target exists and non-empty → 409 `{detail: {code: "target_not_empty", path}}`; path not writable/unreachable → 422 named field `path` with the OS reason. A novel not owned → 404.
  - `POST /api/writing/novels/import` — multipart form: `archive: UploadFile | None`, `path: str | None`, `novel_id: UUID | None`. Exactly one of `archive`/`path` → else 422 named field. `MAX_ARCHIVE_BYTES = 20_000_000` in `writing/service.py` (the `MAX_UPLOAD_BYTES` pattern from knowledge) → 413. `ArchiveError` → 422 with the file named. Success → `201` `ImportReportRead` (the `ImportReport` fields, camelCase per the schema conventions in `schemas.py`).
  - `MAX_ARCHIVE_BYTES`, `ExportRequest`, `ExportDone`, `ImportReportRead` exported from `writing/schemas.py` / `service.py` as the web client's contract.

- [ ] **Step 1: Write the failing tests**

```python
async def test_export_zip_round_trips(): ...              # POST export mode=zip -> application/zip; bytes parse via open_zip into the same novel
async def test_export_path_writes_and_refuses_non_empty_target(): ...
async def test_export_path_unwritable_is_422_named(): ... # tmp_path trick: path under a read-only or non-existent root
async def test_import_zip_as_new_novel(): ...
async def test_import_path_merge_into_existing(): ...     # novel_id set -> report counts match DB
async def test_import_needs_exactly_one_source(): ...     # neither or both of archive/path -> 422 named
async def test_oversized_zip_is_413(): ...                # 20_000_001 bytes of padding
async def test_malformed_archive_is_422_with_file_named(): ...
async def test_foreign_novel_is_404(): ...                # export of another user's novel id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `just test-file app/capabilities/writing/tests/test_interchange_api.py`
Expected: FAIL — 404s on the new routes.

- [ ] **Step 3: Implement the two routes and the service methods**

`WritingService.export_novel(novel_id, mode, path)` and `WritingService.import_novel(archive|path, novel_id)`; thin router, logic in the service calling the kernel engine. The ZIP response is a plain `Response(content=..., media_type=..., headers=...)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `just test-file app/capabilities/writing/tests/test_interchange_api.py`
Expected: PASS (all nine).

- [ ] **Step 5: Commit**

```bash
git add app/capabilities/writing/router.py app/capabilities/writing/schemas.py app/capabilities/writing/service.py app/capabilities/writing/tests/test_interchange_api.py
git commit -m "feat(writing): export and import endpoints over the interchange engine

User-visible: a novel can be exported to a path or as a ZIP and
imported as a new novel or merged into an existing one, with a report."
```

### Task 5: Demo corpus and setup loading

**Files:**
- Create: `app/kernel/interchange/demos/im-stillen-wald/` (metadata.json, chapters/, kb/)
- Create: `app/kernel/interchange/demos/dead-signal/` (same shape)
- Create: `app/kernel/interchange/demos/echoes-of-the-thornwall/` (same shape)
- Create: `app/kernel/interchange/demos.py`
- Modify: `app/capabilities/setup/service.py`
- Modify: `app/capabilities/setup/router.py`, `app/capabilities/setup/schemas.py` (demo choice in first-run)
- Modify: `app/capabilities/setup/web/SetupPage.tsx` (the demo picker: blank + the three demos, from `DEMOS`)
- Modify: `web/lib/i18n.ts` (setup demo keys, en/de/fr)
- Test: `app/kernel/tests/test_interchange_demos.py`
- Test: `app/capabilities/setup/tests/test_demo_load.py`

**Interfaces:**
- Consumes: v1 demo data at git commit `96ae118a`, path `apps/api/narrare/setup/demo_data/{de/en}/<slug>/` — recover with `git show 96ae118a:apps/api/narrare/setup/demo_data/de/im-stillen-wald/metadata.json` (and each chapter/kb file). Task 3's `import_archive`.
- Produces: `DEMOS: tuple[DemoInfo, ...]` and `@dataclass DemoInfo{slug: str, title: str, language: str}` in `demos.py`, ordered `im-stillen-wald`, `dead-signal`, `echoes-of-the-thornwall`; `demos.demo_tree(slug) -> ArchiveTree` (a directory tree over the bundled folder). `SetupService.complete(novel_title: str, demo: str | None = None) -> Novel` — a demo slug imports that archive as a new novel in the same transaction; `None` is today's blank path, byte-for-byte. Router: the first-run payload gains `demo: str | None`; an unknown slug → 422 named field.

- [ ] **Step 1: Port the v1 demos into the C+ shape**

Prose verbatim from v1; structure reshaped per the spec (§6.4): v1 `char-`/`loc-` prefixes become `type: character` / `type: location`; v1 flat fields become Markdown body sections (`## Beschreibung` etc., following each file's existing field order); the v1 `relationships:` map becomes `related_to` edges with the prose as `note`; metadata gains `language` (`de`/`en`/`en`) and `author` from the v1 metadata. No `id`/`updated` in demo frontmatter (hand-maintained source). Verify each archive parses: `parse_archive(demos.demo_tree(slug))`.

- [ ] **Step 2: Write the failing tests**

```python
# app/kernel/tests/test_interchange_demos.py
def test_every_demo_parses(): ...                       # all three slugs -> NovelArchive with >= 1 chapter and >= 1 entity
def test_demo_golden_round_trip_is_byte_identical(): ...  # parse -> serialize -> parse -> serialize; both serializations equal; covers Review Focus 4's engine half

# app/capabilities/setup/tests/test_demo_load.py
async def test_complete_with_demo_loads_archive(): ...  # chapters, entities, relations present; language/author set
async def test_complete_without_demo_is_unchanged(): ... # the blank path creates exactly one empty novel, no demo rows
async def test_unknown_demo_slug_is_422(): ...
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `just test-file app/kernel/tests/test_interchange_demos.py app/capabilities/setup/tests/test_demo_load.py`
Expected: FAIL — `ModuleNotFoundError: app.kernel.interchange.demos`.

- [ ] **Step 4: Implement `demos.py`, the setup extension and the picker UI**

`demos.py` is the manifest plus `demo_tree`; setup's `complete` gains the `demo` parameter calling `import_archive(session, user_id, demo_tree(slug), None)` before the commit; `SetupPage` renders the blank path unchanged plus one card per `DEMOS` entry (title, language, chapter/entity counts), the existing wizard step pattern.

- [ ] **Step 5: Run tests to verify they pass**

Run: `just test-file app/kernel/tests/test_interchange_demos.py app/capabilities/setup/tests/test_demo_load.py`
Expected: PASS (all five).

- [ ] **Step 6: Commit**

```bash
git add app/kernel/interchange/demos app/kernel/interchange/demos.py app/kernel/tests/test_interchange_demos.py app/capabilities/setup/ web/lib/i18n.ts
git commit -m "feat(setup): the three demo novels, loadable through the interchange engine

User-visible: first run can start from a demo novel (fantasy, sci-fi,
German literary) instead of a blank one."
```

### Task 6: Markdown editor (web)

**Files:**
- Modify: `web/package.json` (+`@tiptap/markdown` 3.31.3)
- Create: `web/ui/markdown-editor.tsx` (shared shell component)
- Modify: `app/capabilities/writing/web/ChapterEditor.tsx` (uses Markdown; `getMarkdown()` on save)
- Modify: `app/capabilities/writing/web/ChapterEditor.test.tsx`
- Modify: `app/capabilities/knowledge/web/EntitiesPanel.tsx` (the multiline `TextField` at ~line 528 → the shared Markdown editor; F-26)
- Test: `web/ui/markdown-editor.test.tsx`
- Test: `app/capabilities/writing/web/markdown-roundtrip.test.ts`

**Interfaces:**
- Consumes: `@tiptap/react`, `@tiptap/starter-kit` (pinned 3.31.3), new `@tiptap/markdown` (same version); `@shell/lib/i18n`'s `useTranslation`; the demo corpus at `app/kernel/interchange/demos/` (read via `node:fs` in the Vitest round-trip test).
- Produces: `MarkdownEditor({value: string, onChange: (markdown: string) => void, label: string})` in `web/ui/markdown-editor.tsx` — TipTap with `contentType: 'markdown'`, the same `prose` class and ARIA attributes the chapter editor carries today, `immediatelyRender: false`. `ChapterEditor` keeps all ghost/continuation machinery and switches its save line to `instance.getMarkdown()`; its `body` prop is Markdown now. The entity dialog's body field becomes `MarkdownEditor` wired to the existing `changes.content` save path.

- [ ] **Step 1: Write the failing tests**

```typescript
// web/ui/markdown-editor.test.tsx
test("renders markdown as rich text and emits markdown on change", ...);
test("carries the aria label", ...);

// app/capabilities/writing/web/markdown-roundtrip.test.ts — Review Focus 4
test.each(demoChapterFiles)("editor round-trips %s without drift", (file) => {
  // load body -> editor instance -> getMarkdown() === body, or the difference is in NAMED_NORMALISATIONS
});
```

`NAMED_NORMALISATIONS` is the documented list in the test file's header comment; a new drift fails the test until it is named and justified here.

- [ ] **Step 2: Run tests to verify they fail**

Run: `just test-file web/ui/markdown-editor.test.tsx` and `just test-file app/capabilities/writing/web/markdown-roundtrip.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`pnpm --dir web add @tiptap/markdown@3.31.3`; extract the base editor to `web/ui/markdown-editor.tsx`; rewire `ChapterEditor` (save = `getMarkdown()`) and `EntitiesPanel` (body field). No route changes → no `just generate`.

- [ ] **Step 4: Run the web tests**

Run: `just test-file web/ui/markdown-editor.test.tsx app/capabilities/writing/web/markdown-roundtrip.test.ts app/capabilities/writing/web/ChapterEditor.test.tsx`
Expected: PASS; the round-trip pins each demo chapter byte-identically or via a named normalisation.

- [ ] **Step 5: Commit**

```bash
git add web/package.json web/pnpm-lock.yaml web/ui/markdown-editor.tsx web/ui/markdown-editor.test.tsx app/capabilities/writing/web/ChapterEditor.tsx app/capabilities/writing/web/ChapterEditor.test.tsx app/capabilities/writing/web/markdown-roundtrip.test.ts app/capabilities/knowledge/web/EntitiesPanel.tsx
git commit -m "feat(web): Markdown is the editor's storage format

User-visible: chapters and entity bodies save and load as Markdown;
headings, emphasis and lists survive the round trip."
```

### Task 7: Shelf export/import UI

**Files:**
- Modify: `app/capabilities/writing/web/NovelsPage.tsx`
- Create: `app/capabilities/writing/web/interchange.ts` (client calls)
- Create: `app/capabilities/writing/web/InterchangeDialogs.tsx`
- Test: `app/capabilities/writing/web/InterchangeDialogs.test.tsx`
- Modify: `web/lib/i18n.ts` (all new keys, en/de/fr)

**Interfaces:**
- Consumes: Task 4's endpoints. The house dialog pattern (React Aria) from the knowledge panels.
- Produces: `exportNovel(id, mode, path)`, `importArchive({file?|path?, novelId?})` in `interchange.ts`; `InterchangeDialogs` renders: per-novel export (mode picker path/ZIP, path input prefilled with a timestamped proposal `<slug>-<yyyymmdd-hhmm>`), import (file picker or path, target: new novel or an existing one from the shelf list), and the report receipt (counts and conflicts, each conflict as `file — reason`; `assert_accessible`-clean). i18n keys named `shelf.export*`, `shelf.import*`, `shelf.report*` in all three languages.

- [ ] **Step 1: Write the failing test**

```typescript
test("export dialog proposes a timestamped path and submits the mode", ...);
test("import dialog shows the report with conflicts", ...);   // mocked fetch -> counts + one conflict row rendered
test("zip download delegates to the browser", ...);           // anchor/blob click, no dialog report
```

- [ ] **Step 2: Run test to verify it fails**

Run: `just test-file app/capabilities/writing/web/InterchangeDialogs.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the dialogs and wire them into the shelf**

`NovelsPage` gains an export action per novel and an import action beside "new novel". The ZIP response becomes a blob download via a temporary anchor. The receipt renders every conflict; nothing is silent.

- [ ] **Step 4: Run the tests**

Run: `just test-file app/capabilities/writing/web/InterchangeDialogs.test.tsx`
Expected: PASS (all three).

- [ ] **Step 5: Commit**

```bash
git add app/capabilities/writing/web/NovelsPage.tsx app/capabilities/writing/web/interchange.ts app/capabilities/writing/web/InterchangeDialogs.tsx app/capabilities/writing/web/InterchangeDialogs.test.tsx web/lib/i18n.ts
git commit -m "feat(web): export and import on the shelf

User-visible: every novel on the shelf can be exported to a path or as
a ZIP, and an archive can be imported as a new novel or merged into an
existing one, with a report of what happened."
```

### Task 8: E2E — the WP's done gate

**Files:**
- Create: `app/capabilities/writing/e2e/test_interchange_e2e.py`
- Modify: `app/capabilities/setup/e2e/` (demo path in the first-run flow)

**Interfaces:**
- Consumes: the full stack via the existing `run_stack` conftest pattern (`database="narrare_v2_writing_e2e"`-style); Tasks 4-7's surfaces; `assert_accessible` on every page visited.

- [ ] **Step 1: Write the failing E2E**

Flows (real UI, real API, real DB; no LLM involved):

```python
async def test_setup_with_demo_loads_content(): ...        # first run with im-stillen-wald -> chapters and entities with relations present
async def test_export_reimport_identical(): ...            # export ZIP -> import as new -> same titles, types, bodies, relations (DB-asserted)
async def test_merge_outside_work(): ...                   # export to path; edit one chapter file, add one bare chapter .md and one kb .md; import into the existing novel -> revised + appended, report counts match the DB (Review Focus 3)
async def test_stale_import_is_refused(): ...              # craft an older `updated` on a chapter whose stock moved on -> conflict shown in the UI, prose unchanged in the DB (Review Focus 1)
async def test_non_empty_export_target_refused(): ...      # export to the same path twice -> the refusal is named in the UI (Review Focus 2)
async def test_blank_path_unchanged(): ...                 # first run without a demo -> one empty novel, the workbench opens
```

- [ ] **Step 2: Run to verify it fails**

Run: `just test-file app/capabilities/writing/e2e/test_interchange_e2e.py`
Expected: FAIL — the UI does not exist yet in the flows the test drives.

- [ ] **Step 3: Land whatever the E2E finds missing**

The E2E is the gate; fixes land in the owning file, not in the test.

- [ ] **Step 4: Run the full gate**

Run: `just verify`
Expected: PASS — integration, web, E2E suites and the build, including the new files.

- [ ] **Step 5: Commit**

```bash
git add app/capabilities/writing/e2e/test_interchange_e2e.py app/capabilities/setup/e2e/
git commit -m "test(writing): interchange E2E — export, re-import, merge, refusal

User-visible: none — the gate that proves the WP done criterion."
```

---

## Final wave (after Task 8)

1. `just verify` green on the branch head; read the output.
2. Whole-branch review, then the fix wave, then `docs/superpowers/follow-ups.md` gets every still-open finding as one row (AGENTS.md follow-ups rule).
3. Fahrplan §6 is overwritten with the as-built section (the house pattern: WP1 §4.10, WP2 §5.9); spec and plan are already committed at the branch's start — one state, not two.
