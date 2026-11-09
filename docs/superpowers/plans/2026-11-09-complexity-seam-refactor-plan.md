# Complexity Seam Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the four real method hotspots below a healthy complexity and split the three remaining UI monoliths along their existing responsibilities, without changing behavior or public surfaces.

**Architecture:** Behavior-preserving extraction. Backend helpers stay in their module except `writing/metadata.py`, which follows the capability's existing submodule pattern. UI files become a composition root plus hooks/components inside the same capability's `web/` folder. No new capability, route, schema, generated file or i18n key.

**Tech Stack:** Python 3.14, FastAPI/SQLAlchemy async, Alembic, PostgreSQL, Vite/React/TanStack Router/TanStack Query, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-09-complexity-seam-refactor-design.md` (moved from `~/.opencode/plan/2026-11-09-complexity-seam-refactor-design.md` by the build session).

**Dispatch:** implementer `zai-coding-plan/glm-5.3-flash`; reviewer `opencode-go/deepseek-v4.1-flash`. The reviewer does not edit, stage, commit or push.

**Task report:** one section per task in the session's report: what changed, the exact gate command, its exit status, and any deviation. Written while the work happens.

## Global Constraints

- The five standing rules in `docs/_shared/CONSTRAINTS.md` apply. One capability is one folder; a capability never imports another capability; imports point `api → capabilities → kernel`.
- No new standing rule, checker, hook, required field or mandatory document (`docs/_shared/CONSTRAINTS.md` §8).
- Code, tests and developer documentation are English. No new user-visible text: every UI string keeps an existing catalog key.
- No public API, route, schema, generated file or i18n key changes.
- The checkout is shared with other sessions. Before editing a file: `git status --short`, then re-read the file. If it changed since this plan, stop and report instead of overwriting another session's work.
- Nothing is committed before the review is green. A commit made through an agent ends with `Assisted-by: OpenCode (<model>)` via `git commit --trailer`.
- The work is a pure move unless a task says otherwise. If a move reveals a behavior bug, stop and report; do not fix it inside this task.

## Review Focus

These are the behaviors most likely to break during a mechanical move. Each line names the task whose tests pin it.

1. `update_novel` partial semantics: an absent field is unchanged, a carried `null` clears, a language folds only its primary subtag, and an invalid field is refused by name. Task 2.
2. `url.resolve` precedence and refusal: `NARRE_DATABASE_URL` wins, the dev port moves only the default/parts branch, and every invalid value is refused with its variable name. Task 1.
3. `dump_database` failure cleanup: a failed run leaves no valid-looking dump, retention touches only this database's dumps, and the `PGDMP`/`pg_restore` acceptance still refuses a truncated artifact. Task 3.
4. `prepare_database` bootstrap and lock: the pre-migration dump precedes the stamp, the bootstrap stamps baseline or head only when the schema matches, and the advisory lock is released on every path. Task 4.
5. `NovelPage` selection and draft lifetime: the fallback latch survives a refetch, a switch flushes or asks before dropping a draft, and a 404 from the novel row navigates to the shelf with its note. Task 7.

---

### Task 1: Database URL resolution seams

**Files:**
- Modify: `app/kernel/db/url.py`
- Test: `app/kernel/db/tests/test_url.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `resolve(env: Mapping[str, str] | None = None) -> DatabaseConfig` unchanged.
- Produces (module-private, same file): `_dev_port(source: Mapping[str, str]) -> int | None`, `_port(raw: str, variable: str) -> int`, `_read_parts(source: Mapping[str, str]) -> dict[str, str]`, `_build_url(parts: Mapping[str, str], port: int) -> URL`.
- `DatabaseConfigurationError` messages stay verbatim, including the variable name in each.

- [ ] **Step 1: Add the missing refusal tests**

Append to `app/kernel/db/tests/test_url.py`:

