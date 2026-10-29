# WP3 — Markdown, Demo, Export Design

**Date:** 2026-10-28 · **Status:** approved by the product owner, 2026-10-28
**Authority:** Fahrplan `docs/superpowers/plans/2026-10-25-v2-foundation.md` §6 (WP3),
narrowed by this design; architecture spec `docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md`;
frontend spec `2026-10-22-frontend-design.md`. Builds on **merged WP1** (entity model
C+, relations, merge) and **merged WP2** (WP2a profiles/catalog/settings, WP2b context
budget) — merge commit `8dfb7852`.

## Intent

Three things become one: the storage format, the demo corpus and the user's backup.
Today chapter bodies are TipTap HTML (`ChapterEditor` saves `getHTML()`), entity bodies
are plain source text, no demo content exists in v2 (Fahrplan §1 "not built yet"), and
nothing can leave or enter the app. WP3 makes **Markdown canonical** for prose bodies,
defines **one interchange format** — the demo format — and ships export/import over it:
the backup that makes "no migrations" and WP6's hard deletes defensible, and the round
trip that lets a writer work outside Narrare and bring the work back in.

The export is a **data format, not a final novel format**: no PDF, EPUB, DOCX, no
title page, no typography. It is lossless, machine re-importable, and human-readable
by accident (Markdown). A final-format export would be a future task building on this
canon; nothing in the Fahrplan plans it.

## Goals

- **Markdown canonical (§6.1).** `@tiptap/markdown` (official since 3.7; project on
  3.31.3): `contentType: 'markdown'`, `editor.getMarkdown()` on save. Chapters and
  entity bodies (F-26: the entity detail gets the **same editor component** as
  chapters, replacing the textarea). `db-reset` replaces any HTML→Markdown converter —
  there is no live data, and the demos seed Markdown directly. A **golden round-trip
  test over the demo corpus** (real prose) is the gate: parse → serialize →
  byte-identical, or a named, documented normalisation.
- **One interchange format (§6.2).** The directory tree below; one parser serves demo
  loading (setup) and user import; one serializer serves export. ZIP is the same tree
  through `zipfile` (stdlib; no new backend package; `@tiptap/markdown` is the one new
  frontend dependency, pre-named by the Fahrplan).
- **Export, two deliveries (D1).** Per novel, from the shelf: write to a **path**
  (covers SMB mounts — a mounted share is just a path; an unreachable or unwritable
  path is a visible error, never a silent miss) or download as **ZIP**. Import is
  symmetric: read from a path or accept an uploaded ZIP; both fronts feed the same
  parser over an abstract tree (directory and ZIP look identical).
- **Import into a new novel and into an existing one (D6/D7).** Deterministic rules,
  a per-run report, no conflict wizard.
- **Demo corpus rebuilt in the C+ shape (§6.4).** Three demos from the v1 content
  (git history; `SETUP-002` is the description): *Echoes of the Thornwall* (fantasy,
  en), *Dead Signal* (sci-fi, en), *Im stillen Wald* (literary, de). Bundled **in the
  interchange format** — the demo loader is the first customer of the import parser.
  v1 flat fields become body sections; the v1 `relationships:` map becomes
  `related_to` edges with the prose as `note`. The demos are the golden round-trip
  fixture and the import test corpus.
- **Novel metadata grows `author` and `language` (D3/D4).** Language is a BCP-47-ish
  code (`de`, `en`), nullable — a novel without an answer does not lie about its
  language. Demos carry it (`de` / `en` / `en`). Editing novel metadata in the UI is
  WP6's (`PATCH /novels/{id}`); WP3 adds the columns, the format keys and the demo
  values. `logline` from the Fahrplan sketch is **not** added: `blurb` stays the one
  summary field; format keys are named like the columns.

## Non-goals

- **Findings, suggestions, documents, chat, settings, audit rows do not travel (D2).**
  The export is the user's canon: chapters, entities, relations, novel metadata.
  Findings are derived (one click re-runs the check) and their review state already
  survives no re-run today (`create_many` skips only *pending* summaries); suggestions
  are the ephemeral review queue; the original document file lives on the user's disk.
  Consequence, recorded as overwrites: §6.3's "re-resolved on import" binds from now
  on only when findings ever gain passage anchors (deferred trigger), and WP6's
  document-delete confirmation says "final" honestly instead of pointing at export
  (§8A.2's blanket "export is the backup" narrows to novel and chapter deletes).
- No per-entity language (exception case; trigger: an entity needs its own language —
  then a nullable override column and a frontmatter key).
- No merge UI beyond the report, no selective per-file confirmation clicks.
- No embedding export — vectors are derived; re-embed regenerates (WP0 rule).
- No final-format export (PDF/EPUB/DOCX), no cloud sync, no autosave of exports.

## Anti-goals

No silent conflict resolution: every skip, overwrite and conflict is in the report.
No data loss to a stale import: an older file never overwrites newer prose. No second
prose format: Markdown in, Markdown out; HTML bodies are gone with the reset, not
converted alongside. No capability cross-import: the interchange engine reads the
shared `kernel/contracts` models through the kernel's scoped repository base (the
WP2b continuation precedent).

