# WP1 — Entity Depth (C+) Design

**Date:** 2026-10-26 · **Status:** approved by the product owner, 2026-10-26
**Authority:** Fahrplan `docs/superpowers/plans/2026-10-25-v2-foundation.md` §4 (WP1);
architecture spec `2026-10-21-narrare-v2-architecture-design.md`; frontend spec
`2026-10-22-frontend-design.md`. This document records the conversation's resolutions;
where it and §4 differ, this document wins (and §4 gets overwritten in T4).

## Intent

The entity model becomes the foundation everything later builds on — demo, relations,
graph view, consistency check. Today's `Entity` is `kind: character|place|thing` with a
`description`; WP1 gives it eight types, aliases, tags, a Markdown body, directed
relations with a suggested vocabulary, a merge that rewires edges, API filters
(`type`/`tag`/`q`), and an extraction that proposes types and relations. It is the
schema change with no data to lose: `just db-reset`, no migrations (§4.8).

## Goals

- `ENTITY_TYPES`: eight entries — `character, location, faction, object, system,
  timeline, event, generic`. String column with a closed vocabulary in code, not a PG
  enum.
- Aliases and tags as JSON lists; Markdown body (`content`) replacing `description`;
  `updated_at`; nullable `embedding`.
- `EntityRelation`: directional, free-text `relation_type` with the §4.2 suggested
  vocabulary as UI autocomplete, `note`, unique per `(user_id, from, to, relation_type)`;
  both directions shown on the detail; self-relations allowed and flagged.
- Merge that re-points edges and folds fields; delete that cascades edges.
- `GET /entities?type=&tag=&q=` — the `q` tier is trigram search (§9.1), so
  `pg_trgm` + `unaccent` land in `db-init` with a `search_text` column and a GIN index.
- Extraction v2: the prompt asks the eight types and relations; accepting a suggestion
  creates the entity plus any relations that resolve by name within the novel.
- Frontend: list with type/tag filter and server-side search; compact detail card;
  grown edit dialog; merge and delete dialogs. E2E over all flows (§4.6) as the done
  criterion.

## Non-goals

§4.7 unchanged: revisions/temporal model, typed metadata forms, attribute validity,
cross-novel entities (Series), graph visualisation, AI interview creation. Additionally:
no `@tiptap/markdown` and no Markdown renderer (WP3), no `attributes` JSONB (§4.9), no
dedup tiers on accept (§9.1 arrives with its consumer), no hybrid retrieval, no soft
delete.

## Anti-goals

