# WP6 — Chapter and Novel Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the writing loop — rename chapters and novels, choose a novel's metadata, reorder chapters, and delete a chapter, a novel (with an export warning) or a document.

**Architecture:** Server first: three Alembic revisions, four writing endpoints, one knowledge endpoint, an export timestamp, and the canon rule that every archive-changing write advances the novel row. Then the frontend on the as-built UI-B rail/runhead/shelf/documents panel: the title becomes the runhead's input, chapter actions move into a runhead menu, reorder rides `Alt+↑/↓` and native desktop drag, and delete dialogs warn from the timestamp without ever blocking.

**Tech Stack:** Python 3.14 · FastAPI · SQLAlchemy async · PostgreSQL (deferrable unique constraint) · Alembic · React 19 · TanStack Router/Query · React Aria (`react-aria-components`) · Tailwind v4 tokens · Playwright E2E.

**Spec:** `docs/superpowers/specs/2026-10-30-wp6-chapter-novel-management-design.md`. Read it before Task 1; every "D<n>" below is a decision it records.

## Global Constraints

- Five standing rules (`docs/_shared/CONSTRAINTS.md`): one capability one folder; no capability imports another; `user_id` on every user-owned row; no side effect beyond the request's transaction; English in code and docs.
- **Schema changes are Alembic revisions**, authored with `just db-revision "<message>"`; a downgrade raises (restore the dump). `just test-file app/kernel/db/tests/test_migrations.py` is the gate that keeps the history and the models identical.
- **Generated artefacts are committed:** after any router or schema change run `just generate` (OpenAPI document, capability views, typed web client, catalogs) and include the regenerated files in the same commit.
- Exact values: chapter title trimmed, `""` legal, max 200; novel title trimmed, 1–200, empty refused; `genre` max 80; language `^[a-z]{2}(-[A-Za-z]{2,})?$`, `null`/`""` clears; positions `0..n-1`; stale-order answer `409` with detail `{"code": "order_mismatch", "chapter_ids": [...]}`; rail filter appears above **20** chapters; upload limit `1_000_000` bytes (printed as 1 MB); autosave debounce 800 ms (existing).
- `last_exported_at` is set on **every successful export** (path and ZIP) and by **no failed one**.
- The canon rule (D8): entity create/update/delete, relation create/update/delete and suggestion-accept advance the parent novel's `updated_at`; document writes, findings, chat and extraction enqueues do not.
- Chapter rows keep their `updated_at` when a renumber or reorder moves them; the novel row advances. Every delete renumbers contiguously in its own transaction.
- i18n: every new key lands in `i18n/en.json`, `i18n/de.json` and `i18n/fr.json` in the same commit; `fr` may carry the English string marked with the WP5 convention, and Task 15 is the translation pass.
- No new frontend dependency. The rail keeps plain rows (`<ul>`/`<li>`/`Row`), `aria-current` and the roving tabindex — no role change (UI-B spec).
- Commits: Conventional Commits; `feat`/`fix` carry a real `User-visible:` line; every agent commit ends with `Assisted-by: OpenCode (<model>)` via `git commit --trailer`; never `--no-verify`; nothing committed before its gate is green.
- Gates: `just check` per task; `just test-file <path>` for the inner loop; `just verify` (suites the change touches) before each commit; `just test-e2e writing` / `just test-e2e knowledge` for the E2E steps; `just verify all` in Task 15.

**One narrowing of the spec, for the reviewer (D3/§7):** the spec gives the rail a per-row menu (rename, delete, move up/down). A row is a `<button>` today, and a menu trigger inside it would nest interactive elements. The plan puts **one action menu in the runhead** of the open chapter instead — rename (focuses the title input), delete, move up, move down — and leaves the rail a pure selection list with `Alt+↑/↓` and desktop drag. Touch keeps a path (open the chapter, use its runhead menu), the rail markup stays exactly as UI-B built it, and no `Menu` markup nests inside a row button. If the owner wants the per-row menu, the rail row must first become a `div` with an inner select button — a UI-B change this plan does not make.

## Review Focus

1. **A stale order from a second tab.** A `PUT chapter-order` whose id set no longer matches must answer `409` and leave the stored order untouched; the client must revert its optimistic order and say so. Guessed input: a tab that added or deleted a chapter while another dragged.
2. **Deleting the open chapter with unsaved text.** The pending body must be retired before the delete navigation; no `PUT` may fly at a deleted chapter, and no `save.failed` status may appear for a deletion the user asked for.
3. **A body-only save must never rewrite the title.** Renaming the open chapter from the runhead while a body edit is pending must survive the next debounce (dirty-field flush).
4. **A novel deleted in another tab while open.** The workspace's novel query answers 404; the page degrades to the shelf with a named notice, not an endless spinner and not a stack trace.
5. **"Last touched" and "changed since export" must stay true.** Reorder/delete advance the novel row but preserve chapter rows; an entity edit advances the novel row. A regression here silently corrupts both the shelf order and the delete warning.

## File Structure

**Server**