## Constraints

House rules as always (one capability one folder, generated routes, scoped
repositories, `user_id` on every row, en/de/fr in the same commit, conventional
commits with `User-visible:`, E2E on the real stack with the fake only at the LLM
boundary, `assert_accessible`, `just check`/`just verify`). WP3 adds **no LLM
surface**: no prompt changes, no provider calls — the fake is untouched. Embeddings
stay the kernel's env-based path exactly as WP1 left them (D11); they are not an
LLM profile and not new in WP3.

## The format

```
novel/
  metadata.json      { title, author?, genre?, blurb?, language?,
                       chapters: [{file, position}],            # ordered index
                       relations: [{from, type, to, note?}] }   # names, not ids
  chapters/<file>    Markdown; frontmatter: title, position, id?, updated?
  kb/<file>          Markdown; frontmatter: type, name, aliases[], tags[], id?, updated?
```

- File names are deterministic slugs — `chapters/<nn>-<slug>.md`, `kb/<slug>.md`,
  numeric suffix on collision — so the round trip is byte-stable. `id`/`updated` ride
  only in exports (UUID, ISO-8601 UTC); hand-written files omit them.
- `relations` reference entities **by name** and resolve within the novel — the same
  rule WP1's suggestion-accept uses; an absent target is skipped and reported.

## Merge rules (import into an existing novel)

The engine's decision loop, per item, in order — the content check comes **before**
the timestamp guard, because applying a revision bumps `updated_at` past the file's
`updated` and would otherwise turn every re-import into a conflict:

1. **Match.** Chapters by frontmatter `id` against the novel's stock; entities by
   `id`, else exact casefold `name`.
2. **Already current.** No match → **new**. Match with equal content (the fields the
   rule revises) → **already current**: no write, no timestamp bump, no row changed.
   This is what makes re-importing the same archive idempotent.
3. **Revision guard.** Match with differing content: the file wins only if its
   `updated` is not older than the row's `updated_at`; otherwise **conflict** —
   newer prose is never overwritten by a stale archive. No `updated` in the file
   (hand-written) counts as new, not older.
4. **Chapters:** revision applies title and body. New chapters append after the last
   stock position — in index order if the file is indexed, else filename order.
   **The files are the truth for presence**: a `chapters/*.md` on disk that the
   index does not name still imports (dropping a bare file into the archive is the
   flagship outside gesture); the index's `position` loses against the frontmatter's,
   and a disagreement between the two is reported, not silently resolved.
5. **Entities:** revision applies body, aliases, tags — and **`name`, applied and
   reported as its own row class ("renamed")**: the stock's edges ride foreign keys,
   so a rename breaks nothing in the database, and silently ignoring the user's
   rename would strand the file's own name-based edges. Type discrepancy (file says
   `place`, stock says `character`) → **conflict**, row skipped, reported.
6. **Edges are create-only.** An identical edge (same from/type/to) already in stock
   counts as already current; the same edge with a differing `note` is a **conflict**
   row (never an unguarded overwrite). An edge whose target name does not resolve
   within the novel is skipped and reported.
7. **Novel metadata is not applied on merge.** Title, author, genre, blurb, language
   from `metadata.json` create the novel on the new-novel path only; merging into an
   existing novel touches chapters, entities and relations, and every differing
   metadata field is a reported conflict row ("metadata differs — not applied").
   Nothing retitles a novel silently; novel metadata editing is WP6's surface.
8. **Report:** per run — N new, M revised (renames counted separately), K conflicts
   (file + reason), skipped edges, already-current count. The report is the import
   result payload and the UI's receipt.

**Import maintains WP1's invariants:** `search_text` and the synchronous embedding
are computed in the import's own transaction for every new or content-changed entity
— the existing kernel embedding path (env tier), which is not an LLM surface and not
new. `Entity.embedding`'s nullable design already anticipated seeded rows; the import
is simply another birth path doing what birth does.

**Honest boundary note:** WP1 ruled entities are born only through the review queue
(`POST /entities` does not exist). Import becomes a deliberate **second birth path** —
the user curated these files; recorded here as overwriting that rule.

## Decisions

- **D1 — Delivery both ways.** Path write and ZIP download on export; path and ZIP
  upload on import. One parser over an abstract tree. SMB is a path, not a feature.
  Product owner, 2026-10-28.
- **D2 — Pure canon.** Findings and everything derived stay out of the format
  (§6.3 overwritten as recorded above). Product owner, 2026-10-28.
- **D3 — Language on three levels.** UI language stays the settings locale.
  Prompt language is **derived**, not a setting: templates stay English (house rule),
  `novel.language` flows in as a variable — continuation writes in it, findings
  summarize in it (they quote the prose); the check and extraction prompts gain the
  variable when WP4's registry lands, not before. Content language is
  `novel.language`, one nullable column, chapters and knowledge inherit. Chat's answer
  language is the chat WP's own call (lean: novel language when a novel context
  exists, else UI language). Per-entity override deferred with trigger. Product
  owner, 2026-10-28.