```python
def test_a_dev_db_port_that_is_not_a_number_is_refused_by_name() -> None:
    with pytest.raises(DatabaseConfigurationError) as refused:
        resolve({"NARRE_DEV_DB_PORT": "5442x"})
    assert "NARRE_DEV_DB_PORT" in str(refused.value)


def test_a_dev_db_port_outside_the_range_is_refused() -> None:
    with pytest.raises(DatabaseConfigurationError) as refused:
        resolve({"NARRE_DEV_DB_PORT": "70000"})
    assert "NARRE_DEV_DB_PORT" in str(refused.value)


def test_the_url_wins_over_the_dev_db_port() -> None:
    config = resolve(
        {
            "NARRE_DATABASE_URL": "postgresql+asyncpg://u:p@elsewhere:5432/other",
            "NARRE_DEV_DB_PORT": "5442",
        }
    )
    assert config.url.port == 5432
```

- [ ] **Step 2: Run the tests to establish the baseline**

Run: `just test-file app/kernel/db/tests/test_url.py`

Expected: the three new tests pass against the current implementation. If one fails, the current behavior is the contract; stop and report the difference before refactoring.

- [ ] **Step 3: Extract the helpers in `app/kernel/db/url.py`**

Move the dev-port parsing from `resolve` into `_dev_port`; move the parts dict and password rule into `_read_parts`; move the `NARRE_DB_PORT` validation into `_port`; move the `URL.create` block into `_build_url`. `resolve` keeps the same order: given URL → dev-port parse → parts → missing check → port → URL. Keep `_value`, `_variable`, `DEFAULT_URL`, `DEFAULT_PORT`, `SSL_MODES` and every error message where they are.

- [ ] **Step 4: Run the tests and the fast gate**

Run: `just test-file app/kernel/db/tests/test_url.py && just check`

Expected: all tests pass; ruff and both typecheckers green.

- [ ] **Step 5: Review and commit**

Dispatch the reviewer on the uncommitted diff. After green:

```bash
git add app/kernel/db/url.py app/kernel/db/tests/test_url.py
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "refactor: split database URL resolution into its seams"
```

---

### Task 2: Novel metadata module

**Files:**
- Create: `app/capabilities/writing/metadata.py`
- Modify: `app/capabilities/writing/service.py`
- Test: `app/capabilities/writing/tests/test_metadata.py`

**Interfaces:**
- Consumes: `NovelUpdate` from `app.capabilities.writing.schemas`.
- Produces: `class InvalidNovelUpdateError(ValueError)` with `.field: str`; `service.py` re-exports it by importing it, so `app.capabilities.writing.service.InvalidNovelUpdateError` keeps working.
- Produces: `normalized_novel_updates(changes: NovelUpdate) -> dict[str, object]`, returning only fields in `changes.model_fields_set`, with the same values the current `update_novel` writes. A carried `None` is present in the dict.
- Produces (module-private): `_normalize_title`, `_normalize_genre`, `_normalize_author`, `_normalize_blurb`, `_normalize_language`.

- [ ] **Step 1: Write the failing tests**

Create `app/capabilities/writing/tests/test_metadata.py` with one test per behavior:

```python
import pytest

from app.capabilities.writing.metadata import (
    InvalidNovelUpdateError,
    normalized_novel_updates,
)
from app.capabilities.writing.schemas import NovelUpdate


def test_absent_fields_are_not_updates() -> None:
    assert normalized_novel_updates(NovelUpdate()) == {}


def test_a_carried_null_is_an_update() -> None:
    assert normalized_novel_updates(NovelUpdate(author=None)) == {"author": None}


def test_title_is_trimmed_and_blank_is_refused() -> None:
    assert normalized_novel_updates(NovelUpdate(title="  Dune  ")) == {"title": "Dune"}
    with pytest.raises(InvalidNovelUpdateError) as refused:
        normalized_novel_updates(NovelUpdate(title="   "))
    assert refused.value.field == "title"


def test_genre_is_trimmed_empty_clears_and_width_is_checked() -> None:
    assert normalized_novel_updates(NovelUpdate(genre="  Sci-Fi  ")) == {"genre": "Sci-Fi"}
    assert normalized_novel_updates(NovelUpdate(genre="   ")) == {"genre": None}
    with pytest.raises(InvalidNovelUpdateError) as refused:
        normalized_novel_updates(NovelUpdate(genre="x" * 81))
    assert refused.value.field == "genre"


def test_author_is_trimmed_empty_clears_and_width_is_checked() -> None:
    assert normalized_novel_updates(NovelUpdate(author="  Frank Herbert  ")) == {
        "author": "Frank Herbert"
    }
    assert normalized_novel_updates(NovelUpdate(author="   ")) == {"author": None}
    with pytest.raises(InvalidNovelUpdateError) as refused:
        normalized_novel_updates(NovelUpdate(author="x" * 201))
    assert refused.value.field == "author"


def test_blurb_is_trimmed_and_empty_clears() -> None:
    assert normalized_novel_updates(NovelUpdate(blurb="  A desert planet.  ")) == {
        "blurb": "A desert planet."
    }
    assert normalized_novel_updates(NovelUpdate(blurb="   ")) == {"blurb": None}


@pytest.mark.parametrize(
    ("given", "expected"),
    [("DE", "de"), ("en-GB", "en-GB"), ("  de  ", "de"), ("   ", None)],
)
def test_language_folds_only_its_primary_subtag(given: str, expected: str | None) -> None:
    assert normalized_novel_updates(NovelUpdate(language=given)) == {"language": expected}


def test_an_invalid_language_is_refused_by_name() -> None:
    for value in ("deutsch", "d", "de_DE", "x" * 17):
        with pytest.raises(InvalidNovelUpdateError) as refused:
            normalized_novel_updates(NovelUpdate(language=value))
        assert refused.value.field == "language"
```

- [ ] **Step 2: Run the tests to watch them fail**

Run: `just test-file app/capabilities/writing/tests/test_metadata.py`

Expected: collection error — `app.capabilities.writing.metadata` does not exist.

- [ ] **Step 3: Implement `metadata.py` and wire `update_novel`**

Move `InvalidNovelUpdateError` into `metadata.py`; keep the class docstring. Implement the five normalizers with the exact trims and limits currently in `update_novel` (title 1–200, genre ≤80, author ≤200, blurb trim-only, language ≤16 and `_LANGUAGE_CODE`). Implement `normalized_novel_updates` by checking `changes.model_fields_set` in the same order as today.

In `service.py`, import `InvalidNovelUpdateError` and `normalized_novel_updates` from `metadata.py`; replace the body of `update_novel` after the `novel is None` check with:

```python
updates = normalized_novel_updates(changes)
novel = await self.novels.save(novel, updates)
await self.session.commit()
return self._with_counts(novel, (await self.novels.counts(novel_id)).get(novel_id, (0, 0)))
```

Delete the now-unused `_LANGUAGE_CODE` from `service.py` if nothing else uses it.

- [ ] **Step 4: Run the tests**

Run:

```bash
just test-file app/capabilities/writing/tests/test_metadata.py
just test-file app/capabilities/writing/tests/test_novel_metadata.py
just test-file app/capabilities/writing/tests/test_novel_management.py
just check
```

Expected: all green. If `test_novel_metadata.py` expects an error message or import path that moved, keep the public path stable instead of editing the test.

- [ ] **Step 5: Review and commit**

Dispatch the reviewer. After green:

```bash
git add app/capabilities/writing/metadata.py \
  app/capabilities/writing/service.py \
  app/capabilities/writing/tests/test_metadata.py
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "refactor: give novel metadata its own module"
```

---

### Task 3: Backup dump seams