| File | Responsibility |
|---|---|
| `app/kernel/contracts/models.py` | `Novel.last_exported_at`, `Document.byte_size`, deferred chapter constraint |
| `app/kernel/db/migrations/versions/*.py` | three revisions (one per model change) |
| `app/capabilities/writing/schemas.py` | `NovelUpdate`, `ChapterOrderUpdate`, grown `NovelRead`/`ChapterUpdate` |
| `app/capabilities/writing/service.py` | `update_novel`, `delete_novel`, `delete_chapter`, `reorder_chapters`, export timestamp |
| `app/capabilities/writing/repository.py` | `rename/update`, `renumber`, `touch_exported`, delete helpers |
| `app/capabilities/writing/router.py` | four new routes and their refusals |
| `app/capabilities/knowledge/schemas.py` | grown `DocumentRead` |
| `app/capabilities/knowledge/service.py` | ingest byte size, document list with counts, `delete_document`, canon touches |
| `app/capabilities/knowledge/repository.py` | `count_chunks`, `_touch_novel` |
| `app/capabilities/knowledge/router.py` | `DELETE /documents/{id}` |

**Frontend**

| File | Responsibility |
|---|---|
| `web/lib/save.tsx` | dirty-field draft (`{title, body}`), one status |
| `web/lib/query.ts` | `useUpdateNovel`, `useDeleteNovel`, `useDeleteChapter`, `useReorderChapters`, `useDeleteDocument` |
| `web/ui/Menu.tsx` | the action menu primitive (RAC `MenuTrigger`/`Menu`/`MenuItem`), the wave's one new primitive |
| `app/capabilities/writing/web/ChapterEditor.tsx` | runhead title input, runhead action menu |
| `app/capabilities/writing/web/NovelPage.tsx` | `move()`, drag wiring, filter, chapter dialogs, 404 degrade |
| `app/capabilities/writing/web/ChapterDialogs.tsx` | rename dialog, delete-chapter dialog with the export line |
| `app/capabilities/writing/web/NovelsPage.tsx` | card action menu, details dialog, delete-novel dialog |
| `app/capabilities/knowledge/web/KnowledgePage.tsx` | document row metadata, delete dialog, honest empty state |
| `i18n/{en,de,fr}.json` | every new key |

---

### Task 1: Schema — export timestamp, document size, deferrable positions

**Files:**
- Modify: `app/kernel/contracts/models.py` (`Novel`, `Document`, `Chapter.__table_args__`)
- Create: three revisions under `app/kernel/db/migrations/versions/`
- Test: `app/capabilities/writing/tests/test_chapter_positions.py`

**Interfaces:**
- Produces: `Novel.last_exported_at: datetime | None`, `Document.byte_size: int | None`, `UniqueConstraint("novel_id", "position", deferrable=True, initially="DEFERRED")`. Later tasks read these names.

- [ ] **Step 1: Write the failing test** in `test_chapter_positions.py` — a swap inside one transaction must commit:

```python
async def test_two_chapters_swap_positions_in_one_transaction() -> None:
    # two chapters at 0 and 1; inside one session, set a→1 and b→0, commit
    # (no flush between the two writes)
```
Assert the commit succeeds and a fresh session reads `[(0, b), (1, a)]`, add `test_positions_constraint_is_deferred` reading `pg_constraint.condeferrable` for `uq_chapters_novel_id_position`, and add `test_a_direct_duplicate_position_is_refused_at_commit` (a raw `INSERT` of a second chapter at an existing position must fail when the transaction commits).

- [ ] **Step 2: Run it and read the red**

Run: `just test-file app/capabilities/writing/tests/test_chapter_positions.py`
Expected: FAIL — `IntegrityError` on commit from the plain unique constraint, and `condeferrable` false.

- [ ] **Step 3: Model change + three revisions**

`Chapter.__table_args__` becomes `UniqueConstraint("novel_id", "position", deferrable=True, initially="DEFERRED")` with the existing comment extended by one line on why deferral. Add `last_exported_at: Mapped[datetime | None]` (nullable, `DateTime(timezone=True)`) to `Novel` and `byte_size: Mapped[int | None]` to `Document`.

Then, one at a time, so each revision is one change: change `Novel` → `just db-revision "add novels.last_exported_at"`; change `Document` → `just db-revision "add documents.byte_size"`; change `Chapter` → `just db-revision "chapter positions are deferrable"`. Autogenerate cannot see a deferrability change: hand-write that revision as `op.drop_constraint(op.f("uq_chapters_novel_id_position"), "chapters", type_="unique")` then `op.create_unique_constraint(op.f("uq_chapters_novel_id_position"), "chapters", ["novel_id", "position"], deferrable=True, initially="DEFERRED")`, with a docstring saying plain uniqueness would refuse the renumber that WP6 adds. Every downgrade keeps the house form: raise `RuntimeError("downgrade is not supported; restore the pre-migration dump …")`.

- [ ] **Step 4: Run both gates**

Run: `just test-file app/capabilities/writing/tests/test_chapter_positions.py`
Expected: PASS (all three new tests; the existing allocator tests stay green).
Run: `just test-file app/kernel/db/tests/test_migrations.py`
Expected: PASS — an empty database replayed to head is indistinguishable from the models (gate D3.2), so the revision and the model agree.

