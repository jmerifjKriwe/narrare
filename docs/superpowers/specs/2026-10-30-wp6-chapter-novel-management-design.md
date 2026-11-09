# WP6 — Chapter and novel management: rename, arrange, delete

**Date:** 2026-10-30 · **Revised:** 2026-11-04 against the merges of 30.10.–04.11.
**Status:** decisions settled with the product owner 2026-10-30 (D1–D8); builder
check done 2026-10-30; D3 and D6 re-decided 2026-11-04 after the UI-B wave landed;
plan approved 2026-11-05, its one narrowing (the runhead action menu) accepted
**Authority:** Fahrplan `docs/superpowers/plans/2026-10-25-v2-foundation.md` §8A,
narrowed by this design; architecture spec `2026-10-21-narrare-v2-architecture-design.md`
(§9.4 deletion and backup); **UI-B spec `2026-10-31-narrare-ui-b-pur-design.md`** — the
surface authority for the rail, runhead, shelf and documents panel; its plan
`2026-10-31-narrare-ui-b-pur-plan.md`; schema-migrations design
`2026-10-30-schema-migrations-design.md`; e2e-cadence design
`2026-10-31-e2e-cadence-design.md`; WP3 design
`2026-10-28-wp3-markdown-demo-export-design.md` (D2 narrows §8A.2; D3/D4 assign novel
metadata to WP6); WP5 design `2026-10-30-wp5-ui-coherence-design.md` (Query,
`?chapter=`, commands, modal host) — merged as #480. Builds on merged WP3 (export
exists) and the five standing rules in `docs/_shared/CONSTRAINTS.md`.

## Intent

The writing loop does not close. A chapter's title is written once — by the
server, as `""` — and never again: `ChapterUpdate.title` exists and no field
renders it. No surface deletes or renames a novel, a chapter or a document,
and `Chapter.position` exists with no way to change it. A writer can fill a
book and cannot then arrange it, correct it, or throw a mistake away.