No silent data loss in merge (that is what D3's field folding exists for). No
auto-apply of suggestions — review stays the only door into the canon. No manual
creation path: `POST /entities` does not exist, the only birth is an accepted
suggestion (decided 2026-10-26; a create endpoint plus dialog can arrive on merit
later). No capability importing a capability; no new rules, registries or gates; no
migration tool.

## Constraints

House rules as always: one capability one folder (knowledge owns API + web), generated
routes (`just generate`), `user_id` on every user-owned row, scoped repository base,
en/de/fr catalogs in the same commit (missing key = build error, German du-form),
conventional commits with a real `User-visible:` line, E2E on real UI + real API +
real Postgres with the fake only at the LLM/embeddings boundary, `assert_accessible`
on every page, `just check` before commits, `just verify` before the WP closes.
Embedding in the request's own transaction follows the document-ingestion pattern
(`service.py` embeds in-request) — within D14.

## Approaches (build decomposition)

1. **Monolith** — write the full §4.6 E2E red, make everything green in one pass.
   Rejected: a red test spanning model, prompt and UI names no cause; huge review diff;
   against the house pattern of per-task failing tests.
2. **Two layers** — whole backend (model + API + extraction), then whole frontend.
   Rejected: accept semantics (entity + relations in one transaction) weaves API and
   prompt; the frontend slice would hang off two half-finished ends.
3. **Four tasks, house pattern** (as WP0-B/C) — **chosen**:
   - **T1** Model + `pg_trgm`/`unaccent` + `search_text` + GIN + entity/relation API
     incl. merge edge rewiring (backend tests red→green, `just db-reset`).
   - **T2** Extraction v2: eight types + relation proposals, fake vocabulary, accept
     with name resolution and visible skip note.
   - **T3** Frontend: filters, compact card, grown edit dialog, relations UI
     (E2E red→green).
   - **T4** Full §4.6 E2E (merge edges, delete cascade, misspelt-name search) + Fahrplan
     overwrite (§4.1 gains `event`; merge/delete/embedding decisions recorded).

## Decisions (2026-10-26, product owner)

- **D1 — Type set:** eight types as listed above. The Fahrplan §2 phrase "seven types +
  generic" and §4.1's six-item enumeration resolve to **seven concrete + generic**;
  the missing seventh concrete type is **`event`**. §4.1 is corrected in T4.
- **D2 — Markdown body:** stored as Markdown from WP1 on; edited and shown as plain
  source in the existing multiline `TextField` pattern. No rich editor, no renderer,
  no new dependency — WP3 makes Markdown canonical and brings the shared chapter
  editor. The card shows a truncated preview.
- **D3 — Merge semantics:** re-point the source's edges (both directions) to the
  target, drop exact duplicates after re-pointing, then delete the source. Fields:
  the source's **name becomes an alias** of the survivor (deduped) — the differing
  name is why both rows existed, and search/dedup need it; **aliases and tags are the
  union** (case-insensitive dedupe); **body**: the survivor's body first, the source's
  body appended under `## <source name>` if non-empty (lossless, self-labeling);
  **type conflict:** the survivor wins. A self-relation created by re-pointing stays
  and is flagged like any other.
- **D4 — Deletion:** hard delete with edge cascade stays; export is the safety net.
  This is the §9.4 "decide at WP1 review" decision, now recorded: no soft delete.
- **D5 — Embedding:** computed at birth (accept), on update when
  name/aliases/tags/content changed, and in merge for the survivor — synchronous,
  in the same transaction, exactly the document-ingestion pattern. Content is capped
  at 20 000 characters **for the vector only** (storage unaffected). No job; if
  entities ever make this slow, §9.3's reembed-job trigger applies as for documents.
  One embedding model per user (corpus guard); a switch re-embeds entities too.

  > **Superseded 2026-10-29 (entities only):** the entity vector, its width guard and
  > its re-embed branch were removed — no read path consumed them. The document guard
  > stands. See `docs/superpowers/plans/2026-10-29-entity-embedding-removal.md`.
- **D6 — Search:** `q` is server-side trigram over `search_text` = name + aliases +
  tags, ranked by **`word_similarity(query, search_text)`** with a threshold measured
  in T1 against realistic misspellings (start at 0.5), debounced; it **replaces**
  today's client-side name filtering. Plain `similarity() ≥ 0.8` stays what it is in
  §9.1 — a **dedup** tier, not the search bar; a literal 0.8 on the search path would
  miss real misspellings (`kathrina` vs `katharina` ≈ 0.58 plain). The panel's passage
  second tier stays untouched. `type` and `tag` are exact filters; the tag filter
  offers the novel's existing tags.
- **D7 — API:** extend the existing entity endpoints with `type`, `aliases`, `tags`,
  `content`; `GET/POST /entities/{id}/relations`, `PATCH/DELETE /relations/{id}`;
  relation `relation_type` accepts free text (the vocabulary is a UI suggestion, not
  an API constraint).
- **D8 — Extraction v2:** the prompt asks the eight types and proposes relations;
  `EntitySuggestion` gains `type` and its proposed relations; accept creates the
  entity with the description as body plus relations whose targets resolve by name
  (aliases included) within the novel. **Resolution rules:** trimmed,
  case-insensitive exact match against names and aliases — no fuzzy matching (that is
  §9.1, later); **multiple matches mean ambiguous: skipped with the note**, never a
  guessed attach to one of the candidates; resolution sees **existing entities only**
  — a target still pending in the queue skips visibly, so accept order matters and
  the note says so. The skip note is **transient**: the accept response carries
  `skipped_relations`, the UI announces them once (the live announcer; §3.2's
  `truncated: true` is the precedent — visible in the moment, no persisted ledger).
  Fake provider's type vocabulary and E2E fixtures move in the same commit (§4.8).
  Structured output stays on the `{"items": [...]}` root.
- **D9 — Frontend, variant B (picked over inline detail):** the detail card stays
  compact — name, type badge, truncated body preview, alias/tag chips, compact
  relation rows (both directions), buttons. **Editing** (name, type, aliases, tags,
  body, relations incl. add/edit/delete) lives in the grown edit dialog: target
  ComboBox over the novel's entities, relation-type ComboBox over the §4.2 vocabulary
  with free text allowed. Merge and delete stay confirm dialogs. The review
  ProposalCard shows the proposed type and relations plus the skip note.
- **D10 — Review-consumed exclusivity** stays exactly as built: a second accept is
  refused; discard creates nothing.

## Left to the builder

- `ENTITY_TYPES` lives beside the Entity model in `app/kernel/contracts/models.py`
  (prompt and UI both consume it; one home).
- `EntitySuggestion`'s proposed relations as a JSON column on the row (no child table).
- Alias/tag chips input mechanics on top of the existing `TextField`/`ComboBox`
  primitives; details of the tag-filter picker.
- Exact merge duplicate-drop semantics against the unique constraint
  (re-point → dedupe within the transaction before insert).
- Error codes stay as the shipped surfaces use (consumed suggestion → refused; the
  public contract does not change shape).
- Test and E2E file layout per the house pattern; i18n key naming.

## Done criterion

§4.6 E2E over the real stack: create an entity of **each of the eight types** (there
is no manual birth path — the flow drives extraction with the fake, whose vocabulary
cycles all eight, and accepts); edit body/aliases/tags; link two entities; merge two
and see the edges move; delete an entity and its edges; filter by type and tag; search
a misspelt name (trigram); accept an extraction suggestion with a relation.
`assert_accessible` on every page. `just verify` green. Fake only at the
LLM/embeddings boundary.