- [ ] **Step 5: Commit**

```bash
git add app/kernel/contracts/models.py app/kernel/db/migrations/versions app/capabilities/writing/tests/test_chapter_positions.py
git commit --trailer "Assisted-by: OpenCode (<model>)" \
  -m "feat(writing): chapter positions are deferrable; exports and uploads gain a timestamp and a size" \
  -m "User-visible: none yet — the columns and the constraint land before their surfaces."
```

---

### Task 2: `PATCH /novels/{id}`

**Files:**
- Modify: `app/capabilities/writing/schemas.py` (`NovelUpdate`, `NovelRead.last_exported_at`), `service.py` (`update_novel`, `InvalidNovelUpdateError`), `repository.py` (reuse `save`), `router.py`
- Test: `app/capabilities/writing/tests/test_novel_management.py` (create)

**Interfaces:**
- Produces: `WritingService.update_novel(novel_id: UUID, changes: NovelUpdate) -> Novel`; `InvalidNovelUpdateError(field: str)`; route `PATCH /api/writing/novels/{novel_id}` → `NovelRead`, 404 `"novel not found"`, 422 with `detail` naming the field.
- Consumes: Task 1's `Novel.last_exported_at`.

- [ ] **Step 1: Failing tests** (`ASGITransport(app)` client as in `test_novels.py`): `test_patch_changes_only_the_fields_sent`, `test_patch_trims_the_title`, `test_patch_refuses_an_empty_title`, `test_patch_refuses_a_bad_language_code`, `test_patch_clears_the_language_with_null_and_with_empty_string`, `test_patch_accepts_bcp47_like_codes` (`de`, `en-GB`), `test_patch_refuses_a_genre_over_80`, `test_patch_bumps_updated_at`, `test_patch_answers_404_for_a_foreign_novel`.

```python
patched = await client.patch(f"/api/writing/novels/{novel_id}", json={"author": "J. Autorin"})
assert patched.status_code == 200
assert patched.json()["author"] == "J. Autorin"
assert patched.json()["title"] == "Der Nebel"  # untouched
```

- [ ] **Step 2: Red** — `just test-file app/capabilities/writing/tests/test_novel_management.py` → 405 (no route).

- [ ] **Step 3: Implement.** `NovelUpdate` follows the `EntityUpdate` precedent: every field `str | None = None`, partial through `model_fields_set`. Validation lives in the service (so a hand-written call cannot skip it): title `strip()`, refuse `""`, `>200`; genre `strip()`, refuse `>80`; author/blurb `strip()`, `""` becomes `None`; language `strip()`, `""` → `None`, else must match `^[a-z]{2}(-[A-Za-z]{2,})?$`. Raise `InvalidNovelUpdateError("title")` etc.; the router maps it to `HTTPException(422, detail=f"invalid {field}")`. Write through `NovelRepository.save(novel, changes.model_dump(exclude_unset=True))` and commit; `updated_at` comes from the column's `onupdate`.

- [ ] **Step 4: Green** — the same `just test-file` command, all tests PASS; then `just check`.

- [ ] **Step 5: Commit** — `feat(writing): a novel's five metadata fields are editable`, `User-visible: a book's title, genre, blurb, author and language can be corrected after it exists.`

---

### Task 3: `DELETE /novels/{id}`

**Files:**
- Modify: `service.py` (`delete_novel`), `router.py`
- Test: `app/capabilities/writing/tests/test_novel_management.py`

**Interfaces:**
- Produces: `WritingService.delete_novel(novel_id: UUID) -> None`; `DELETE /api/writing/novels/{novel_id}` → 204, 404 `"novel not found"`.
- Consumes: Task 2's error conventions.

- [ ] **Step 1: Failing tests** — `test_delete_novel_answers_204_and_is_gone`, `test_delete_novel_cascades_chapters_entities_relations_suggestions_findings` (seed via the API/DB, then `SELECT count(*)` per table is 0 for that novel), `test_delete_novel_leaves_documents_alone` (one document before, one after), `test_delete_novel_answers_404_for_a_foreign_novel`.

- [ ] **Step 2: Red** — the route does not exist (405).

- [ ] **Step 3: Implement.** `get` → `NotFoundError`; `await self.novels.delete(novel)`; commit. The FKs already cascade (`ondelete="CASCADE"`); no manual child deletes.

- [ ] **Step 4: Green** — same file, all PASS; `just check`.

- [ ] **Step 5: Commit** — `feat(writing): a novel can be deleted with everything it carried`, `User-visible: deleting a book removes its chapters, entities, relations, suggestions and findings; documents stay in the library.`

---

### Task 4: `DELETE /chapters/{id}` with contiguous renumber

**Files:**
- Modify: `repository.py` (`renumber`), `service.py` (`delete_chapter`), `router.py`
- Test: `app/capabilities/writing/tests/test_chapter_management.py` (create)