WP6 adds the management surfaces: rename and edit novel metadata, rename
chapters, reorder by drag and by keyboard, delete a chapter, a novel (after
export), and a document. The server half (schema, endpoints, export trace) is
independent of the frontend half; the frontend half reopens the rail, the
runhead, the shelf and the documents panel **as built** after WP5 (#480) and the
UI-B wave (#581) — not as either plan imagined them.

## Goals

- **API (writing):** `PATCH /novels/{id}` (title, genre, blurb, author,
  language), `DELETE /novels/{id}` (chapters cascade), `DELETE /chapters/{id}`
  (remaining positions renumbered in the same transaction),
  `PUT /novels/{id}/chapter-order` (full list, rewritten contiguously
  `0..n-1`, one transaction).
- **API (knowledge):** `DELETE /documents/{id}` (chunks cascade) — a wrong
  upload is permanent today, which is why the corpus guard can tell a user to
  re-embed but never to remove.
- **Export leaves a trace:** `novels.last_exported_at`, set by every
  successful export (path *and* ZIP). Delete dialogs compare it with the
  newest change and warn — they never block.
- **Chapter title editable** in the runhead (where the book · chapter line
  already sits, read-only today) and from the rail (dialog); `""` is a legal
  title meaning "unnamed"; the debounced save carries title **and** body in one
  request, sends only the fields that changed, and `flush()` cannot lose a
  rename to a navigation.
- **Rail reorder** on the plain-`Row` rail the UI-B wave built: native drag on
  desktop, `Alt+↑/↓` everywhere, and a per-row menu (rename, delete, move up,
  move down) that is also the touch path; no new dependency and no role change.
- **Filter field** above 20 chapters in the rail that already scrolls itself;
  the rail's bounded scroll container and word counts landed with UI-B.
- **Shelf:** novel details dialog (all five metadata fields), novel delete, on
  the card grid UI-B built.
- **Documents:** size, chunk count, upload date and a delete button in the
  existing `Panel` list; an empty state that claims only what the server holds.
- **Database invariants, not endpoint promises:** contiguity of positions is
  enforced by a unique constraint (which WP6 makes deferrable) and preserved by
  delete; every delete's cascade is proven against the database, not the screen.

## Non-goals (§8A.5, unchanged)

Multi-select, chapter duplication, parts/volumes (Series is Tier 2), undo or
trash (soft delete lands with relations, §9.4), importing an existing
manuscript at scale (WP3's import). No palette commands for item actions —
the palette's `ctx` carries no item, so delete/rename stay row actions. No
per-chapter export record; the novel's timestamp covers its chapters. No
soft-delete columns.

## Anti-goals

No delete without a named confirmation that says what dies. No silent
reordering: a stale order is refused (`409`), never merged. No UI claim the
server does not hold (the documents empty state names text files up to 1 MB
because the endpoint checks bytes, not extensions). **No new frontend
package, and no change to the rail's element roles** — the UI-B spec decided
the chapter rail stays a list of plain rows (`<ul>`/`<li>`/`Row`), with the
React-Aria `GridList` reserved for the entity list.

## Constraints

- The five standing rules (`docs/_shared/CONSTRAINTS.md`): one capability one
  folder, no capability imports another, `user_id` on every user-owned row, no
  side effect beyond the request's transaction, English in code and docs.
- **Alembic is the schema path** (schema-migrations wave, #509): every change is
  a revision authored with `just db-revision "<message>"`, and `just db-init`
  upgrades an existing database (`db-reset` is no longer the only door). The
  former "no migrations" rule is superseded by that wave's design.
- Existing API contracts stay intact. The one relaxation —
  `ChapterUpdate.title` accepting `""` — is additive permissiveness on a field
  no client sends today, and is pinned by tests.
- i18n: every key ships in en, de and fr in the same commit; `fr` may carry
  the English string as a marked placeholder in the WP commit, the translation
  pass is its own commit (WP5's rule).
- The UI-B spec governs how new surfaces look and what roles they carry: `Row`,
  `Dialog`, `Panel`, `Table` are the primitives, the rail keeps its plain rows
  and roving tabindex, and no wave re-litigates those decisions by accident.
- Sequencing: the server half may land before the frontend half; the frontend
  half starts from the as-built rail/runhead/shelf/documents panel.

## Current state (as built, 2026-11-04)

- **Rail (UI-B P12 + werkbank #581):** a `<ul>` of plain `Row`s — 28 px rows,
  `aria-current` on the open chapter, one tab stop with a roving `tabIndex` and
  a hand-rolled Up/Down walk (`walkRail`), a per-row word count, the collapse
  control in the toolbar band, and a list that scrolls itself in the desktop
  columns (`lg:min-h-0 lg:flex-1 lg:overflow-y-auto`). The UI-B spec decides
  explicitly that the rail keeps plain elements and **no role change**, and that
  `web/ui/GridList` (React Aria) is the entity list's primitive. E2E queries
  rows as `get_by_role("button", name=^Kapitel N)` and asserts `aria-current`.
- **Workspace seams from WP5 (#480), merged:** `useNovelQuery(id)` →
  `["novels", id]`, `useChaptersQuery(id)` → `["chapters", id]`,
  `useEntitiesQuery`, `useNovelsQuery`; the active chapter is `?chapter=` behind
  a widened `useBlocker` that flushes the autosave; the palette
  (`web/components/Palette.tsx`) runs capability commands and owns a modal slot
  (`ctx.openModal(load)`); `writing/web/commands.ts` is data-only. The rail and
  dock overlay below 1024 px with a scrim and `inert`.
- **Runhead (UI-B):** the editor card carries book title · chapter title on the
  left and the save state on the right, plus a footer with the chapter's word
  count and "Kapitel n von m". The chapter title is **read-only** — the slot
  WP6's input goes into exists; its editability does not.
- **Shelf (UI-B):** a card grid with cover, genre, language, last touched and
  the derived chapter/word counts; no card actions exist yet.
- **Titles:** `ChapterCreate.title` defaults to `""` (the localized
  placeholder is a rendering of `position + 1`); `ChapterUpdate.title` still
  requires `min_length=1`. A chapter may be born untitled but can never become
  untitled. No surface edits it either way.
- **No management endpoints exist.** `DELETE` exists for entities, relations,
  profiles and prompt overrides; nothing deletes novels, chapters or
  documents. No `PATCH` exists for novels.
- **Positions (chapter-position fix #522):** `chapters` carries
  `UNIQUE (novel_id, position)` — plain, **not deferrable** — and
  `app/kernel/contracts/positions.py::next_chapter_position` serializes appends
  by locking the novel row (`SELECT … FOR UPDATE`) before reading `MAX + 1`.
  The allocator is built; a renumbering rewrite inside one transaction is not,
  and the plain constraint would refuse one.
- **Export is stateless.** `export_novel` returns a ZIP or writes a directory
  and records nothing; "export before delete" is today unprovable.
- **Derived counts:** `NovelRead` carries `chapter_count` and `word_count`,
  counted from the chapters in one grouped query. The shelf already shows both.
- **Documents:** `Document` stores title, `embedding_width`, `created_at`;
  `DocumentRead` exposes id, title, created_at. `ingest` checks
  `len(text.encode("utf-8")) > 1_000_000` but stores no size. The page renders
  a `Panel` list with one "+ Dokument" dialog; upload takes any file as text and
  falls back to the filename as the title.
- **Cascades already on the keys:** `EntitySuggestion.chapter_id` and every
  novel-scoped table cascade on their FKs; `ConsistencyFinding` is novel-scoped
  with no chapter FK.
- `update_chapter` already advances the novel's `updated_at` (the shelf's
  "last touched") through the novel-row lock.
- `web/ui/Dialog` exists with a controlled mode (the palette's modal slot).

## Approaches (settled with the owner, 2026-10-30)

**D1 — Export before delete is unprovable; make it comparable, don't police it.**
Three ways: state the sentence only; record `last_exported_at` and warn;
have the server refuse deletes without a fresh export. **Chosen: the
timestamp.** A refusal is theatre — the exported file can be discarded, and a
throwaway export would satisfy it; the bare sentence is today's non-solution.
The comparison (timestamp vs. newest `updated_at`) is the one statement that
is actually true.

**D2 — A stale order is refused, never merged.** `PUT chapter-order` with an
id set that does not match the novel's chapters answers `409 order_mismatch`
carrying the current ids; the client refetches and the user retries.
Applying the submitted order to the intersection would silently produce an
order nobody saw — the house rule is "refused is named, never silent".

**D3 — Reordering stays on the plain-`Row` rail (re-decided 2026-11-04).**
The original choice was a React Aria `GridList` with `useDragAndDrop`, for touch
support. Since then the UI-B wave landed and its spec decided the opposite in
so many words: the chapter rail keeps plain elements and no role change, the
`GridList` is the entity list's primitive, and the rail's E2E asserts
`aria-current` on `button` rows. **Chosen now: keep the rail as built** — native
drag on desktop, `Alt+↑/↓` everywhere, and a per-row menu (rename, delete, move
up, move down) that is the touch path. Trade-offs, named: drag does not work on
touch (the menu does), and the desktop drag is not the APG announcement
contract — the move is announced through the app's live announcer instead. What
this buys: no overturned UI-B decision, no dependency, no gridcell/row rewrite,
and the roving tabindex and word-count rows survive. The `GridList` route is
recorded as rejected *for this wave*: its trigger is a user asking for drag on
touch after the menu has proven itself.

**D4 — An empty title is legal.** `""` (after trim) means unnamed; the
placeholder stays a rendering. Refusing empty (`422`) forces invented titles;
silently reverting hides what was typed. Symmetric with `ChapterCreate`.

**D5 — Novel metadata takes all five fields.** §8A.1 names title, genre,
blurb; WP3's D3/D4 added `author` and `language` and named WP6 as their edit
surface. Without them, every hand-made novel exports `author: null`,
`language: null` while the demos carry values. **Chosen: one details dialog
with all five.** Language is validated free text (`^[a-z]{2}(-[A-Za-z]{2,})?$`,
trimmed, or cleared) — a select over `de|en|fr` could not honestly display an
imported `es`, and the three UI languages are not the three novel languages.

**D6 — Navigation walk stays, reorder gets one extra modifier (revised
2026-11-04).** The rail's Up/Down walk (roving tabindex, one tab stop) is
UI-B's decision and stays untouched. Reordering is `Alt+↑/↓` on the focused
row — one key model, no second navigation mode — and every move is announced
through `@react-aria/live-announcer` (already a dependency) with the chapter's
new position, because a plain list gives AT no "moved" story of its own. The
row menu's move items carry the hint, so the shortcut is discoverable exactly
where the action lives. Inside the editor `Alt+↑/↓` stays the system's
word-jump; the handler is scoped to the rail.

**D7 — Which neighbour opens after a delete.** The chapter that takes the
deleted one's place: the next, else the previous. Deleting the last remaining
chapter shows the empty state. Deleting a chapter that is not the open one
leaves the editor where it is.

**D8 — "Touched" means the whole canon (owner, 2026-10-30).** The export
archive carries chapters, novel metadata, entities and relations — but only
chapter writes advance `novel.updated_at` today. An entity edited, a relation
added, an entity deleted after an export left no trace anywhere, and the
delete dialog would have said "nothing changed since the export" over a
drifted canon. **Chosen: one rule — every write path that changes what the
export archive carries advances `novel.updated_at`.** Chapter saves already
do; WP6 adds chapter delete, chapter reorder, novel metadata (via `onupdate`),
and the knowledge capability's entity and relation writes. Documents,
suggestions queues, findings and chat are not in the archive and do not bump.
Consequences, accepted with the decision: an entity edit floats the novel to
the top of the shelf's "last touched", and this overturns an earlier call —
**reordering now advances `novel.updated_at`** (the archive's order differs),
while the moved chapter *rows* keep their `updated_at`, so WP5's
"arrival without `?chapter=` opens the last-written chapter" and D7 keep
their meaning.

## The design

### 1. Schema (three revisions, authored with `just db-revision`)

- `novels.last_exported_at: DateTime(timezone=True) | None` — written only by
  the export path, never by `onupdate`.
- `documents.byte_size: int` — set at ingest from the same byte count the
  limit already computes; a backfill is unnecessary (no live data), but the
  revision states the default for the existing rows.
- `chapters`: the constraint #522 landed — `UNIQUE (novel_id, position)` — is
  **replaced by its deferrable form** (`DEFERRABLE INITIALLY DEFERRED`).
  Contiguity is already the table's property; deferral is what lets one
  transaction renumber (a delete, a swap) without passing through a refused
  intermediate state. `just db-init` upgrades an existing database; `db-reset`
  stays a convenience, not the only door.

### 2. Writing API

- `PATCH /novels/{id}` — `NovelUpdate {title?, genre?, blurb?, author?,
  language?}`; absent fields unchanged. Title trimmed, 1–200 chars, empty
  refused (a novel has no placeholder — the asymmetry with chapters is
  deliberate and tested on both sides). Language trimmed, lowercased where
  the pattern allows, matched against `^[a-z]{2}(-[A-Za-z]{2,})?$` or
  `null`/`""` to clear; anything else is a 422 naming the field. Returns
  `NovelRead` (which grows `last_exported_at`). The row's `onupdate` bumps
  `updated_at`, so a metadata edit makes the export comparison honestly
  stale.
- `DELETE /novels/{id}` — 204. Chapters, entities, relations, suggestions and
  findings cascade (FKs). Documents are library-scoped (no `novel_id` today)
  and survive a novel delete — the dialog says so.
- `DELETE /chapters/{id}` — 204. Remaining chapters renumbered `0..n-1` in
  the same transaction; the deferred constraint holds at commit, and the
  renumbered rows **keep their `updated_at`** (set explicitly; the column's
  `onupdate` would otherwise stamp every moved row and corrupt "last
  written"). Pending suggestions for the chapter cascade; consistency
  findings are novel-scoped and deliberately untouched (a whole-novel finding
  can outlive one of its chapters). Advances `novel.updated_at` — the archive
  lost a chapter (D8).
- `PUT /novels/{id}/chapter-order` — body `{chapter_ids: [UUID]}`. Must be
  exactly the novel's current chapter set, any order; the server rewrites
  positions `0..n-1` in one transaction, preserving each row's `updated_at`
  as above. Missing, extra, foreign or duplicate ids → `409` with code
  `order_mismatch` and the current ids in the detail. Success: 204.
  Advances `novel.updated_at` — the archive's order changed (D8) — but no
  chapter row's timestamp (nothing in any chapter was written).
- Chapter append: **already built** — `next_chapter_position` locks the novel
  row and allocates `MAX + 1` (#522). WP6 reuses it unchanged; nothing here
  re-implements the allocator, and the deferral does not weaken it.
- Foreign and missing ids answer 404 like every owned route today ("the two
  are one answer").

### 3. Knowledge API

- `DELETE /documents/{id}` — 204, chunks cascade; passages stop answering
  search immediately.
- `DocumentRead` grows `byte_size` and `chunk_count`. The list counts chunks
  with one `GROUP BY` over the list's document ids, not a query per row.
- **The canon rule reaches the knowledge capability (D8):** entity
  create/update/delete, relation create/delete and suggestion-accept (it
  creates an entity) advance the parent novel's `updated_at`, in the same
  transaction as the write — the same `_touch_novel` pattern, in the
  knowledge capability's own repository over the kernel model (no capability
  import). Enqueued extraction, document writes, findings and chat do not:
  none of them is in the archive.

### 4. The export trace

`export_novel` sets `novels.last_exported_at = now(UTC)` after the engine
succeeds, in both deliveries — the ZIP answer commits the timestamp as its
own write (the download is the record), the path mode sets it in the same
transaction that writes the receipt. A failed export (refused target,
transport error) sets nothing.

### 5. Delete dialogs (§8A.2, as narrowed by WP3 D2)

One statement per delete, in its own dialog built on `web/ui/Dialog` (the
controlled mode the palette's modal slot already uses; the shelf and knowledge
pages mount the same components through their own triggers):

- **Novel:** names what dies — chapter count *and* entity count (both
  cascade; §8A.2's chapter count alone understates it) — and that documents
  survive. The chapter count is already on `NovelRead.chapter_count` (the card
  grid shows it); the entity count comes from `useEntitiesQuery` opened with the
  dialog, because no read carries it and an added derived count would be paid by
  every shelf load. Below it the export line: "never exported", or "exported N
  days ago — changed since", computed from `last_exported_at` against
  `novel.updated_at`, which D8 makes the one true answer for the whole archive.
  An **Export now** button sits in the dialog (path mode; a successful export
  invalidates `["novels", id]`, and the dialog recomputes its line from the
  refetch). Confirm deletes.
- **Chapter:** names the chapter (title or placeholder) and shows the same
  export line, compared against *that chapter's* `updated_at` — scoped to
  the chapter's own content; a reorder after the export is the novel line's
  story, not this one's.
- **Document:** "final" wording per WP3 D2 — the original file lives on the
  user's disk; no export reference.

Nothing is deleted on the first click; every confirm is a named button, not a
browser `confirm()`.

### 6. Chapter title

- `ChapterUpdate.title` loses `min_length`; `""` after trim is legal and
  means unnamed. `None` still means "unchanged" (`exclude_none` keeps that).
- The **runhead**'s chapter title becomes the input — the slot UI-B built
  (book title · chapter title on the left, save state on the right). The
  debounced save's payload becomes the whole document — `{title, body}` — and
  one status covers both. `useAutosave`'s pending slot holds the pair and
  tracks **which fields are dirty; the flush sends only the dirty ones** (the
  endpoint's `exclude_none` keeps the rest untouched). A body-only edit can
  therefore never rewrite the title — which is what makes the rail's rename
  dialog safe against a body flush that lands after it — and WP5's navigation
  blocker (which awaits `flush()`) cannot lose a rename to a chapter switch.
- The rail's rename is a small dialog from the row menu (an input inside a
  grid row would fight the keyboard model just chosen); it writes the same
  endpoint directly and invalidates `["chapters", id]` and `["novels", id]`.
  If it renames the chapter that is open with a body edit pending, the
  pending pair's title is not dirty, so the next flush carries the body only
  — the rename survives the debounce (pinned by name in §12).
- Deleting the chapter that is currently open discards its pending document
  the moment the delete is confirmed (the hook's existing retire/generation
  mechanism): no `PUT` flies at a chapter that no longer exists, no failed
  status is reported for a deletion the user asked for.

### 7. The rail, on the plain rows UI-B built

- **No role change.** The rail keeps `<ul>`/`<li>` and plain `Row`s,
  `aria-current` on the open chapter, the roving `tabIndex` and the Up/Down
  walk. React Aria's `GridList` stays the entity list's primitive; WP6 does not
  touch it.
- **Drag (desktop):** native HTML5 drag on the row — `draggable`, a drag start
  that carries the chapter id in component state (not in `dataTransfer`, so the
  DOM test can drive it), a drop target that marks the row it would land before,
  and a drop that calls the same `move(id, ±1 × distance)` the menu uses.
  **Drop persists**: optimistic reorder, one `PUT chapter-order`; on `409` or a
  transport failure revert and show the named alert. No refetch of
  `["chapters", id]` — the optimistic list is what the 204 acknowledged, and a
  refetch mid-unsaved-body is exactly the state WP5's invalidation rule guards
  against. Success invalidates `["novels"]` (D8 advanced the novel row).
- **Keyboard and menu:** `Alt+↑/↓` on the focused row moves it one step; the
  row menu (Rename, Delete, Move up `Alt+↑`, Move down `Alt+↓`) is the visible
  path and the touch path. Every move is announced through the live announcer
  with the new position (`Kapitel 7, Position 2 von 9`), since a plain list
  tells AT nothing about a reordering.
- **Reorder is disabled while the filter is active** (a filtered list has no
  unambiguous drop index); the menu's move items disable with it and say why.
- **Filter:** above 20 chapters a field appears in the rail's toolbar band. It
  matches the **rendered label in the active locale** — an untitled chapter is
  found by "Kapitel 7" because that is what it says. Creating a chapter clears
  the filter (otherwise the new chapter opens outside the visible list).
- The rail's bounded scroll container, the 28 px rows and the word-count
  trailing already exist; WP6 adds only the filter, the menu and the reorder.

### 8. Shelf

- Card actions per novel: **Details** (the five-field dialog: title, genre,
  blurb, author, language) and **Delete** (§5's dialog). These are the only
  novel-management surfaces — the workspace has none (§8A gives it chapter
  surfaces only). The card grid, covers and metadata line are UI-B's; WP6 adds
  the action affordance without repainting the card.
- A novel deleted from the shelf while its workspace is open in another tab
  makes the workspace's novel query answer 404; the workspace degrades to
  the shelf (WP5's failure states name the error; the degrade navigation is
  WP6's one addition to them).
- Deleting the currently open novel from its own workspace is therefore not
  a flow this WP builds; the sentence "deleting the open novel navigates to
  the shelf" resolves to the 404-degrade above.
- A rename or metadata edit bumps `updated_at`, and D8 extends the same to
  entity and relation edits: the novel may jump to the top of "last touched"
  — accepted and stated here so nobody calls it a bug later.

### 9. Documents panel

- Each row: title, human-readable `byte_size`, chunk count, upload date,
  delete button (§5's dialog).
- The empty state names what the server holds: text files up to 1 MB — no
  extension promise, because the endpoint checks bytes only.
- After delete, the list and the search behavior both re-check their queries.

### 10. Query keys and invalidation

| Action | Invalidates |
|---|---|
| chapter save (title or body) | `["chapters", id]`, `["novels", id]` |
| reorder `PUT` (success) | `["novels"]` only — the optimistic chapter order stands |
| chapter delete | `["chapters", id]`, `["novels"]` (neighbour opens; pending document retired) |
| novel `PATCH` | `["novels", id]`, `["novels"]` |
| novel delete | `["novels"]` |
| export (success, both deliveries) | `["novels", id]` — the delete dialog recomputes its line |
| document delete | the documents list query |

### 11. E2E (§8A.4, adapted to D3/D6 and the UI-B selectors)

Rename a chapter → the runhead, the rail row and the shelf's "last touched"
all carry it. Rename an entity → the shelf's "last touched" carries that too
(D8's proof). Move a chapter with `Alt+↑` **and** with a mouse drag → the order
survives a reload, the moved rows keep their `updated_at`, and the novel's row
has advanced; the rail rows are queried as `get_by_role("button", name=^Kapitel
N)` with `aria-current`, exactly as the existing suites do. If mouse-drag under
Playwright proves flaky at review, drag carries a DOM-level test and the E2E
keeps `Alt` + menu — the named fallback. Delete a chapter with an unsaved body
open on it → the neighbour opens, one row fewer, no failed-save status, and the
database shows contiguous `0..n-1`. Rename a novel through the details dialog;
export, then delete it → gone from shelf and database, and its suggestions and
findings are zero rows. Delete a document → its passages no longer answer a
search. A 60-chapter novel (seeded through the API) keeps the rail inside the
viewport while the editor scrolls and shows the filter above 20.
`assert_accessible` on every page.

### 12. Verification

`just check` before every commit; `just test-e2e writing` and `just test-e2e
knowledge` (affected scope by default, per the e2e-cadence design); `just verify`
(the suites the change touches) before each commit's gate and `just verify all`
before the WP closes. Edge tests pinned by name: neighbour-swap succeeds
under the **deferrable** constraint (and the plain one it replaces refuses the
same transaction — the revision is proven by both directions); duplicate
position refused at commit; the allocator's serialization test from #522 keeps
passing; renumber-after-delete leaves `0..n-1` with every surviving row's
`updated_at` unchanged and the novel's advanced; reorder likewise;
`409 order_mismatch` shape (missing, extra, foreign, duplicate); `""` title
round-trip and trim; a body-only flush does not rewrite the title, and a
rail rename of the open chapter survives the next debounce; deleting the
open chapter retires the pending save (no request, no failed status); the
move's live-announcer text names the new position and the total; language
pattern accept/clear/refuse; `byte_size` stored at ingest; the staleness
comparison as a pure function (never exported / fresh / stale over the whole
canon — an entity edit flips it); `last_exported_at` set by both export
deliveries and untouched by a failed one; entity, relation and
suggestion-accept writes advance `novel.updated_at` while document and
finding writes do not.

## Sequencing (the frontend dependency is now history)

WP5 and the UI-B wave are merged; the frontend half starts from the as-built
rail, runhead, shelf and documents panel verified above (2026-11-04). Plan step
0 re-reads the merged code once for the seams the design names — the blocker's
API, the modal-host signature, `Row`'s props, `useAutosave`'s pending slot — and
records any delta before a component is touched. The server half touches no
frontend file and may land first. The rail's tests are **extended**, not
rewritten: `aria-current`, roving tabindex and the word-count rows are UI-B's
and stay.

## My calls (mine to overturn)

Reorder persists on drop (not live-dragging); `409` reverts optimistically
with a named alert; reorder success invalidates `["novels"]` only and trusts
the optimistic chapter order; the drag id rides component state, not
`dataTransfer`; the move is announced through the live announcer; no palette
commands for item actions; rail rename is a dialog, not inline, and the save
hook sends only dirty fields; deleting the open chapter retires its pending
document; export success invalidates `["novels", id]`; the chapter count comes
from `NovelRead.chapter_count`, the entity count from a fetch on open; novel
management is shelf-only, the workspace degrades to the shelf on a novel 404;
the filter matches rendered labels in the active locale; creating a chapter
clears the filter; the documents empty state names bytes and 1 MB, not
extensions; `204`/`404` response codes; moved chapter rows keep their
`updated_at`; chunk counts load with one `GROUP BY`; `NovelRead`/`DocumentRead`
grow additively; the deferrable constraint is a revision, not a reset.

## Left to the builder

The drop indicator's look on a `Row` and the auto-scroll while dragging; the
live-announcer's exact phrasing; the filter's placement inside the rail's
toolbar band; the card action's affordance on the shelf grid; seeding the
60-chapter novel in E2E; the exact i18n phrasing of the export-staleness lines;
the dialog components' decomposition; whether the documents panel's row grows
a trailing delete or a menu; the order in which the two halves land (server
first is permitted, not required). Findings from the review of this wave are
filed as issues with `area:` (and `kind:` where it applies); commits made
through an agent carry the `Assisted-by: OpenCode (<model>)` trailer.