- **D4 — `author` + `language` columns; no `logline`.** `blurb` remains the one
  summary field; format keys mirror column names. Product owner, 2026-10-28.
- **D5 — Documents stay out, also for WP6.** The source file lives on the user's
  disk; deleting a document loses nothing that does not exist outside. WP6's
  document-delete confirmation says "final", it does not point at export. Coordinator
  ruling (design), 2026-10-28.
- **D6 — Deterministic merge, report not wizard.** The rules above; the report
  replaces interactive resolution. Product owner, 2026-10-28.
- **D7 — Merge in scope.** Import-into-existing ships in WP3 (owner overrode the
  new-only lean): the round trip out-and-back is a first-class workflow. Product
  owner, 2026-10-28.
- **D8 — db-reset, no converter.** No HTML→Markdown migration code; demos seed
  Markdown; `just db-reset` after the model change (Fahrplan §6.1 allows it
  explicitly). Coordinator ruling (design), 2026-10-28.
- **D9 — Homes.** Engine `app/kernel/interchange/` (format, parse, serialize,
  abstract tree, merge rules) over `kernel/contracts` models and the scoped
  repository base — two capabilities need it (setup: demo load; writing: the HTTP
  surface), which is the §10 kernel test. HTTP surface in the **writing** capability
  (the novel is the unit of export); demo archives bundled as data under the engine
  (`app/kernel/llm/data/models.json` is the precedent). UI on the shelf: export per
  novel, import beside "new novel". Coordinator ruling (design), 2026-10-28.
- **D10 — Export refuses a non-empty target.** A path that already holds anything is
  a named error, never an overwrite: WP6's "export before delete" must not be able
  to shrink a backup by re-exporting a thinner novel over it. The UI proposes a
  timestamped target (`<slug>-<yyyymmdd-hhmm>/`) so the common path never hits the
  refusal. Coordinator ruling (design), 2026-10-28 — the safety call, listed for
  veto.
- **D11 — Merge-rule internals settled by the check, not the owner** (all follow the
  approved principles: deterministic rules, full report, no silent overwrite, no data
  loss): content-equality short-circuit before the timestamp guard (idempotence);
  files-are-truth presence with the index advisory; frontmatter position wins;
  entity rename applied and reported; edges create-only with note-diff = conflict;
  novel metadata not applied on merge, diffs reported; embeddings and `search_text`
  maintained in the import transaction (D5's WP1 invariant). Builder check 2026-10-28.
- **D12 — Two round-trip gates.** The golden byte-identical gate is the engine's
  (Python). The TipTap editor is a second Markdown serializer (TypeScript): T5 adds
  its own round-trip test over the demo corpus (load → save → compare), and any
  normalisation TipTap performs is named in the same documented list — accepted
  drift is named drift, never discovered drift. Coordinator ruling (design),
  2026-10-28.

## Approaches (build decomposition)

1. **Merge deferred, new-novel import only** — rejected by the product owner
   2026-10-28 (D7): working outside Narrare and returning is a first-class workflow,
   not a nicety.
2. **Interactive conflict wizard** — rejected 2026-10-28 (D6): deterministic rules
   plus a full report are cheaper, auditable and testable; a wizard re-asks what the
   rules already decide.
3. **HTML→Markdown converter path** — rejected 2026-10-28 (D8): no live data; a
   converter would be permanent code for a one-time empty database.

## Tasks (coarse; the plan refines)

- **T1** Model: `Novel.author`, `Novel.language`; `db-reset`; fixtures.
- **T2** `app/kernel/interchange/`: format, abstract tree (dir + ZIP), parser,
  serializer, merge engine, report shape; golden round-trip over the demo corpus.
- **T3** Writing HTTP surface: export (path + ZIP), import (path + upload, new +
  merge), report payload; validation errors as named 422 fields (house pattern).
- **T4** Demo corpus: three archives in the interchange format from the v1 content;
  setup loads a demo through the kernel engine (blank path unchanged).
- **T5** Web: shelf export/import UI with the report receipt; Markdown editor for
  chapters and entity bodies (F-26) with its own round-trip test (D12); en/de/fr;
  `just generate`.
- **T6** E2E: §6.5 below.

## E2E (done criterion)

On the real stack (real UI, real API, real DB; no LLM involved): setup with a demo →
chapters and entities present with relations; export → the directory re-imports into
an **identical** novel (same titles, types, bodies, relations); edit a chapter file
outside, add one chapter and one kb file, import into the existing novel → revisions
applied, new rows appended, report counts match the database; import a stale
(older-than-stock) chapter → conflict reported, prose unchanged; blank path unchanged.
Golden round-trip byte-identical (or named normalisations). `assert_accessible` on
every page visited.

## Left to the builder

Slug algorithm details, frontmatter library choice, exact route paths and status
codes, the report payload's field names, ZIP entry ordering, demo prose porting
fidelity (v1 text reused verbatim, structure reshaped), i18n key names.