**Files:**
- Modify: `app/kernel/db/backup.py`
- Test: `app/kernel/db/tests/test_migrations.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `dump_database(database_url: str, directory: Path, *, keep: int = 3) -> Path` unchanged.
- Produces (module-private, same file): `_run_dump(command_line: list[str], partial: Path, *, timeout: float, file: Path, file_existed_before: bool) -> subprocess.CompletedProcess[bytes]`, `async def _accept_dump(artifact: Path, *, command_line: list[str], timeout: float, file: Path, file_existed_before: bool) -> None`, `def _retain_dumps(directory: Path, database: str, file: Path, keep: int) -> None`.
- Every failure still raises `BackupFailed`; `partial` is still removed in `dump_database`'s `finally`.

- [ ] **Step 1: Run the existing backup and migration tests**

Run: `just test-file app/kernel/db/tests/test_migrations.py`

Expected: green (or the suite's documented skips when `pg_dump`/`pg_restore` are absent). This is the baseline; do not change behavior.

- [ ] **Step 2: Extract the three stages in `app/kernel/db/backup.py`**

Move the inner `_dump()` body into `_run_dump`; move the magic + `pg_restore --list` block into `_accept_dump`; move the retention glob/sort/unlink block into `_retain_dumps`. `dump_database` becomes: prepare directory and names → call `_run_dump` in a thread → choose artifact → call `_accept_dump` → replace partial if needed → call `_retain_dumps` → return. Keep the `finally: partial.unlink(missing_ok=True)` in `dump_database`.

- [ ] **Step 3: Run the tests and the fast gate**

Run: `just test-file app/kernel/db/tests/test_migrations.py && just check`

Expected: all green. The backup round-trip test (`test_backup_round_trip`) still produces a restorable dump; the `_libpq_url` tests still pass unchanged.

- [ ] **Step 4: Review and commit**

Dispatch the reviewer. After green:

```bash
git add app/kernel/db/backup.py
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "refactor: split the pre-migration dump into its stages"
```

---

### Task 4: Migration preparation seams

**Files:**
- Modify: `app/kernel/db/migrate.py`
- Test: `app/kernel/db/tests/test_migrations.py`

**Interfaces:**
- Consumes: `dump_database`, `BackupFailed` (already imported).
- Produces: `prepare_database(...) -> MigrationOutcome` unchanged.
- Produces (module-private): `async def _take_pre_migration_backup(database_url: str, *, pending: bool, has_tables: bool, backup: bool, backup_dir: Path | None) -> Path | None` — the same condition and `MigrationRefused` wrap as today. `pending` is `current is None or current != head`.
- Produces (module-private): `async def _bootstrap_or_refuse(config: Config, engine: AsyncEngine, database_url: str) -> str` — returns the stamp target (`baseline` or `head`) and raises `MigrationRefused` with the same message when neither matches.

- [ ] **Step 1: Run the existing migration tests**

Run: `just test-file app/kernel/db/tests/test_migrations.py`

Expected: green baseline.

- [ ] **Step 2: Extract the backup step**

Replace the inline backup condition in `prepare_database` with `backup_path = await _take_pre_migration_backup(database_url, pending=(current is None or current != head), has_tables=has_tables, backup=backup, backup_dir=backup_dir)`. The helper reads `NARRE_MIGRATION_BACKUP`, computes the directory, calls `dump_database`, and wraps `BackupFailed` in the current `MigrationRefused` message.

- [ ] **Step 3: Extract the bootstrap decision**

Move the whole `if bootstrapped:` block (normalize legacy names, read baseline, compare baseline then head, apply renames, refuse) into `_bootstrap_or_refuse`. It returns `stamp_target`; `prepare_database` keeps the `if bootstrapped: await asyncio.to_thread(command.stamp, config, stamp_target)` line and the upgrade. Do not move the advisory lock, the URL write or the `finally` release.

- [ ] **Step 4: Run the tests and the fast gate**

Run: `just test-file app/kernel/db/tests/test_migrations.py && just check`

Expected: all green. The lock, dump-before-stamp and refusal tests are the proof.

- [ ] **Step 5: Review and commit**

Dispatch the reviewer. After green:

```bash
git add app/kernel/db/migrate.py
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "refactor: split migration preparation into backup and bootstrap"
```

---

### Task 5: EntitiesPanel file split

**Files:**
- Create: `app/capabilities/knowledge/web/entityTypes.ts`
- Create: `app/capabilities/knowledge/web/EntityDetail.tsx`
- Create: `app/capabilities/knowledge/web/EditEntityDialog.tsx`
- Create: `app/capabilities/knowledge/web/MergeEntityDialog.tsx`
- Create: `app/capabilities/knowledge/web/DeleteEntityDialog.tsx`
- Modify: `app/capabilities/knowledge/web/EntitiesPanel.tsx`
- Modify: `app/capabilities/knowledge/web/ExtractionPanel.tsx` (import `entityTypeLabel` from `./entityTypes`)
- Test: `app/capabilities/knowledge/web/EntitiesPanel.test.tsx`

**Interfaces:**
- `entityTypes.ts` exports `TYPE_KEYS` and `entityTypeLabel(t, type)` exactly as `EntitiesPanel.tsx` does today.
- `EntityDetail.tsx` exports `EntityDetail` with the same props: `{ entity: Entity; rows: Entity[]; novelId: string; onSelect: (id: string | null) => void }`.
- `EditEntityDialog.tsx` exports `EditEntityDialog`; `MergeEntityDialog.tsx` exports `MergeEntityDialog`; `DeleteEntityDialog.tsx` exports `DeleteEntityDialog`. Their props are the current ones; `ChipsField` moves with `EditEntityDialog`.
- `EntitiesPanel` export and props stay unchanged.

- [ ] **Step 1: Run the existing panel test**

Run: `just test-file app/capabilities/knowledge/web/EntitiesPanel.test.tsx`

Expected: green baseline.

- [ ] **Step 2: Move the code without edits**

Move `TYPE_KEYS`/`entityTypeLabel` to `entityTypes.ts`; move `EntityDetail`, `EdgeGroup`, `ChipRow` and `truncate` to `EntityDetail.tsx`; move the three dialog functions and `ChipsField` to their files. Move imports with each block. Do not rename props, change conditions, or reorder JSX.

- [ ] **Step 3: Update imports**

`EntitiesPanel.tsx` imports `entityTypeLabel` from `./entityTypes`, `EntityDetail` from `./EntityDetail`, and the dialogs from their files. `ExtractionPanel.tsx` imports `entityTypeLabel` from `./entityTypes`. No other file changes.

- [ ] **Step 4: Run the tests and the fast gate**

Run: `just test-file app/capabilities/knowledge/web/EntitiesPanel.test.tsx && just check`

Expected: all green.

- [ ] **Step 5: Review and commit**

Dispatch the reviewer. After green:

```bash
git add app/capabilities/knowledge/web/entityTypes.ts \
  app/capabilities/knowledge/web/EntityDetail.tsx \
  app/capabilities/knowledge/web/EditEntityDialog.tsx \
  app/capabilities/knowledge/web/MergeEntityDialog.tsx \
  app/capabilities/knowledge/web/DeleteEntityDialog.tsx \
  app/capabilities/knowledge/web/EntitiesPanel.tsx \
  app/capabilities/knowledge/web/ExtractionPanel.tsx
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "refactor: split the entity panel into its parts"
```

---

### Task 6: PromptsPage file split

**Files:**
- Create: `app/capabilities/prompts/web/promptLabels.ts`
- Create: `app/capabilities/prompts/web/diff.ts`
- Create: `app/capabilities/prompts/web/PromptEditor.tsx`
- Create: `app/capabilities/prompts/web/PromptCard.tsx`
- Modify: `app/capabilities/prompts/web/PromptsPage.tsx`
- Test: `app/capabilities/prompts/web/diff.test.ts`
- Test: `app/capabilities/prompts/web/PromptsPage.test.tsx`

**Interfaces:**
- `promptLabels.ts` exports `type Translate`, `KEY_LABELS`, `REASON_LABELS`, `keyLabelOf(key: string, t: Translate): string`, `reasonLabelOf(reason: string, t: Translate): string`.
- `diff.ts` exports `type DiffRow = { left: string | null; right: string | null }` and `sideBySide(bundled: string, override: string): DiffRow[]`.
- `PromptEditor.tsx` exports `PromptEditor` with its current props and owns the private `refusalOf` helper.
- `PromptCard.tsx` exports `PromptCard` with its current props and owns the private `Chip` helper.
- `PromptsPage` export and behavior stay unchanged.

- [ ] **Step 1: Write the failing diff test**

Create `app/capabilities/prompts/web/diff.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { sideBySide } from "./diff";