**Interfaces:**
- Produces: `ChapterRepository.renumber(novel_id: UUID, ordered_ids: Sequence[UUID]) -> None` — one Core `UPDATE` per chapter in the given order setting `position=i` and `updated_at=Chapter.updated_at` (the self-assignment is what defeats the column's `onupdate`); `WritingService.delete_chapter(chapter_id: UUID) -> None`; route 204 / 404 `"chapter not found"`.
- Consumes: Task 1's deferrable constraint; the existing novel-row lock pattern (`_touch_novel`).

- [ ] **Step 1: Failing tests** — `test_delete_chapter_renumbers_contiguously` (`[0,1,2]` minus the middle → positions `[0,1]`), `test_delete_chapter_keeps_the_survivors_updated_at` (read `updated_at` before, compare after), `test_delete_chapter_advances_the_novel_timestamp`, `test_delete_chapter_cascades_its_pending_suggestions`, `test_delete_chapter_leaves_findings`, `test_delete_chapter_answers_404_for_a_foreign_chapter`.

- [ ] **Step 2: Red** — 405.

- [ ] **Step 3: Implement.** Load the chapter (owned) → `NotFoundError`; `await self.chapters.delete(chapter)`; fetch the survivors ordered by position; `await self.chapters.renumber(novel_id, [c.id for c in survivors])`; `await self._touch_novel(novel_id)`; commit. Flush before the renumber so the delete is visible to the read.

- [ ] **Step 4: Green** — `just test-file app/capabilities/writing/tests/test_chapter_management.py` PASS; `just test-file app/capabilities/writing/tests/test_chapter_positions.py` still PASS; `just check`.

- [ ] **Step 5: Commit** — `feat(writing): a chapter can be deleted, and the rest close the gap`, `User-visible: deleting a chapter renumbers the book so the rail never shows a missing number.`

---

### Task 5: `PUT /novels/{id}/chapter-order`

**Files:**
- Modify: `schemas.py` (`ChapterOrderUpdate`), `service.py` (`reorder_chapters`, `OrderMismatchError`), `router.py`
- Test: `app/capabilities/writing/tests/test_chapter_management.py`

**Interfaces:**
- Produces: `ChapterOrderUpdate {chapter_ids: list[UUID]}`; `WritingService.reorder_chapters(novel_id: UUID, chapter_ids: Sequence[UUID]) -> None`; `OrderMismatchError(current: list[UUID])`; route 204; `409` detail `{"code": "order_mismatch", "chapter_ids": [str(id), ...]}` in current position order; 422 for a repeated id inside the body (schema-level `field_validator`).
- Consumes: Task 4's `renumber`.

- [ ] **Step 1: Failing tests** — `test_reorder_rewrites_contiguously`, `test_reorder_keeps_each_rows_updated_at`, `test_reorder_advances_the_novel_timestamp`, `test_reorder_refuses_a_missing_id` (409 + detail shape), `test_reorder_refuses_an_extra_id`, `test_reorder_refuses_a_foreign_id`, `test_reorder_refuses_a_duplicate_id` (422), `test_reorder_leaves_the_order_untouched_on_refusal` (read back the old order).

- [ ] **Step 2: Red** — 405/404.

- [ ] **Step 3: Implement.** Load the current ids ordered by position under the existing novel-row lock; compare as a set and length; on mismatch raise `OrderMismatchError(current)`; else `renumber(novel_id, chapter_ids)` + `_touch_novel` + commit. The comparison is exact — no intersection.

- [ ] **Step 4: Green** — the same file PASS; `just check`.

- [ ] **Step 5: Commit** — `feat(writing): a novel's chapter order is written as a whole`, `User-visible: arranging a book is one transaction; a stale arrangement is refused with the current order instead of silently reshaping it.`

---

### Task 6: Documents — size, chunk count, delete

**Files:**
- Modify: `app/capabilities/knowledge/schemas.py`, `service.py` (`ingest`, `list_documents`, `delete_document`), `repository.py` (`count_chunks`), `router.py`
- Test: `app/capabilities/knowledge/tests/test_document_management.py` (create)

**Interfaces:**
- Produces: `DocumentRead {id, title, created_at, byte_size: int | None, chunk_count: int}`; `KnowledgeService.list_documents() -> list[tuple[Document, int]]`; `delete_document(document_id: UUID) -> None`; route `DELETE /api/knowledge/documents/{document_id}` 204 / 404 `"document not found"`.
- Consumes: Task 1's `Document.byte_size`.

- [ ] **Step 1: Failing tests** — `test_ingest_stores_the_utf8_byte_size`, `test_document_list_counts_chunks_in_one_query` (two documents, counts per row), `test_delete_document_cascades_chunks`, `test_delete_document_removes_its_passages_from_search`, `test_delete_document_answers_404_for_a_foreign_document`.

- [ ] **Step 2: Red** — missing field and route.

- [ ] **Step 3: Implement.** `byte_size=len(text.encode("utf-8"))` at ingest (the same expression the limit already uses, computed once); `count_chunks(ids)` returns `{document_id: count}` from one `GROUP BY`; the router builds `DocumentRead` from the pair (`.model_validate(document).model_copy(update={"chunk_count": count})`); delete loads, deletes, commits — chunks cascade.

- [ ] **Step 4: Green** — `just test-file app/capabilities/knowledge/tests/test_document_management.py` PASS; `just test-file app/capabilities/knowledge/tests/test_knowledge.py` PASS; `just check`.

- [ ] **Step 5: Commit** — `feat(knowledge): a document knows its size, its passages and how to leave`, `User-visible: the documents list shows size and passage count, and a wrong upload can be removed.`

---

### Task 7: The export trace

**Files:**
- Modify: `app/capabilities/writing/repository.py` (`touch_exported`), `service.py` (`export_novel`), `schemas.py` (`NovelRead.last_exported_at` is Task 2's; assert it here)
- Test: `app/capabilities/writing/tests/test_novel_management.py`, `app/capabilities/writing/tests/test_interchange_api.py`

**Interfaces:**
- Produces: `NovelRepository.touch_exported(novel_id: UUID) -> None` writing `last_exported_at = datetime.now(UTC)`; `export_novel` calls it after the engine succeeds, in **both** deliveries, and commits (ZIP mode's commit carries only the timestamp).
- Consumes: Task 1's column, Task 2's `NovelRead`.

- [ ] **Step 1: Failing tests** — `test_zip_export_records_the_timestamp`, `test_path_export_records_the_timestamp`, `test_a_refused_path_export_records_nothing` (point at a non-empty directory; assert the column stays `None`), `test_a_missing_novel_export_records_nothing`, `test_novel_read_carries_the_timestamp`.

- [ ] **Step 2: Red** — the field is `None` after a successful export.

- [ ] **Step 3: Implement.** In `export_novel`, after the engine call and after the path write succeeds: `await self.novels.touch_exported(novel_id)` then `await self.session.commit()`; the ZIP branch commits before returning the bytes. Refusals raise before the touch.

- [ ] **Step 4: Green** — both files PASS; `just check`.

- [ ] **Step 5: Commit** — `feat(writing): an export leaves a timestamp behind`, `User-visible: the delete dialog can tell how old a book's backup is; nothing blocks on it.`

---

### Task 8: The canon rule in the knowledge capability

**Files:**
- Modify: `app/capabilities/knowledge/repository.py` (`EntityRepository`/`RelationRepository` `_touch_novel`), `service.py` (call sites)
- Test: `app/capabilities/knowledge/tests/test_canon_timestamps.py` (create)

**Interfaces:**
- Produces: `KnowledgeService` writes that advance the novel: `create_relation`, `update_relation`, `delete_relation`, `update_entity`, `delete_entity`, `accept_suggestion`. The helper locks the novel row and sets `updated_at` — the same shape as writing's `_touch_novel`.
- Consumes: nothing from earlier tasks; runs on the merged tree.

- [ ] **Step 1: Failing tests** — one test per path, each: read the novel's `updated_at`, do the write, read again, assert it moved: `test_adding_an_relation_advances_the_novel`, `test_retyping_a_relation_advances_the_novel`, `test_deleting_a_relation_advances_the_novel`, `test_editing_an_entity_advances_the_novel`, `test_deleting_an_entity_advances_the_novel`, `test_accepting_a_suggestion_advances_the_novel`; plus `test_ingesting_a_document_does_not_advance_the_novel` and `test_dismissing_a_finding_does_not_advance_the_novel`.

- [ ] **Step 2: Red** — the timestamp does not move.

- [ ] **Step 3: Implement.** One private helper in the knowledge repository (not imported from writing — no capability import): lock the novel row for the entity's `novel_id`, set `updated_at = datetime.now(UTC)`. Call it inside each listed write, before that method's commit. Document writes and findings do not call it.

- [ ] **Step 4: Green** — `just test-file app/capabilities/knowledge/tests/test_canon_timestamps.py` PASS; `just test-file app/capabilities/knowledge/tests/test_entities.py` and `test_relations.py` PASS; `just check`.

- [ ] **Step 5: Commit** — `fix(knowledge): working on the canon counts as touching the book`, `User-visible: an entity or relation edit now moves its book up the shelf and makes its export warning current.`

---

### Task 9: The title in the runhead, and a draft-aware autosave

**Files:**
- Modify: `web/lib/save.tsx`, `app/capabilities/writing/web/ChapterEditor.tsx`, `app/capabilities/writing/web/NovelPage.tsx`, `i18n/{en,de,fr}.json`
- Test: `web/lib/save.test.tsx` (create), `app/capabilities/writing/web/ChapterEditor.test.tsx`, `app/capabilities/writing/e2e/test_chapters_e2e.py`

**Interfaces:**
- Produces: `useAutosave(chapterId: string | null, onSaved?: (chapterId: string, draft: DocumentDraft) => void)` with `DocumentDraft = {title: string; body: string}` and `schedule(draft: DocumentDraft, changed: keyof DocumentDraft)`; `flush()` sends only the dirty fields and clears them on success; `discard()` unchanged. `ChapterEditor` gains `title: string` and `onTitleChange: (value: string) => void`.
- Consumes: nothing; Task 2's `PATCH`-style semantics live on `PUT /chapters/{id}` already (partial through `exclude_none`).

- [ ] **Step 1: Failing tests.** Unit (`save.test.tsx`): `a_body_only_save_sends_no_title`, `a_title_only_save_sends_no_body`, `a_flush_carries_every_dirty_field`, `a_refused_save_keeps_its_draft`. Component: `the_runhead_renders_the_title_as_an_editable_field`, `typing_a_title_leaves_the_save_pending`. E2E (add to `test_chapters_e2e.py`): `test_renaming_a_chapter_carries_to_the_rail_and_the_shelf` — type a title, wait for `save.saved`, assert the rail row and the shelf card.

- [ ] **Step 2: Red** — `cd web && pnpm vitest run lib/save.test.tsx` — the hook has no draft concept; the runhead shows a `<p>`.

- [ ] **Step 3: Implement.** The hook's pending slot becomes `{draft: DocumentDraft, dirty: Set<keyof DocumentDraft>}`, one entry per field at most, generation-based retirement unchanged. `flush()` sends `{title?, body?}` for dirty keys only; a `"pending"` status covers both fields. `NovelPage` holds `draft` state next to the body, passes `title`/`onTitleChange` down, and `remember` updates `["chapters", id]` from the draft. In `ChapterEditor`, the runhead's chapter line becomes an `<input>` (`aria-label={t("chapters.titleLabel")}`, `maxLength={200}`, `value={title}`, no `required` — empty is legal), with the same typographic class as the heading. New keys: `chapters.titleLabel` ("Chapter title"/"Kapiteltitel"/"Titre du chapitre").

- [ ] **Step 4: Green** — `just test-frontend` for the two files, then `just test-e2e writing`; `just check`.

- [ ] **Step 5: Commit** — `feat(writing): a chapter's title is written where it is read`, `User-visible: the chapter title is editable in the runhead and saves with the body in one request.`

---

### Task 10: `web/ui/Menu`, the runhead action menu, and deleting a chapter

**Files:**
- Create: `web/ui/Menu.tsx`, `web/ui/Menu.test.tsx`, `app/capabilities/writing/web/ChapterDialogs.tsx`
- Modify: `ChapterEditor.tsx`, `NovelPage.tsx`, `web/lib/query.ts`, `i18n/{en,de,fr}.json`
- Test: `web/ui/Menu.test.tsx`, `app/capabilities/writing/web/NovelPage.test.tsx`, `test_chapters_e2e.py`

**Interfaces:**
- Produces: `ActionMenu({ label, ariaLabel, items }: { items: { id: string; label: string; shortcut?: string; onSelect: () => void; disabled?: boolean }[] })` built on RAC `MenuTrigger`/`Menu`/`MenuItem` with the shell's `Button`; `useDeleteChapter(novelId)`; `ChapterDeleteDialog({ novelId, chapter, open, onOpenChange })`; `ChapterRenameDialog({ chapter, open, onOpenChange })`.
- Consumes: Task 4's `DELETE /chapters/{id}`, Task 9's draft hook and title input, Task 7's `last_exported_at`.

- [ ] **Step 1: Failing tests** — `Menu.test.tsx`: `the_trigger_opens_on_press_and_escape_closes`, `arrow_keys_walk_the_items`, `a_disabled_item_does_not_fire`. `NovelPage.test.tsx`: `the_runhead_menu_offers_rename_delete_and_move`, `deleting_the_open_chapter_opens_its_neighbour`, `deleting_the_open_chapter_retires_the_pending_save`, `renaming_the_open_chapter_survives_the_next_debounce` (rename with a body edit still pending; the next flush must send the body only and the new title must stand), `the_delete_dialog_names_the_chapter_and_the_export_age`. E2E: `test_deleting_a_chapter_opens_its_neighbour` — delete chapter 2, assert the header shows chapter 3, the rail has one row fewer, and the database holds `0..n-1` via a `_rows` helper in the file.

- [ ] **Step 2: Red** — no menu, no dialog, no mutation.

- [ ] **Step 3: Implement.** New primitive with the tokens (`buttonClass`, `--card`, `--border`, `--radius`, focus ring once); the runhead's right side gains the menu (rename → focus the title input; move up/down → Task 11's `move()`; delete → the dialog). Deleting the open chapter: `discard()` the autosave, `DELETE`, invalidate `["chapters", id]` and `["novels"]`, then `navigate` to the neighbour in the new list (`?chapter=`, push); a non-open chapter's delete leaves the URL alone. The chapter dialog compares `last_exported_at` with that chapter's `updated_at` and prints "never exported" / "exported N days ago" / "changed since". Keys: `chapters.actions`, `chapters.rename`, `chapters.delete`, `chapters.moveUp`, `chapters.moveDown`, `chapters.deleteTitle`, `chapters.deleteBody` (names the chapter), `chapters.exportFresh`, `chapters.exportStale`, `chapters.exportNever`.

- [ ] **Step 4: Green** — `just test-frontend`, `just test-e2e writing`, `just check`.

- [ ] **Step 5: Commit** — `feat(writing): a chapter's actions live in its runhead`, `User-visible: renaming, moving and deleting a chapter are one menu away, and deleting opens the neighbour.`

---

### Task 11: Reorder — `Alt+↑/↓`, the announcer, and desktop drag

**Files:**
- Modify: `NovelPage.tsx`, `web/lib/query.ts`, `i18n/{en,de,fr}.json`
- Test: `app/capabilities/writing/web/NovelPage.test.tsx`, `test_chapters_e2e.py`

**Interfaces:**
- Produces: `useReorderChapters(novelId)` calling `PUT /novels/{novel_id}/chapter-order`; `move(chapterId: string, delta: -1 | 1) -> Promise<void>` and `moveTo(chapterId: string, index: number) -> Promise<void>` in `NovelPage` (both optimistic via `setQueryData`, revert on any failure with a `Notice tone="danger"`, `409` refreshes `["chapters", id]`); drag handlers on each `<li>`/`Row`.
- Consumes: Task 5's endpoint, Task 10's menu items.

- [ ] **Step 1: Failing tests** — `NovelPage.test.tsx`: `alt_arrow_down_moves_the_focused_chapter`, `a_refused_order_reverts_and_names_the_refusal`, `a_successful_move_invalidates_the_shelf`, `the_move_is_announced_with_its_new_position`. E2E: `test_moving_a_chapter_by_keyboard_survives_a_reload` (focus a row, `Alt+ArrowUp`, reload, order is the new one, `updated_at` of the moved row unchanged, the novel's advanced).

- [ ] **Step 2: Red** — no handler, no mutation.

- [ ] **Step 3: Implement.** `move` computes the new id list, `setQueryData` optimistically, `PUT`; failure → restore the previous list, `Notice` with `chapters.orderFailed`, and on `409` also `refetch()`. `onKeyDown` on the rail: `event.altKey && (ArrowUp|ArrowDown)` → `move(id, ±1)`, `preventDefault`, announce via `announce()` from `@react-aria/live-announcer` with `chapters.moved` = "Chapter {title}, position {n} of {m}". Drag: `draggable` on the row, `onDragStart` stores the id in a ref, `onDragOver` sets `dropIndex` (and `preventDefault`), `onDrop` calls `moveTo(sourceId, dropIndex)`; no roles, no `dataTransfer` reads; drag is wired only while no filter is active.

- [ ] **Step 4: Green** — `just test-frontend`, `just test-e2e writing`, `just check`.

- [ ] **Step 5: Commit** — `feat(writing): chapters are arranged by drag and by keyboard`, `User-visible: dragging a chapter or pressing Alt+↑/↓ reorders the book and survives a reload.`

---

### Task 12: The rail filter

**Files:**
- Modify: `NovelPage.tsx`, `i18n/{en,de,fr}.json`
- Test: `app/capabilities/writing/web/NovelPage.test.tsx`, `test_chapters_e2e.py`

**Interfaces:**
- Consumes: the rail's `chapters` list, `walkRail`, `move`.
- Produces: `chapters.railFilter`, `chapters.railFilterAria`; filter state cleared on create (existing create path).

- [ ] **Step 1: Failing tests** — `the_filter_appears_only_above_twenty_chapters`, `the_filter_matches_an_untitled_chapters_rendered_label`, `the_filter_matches_diacritics_insensitively`, `creating_a_chapter_clears_the_filter`, `the_move_menu_items_are_disabled_while_the_filter_is_active`. E2E: `test_a_sixty_chapter_rail_stays_inside_the_viewport` — seed 60 chapters through the API, open the workspace at 1280; assert the rail's box is inside the viewport while the editor scrolls, the filter is visible, `assert_page_fits(page, prose_selector=…)` and `assert_accessible(page)` pass.

- [ ] **Step 2: Red**.

- [ ] **Step 3: Implement.** A `Field`/`Input` in the rail's toolbar band when `chapters.length > 20`; matching reuses the palette's `normalize` (move it to `web/lib/search.ts` and import it in both places — one definition); the visible list is the filtered list, the walk indexes into it, `move` is disabled while a filter is active and the menu items say why via `disabled` + `aria-describedby`-free tooltip text in the item label ("Move up (clear the filter first)").

- [ ] **Step 4: Green** — `just test-frontend`, `just test-e2e writing`, `just check`.

- [ ] **Step 5: Commit** — `feat(writing): a long rail gets a filter`, `User-visible: past twenty chapters the rail gains a filter that finds titles and the chapter numbers shown for untitled ones.`

---

### Task 13: Shelf — details dialog, delete, and the export warning

**Files:**
- Create: `web/lib/exportAge.ts`, `web/lib/exportAge.test.ts`, `app/capabilities/writing/web/NovelsPage.test.tsx` (if absent)
- Modify: `NovelsPage.tsx`, `NovelPage.tsx` (the 404 degrade), `web/lib/query.ts`, `i18n/{en,de,fr}.json`
- Test: `web/lib/exportAge.test.ts`, `app/capabilities/writing/web/NovelsPage.test.tsx`, `app/capabilities/writing/web/NovelPage.test.tsx`, `app/capabilities/writing/e2e/test_novels_e2e.py`

**Interfaces:**
- Produces: `exportAge(lastExportedAt: string | null, changedAt: string, now: Date) -> { kind: "never" } | { kind: "fresh" } | { kind: "stale"; days: number }` — the one pure comparison both dialogs use; `useUpdateNovel`, `useDeleteNovel`; `NovelDetailsDialog({ novel, open, onOpenChange })`, `NovelDeleteDialog({ novel, open, onOpenChange })`.
- Consumes: Task 2, Task 3, Task 7; `useEntitiesQuery` for the entity count; `ExportNovelDialog` for "Export now".

- [ ] **Step 1: Failing tests** — `exportAge.test.ts`: `never_exported_is_never`, `an_export_after_the_last_change_is_fresh`, `an_export_before_the_last_change_is_stale_with_its_day_count`, `a_change_without_an_export_is_stale`. Component: `the_card_menu_offers_details_and_delete`, `details_saves_all_five_fields`, `an_empty_title_is_refused_by_name`, `the_delete_dialog_names_chapters_entities_and_that_documents_survive`, `the_delete_dialog_says_never_exported_and_offers_export`, `a_fresh_export_flips_the_line`. `NovelPage.test.tsx`: `a_novel_deleted_elsewhere_degrades_to_the_shelf` (the novel query answers 404 → navigate `/` with a quiet named notice). E2E: `test_export_then_delete_a_novel` — details dialog rename, export to a temp folder, delete; assert gone from the shelf and zero rows in chapters/entities/relations/suggestions/findings for the id.

- [ ] **Step 2: Red**.

- [ ] **Step 3: Implement.** `exportAge` as above (no clock inside; `now` is a parameter). Card action menu (Task 10's primitive); the details dialog mirrors `NewBookForm`'s field/refusal style for five fields, language as a validated text field (`pattern` + server 422 shown on the field), saving only the fields the user changed. The delete dialog reads `chapter_count` from the card's novel, entity count from `useEntitiesQuery`, and its line from `exportAge(...)`; "Export now" (path mode) invalidates `["novels", id]` on success. `NovelPage`: when `useNovelQuery` errors with a 404, `navigate({ to: "/" })` and show `novels.deleteElsewhere` as a quiet notice.

- [ ] **Step 4: Green** — `just test-frontend`, `just test-e2e writing`, `just check`.

- [ ] **Step 5: Commit** — `feat(writing): a book's details are editable and its deletion is warned`, `User-visible: the shelf can correct a book's metadata and delete it after saying what dies and how old the backup is.`

---

### Task 14: Documents panel — size, passages, date, delete

**Files:**
- Modify: `app/capabilities/knowledge/web/KnowledgePage.tsx`, `web/lib/query.ts`, `i18n/{en,de,fr}.json`
- Test: `app/capabilities/knowledge/e2e/test_knowledge_e2e.py`

**Interfaces:**
- Produces: `useDeleteDocument`; rows built on `Row as="div"` with `trailing` metadata and a delete `Dialog`.
- Consumes: Task 6's `DocumentRead`.

- [ ] **Step 1: Failing tests** — E2E: `test_deleting_a_document_removes_its_passages_from_search` (upload, search hits, delete, search empty, database chunk count 0), `the_empty_state_names_text_files_up_to_one_megabyte`.

- [ ] **Step 2: Red**.

- [ ] **Step 3: Implement.** Row: title, `formatBytes(byte_size)` (a small local helper; `—` when null), `t("knowledge.chunkCount", {count})`, `t("knowledge.uploadedOn", {date})`, delete dialog with `knowledge.deleteBody` = "final — the original file stays where you uploaded it from". Empty state: `knowledge.empty` names text files up to 1 MB, no extensions.

- [ ] **Step 4: Green** — `just test-e2e knowledge`; `just check`.

- [ ] **Step 5: Commit** — `feat(knowledge): the documents list says what it holds and can delete`, `User-visible: each document shows its size, its passages and its upload date, and a wrong upload can be removed for good.`

---

### Task 15: French pass, the report, and close-out

**Files:**
- Modify: `i18n/fr.json`
- Create: `docs/superpowers/reports/2026-11-0X-wp6-report.md`

- [ ] **Step 1: Translate `fr`** — every key Tasks 9–14 added carries real French; no English placeholder survives (`rg -n "TODO|FIXME" i18n/fr.json` empty).

- [ ] **Step 2: Full gate** — `just verify all` (every suite, every capability's E2E) and `just test-e2e all`; read the output and paste the summary lines into the report. A gate counts only when its output was read.

- [ ] **Step 3: File the findings** — every finding this wave's reviews produced becomes a GitHub issue with `--label follow-up --label "severity: …" --label "area: …"` and `--label "kind: …"` where it applies (`test-gap`, `docs-drift`, `flake`, `a11y`, `i18n`, `race`); add the wave's index row to `docs/superpowers/follow-ups.md`.

- [ ] **Step 4: Commit** — `docs(writing): WP6's report and the French pass`, `User-visible: none — the report and the translation pass.`