describe("sideBySide", () => {
  it("keeps identical lines on both sides", () => {
    expect(sideBySide("a\nb", "a\nb")).toEqual([
      { left: "a", right: "a" },
      { left: "b", right: "b" },
    ]);
  });

  it("marks an insertion on the right", () => {
    expect(sideBySide("a\nc", "a\nb\nc")).toEqual([
      { left: "a", right: "a" },
      { left: null, right: "b" },
      { left: "c", right: "c" },
    ]);
  });

  it("marks a deletion on the left", () => {
    expect(sideBySide("a\nb\nc", "a\nc")).toEqual([
      { left: "a", right: "a" },
      { left: "b", right: null },
      { left: "c", right: "c" },
    ]);
  });

  it("marks a replacement as deletion plus insertion", () => {
    expect(sideBySide("a\nb", "a\nc")).toEqual([
      { left: "a", right: "a" },
      { left: "b", right: null },
      { left: null, right: "c" },
    ]);
  });
});
```

- [ ] **Step 2: Run the test to watch it fail**

Run: `just test-file app/capabilities/prompts/web/diff.test.ts`

Expected: FAIL — `./diff` does not exist.

- [ ] **Step 3: Move the pure helpers**

Create `diff.ts` with `DiffRow` and `sideBySide` moved verbatim from `PromptsPage.tsx`. Create `promptLabels.ts` with `Translate`, the two label maps, `keyLabelOf` and `reasonLabelOf` moved verbatim. Run the diff test; it must pass.

- [ ] **Step 4: Move the components**

Move `PromptEditor` and its `refusalOf` helper into `PromptEditor.tsx`; move `PromptCard` and `Chip` into `PromptCard.tsx`. Keep the signatures and JSX unchanged. Update `PromptsPage.tsx` imports. No new keys, no copy edits.

- [ ] **Step 5: Run the tests and the fast gate**

Run:

```bash
just test-file app/capabilities/prompts/web/diff.test.ts
just test-file app/capabilities/prompts/web/PromptsPage.test.tsx
just check
```

Expected: all green.

- [ ] **Step 6: Review and commit**

Dispatch the reviewer. After green:

```bash
git add app/capabilities/prompts/web/promptLabels.ts \
  app/capabilities/prompts/web/diff.ts \
  app/capabilities/prompts/web/PromptEditor.tsx \
  app/capabilities/prompts/web/PromptCard.tsx \
  app/capabilities/prompts/web/PromptsPage.tsx \
  app/capabilities/prompts/web/diff.test.ts
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "refactor: split the prompts page into its parts"
```

---

### Task 7: NovelPage state hooks

**Files:**
- Create: `app/capabilities/writing/web/novel/useNovelWorkspace.ts`
- Create: `app/capabilities/writing/web/novel/useNovelDraft.ts`
- Create: `app/capabilities/writing/web/novel/useChapterRail.ts`
- Modify: `app/capabilities/writing/web/NovelPage.tsx`
- Test: `app/capabilities/writing/web/NovelPage.test.tsx`

**Interfaces:**
- `NovelPage.tsx` keeps `export function NovelPage()` and renders the same DOM. `routes.tsx` does not change.
- `useNovelWorkspace(novelId: string)` returns the data, selection and panel state the page uses today: `novelQuery`, `chaptersQuery`, `chapters`, `chapterCounts`, `pending`, `failed`, `refreshFailed`, `retry`, `active`, `select`, `current`, `currentIndex`, `focus`, `collapsed`, `narrow`, `showRail`, `openDock`, `activeDock`, `step`, `toggleRail`, `toggleDock`, `offer`, `resolveOffer`, `hintShown`.
- `useNovelDraft(novelId: string, current: Chapter | null)` returns `status`, `schedule`, `flush`, `discard`, `draft`, `changeTitle`, `rename`, `unsaved`, `guardOpen`, `answerGuard`. It owns `remember`, `useAutosave`, the held-draft state and the leave guard's `useBlocker`. `rename(title)` is the current `renamed` callback: it updates the held draft's title for the current chapter.
- `useChapterRail(novelId: string, chapters: Chapter[], active: string | null)` returns `visibleChapters`, `activeVisibleIndex`, `railListRef`, `walkedIndex`, `setWalkedIndex`, `walkRail`, `railFilter`, `setRailFilter`, `orderFailed`, `move`, `moveTo`, `dragId`, `dropIndex`, `setDropIndex`.
- `createChapter`, `confirmDeleteChapter` stay in `NovelPage.tsx`; they compose the hooks. The rename dialog uses `rename` from `useNovelDraft`.

- [ ] **Step 1: Run the existing page test**

Run: `just test-file app/capabilities/writing/web/NovelPage.test.tsx`

Expected: green baseline. Record the test count; it must not drop.

- [ ] **Step 2: Create `useNovelWorkspace.ts`**

Move the route/search reads, queries, `chapterCounts`, `pending`/`failed`/`refreshFailed`/`retry`, the deleted-elsewhere effect, `usePageTitle`, `useBelowWorkbenchBreakpoint`, the fallback latch, `active`, `select`, the dead-param cleanup, `offer`/`resolveOffer`, `step`, `toggleRail`, `toggleDock`, `activeDock`, `childMatches`, `showRail`, `openDock`, the keyboard effect, the body focus attribute and `hintShown` into the hook. `NovelPage.tsx` calls it and destructures. Run the page test.

- [ ] **Step 3: Create `useNovelDraft.ts`**

Move the `held` draft state, `draftRef`, `scheduleDraft`, `changeTitle`, `remember`, `useAutosave`, `unsaved`/`unsavedNow`, the `useBlocker` call, the guard state, `answerGuard` and the current `renamed` callback (as `rename`) into the hook. The hook takes `novelId` and `current`. `NovelPage.tsx` calls it and passes `status`, `draft`, `changeTitle`, `schedule`, `rename` to the editor, rail and dialogs. Run the page test.

- [ ] **Step 4: Create `useChapterRail.ts`**

Move the rail filter, `locale`, `visibleChapters`, `activeVisibleIndex`, the filter-reset effect, `railListRef`, `walkedIndex`, `walkRail`, `reorder`, `orderFailed`, `writes`, `move`, `moveTo`, `dragId`, `dropIndex` and the drag handlers into the hook. Run the page test.

- [ ] **Step 5: Run the tests and the fast gate**

Run:

```bash
just test-file app/capabilities/writing/web/NovelPage.test.tsx
just check
```

Expected: all green; the page test count is not lower than Step 1.

- [ ] **Step 6: Review and commit**

Dispatch the reviewer. After green:

```bash
git add app/capabilities/writing/web/NovelPage.tsx \
  app/capabilities/writing/web/novel/useNovelWorkspace.ts \
  app/capabilities/writing/web/novel/useNovelDraft.ts \
  app/capabilities/writing/web/novel/useChapterRail.ts
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "refactor: move the novel workbench state into hooks"
```

---

### Task 8: NovelPage presentational components

**Files:**
- Create: `app/capabilities/writing/web/novel/ChapterRail.tsx`
- Create: `app/capabilities/writing/web/novel/WorkspaceToolbar.tsx`
- Create: `app/capabilities/writing/web/novel/EditorColumn.tsx`
- Create: `app/capabilities/writing/web/novel/DockColumn.tsx`
- Modify: `app/capabilities/writing/web/NovelPage.tsx`
- Test: `app/capabilities/writing/web/NovelPage.test.tsx`

**Interfaces:**
- Consumes: the three hooks from Task 7.
- Produces: `ChapterRail`, `WorkspaceToolbar`, `EditorColumn` and `DockColumn`, each with its props type local to its file. No new shared types.
- `NovelPage.tsx` keeps `export function NovelPage()` and becomes the composition root.

- [ ] **Step 1: Run the page test**

Run: `just test-file app/capabilities/writing/web/NovelPage.test.tsx`

Expected: green baseline.

- [ ] **Step 2: Extract the toolbar and rail**

Move the toolbar JSX into `WorkspaceToolbar.tsx` and the rail `aside` into `ChapterRail.tsx`. Pass only the values those blocks consume. Keep every `aria-label`, role, `className`, `key`, drag handler and keyboard handler as it is. Run the page test.

- [ ] **Step 3: Extract the editor and dock columns**

Move the editor `section` and its notice/editor block into `EditorColumn.tsx`, and the dock `aside` into `DockColumn.tsx`. Keep `ChapterRenameDialog`, `ChapterDeleteDialog` and the leave `Dialog` in `NovelPage.tsx`; `ChapterRenameDialog` receives `onRenamed={rename}`. Run the page test after each move.

- [ ] **Step 4: Run the tests and the fast gate**

Run:

```bash
just test-file app/capabilities/writing/web/NovelPage.test.tsx
just test-file app/capabilities/writing/web/ChapterEditor.test.tsx
just check
```

Expected: all green; the page test count is not lower than Task 7 Step 1.

- [ ] **Step 5: Review and commit**

Dispatch the reviewer. After green:

```bash
git add app/capabilities/writing/web/NovelPage.tsx \
  app/capabilities/writing/web/novel/ChapterRail.tsx \
  app/capabilities/writing/web/novel/WorkspaceToolbar.tsx \
  app/capabilities/writing/web/novel/EditorColumn.tsx \
  app/capabilities/writing/web/novel/DockColumn.tsx
git commit --trailer "Assisted-by: OpenCode (zai-coding-plan/glm-5.3-flash)" \
  -m "refactor: split the novel workbench into its parts"
```

---

## Final Verification

- [ ] **Run the full gate once**

Run: `just verify all`

Expected: green. If the full run is too slow for the session, run the affected suites in sequence:

```bash
just verify writing
just verify knowledge
just verify prompts
```

- [ ] **Confirm no generated or catalog files changed**

Run: `git status --short`

Expected: only the files named in this plan. If `app/generated/`, `web/lib/generated/`, `web/lib/api/openapi.json`, `web/lib/api/schema.d.ts` or any `i18n/*.json` appears, stop and report.

- [ ] **Measure the four methods**

Run the local AST count used in the analysis (a throwaway script in `/tmp/opencode`, not committed). Expected: each of `url.resolve`, `writing.service.update_novel`, `backup.dump_database`, `migrate.prepare_database` is below 20. No new gate is added.

- [ ] **Re-check Codacy after the push**

The four UI files should drop in file complexity; the four backend methods should no longer be the method hotspots. The kernel file sums for `backup.py` and `migrate.py` may stay high — that is the design's accepted trade-off.

## Deferred

- Settings UI: PR #755 already split `ProvidersPanel.tsx` into sections while this plan was being written. If Codacy still flags `ProvidersSection.tsx` or `ModelsSection.tsx` after its next analysis, open a separate design; do not fold it into these tasks.
